"""Common 1 km grid and monthly aggregations.

All inputs are standardized, confidence-filtered detections that already
carry a ``region`` column. Detection counts are counts of satellite
detections, not unique fires.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pyproj import CRS, Transformer

from config.settings import (
    CONFIDENCE_POLICY_NAME,
    GRID_CELL_SIZE_M,
    PROJECTED_CRS,
    REGIONS,
    SOURCE_CRS,
    VIIRS_PLATFORM_LABEL,
)
from processing.coverage import COMPLETE, NONE, PARTIAL
from processing.standardize import detection_type_label

# Columns in harmonization-ready monthly totals per sensor/platform.
PLATFORM_COLUMNS = {"Terra": "modis_terra_count", "Aqua": "modis_aqua_count",
                    VIIRS_PLATFORM_LABEL: "viirs_snpp_count"}


# ---------------------------------------------------------------------------
# Common grid
# ---------------------------------------------------------------------------
def validate_projection(lon: np.ndarray, crs: str = PROJECTED_CRS) -> None:
    """Ensure every longitude lies inside the projected UTM zone's 6° band."""
    info = CRS.from_user_input(crs).utm_zone
    if info is None:
        raise ValueError(f"{crs} is not a UTM projection")
    zone = int(info[:-1])
    west, east = -180 + 6 * (zone - 1), -180 + 6 * zone
    lon = np.asarray(lon, dtype=float)
    if len(lon) and (np.nanmin(lon) < west or np.nanmax(lon) > east):
        raise ValueError(f"Longitudes {np.nanmin(lon):.3f}..{np.nanmax(lon):.3f} fall outside "
                         f"UTM zone {info} ({west}..{east}°E)")


def assign_grid_cells(df: pd.DataFrame, cell_size_m: int = GRID_CELL_SIZE_M) -> pd.DataFrame:
    """Add common-grid cell index, id and cell-centre coordinates.

    Cells are square ``cell_size_m`` cells in ``PROJECTED_CRS``. A cell count
    is a count of detections, not of distinct fires.
    """
    validate_projection(df["longitude"].to_numpy())
    fwd = Transformer.from_crs(SOURCE_CRS, PROJECTED_CRS, always_xy=True)
    inv = Transformer.from_crs(PROJECTED_CRS, SOURCE_CRS, always_xy=True)
    x, y = fwd.transform(df["longitude"].to_numpy(), df["latitude"].to_numpy())
    ix = np.floor(x / cell_size_m).astype(np.int32)
    iy = np.floor(y / cell_size_m).astype(np.int32)
    cx, cy = inv.transform((ix + 0.5) * cell_size_m, (iy + 0.5) * cell_size_m)
    out = df.copy()
    out["cell_ix"], out["cell_iy"] = ix, iy
    out["cell_id"] = pd.Series(ix, index=df.index).astype(str) + "_" + \
        pd.Series(iy, index=df.index).astype(str)
    out["cell_lon"], out["cell_lat"] = cx.astype("float32"), cy.astype("float32")
    return out


