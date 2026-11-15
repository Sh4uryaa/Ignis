"""Run the IGNIS preprocessing pipeline.

Usage::

    python -m scripts.run_pipeline

Phase 4 steps (harmonization, uncertainty, validation and anomalies are
added in later phases):

1. Extract the historical archive CSVs (NRT CSVs ignored).
2. Inspect raw data and compare with expected statistics.
3. Standardize the schema.
4. Derive per-satellite observation coverage from the data.
5. Apply the Nominal + High confidence policy.
6. Assign Punjab / Haryana / outside by point-in-polygon.
7. Assign common 1 km grid cells.
8. Aggregate monthly counts, region totals, type breakdown, grid summary.
9. Write outputs and the quality report.
"""
from __future__ import annotations

import json
import logging
import sys

import pandas as pd

from config import settings as S
from processing.aggregate import (
    assign_grid_cells,
    detection_type_breakdown,
    grid_monthly_summary,
    monthly_region_totals,
    monthly_sensor_counts,
)
from processing.build_outputs import (
    build_quality_report,
    harmonization_summary,
    read_table,
    write_map_detections,
    write_quality_report,
    write_table,
)
from processing.calculate_anomalies import calculate_anomalies
from processing.harmonize import (
    calibrated_modis_series,
    calibration_factors,
    harmonize,
    training_pairs,
)
from processing.uncertainty import factor_intervals, uncertainty_intervals
from processing.diagnostics import overpass_times
from processing.validate import (
    calibrated_period_metrics,
    calibrated_yearly_metrics,
    leave_one_year_out,
    pooled_constant_factors,
    validation_metrics,
    validation_months,
)
from processing.clean_data import apply_confidence_policy
from processing.coverage import monthly_coverage, observation_gaps
from processing.extract_archives import ArchiveError, extract_historical_csv
from processing.geo_filter import BoundaryError, assign_regions, load_region_boundaries
from processing.inspect_data import inspect_archive
from processing.read_source import read_raw_strings
from processing.standardize import satellite_date_coverage, standardize
from utils.logging_config import configure_logging

logger = logging.getLogger("run_pipeline")

DETECTION_COLUMNS = [
    "region", "sensor", "satellite", "latitude", "longitude", "acq_date", "acq_time",
    "acq_datetime_utc", "year", "month", "confidence_raw", "confidence_class",
    "detection_type", "detection_type_label", "frp", "brightness", "daynight",
    "version", "cell_id", "cell_lat", "cell_lon",
]


def load_and_standardize() -> tuple[pd.DataFrame, dict, list[str]]:
    """Steps 1-3: extract, inspect and standardize every archive."""
    inspection = {"archives": {}}
    frames, warnings = [], []
    for key, archive in S.SOURCE_ARCHIVES.items():
        csv_path = extract_historical_csv(archive)
        logger.info("Reading %s", csv_path.name)
        raw = read_raw_strings(csv_path)
        result = inspect_archive(archive, raw)
        inspection["archives"][key] = result
        warnings.extend(result["warnings"])
        std, w = standardize(raw, key)
        warnings.extend(w)
        frames.append(std)
        del raw
    df = pd.concat(frames, ignore_index=True)
    for col in ("sensor", "satellite", "satellite_raw", "confidence_class",
                "detection_type_label", "daynight", "version"):
        df[col] = df[col].astype("category")
    return df, inspection, warnings


def region_breakdown(df: pd.DataFrame) -> dict[str, dict[str, int]]:
    """Counts of Punjab / Haryana / outside per satellite."""
    tab = pd.crosstab(df["satellite"].astype(str), df["region"].astype(str))
    return {sat: {r: int(v) for r, v in row.items()} for sat, row in tab.iterrows()}


