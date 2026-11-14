"""Independent validation of the seasonal calibration.

Factors are fitted on the training window only; this module applies them
to the held-out validation window and compares against observed VIIRS.
Nothing here is ever used to tune the factors.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config.settings import MIN_VALID_YEAR_PAIRS, REGIONS, VALIDATION_END, VALIDATION_START
from processing.harmonize import calibration_factors
from processing.coverage import COMPLETE
from utils.dates import in_period


def validation_months(totals: pd.DataFrame, factors: pd.DataFrame,
                      start: str = VALIDATION_START, end: str = VALIDATION_END,
                      constant_factors: dict[str, float] | None = None) -> pd.DataFrame:
    """Per-month comparison in the validation window (complete overlap only).

    * raw prediction: combined MODIS as-is
    * calibrated prediction: MODIS x seasonal factor r_m
    * constant-factor prediction (diagnostic): MODIS x one pooled training
      ratio per region, to test whether seasonality adds value
    """
    t = totals[in_period(totals["year"], totals["month"], start, end)]
    t = t[(t["modis_combined_coverage"] == COMPLETE) & (t["viirs_snpp_coverage"] == COMPLETE)]
    f = factors.set_index(["region", "calendar_month"])["calibration_factor"]
    out = t[["region", "year", "month"]].copy()
    out["actual_viirs_count"] = t["viirs_snpp_count"].astype(float)
    out["modis_combined_count"] = t["modis_combined_count"].astype(float)
    out["calibration_factor"] = [f.get((r, m), np.nan) for r, m in zip(out["region"], out["month"])]
    out["predicted_viirs_equivalent"] = out["modis_combined_count"] * out["calibration_factor"]
    out["raw_error"] = out["modis_combined_count"] - out["actual_viirs_count"]
    out["calibrated_error"] = out["predicted_viirs_equivalent"] - out["actual_viirs_count"]
    if constant_factors:
        out["constant_factor"] = out["region"].map(constant_factors)
        out["constant_factor_prediction"] = out["modis_combined_count"] * out["constant_factor"]
        out["constant_factor_error"] = out["constant_factor_prediction"] - out["actual_viirs_count"]
    out["included_in_metrics"] = out["calibration_factor"].notna()
    return out.sort_values(["region", "year", "month"]).reset_index(drop=True)


def error_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    """MAE, RMSE, WAPE (%) and relative bias (%). Zero denominators -> NaN."""
    a = np.asarray(actual, dtype=float)
    p = np.asarray(predicted, dtype=float)
    n = a.size
    if n == 0:
        return {"n_months": 0, "mae": np.nan, "rmse": np.nan, "wape_pct": np.nan,
                "relative_bias_pct": np.nan}
    err = p - a
    denom = a.sum()
    return {
        "n_months": int(n),
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "wape_pct": float(np.abs(err).sum() / denom * 100) if denom > 0 else np.nan,
        "relative_bias_pct": float(err.sum() / denom * 100) if denom > 0 else np.nan,
    }


def validation_metrics(rows: pd.DataFrame, regions: tuple[str, ...] = REGIONS,
                       period: tuple[str, str] = (VALIDATION_START, VALIDATION_END),
                       validation_type: str = "primary_independent_holdout") -> pd.DataFrame:
    """Raw vs calibrated (and constant-factor) metrics per region."""
    records = []
    for region in regions:
        r = rows[(rows["region"] == region) & rows["included_in_metrics"]]
        comparisons = {"raw_modis": r["modis_combined_count"],
                       "calibrated_seasonal": r["predicted_viirs_equivalent"]}
        if "constant_factor_prediction" in r:
            comparisons["constant_factor"] = r["constant_factor_prediction"]
        for name, pred in comparisons.items():
            records.append({"region": region, "comparison": name,
                            "validation_type": validation_type,
                            "validation_start": period[0],
                            "validation_end": period[1],
                            **error_metrics(r["actual_viirs_count"], pred)})
    out = pd.DataFrame(records)
    # Did seasonal calibration beat raw MODIS on WAPE?
    out["improves_on_raw_wape"] = pd.Series(pd.NA, index=out.index, dtype="boolean")
    for region in regions:
        sel = out["region"] == region
        raw = out.loc[sel & (out["comparison"] == "raw_modis"), "wape_pct"]
        if not raw.empty and np.isfinite(raw.iloc[0]):
            other = sel & (out["comparison"] != "raw_modis")
            out.loc[other, "improves_on_raw_wape"] = out.loc[other, "wape_pct"] < raw.iloc[0]
    return out


def pooled_constant_factors(pairs: pd.DataFrame) -> dict[str, float]:
    """One non-seasonal factor per region: sum(V) / sum(M) over valid training pairs.

    Used only as a diagnostic baseline in validation, never in the series.
    """
    p = pairs[pairs["is_valid_pair"]]
    g = p.groupby("region")[["viirs_snpp_count", "modis_combined_count"]].sum()
    return {r: float(row["viirs_snpp_count"] / row["modis_combined_count"])
            for r, row in g.iterrows() if row["modis_combined_count"] > 0}


def leave_one_year_out(pairs: pd.DataFrame, first_year: int, last_year: int,
                       regions: tuple[str, ...] = REGIONS,
                       min_pairs: int = MIN_VALID_YEAR_PAIRS) -> pd.DataFrame:
    """Supplementary cross-validation within stable-orbit training years.

    For each year y in [first_year, last_year], seasonal and constant factors
    are refitted on the *other* years of that window only, then used to
    predict year y's complete months. This tests the method while MODIS
    overpass times were stable. It re-uses training-period data, so it is
    labelled supplementary and never replaces the independent hold-out.
    """
    window = pairs[(pairs["year"] >= first_year) & (pairs["year"] <= last_year)]
    out = []
    for y in range(first_year, last_year + 1):
        fit = window[window["year"] != y]
        test = window[window["year"] == y]
        if test.empty:
            continue
        factors = calibration_factors(fit, regions=regions, min_pairs=min_pairs)
        f = factors.set_index(["region", "calendar_month"])["calibration_factor"]
        const = pooled_constant_factors(fit)
        rows = test[["region", "year", "month"]].copy()
        rows["actual_viirs_count"] = test["viirs_snpp_count"].astype(float)
        rows["modis_combined_count"] = test["modis_combined_count"].astype(float)
        rows["calibration_factor"] = [f.get((r, m), np.nan)
                                      for r, m in zip(rows["region"], rows["month"])]
        rows["predicted_viirs_equivalent"] = rows["modis_combined_count"] * rows["calibration_factor"]
        rows["raw_error"] = rows["modis_combined_count"] - rows["actual_viirs_count"]
        rows["calibrated_error"] = rows["predicted_viirs_equivalent"] - rows["actual_viirs_count"]
        rows["constant_factor"] = rows["region"].map(const)
        rows["constant_factor_prediction"] = rows["modis_combined_count"] * rows["constant_factor"]
        rows["constant_factor_error"] = rows["constant_factor_prediction"] - rows["actual_viirs_count"]
        rows["included_in_metrics"] = rows["calibration_factor"].notna()
        rows["held_out_year"] = y
        out.append(rows)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()