# ---------------------------------------------------------------------------
# Monthly aggregations
# ---------------------------------------------------------------------------
def monthly_sensor_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Counts by region, year, month, sensor, satellite and detection type.

    Only observed combinations appear; use ``monthly_region_totals`` for a
    complete month grid that distinguishes zero from not-observed.
    """
    keys = ["region", "year", "month", "sensor", "satellite", "detection_type"]
    out = (df.groupby(keys, observed=True).size().rename("detection_count").reset_index())
    out.insert(6, "confidence_policy", CONFIDENCE_POLICY_NAME)
    for c in ("region", "sensor", "satellite"):
        out[c] = out[c].astype(str)
    return out.sort_values(keys).reset_index(drop=True)


def _combined_status(terra: str, aqua: str) -> str:
    """Coverage status of combined Terra+Aqua for one month."""
    if terra == NONE and aqua == NONE:
        return NONE
    if terra == NONE:
        return "aqua_only"
    if aqua == NONE:
        return "terra_only"
    return COMPLETE if terra == COMPLETE and aqua == COMPLETE else PARTIAL


def monthly_region_totals(df: pd.DataFrame, coverage: pd.DataFrame,
                          regions: tuple[str, ...] = REGIONS) -> pd.DataFrame:
    """One row per region and month with per-platform totals and coverage.

    * A platform's count is 0 when it observed (part of) the month but made
      no detections in the region, and missing (NaN) when it did not observe
      the month at all. Missing is never turned into zero.
    * ``modis_combined_count`` = Terra + Aqua, and is only defined when both
      platforms observed the month. Terra-only months stay Terra-only.
    """
    counts = (df.groupby(["region", "year", "month", "satellite"], observed=True)
              .size().rename("n").reset_index())
    counts["satellite"] = counts["satellite"].astype(str)
    cov = coverage.pivot_table(index=["year", "month"], columns="satellite",
                               values="coverage_status", aggfunc="first")
    rows = []
    for region in regions:
        sub = counts[counts["region"].astype(str) == region]
        wide = sub.pivot_table(index=["year", "month"], columns="satellite",
                               values="n", aggfunc="sum")
        frame = pd.DataFrame(index=cov.index)
        frame.insert(0, "region", region)
        for sat, col in PLATFORM_COLUMNS.items():
            status = cov[sat] if sat in cov else pd.Series(NONE, index=cov.index)
            vals = wide[sat].reindex(cov.index) if sat in wide else pd.Series(np.nan, index=cov.index)
            observed = status.isin([COMPLETE, PARTIAL])
            frame[col] = vals.fillna(0).where(observed)  # 0 if observed, NaN if not
            frame[col.replace("_count", "_coverage")] = status.fillna(NONE)
        frame["modis_combined_coverage"] = [
            _combined_status(t, a) for t, a in
            zip(frame["modis_terra_coverage"], frame["modis_aqua_coverage"])]
        both = frame["modis_combined_coverage"].isin([COMPLETE, PARTIAL])
        frame["modis_combined_count"] = (frame["modis_terra_count"]
                                         + frame["modis_aqua_count"]).where(both)
        rows.append(frame.reset_index())
    out = pd.concat(rows, ignore_index=True)
    out["confidence_policy"] = CONFIDENCE_POLICY_NAME
    for col in ("modis_terra_count", "modis_aqua_count", "modis_combined_count", "viirs_snpp_count"):
        out[col] = out[col].astype("Int64")
    order = ["region", "year", "month", "modis_terra_count", "modis_aqua_count",
             "modis_combined_count", "viirs_snpp_count", "modis_terra_coverage",
             "modis_aqua_coverage", "modis_combined_coverage", "viirs_snpp_coverage",
             "confidence_policy"]
    return out[order].sort_values(["region", "year", "month"]).reset_index(drop=True)


def detection_type_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """Annual counts by region, sensor, satellite and detection type."""
    keys = ["region", "year", "sensor", "satellite", "detection_type"]
    out = df.groupby(keys, observed=True).size().rename("detection_count").reset_index()
    out.insert(5, "detection_type_label", out["detection_type"].map(detection_type_label))
    out["confidence_policy"] = CONFIDENCE_POLICY_NAME
    for c in ("region", "sensor", "satellite"):
        out[c] = out[c].astype(str)
    return out.sort_values(keys).reset_index(drop=True)


def grid_monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Detections per common grid cell, month and satellite (for maps)."""
    keys = ["region", "year", "month", "sensor", "satellite", "cell_id"]
    g = df.groupby(keys, observed=True)
    out = g.agg(cell_lat=("cell_lat", "first"), cell_lon=("cell_lon", "first"),
                detection_count=("cell_id", "size"), frp_sum=("frp", "sum")).reset_index()
    out["confidence_policy"] = CONFIDENCE_POLICY_NAME
    for c in ("region", "sensor", "satellite"):
        out[c] = out[c].astype("category")
    return out
