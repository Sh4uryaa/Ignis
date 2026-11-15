"""Seasonal MODIS -> VIIRS calibration and the harmonized monthly series.

For each region and calendar month m, with complete-month training pairs:

    r_{y,m} = V_{y,m} / M_{y,m}          (VIIRS / combined Terra+Aqua MODIS)
    r_m     = median_y r_{y,m}

Historical months before the VIIRS record are reconstructed as
``H = M * r_m`` (estimates on the VIIRS S-NPP reference scale); complete
VIIRS months use ``H = V`` directly. MODIS and VIIRS are never added.

Note: combined Terra+Aqua is compared with a single VIIRS satellite, so r_m
absorbs differences in observation opportunities (overpass count and time)
as well as detection sensitivity. This is an empirical adjustment, not a
physical conversion, and VIIRS is a reference, not ground truth.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config.settings import (
    CALIBRATION_METHOD,
    CONFIDENCE_POLICY_NAME,
    MIN_MONTHLY_DETECTIONS,
    MIN_VALID_YEAR_PAIRS,
    REGIONS,
    TRAINING_END,
    TRAINING_START,
    VALIDATION_END,
    VALIDATION_START,
)
from processing.coverage import COMPLETE, NONE, PARTIAL
from utils.dates import in_period

# Source flags used in harmonized_monthly.csv.
FLAG_TERRA_ONLY = "terra_only_unharmonized"
FLAG_PARTIAL_PLATFORM = "partial_modis_platform_coverage"
FLAG_ESTIMATED = "estimated_from_modis"
FLAG_NO_FACTOR = "estimate_unavailable_no_factor"
FLAG_PARTIAL_VIIRS = "partial_viirs_month"
FLAG_VIIRS = "viirs_reference"
FLAG_MODIS_ONLY_AFTER = "modis_only_after_reference"
FLAG_NO_DATA = "no_observations"

FLAG_DESCRIPTIONS: dict[str, str] = {
    FLAG_TERRA_ONLY: "Terra-only MODIS; not on the combined harmonized scale",
    FLAG_PARTIAL_PLATFORM: "Partial combined Terra+Aqua coverage",
    FLAG_ESTIMATED: "Estimated VIIRS-equivalent activity (MODIS x seasonal factor)",
    FLAG_NO_FACTOR: "MODIS observed but no valid calibration factor for this month",
    FLAG_PARTIAL_VIIRS: "Partial VIIRS reference month",
    FLAG_VIIRS: "Direct VIIRS S-NPP reference observation",
    FLAG_MODIS_ONLY_AFTER: "MODIS-only period after the VIIRS reference ends",
    FLAG_NO_DATA: "No satellite observations",
}


# ---------------------------------------------------------------------------
# Training pairs and factors
# ---------------------------------------------------------------------------
def training_pairs(totals: pd.DataFrame, start: str = TRAINING_START, end: str = TRAINING_END,
                   min_detections: int = MIN_MONTHLY_DETECTIONS) -> pd.DataFrame:
    """Complete overlapping months in the training window, with ratio validity.

    A pair is valid when both sensors have complete coverage and at least
    ``min_detections`` detections (which also rules out division by zero).
    """
    t = totals[in_period(totals["year"], totals["month"], start, end)].copy()
    t = t[(t["modis_combined_coverage"] == COMPLETE) & (t["viirs_snpp_coverage"] == COMPLETE)]
    m = t["modis_combined_count"].astype(float)
    v = t["viirs_snpp_count"].astype(float)
    valid = (m >= min_detections) & (v >= min_detections)
    reason = np.where(m < min_detections, f"MODIS count < {min_detections}",
                      np.where(v < min_detections, f"VIIRS count < {min_detections}", ""))
    out = t[["region", "year", "month"]].copy()
    out["modis_combined_count"] = m.astype("Int64")
    out["viirs_snpp_count"] = v.astype("Int64")
    out["ratio"] = np.where(valid, v / m.where(m > 0), np.nan)
    out["is_valid_pair"] = valid.to_numpy()
    out["exclusion_reason"] = reason
    return out.reset_index(drop=True)


def calibration_factors(pairs: pd.DataFrame, regions: tuple[str, ...] = REGIONS,
                        min_pairs: int = MIN_VALID_YEAR_PAIRS,
                        min_detections: int = MIN_MONTHLY_DETECTIONS,
                        start: str = TRAINING_START, end: str = TRAINING_END) -> pd.DataFrame:
    """Median seasonal factor per region and calendar month.

    Months with fewer than ``min_pairs`` valid year pairs get no factor
    (NaN) and an explicit reason; no fallback value is invented.
    """
    rows = []
    for region in regions:
        for month in range(1, 13):
            p = pairs[(pairs["region"] == region) & (pairs["month"] == month) & pairs["is_valid_pair"]]
            n = int(len(p))
            ok = n >= min_pairs
            pooled = (p["viirs_snpp_count"].sum() / p["modis_combined_count"].sum()) if n else np.nan
            rows.append({
                "region": region,
                "calendar_month": month,
                "calibration_factor": float(p["ratio"].median()) if ok else np.nan,
                "pooled_ratio_diagnostic": float(pooled) if n else np.nan,
                "training_start": start,
                "training_end": end,
                "valid_training_pairs": n,
                "minimum_detection_threshold": min_detections,
                "minimum_valid_pairs": min_pairs,
                "method": CALIBRATION_METHOD,
                "validation_status": "available" if ok else "unavailable",
                "unavailable_reason": "" if ok else
                    f"Only {n} valid year pairs (< {min_pairs} required)",
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Harmonized series
# ---------------------------------------------------------------------------
def _source_flag(row: pd.Series, viirs_start: pd.Period, has_factor: bool) -> str:
    """Classify a month from data-derived coverage (no hard-coded dates)."""
    v, mc = row["viirs_snpp_coverage"], row["modis_combined_coverage"]
    period = pd.Period(year=int(row["year"]), month=int(row["month"]), freq="M")
    if v == COMPLETE:
        return FLAG_VIIRS
    if v == PARTIAL:
        return FLAG_PARTIAL_VIIRS
    # VIIRS not observing this month.
    if period > viirs_start:
        return FLAG_MODIS_ONLY_AFTER if mc != NONE else FLAG_NO_DATA
    if mc == "terra_only":
        return FLAG_TERRA_ONLY
    if mc in (PARTIAL, "aqua_only"):
        return FLAG_PARTIAL_PLATFORM
    if mc == COMPLETE:
        return FLAG_ESTIMATED if has_factor else FLAG_NO_FACTOR
    return FLAG_NO_DATA


def harmonize(totals: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    """Build harmonized_monthly from monthly region totals and factors."""
    viirs_obs = totals[totals["viirs_snpp_coverage"] != NONE]
    if viirs_obs.empty:
        raise ValueError("No VIIRS reference months available.")
    first = viirs_obs.sort_values(["year", "month"]).iloc[0]
    viirs_start = pd.Period(year=int(first["year"]), month=int(first["month"]), freq="M")

    f = factors.set_index(["region", "calendar_month"])["calibration_factor"]
    out = totals.copy()
    out["calibration_factor"] = [f.get((r, m), np.nan) for r, m in zip(out["region"], out["month"])]
    out["source_flag"] = [
        _source_flag(row, viirs_start, not np.isnan(row["calibration_factor"]))
        for _, row in out.iterrows()]

    m = out["modis_combined_count"].astype(float)
    v = out["viirs_snpp_count"].astype(float)
    est = out["source_flag"] == FLAG_ESTIMATED
    ref = out["source_flag"] == FLAG_VIIRS
    out["harmonized_activity"] = np.where(est, m * out["calibration_factor"],
                                          np.where(ref, v, np.nan))
    out.loc[~est, "calibration_factor"] = np.nan  # factor only shown where applied
    out["is_estimated"] = est
    out["is_partial_month"] = (
        out["source_flag"].isin([FLAG_PARTIAL_PLATFORM, FLAG_PARTIAL_VIIRS])
        | ((out["source_flag"] == FLAG_MODIS_ONLY_AFTER)
           & (out["modis_combined_coverage"] != COMPLETE)))
    out["status_description"] = out["source_flag"].map(FLAG_DESCRIPTIONS)
    out["confidence_policy"] = CONFIDENCE_POLICY_NAME
    cols = ["region", "year", "month", "modis_terra_count", "modis_aqua_count",
            "modis_combined_count", "viirs_snpp_count", "harmonized_activity",
            "calibration_factor", "source_flag", "is_estimated", "is_partial_month",
            "status_description", "confidence_policy"]
    return out[cols].sort_values(["region", "year", "month"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Calibrated MODIS comparison series
# ---------------------------------------------------------------------------
PERIOD_BACKCAST = "historical_backcast"
PERIOD_TRAINING = "training_in_sample"
PERIOD_VALIDATION = "validation_out_of_sample"
PERIOD_OTHER = "not_a_comparison_month"

PERIOD_DESCRIPTIONS: dict[str, str] = {
    PERIOD_BACKCAST: "Before VIIRS: calibrated MODIS is the harmonized estimate",
    PERIOD_TRAINING: "Training years: in-sample comparison with VIIRS (factors fitted here)",
    PERIOD_VALIDATION: "Held-out years: out-of-sample prediction of VIIRS",
    PERIOD_OTHER: "Complete MODIS month without a complete VIIRS comparison month",
}


def calibrated_modis_series(totals: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    """``Calibrated_MODIS = MODIS_combined × r_m`` for every eligible month.

    Eligible: combined Terra + Aqua coverage is complete and the region-month
    factor is available. ``factors`` are the training-period factors; nothing
    is refitted here, so validation months stay out-of-sample.

    This is a comparison series only — the final harmonized record
    (``harmonize``) still uses actual VIIRS once it is available.
    """
    t = totals[totals["modis_combined_coverage"] == COMPLETE].copy()
    f = factors.set_index(["region", "calendar_month"])["calibration_factor"]
    t["calibration_factor"] = [f.get((r, m), np.nan) for r, m in zip(t["region"], t["month"])]
    t = t[t["calibration_factor"].notna()]

    viirs_obs = totals[totals["viirs_snpp_coverage"] != NONE]
    first = viirs_obs.sort_values(["year", "month"]).iloc[0] if not viirs_obs.empty else None
    first_key = int(first["year"]) * 100 + int(first["month"]) if first is not None else 10**9
    key = t["year"].astype(int) * 100 + t["month"].astype(int)

    m = t["modis_combined_count"].astype(float)
    v = t["viirs_snpp_count"].astype(float)
    overlap = t["viirs_snpp_coverage"] == COMPLETE
    period = np.select(
        [(t["viirs_snpp_coverage"] == NONE) & (key < first_key),
         overlap & in_period(t["year"], t["month"], TRAINING_START, TRAINING_END),
         overlap & in_period(t["year"], t["month"], VALIDATION_START, VALIDATION_END)],
        [PERIOD_BACKCAST, PERIOD_TRAINING, PERIOD_VALIDATION], default=PERIOD_OTHER)

    out = t[["region", "year", "month"]].copy()
    out["modis_combined_count"] = m.astype("Int64")
    out["viirs_snpp_count"] = v.where(overlap).astype("Int64")
    out["calibration_factor"] = t["calibration_factor"]
    out["calibrated_modis"] = m * t["calibration_factor"]
    out["comparison_period"] = period
    out["is_complete_overlap"] = overlap.to_numpy()
    err = (out["calibrated_modis"] - v).where(overlap)
    out["error"] = err
    out["absolute_error"] = err.abs()
    out["relative_error_pct"] = (err / v.where(v > 0) * 100)
    out["confidence_policy"] = CONFIDENCE_POLICY_NAME
    return out.sort_values(["region", "year", "month"]).reset_index(drop=True)
