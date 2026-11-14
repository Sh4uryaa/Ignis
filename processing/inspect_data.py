"""Inspect raw FIRMS archive data and compare it with expected statistics.

Everything here is independent of Streamlit and works on plain DataFrames,
so it can be unit-tested with synthetic data.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from config.settings import (
    DETECTION_TYPE_LABELS,
    DOCUMENTED_DISCREPANCIES,
    DOWNLOAD_EXTENT,
    SOURCE_COLUMNS,
    SourceArchive,
)
from processing.clean_data import classify_confidence, passes_confidence_policy

logger = logging.getLogger(__name__)

NUMERIC_COLUMNS = ("latitude", "longitude", "brightness", "scan", "track",
                   "bright_t31", "frp")


def _counts(series: pd.Series) -> dict[str, int]:
    """Value counts as a plain, sorted ``{str: int}`` dict (NaN included)."""
    vc = series.value_counts(dropna=False)
    return {("<missing>" if pd.isna(k) else str(k)): int(v)
            for k, v in sorted(vc.items(), key=lambda kv: str(kv[0]))}


def inspect_dataframe(df: pd.DataFrame, sensor: str) -> dict[str, Any]:
    """Compute descriptive statistics for a raw (all-string) FIRMS frame."""
    report: dict[str, Any] = {
        "total_rows": int(len(df)),
        "columns": list(df.columns),
        "n_columns": int(df.shape[1]),
        "missing_required_columns": [c for c in SOURCE_COLUMNS if c not in df.columns],
        "unexpected_columns": [c for c in df.columns if c not in SOURCE_COLUMNS],
        "missing_values_by_column": {c: int(df[c].isna().sum()) for c in df.columns},
    }
    report["missing_values"] = int(sum(report["missing_values_by_column"].values()))
    report["exact_duplicates"] = int(df.duplicated().sum())

    # --- dates -----------------------------------------------------------
    dates = pd.to_datetime(df["acq_date"], format="%Y-%m-%d", errors="coerce")
    report["unparseable_dates"] = int(dates.isna().sum() - df["acq_date"].isna().sum())
    report["first_date"] = dates.min().strftime("%Y-%m-%d") if dates.notna().any() else None
    report["last_date"] = dates.max().strftime("%Y-%m-%d") if dates.notna().any() else None

    times = df["acq_time"].astype("object")
    bad_time = ~times.fillna("").str.fullmatch(r"\d{3,4}")
    report["unparseable_times"] = int(bad_time.sum())

    # --- platforms -------------------------------------------------------
    report["satellite_counts"] = _counts(df["satellite"])
    report["instrument_counts"] = _counts(df["instrument"])
    coverage = {}
    for sat, grp in dates.groupby(df["satellite"].astype("object")):
        coverage[str(sat)] = [grp.min().strftime("%Y-%m-%d"), grp.max().strftime("%Y-%m-%d")]
    report["satellite_coverage"] = coverage

    # --- confidence ------------------------------------------------------
    classes = classify_confidence(sensor, df["confidence"])
    if sensor == "VIIRS":
        report["confidence_raw_counts"] = _counts(df["confidence"])
    report["confidence_class_counts"] = {
        k: int(v) for k, v in classes.value_counts().items()
    }
    report["confidence_unknown"] = int((classes == "unknown").sum())
    passes = passes_confidence_policy(sensor, df["confidence"])
    report["nominal_plus_high"] = int(passes.sum())
    report["low_confidence_excluded"] = int((classes == "low").sum())

    # --- detection type --------------------------------------------------
    report["type_counts"] = _counts(df["type"])
    known = {str(k) for k in DETECTION_TYPE_LABELS}
    report["unknown_types"] = sorted(
        k for k in report["type_counts"] if k not in known
    )

    # --- misc categorical ------------------------------------------------
    report["version_counts"] = _counts(df["version"])
    report["daynight_counts"] = _counts(df["daynight"])

    # --- numeric parse + spatial extent ----------------------------------
    parse_failures = {}
    numeric = {}
    for col in NUMERIC_COLUMNS:
        vals = pd.to_numeric(df[col], errors="coerce")
        parse_failures[col] = int(vals.isna().sum() - df[col].isna().sum())
        numeric[col] = vals
    report["numeric_parse_failures"] = parse_failures
    lat, lon = numeric["latitude"], numeric["longitude"]
    report["latitude_range"] = [float(np.nanmin(lat)), float(np.nanmax(lat))]
    report["longitude_range"] = [float(np.nanmin(lon)), float(np.nanmax(lon))]
    e = DOWNLOAD_EXTENT
    outside = ~((lat >= e["lat_min"]) & (lat <= e["lat_max"])
                & (lon >= e["lon_min"]) & (lon <= e["lon_max"]))
    report["rows_outside_download_extent"] = int(outside.sum())
    report["frp_range"] = [float(np.nanmin(numeric["frp"])), float(np.nanmax(numeric["frp"]))]
    return report


def compare_with_expected(actual: dict[str, Any], expected: dict[str, Any]) -> list[dict[str, Any]]:
    """Compare each expected statistic with the actual value.

    Returns one record per check: ``{"check", "expected", "actual", "match"}``.
    Discrepancies are reported, never forced to match.
    """
    checks = []
    for key, exp in expected.items():
        act = actual.get(key)
        if isinstance(exp, dict) and isinstance(act, dict):
            # Compare only the keys we have expectations for, but flag extras.
            match = all(act.get(k) == v for k, v in exp.items()) and set(act) == set(exp)
        else:
            match = act == exp
        checks.append({"check": key, "expected": exp, "actual": act, "match": bool(match)})
    return checks


def inspect_archive(archive: SourceArchive, df: pd.DataFrame) -> dict[str, Any]:
    """Inspect one archive's raw frame and attach expectation checks."""
    stats = inspect_dataframe(df, archive.key)
    checks = compare_with_expected(stats, archive.expected)
    notes = DOCUMENTED_DISCREPANCIES.get(archive.key, {})
    for c in checks:
        if not c["match"] and c["check"] in notes:
            c["explanation"] = notes[c["check"]]
    warnings = [
        f"{archive.key}: '{c['check']}' expected {c['expected']} but found {c['actual']}"
        for c in checks if not c["match"]
    ]
    if stats["unknown_types"]:
        warnings.append(f"{archive.key}: unknown detection types {stats['unknown_types']}")
    if stats["confidence_unknown"]:
        warnings.append(f"{archive.key}: {stats['confidence_unknown']} rows with unknown confidence")
    for w in warnings:
        logger.warning(w)
    return {
        "sensor": archive.key,
        "collection": archive.collection,
        "zip_name": archive.zip_name,
        "archive_csv": archive.archive_csv,
        "ignored_csvs": list(archive.ignored_csvs),
        "statistics": stats,
        "expectation_checks": checks,
        "all_expectations_met": all(c["match"] for c in checks),
        "warnings": warnings,
    }
