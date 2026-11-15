"""Download geoBoundaries India ADM1 and build the Punjab / Haryana files.

Usage::

    python -m scripts.prepare_boundaries                 # download (pinned release)
    python -m scripts.prepare_boundaries --source FILE   # use a local copy

Writes ``data/geo/punjab.geojson``, ``data/geo/haryana.geojson`` and
``data/geo/boundary_provenance.json`` (source, licence, CRS, download date,
area checks and coverage of the FIRMS download polygon).
"""
from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import requests

from config.settings import (
    BOUNDARY_PROVENANCE_PATH,
    BOUNDARY_SOURCE,
    REGION_BOUNDARY_FILES,
    SOURCE_CRS,
)
from processing.geo_filter import (
    BoundaryError,
    download_area_coverage,
    load_download_area,
    select_states,
    validate_boundaries,
    write_geojson,
    write_json,
)
from utils.logging_config import configure_logging

logger = logging.getLogger("prepare_boundaries")


def _download(url: str, dest: Path) -> None:
    logger.info("Downloading %s", url)
    with requests.get(url, stream=True, timeout=120,
                      headers={"User-Agent": "ignis-pipeline"}) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)


def build(source_file: Path) -> dict:
    """Select, validate and write the state boundaries; return provenance."""
    source = gpd.read_file(source_file)
    states = select_states(source)
    diagnostics = validate_boundaries(states)
    for region, path in REGION_BOUNDARY_FILES.items():
        write_geojson(states[states["region"] == region], path)
        logger.info("Wrote %s", path)

    provenance = {
        **BOUNDARY_SOURCE,
        "crs": SOURCE_CRS,
        "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": {r: p.name for r, p in REGION_BOUNDARY_FILES.items()},
        "source_names": dict(zip(states["region"], states["shapeName"])),
        "diagnostics": diagnostics,
    }
    area = load_download_area()
    if area is not None:
        provenance["firms_download_polygon_coverage"] = download_area_coverage(states, area)
    return provenance


def main() -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Local geoBoundaries IND ADM1 GeoJSON")
    args = parser.parse_args()
    try:
        if args.source:
            provenance = build(args.source)
        else:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "geoBoundaries-IND-ADM1.geojson"
                _download(BOUNDARY_SOURCE["download_url"], path)
                provenance = build(path)
    except (BoundaryError, requests.RequestException) as exc:
        logger.error("%s", exc)
        return 1
    write_json(provenance, BOUNDARY_PROVENANCE_PATH)
    for region, d in provenance["diagnostics"].items():
        print(f"{region}: {d['area_km2']:,} km2, bounds {d['bounds_wgs84']}")
    for region, c in provenance.get("firms_download_polygon_coverage", {}).items():
        print(f"{region}: {c['percent_covered']}% inside FIRMS download polygon "
              f"({c['area_outside_download_polygon_km2']:,} km2 outside)")
    print(f"Provenance written to {BOUNDARY_PROVENANCE_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
