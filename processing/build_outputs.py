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
    "map_detections": "map_detections.parquet",
    "grid_monthly": "grid_monthly.parquet",
    "monthly_sensor_counts": "monthly_sensor_counts.csv",
    "monthly_region_totals": "monthly_region_totals.csv",
    "sensor_coverage": "sensor_monthly_coverage.csv",
    "detection_type_breakdown": "detection_type_breakdown.csv",
    "training_pairs": "calibration_training_pairs.csv",
    "calibration_factors": "calibration_factors.csv",
    "harmonized_monthly": "harmonized_monthly.csv",
    "uncertainty_intervals": "uncertainty_intervals.csv",
    "validation_results": "validation_results.csv",
    "validation_metrics": "validation_metrics.csv",
    "anomaly_results": "anomaly_results.csv",
    "validation_cv_results": "validation_stable_orbit_cv_results.csv",
    "validation_cv_metrics": "validation_stable_orbit_cv_metrics.csv",
    "overpass_times": "overpass_times.csv",
    "calibrated_modis": "calibrated_modis_monthly.csv",
    "calibrated_period_metrics": "calibrated_modis_period_metrics.csv",
    "calibrated_yearly_metrics": "calibrated_modis_yearly_metrics.csv",
}


def read_table(key: str, base: Path = S.PROCESSED_DIR) -> pd.DataFrame:
    """Read a configured output back from disk."""
    path = output_path(key, base)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run `python -m scripts.run_pipeline`.")
    return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)


def harmonization_summary(factors: pd.DataFrame, harmonized: pd.DataFrame,
                          metrics: pd.DataFrame, intervals: pd.DataFrame,
                          cv_metrics: pd.DataFrame | None = None,
                          calibrated_periods: pd.DataFrame | None = None,
                          calibrated_years: pd.DataFrame | None = None) -> dict[str, Any]:
    """Settings and headline results of Phase 5 for the quality report."""
    unavailable = factors[factors["validation_status"] != "available"]
    return {
        "calibration_settings": {
            "method": S.CALIBRATION_METHOD,
            "training_period": [S.TRAINING_START, S.TRAINING_END],
            "min_monthly_detections": S.MIN_MONTHLY_DETECTIONS,
            "min_valid_year_pairs": S.MIN_VALID_YEAR_PAIRS,
            "note": ("Combined Terra+Aqua is calibrated against one VIIRS satellite; "
                     "factors include differences in observation opportunities as "
                     "well as detection sensitivity."),
        },
        "validation_settings": {"validation_period": [S.VALIDATION_START, S.VALIDATION_END],
                                "complete_overlapping_months_only": True},
        "bootstrap_settings": {"iterations": S.BOOTSTRAP_ITERATIONS, "seed": S.BOOTSTRAP_SEED,
                               "interval_level": S.INTERVAL_LEVEL,
                               "scope": S.UNCERTAINTY_SCOPE},
        "unavailable_factors": unavailable[["region", "calendar_month", "unavailable_reason"]]
            .to_dict("records"),
        "source_flag_counts": {
            r: _counts(g["source_flag"]) for r, g in harmonized.groupby("region")},
        "estimated_months_with_interval": int(len(intervals)),
        "validation_metrics": metrics.to_dict("records"),
        "supplementary_stable_orbit_cv": {
            "years": list(S.STABLE_ORBIT_CV_YEARS),
            "method": "leave-one-year-out; factors refitted without the held-out year",
            "note": ("Supplementary diagnostic using training-period data while MODIS "
                     "overpass times were stable. Not an independent hold-out and does "
                     "not replace the primary validation."),
            "metrics": [] if cv_metrics is None else cv_metrics.to_dict("records"),
        },
        "calibrated_modis_comparison": {
            "formula": "Calibrated_MODIS = MODIS_combined x r(region, calendar month)",
            "note": ("Comparison series only; the final harmonized record uses actual VIIRS "
                     "once available. Training rows are in-sample, validation rows "
                     "out-of-sample. Factors are never refitted on validation data."),
            "by_period": [] if calibrated_periods is None else calibrated_periods.to_dict("records"),
            "by_year": [] if calibrated_years is None else calibrated_years.to_dict("records"),
        },
    }


# Columns the Historical Fire Map reads. map_detections.parquet is the one
# processed parquet committed to git, so a fresh clone has a working map.
MAP_COLUMNS: list[str] = [
    "region", "sensor", "satellite", "latitude", "longitude", "acq_date", "acq_time",
    "acq_datetime_utc", "detection_type", "detection_type_label", "confidence_raw",
    "confidence_class", "frp", "cell_id", "cell_lat", "cell_lon",
]


def write_map_detections(detections: pd.DataFrame, base: Path = S.PROCESSED_DIR) -> Path:
    """Compact copy of the retained detections for the map (values unchanged).

    Same rows and values as detections.parquet, restricted to MAP_COLUMNS,
    repeated text stored as categories and zstd-compressed (~25 MB).
    """
    df = detections[MAP_COLUMNS].copy()
    for col in ("region", "sensor", "satellite", "detection_type_label",
                "confidence_class", "confidence_raw", "acq_time"):
        df[col] = df[col].astype(str).astype("category")
    path = output_path("map_detections", base)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False, compression="zstd", compression_level=19)
    logger.info("Wrote %s (%s rows)", path.name, f"{len(df):,}")
    return path


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