def run_harmonization(totals: pd.DataFrame) -> dict:
    """Phase 5: calibration, harmonized series, uncertainty, validation, anomalies."""
    pairs = training_pairs(totals)
    factors = calibration_factors(pairs)
    intervals = factor_intervals(pairs)
    factors = factors.merge(intervals[["region", "calendar_month", "factor_lower",
                                       "factor_upper", "interval_status"]],
                            on=["region", "calendar_month"], how="left")
    harmonized = harmonize(totals, factors)
    unc = uncertainty_intervals(harmonized, intervals)
    val_rows = validation_months(totals, factors, constant_factors=pooled_constant_factors(pairs))
    metrics = validation_metrics(val_rows)
    cv_first, cv_last = S.STABLE_ORBIT_CV_YEARS
    cv_rows = leave_one_year_out(pairs, cv_first, cv_last)
    cv_metrics = validation_metrics(cv_rows, period=(str(cv_first), str(cv_last)),
                                    validation_type="supplementary_stable_orbit_loyo_cv")
    anomalies = calculate_anomalies(harmonized)
    calibrated = calibrated_modis_series(totals, factors)   # same training factors
    cal_periods = calibrated_period_metrics(calibrated)
    cal_years = calibrated_yearly_metrics(calibrated)

    for key, df in [("training_pairs", pairs), ("calibration_factors", factors),
                    ("harmonized_monthly", harmonized), ("uncertainty_intervals", unc),
                    ("validation_results", val_rows), ("validation_metrics", metrics),
                    ("validation_cv_results", cv_rows), ("validation_cv_metrics", cv_metrics),
                    ("anomaly_results", anomalies), ("calibrated_modis", calibrated),
                    ("calibrated_period_metrics", cal_periods),
                    ("calibrated_yearly_metrics", cal_years)]:
        write_table(df, key)
    for _, f in factors[factors["validation_status"] != "available"].iterrows():
        logger.warning("No calibration factor: %s month %s — %s",
                       f["region"], f["calendar_month"], f["unavailable_reason"])
    print("\nCalibration factors (VIIRS / MODIS, median of training years):")
    print(factors.pivot(index="calendar_month", columns="region",
                        values="calibration_factor").round(2).to_string())
    print("\nValidation (held-out months):")
    print(metrics[["region", "comparison", "n_months", "mae", "rmse", "wape_pct",
                   "relative_bias_pct"]].round(1).to_string(index=False))
    print(f"\nSupplementary stable-orbit leave-one-year-out CV ({cv_first}-{cv_last}):")
    print(cv_metrics[["region", "comparison", "n_months", "wape_pct",
                      "relative_bias_pct"]].round(1).to_string(index=False))
    print("\nCalibrated MODIS vs VIIRS by period:")
    print(cal_periods[["region", "comparison_period", "n_months", "wape_pct",
                       "relative_bias_pct"]].round(1).to_string(index=False))
    return harmonization_summary(factors, harmonized, metrics, unc, cv_metrics,
                                 cal_periods, cal_years)


def main() -> int:
    configure_logging()
    if "--skip-ingest" in sys.argv:
        # Re-run Phase 5 only, from the saved monthly region totals.
        try:
            totals = read_table("monthly_region_totals")
        except FileNotFoundError as exc:
            logger.error("%s", exc)
            return 1
        summary = run_harmonization(totals)
        report = (json.loads(S.QUALITY_REPORT_PATH.read_text(encoding="utf-8"))
                  if S.QUALITY_REPORT_PATH.exists() else {})
        report["harmonization"] = summary
        write_quality_report(report)
        return 0
    try:
        boundaries = load_region_boundaries()
        df, inspection, warnings = load_and_standardize()
    except (ArchiveError, BoundaryError) as exc:
        logger.error("%s", exc)
        return 1

    # Step 4: coverage is taken from all records (any confidence, whole download area).
    sat_cov = satellite_date_coverage(df)
    first = min(v[0] for v in sat_cov.values()).to_period("M")
    last = max(v[1] for v in sat_cov.values()).to_period("M")
    coverage = monthly_coverage(sat_cov, first, last)
    gaps = observation_gaps(df)
    for g in gaps:
        logger.info("Observation gap: %s", g)

    # Step 5: confidence policy.
    kept, conf_stats = apply_confidence_policy(df)
    del df

    # Step 6: regions.
    kept = kept.copy()
    kept["region"] = pd.Categorical(
        assign_regions(kept["latitude"].to_numpy(), kept["longitude"].to_numpy(), boundaries))
    reg_stats = region_breakdown(kept)
    in_region = kept[kept["region"].astype(str).isin(S.REGIONS)].copy()
    in_region["region"] = in_region["region"].cat.remove_unused_categories()
    del kept

    # Step 7: grid.
    in_region = assign_grid_cells(in_region)

    # Step 8: aggregations.
    write_table(in_region[DETECTION_COLUMNS], "detections")
    write_map_detections(in_region)   # compact, committed copy for the map
    write_table(coverage, "sensor_coverage")
    write_table(monthly_sensor_counts(in_region), "monthly_sensor_counts")
    totals = monthly_region_totals(in_region, coverage)
    write_table(totals, "monthly_region_totals")
    write_table(detection_type_breakdown(in_region), "detection_type_breakdown")
    write_table(overpass_times(in_region), "overpass_times")
    write_table(grid_monthly_summary(in_region), "grid_monthly")

    # Step 9: quality report.
    provenance = (json.loads(S.BOUNDARY_PROVENANCE_PATH.read_text(encoding="utf-8"))
                  if S.BOUNDARY_PROVENANCE_PATH.exists() else None)
    if provenance is None:
        warnings.append("Boundary provenance file missing; run scripts.prepare_boundaries.")
    report = build_quality_report(
        inspection, conf_stats, reg_stats, in_region,
        {k: [v[0].strftime("%Y-%m-%d"), v[1].strftime("%Y-%m-%d")] for k, v in sat_cov.items()},
        gaps, provenance, warnings)
    # Phase 5 reads totals back from CSV so both entry points use identical input.
    report["harmonization"] = run_harmonization(read_table("monthly_region_totals"))
    write_quality_report(report)

    print("\nRetained detections (Nominal + High, inside state boundaries):")
    print(pd.crosstab(in_region["region"], in_region["satellite"], margins=True).to_string())
    print(f"\nWarnings: {len(warnings)}")
    for w in warnings:
        print(f"  - {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
