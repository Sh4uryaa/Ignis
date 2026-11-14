"""Write processed outputs and assemble the data-quality report."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from config import settings as S

logger = logging.getLogger(__name__)

# Output file names (data/processed/).
OUTPUT_FILES: dict[str, str] = {
    "detections": "detections.parquet",
    "grid_monthly": "grid_monthly.parquet",
    "monthly_sensor_counts": "monthly_sensor_counts.csv",
    "monthly_region_totals": "monthly_region_totals.csv",
    "sensor_coverage": "sensor_monthly_coverage.csv",
    "detection_type_breakdown": "detection_type_breakdown.csv",
}


def output_path(key: str, base: Path = S.PROCESSED_DIR) -> Path:
    return base / OUTPUT_FILES[key]


def write_table(df: pd.DataFrame, key: str, base: Path = S.PROCESSED_DIR) -> Path:
    """Write a DataFrame to its configured CSV or Parquet output."""
    path = output_path(key, base)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".parquet":
        df.to_parquet(path, index=False)
    else:
        df.to_csv(path, index=False)
    logger.info("Wrote %s (%s rows)", path.name, f"{len(df):,}")
    return path


def _counts(series: pd.Series) -> dict[str, int]:
    return {str(k): int(v) for k, v in series.value_counts().sort_index().items()}


def processing_summary(retained: pd.DataFrame) -> dict[str, Any]:
    """Distributions of the final, in-region, policy-filtered detections."""
    out: dict[str, Any] = {}
    for sensor, sub in retained.groupby("sensor", observed=True):
        out[str(sensor)] = {
            "retained_total": int(len(sub)),
            "by_region": _counts(sub["region"].astype(str)),
            "by_region_and_satellite": {
                str(r): _counts(g["satellite"].astype(str))
                for r, g in sub.groupby("region", observed=True)},
            "by_confidence_class": _counts(sub["confidence_class"].astype(str)),
            "by_detection_type": _counts(sub["detection_type"].astype(str)),
            "by_version": _counts(sub["version"].astype(str)),
            "date_coverage": [sub["acq_date"].min().strftime("%Y-%m-%d"),
                              sub["acq_date"].max().strftime("%Y-%m-%d")],
        }
    return out


def build_quality_report(
    inspection: dict[str, Any],
    confidence_stats: dict[str, dict[str, int]],
    region_stats: dict[str, dict[str, int]],
    retained: pd.DataFrame,
    satellite_coverage: dict[str, list[str]],
    gaps: list[dict],
    boundary_provenance: dict[str, Any] | None,
    warnings: list[str],
) -> dict[str, Any]:
    """Assemble the machine-readable quality report."""
    return {
        "processing_date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "inputs": {
            k: {"archive": a["zip_name"], "archive_csv": a["archive_csv"],
                "ignored_csvs": a["ignored_csvs"], "collection": a["collection"]}
            for k, a in inspection["archives"].items()},
        "raw_statistics": {k: a["statistics"] for k, a in inspection["archives"].items()},
        "expectation_checks": {k: a["expectation_checks"] for k, a in inspection["archives"].items()},
        "confidence_policy": {
            "name": S.CONFIDENCE_POLICY_NAME, "label": S.CONFIDENCE_POLICY_LABEL,
            "modis_rule": f"confidence >= {S.MODIS_MIN_CONFIDENCE}",
            "viirs_rule": f"confidence in {list(S.VIIRS_ACCEPTED_CONFIDENCE)}",
            "counts": confidence_stats},
        "geographic_filter": {
            "regions": list(S.REGIONS),
            "method": "point-in-polygon (Shapely) against geoBoundaries ADM1 state polygons",
            "source_crs": S.SOURCE_CRS, "projected_crs": S.PROJECTED_CRS,
            "counts_after_confidence_filter": region_stats,
            "boundaries": boundary_provenance},
        "grid": {"cell_size_m": S.GRID_CELL_SIZE_M, "crs": S.PROJECTED_CRS,
                 "note": "Cell counts are detections, not unique fires."},
        "retained": processing_summary(retained),
        "satellite_observation_coverage": satellite_coverage,
        "observation_gaps_over_20_days": gaps,
        "warnings": warnings,
    }


def write_quality_report(report: dict[str, Any], path: Path = S.QUALITY_REPORT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    logger.info("Wrote %s", path.name)
    return path
