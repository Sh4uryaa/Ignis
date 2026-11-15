"""Bootstrap calibration-factor uncertainty for pre-reference estimates.

For each region and calendar month, the valid training-year ratios are
resampled with replacement, their median recomputed, and the 2.5th / 97.5th
percentiles of those medians give [r_lower, r_upper]. Estimated months get
``[M * r_lower, M * r_upper]``.

Scope: this is a *95% bootstrap calibration-factor uncertainty interval*
only — not a prediction interval and not total observation uncertainty.
No interval is produced for VIIRS reference months or for months without
enough valid training pairs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config.settings import (
    BOOTSTRAP_ITERATIONS,
    BOOTSTRAP_SEED,
    INTERVAL_LEVEL,
    MIN_VALID_YEAR_PAIRS,
    REGIONS,
    UNCERTAINTY_SCOPE,
)
from processing.harmonize import FLAG_ESTIMATED

INTERVAL_METHOD = "bootstrap_median_of_year_pair_ratios"


def bootstrap_median_interval(ratios: np.ndarray, iterations: int = BOOTSTRAP_ITERATIONS,
                              level: float = INTERVAL_LEVEL,
                              rng: np.random.Generator | None = None) -> tuple[float, float]:
    """Percentile interval of the bootstrap distribution of the median."""
    ratios = np.asarray(ratios, dtype=float)
    if ratios.size == 0:
        raise ValueError("No ratios to bootstrap.")
    rng = rng or np.random.default_rng(BOOTSTRAP_SEED)
    idx = rng.integers(0, ratios.size, size=(iterations, ratios.size))
    medians = np.median(ratios[idx], axis=1)
    alpha = (1 - level) / 2
    lo, hi = np.quantile(medians, [alpha, 1 - alpha])
    return float(lo), float(hi)


def factor_intervals(pairs: pd.DataFrame, regions: tuple[str, ...] = REGIONS,
                     min_pairs: int = MIN_VALID_YEAR_PAIRS,
                     iterations: int = BOOTSTRAP_ITERATIONS,
                     seed: int = BOOTSTRAP_SEED, level: float = INTERVAL_LEVEL) -> pd.DataFrame:
    """Bootstrap factor interval per region and calendar month.

    Each (region, month) uses its own generator seeded from ``seed`` and the
    region/month position, so results are reproducible and independent of
    processing order.
    """
    rows = []
    for ri, region in enumerate(regions):
        for month in range(1, 13):
            r = pairs.loc[(pairs["region"] == region) & (pairs["month"] == month)
                          & pairs["is_valid_pair"], "ratio"].to_numpy(dtype=float)
            row = {"region": region, "calendar_month": month,
                   "valid_training_pairs": int(r.size),
                   "factor_lower": np.nan, "factor_upper": np.nan,
                   "interval_status": f"unavailable: {r.size} valid pairs (< {min_pairs})"}
            if r.size >= min_pairs:
                rng = np.random.default_rng([seed, ri, month])
                row["factor_lower"], row["factor_upper"] = bootstrap_median_interval(
                    r, iterations, level, rng)
                row["interval_status"] = "available"
            rows.append(row)
    return pd.DataFrame(rows)


def uncertainty_intervals(harmonized: pd.DataFrame, intervals: pd.DataFrame,
                          level: float = INTERVAL_LEVEL) -> pd.DataFrame:
    """Apply factor intervals to estimated months only."""
    est = harmonized[harmonized["source_flag"] == FLAG_ESTIMATED]
    merged = est.merge(intervals, left_on=["region", "month"],
                       right_on=["region", "calendar_month"], how="left")
    merged = merged[merged["interval_status"] == "available"]
    m = merged["modis_combined_count"].astype(float)
    out = pd.DataFrame({
        "region": merged["region"],
        "year": merged["year"],
        "month": merged["month"],
        "harmonized_estimate": merged["harmonized_activity"],
        "lower_bound": m * merged["factor_lower"],
        "upper_bound": m * merged["factor_upper"],
        "factor_lower": merged["factor_lower"],
        "factor_upper": merged["factor_upper"],
        "interval_level": level,
        "interval_method": INTERVAL_METHOD,
        "valid_training_pairs": merged["valid_training_pairs"],
        "uncertainty_scope": UNCERTAINTY_SCOPE,
    })
    return out.sort_values(["region", "year", "month"]).reset_index(drop=True)
