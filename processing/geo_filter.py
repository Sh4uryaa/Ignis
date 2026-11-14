"""State boundaries and point-in-polygon region assignment.

Boundaries are real administrative polygons (see config.BOUNDARY_SOURCE).
A rectangular extent or the FIRMS download polygon is never used in their
place.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely import wkt

from config.settings import (
    DOWNLOAD_AREA_WKT_PATH,
    OUTSIDE_REGION_LABEL,
    PROJECTED_CRS,
    REGION_BOUNDARY_FILES,
    REGION_ISO_CODES,
    REGIONS,
    SOURCE_CRS,
)

logger = logging.getLogger(__name__)


class BoundaryError(RuntimeError):
    """Raised when a boundary file is missing or invalid."""


def missing_boundary_message(region: str, path: Path) -> str:
    return (
        f"Boundary file for {region} not found at {path}.\n"
        "Run `python -m scripts.prepare_boundaries` to download and build the "
        "state boundaries. A rectangular extent is never substituted."
    )


def select_states(source: gpd.GeoDataFrame, iso_codes: dict[str, str] = REGION_ISO_CODES
                  ) -> gpd.GeoDataFrame:
    """Pick each configured state from an ADM1 dataset by ISO code.

    Returns one row per region with a plain ``region`` column, in EPSG:4326.
    """
    if source.crs is None:
        raise BoundaryError("Source boundaries have no CRS.")
    rows = []
    for region, iso in iso_codes.items():
        match = source[source["shapeISO"] == iso]
        if len(match) != 1:
            raise BoundaryError(f"Expected one feature with shapeISO={iso}, found {len(match)}.")
        rows.append({"region": region, "shapeISO": iso,
                     "shapeName": match.iloc[0]["shapeName"],
                     "geometry": match.iloc[0].geometry})
    out = gpd.GeoDataFrame(rows, crs=source.crs).to_crs(SOURCE_CRS)
    return out


def validate_boundaries(gdf: gpd.GeoDataFrame) -> dict[str, dict]:
    """Check validity, CRS and overlap; return per-region diagnostics."""
    if gdf.crs is None or gdf.crs.to_string() != SOURCE_CRS:
        raise BoundaryError(f"Boundaries must be in {SOURCE_CRS}, got {gdf.crs}.")
    invalid = gdf.loc[~gdf.is_valid, "region"].tolist()
    if invalid:
        raise BoundaryError(f"Invalid geometry for: {invalid}")
    projected = gdf.to_crs(PROJECTED_CRS)
    report = {}
    for _, row in projected.iterrows():
        report[row["region"]] = {
            "area_km2": round(row.geometry.area / 1e6, 1),
            "geometry_type": row.geometry.geom_type,
            "bounds_wgs84": [round(float(v), 5) for v in
                             gdf.loc[gdf["region"] == row["region"]].total_bounds],
        }
    # States must not overlap, otherwise a point could be double counted.
    geoms = list(projected.geometry)
    overlap = sum(a.intersection(b).area for i, a in enumerate(geoms) for b in geoms[i + 1:])
    if overlap > 1e4:  # > 0.01 km2
        raise BoundaryError(f"Region boundaries overlap by {overlap / 1e6:.3f} km2.")
    for r in report.values():
        r["overlap_with_other_regions_km2"] = round(overlap / 1e6, 4)
    return report


def load_region_boundaries(files: dict[str, Path] = REGION_BOUNDARY_FILES) -> gpd.GeoDataFrame:
    """Load the per-state GeoJSON files into one GeoDataFrame (EPSG:4326)."""
    frames = []
    for region, path in files.items():
        if not path.exists():
            raise BoundaryError(missing_boundary_message(region, path))
        g = gpd.read_file(path)
        if g.crs is None:
            raise BoundaryError(f"{path} has no CRS.")
        g = g.to_crs(SOURCE_CRS)
        frames.append(gpd.GeoDataFrame({"region": [region]},
                                       geometry=[g.union_all()], crs=SOURCE_CRS))
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=SOURCE_CRS)


def assign_regions(lat: np.ndarray, lon: np.ndarray, boundaries: gpd.GeoDataFrame
                   ) -> np.ndarray:
    """Label each point with its region, or OUTSIDE_REGION_LABEL.

    Points exactly on a shared border are assigned to the first region in
    ``REGIONS`` order so no point is ever counted twice.
    """
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    labels = np.full(lat.shape, OUTSIDE_REGION_LABEL, dtype=object)
    unassigned = np.ones(lat.shape, dtype=bool)
    by_region = dict(zip(boundaries["region"], boundaries.geometry))
    for region in REGIONS:
        geom = by_region.get(region)
        if geom is None:
            continue
        shapely.prepare(geom)
        inside = shapely.intersects_xy(geom, lon, lat) & unassigned
        labels[inside] = region
        unassigned &= ~inside
    return labels


def load_download_area() -> shapely.Geometry | None:
    """The polygon used to request the FIRMS archives (provenance only)."""
    if not DOWNLOAD_AREA_WKT_PATH.exists():
        return None
    return wkt.loads(DOWNLOAD_AREA_WKT_PATH.read_text().strip())


def download_area_coverage(boundaries: gpd.GeoDataFrame, area: shapely.Geometry
                           ) -> dict[str, dict]:
    """How much of each state lies inside the FIRMS download polygon.

    Any part of a state outside the polygon has no detections in the archives,
    which would lead to an undercount for that state.
    """
    area_gdf = gpd.GeoSeries([area], crs=SOURCE_CRS).to_crs(PROJECTED_CRS).iloc[0]
    projected = boundaries.to_crs(PROJECTED_CRS)
    result = {}
    for _, row in projected.iterrows():
        state = row.geometry
        missed = state.difference(area_gdf)
        result[row["region"]] = {
            "state_area_km2": round(state.area / 1e6, 1),
            "area_outside_download_polygon_km2": round(missed.area / 1e6, 1),
            "percent_covered": round(100 * (1 - missed.area / state.area), 2),
        }
    return result


def write_geojson(gdf: gpd.GeoDataFrame, path: Path) -> None:
    """Write a GeoDataFrame as GeoJSON (EPSG:4326, RFC 7946)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(gdf.to_crs(SOURCE_CRS).to_json(drop_id=True), encoding="utf-8")


def write_json(obj: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
