"""Same-calendar-month anomalies of the harmonized series.

Each month is compared with the median of the *same calendar month* in all
other years of the baseline (leave-one-out, so a month never influences its
own baseline):

    A     = H_{y,m} - median(H_{other years, m})
    A_pct = A / median(...) * 100      (undefined when the median is 0)

Only complete harmonized months (estimated or VIIRS reference) are used;
partial, Terra-only and unavailable months are excluded. An unusual value is
an unusual satellite-detection count, not by itself evidence of an emergency.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config.settings import ANOMALY_NEAR_BAND_PCT
from processing.harmonize import FLAG_ESTIMATED, FLAG_VIIRS

ABOVE = "Above historical median"
NEAR = "Near historical median"
BELOW = "Below historical median"


def anomaly_label(value: float, baseline: float, pct: float,
                  band: float = ANOMALY_NEAR_BAND_PCT) -> str:
    """Label relative to the same-month median; safe for a zero baseline."""
    if np.isnan(value) or np.isnan(baseline):
        return "Insufficient baseline"
    if baseline == 0:
        return NEAR if value == 0 else ABOVE
    if pct > band:
        return ABOVE
    if pct < -band:
        return BELOW
    return NEAR


def calculate_anomalies(harmonized: pd.DataFrame, min_baseline_years: int = 5,
                        band: float = ANOMALY_NEAR_BAND_PCT) -> pd.DataFrame:
    """Leave-one-out same-month anomaly for every complete harmonized month."""
    h = harmonized[harmonized["source_flag"].isin([FLAG_ESTIMATED, FLAG_VIIRS])
                   & harmonized["harmonized_activity"].notna()].copy()
    rows = []
    for (region, month), grp in h.groupby(["region", "month"]):
        for _, row in grp.iterrows():
            others = grp[grp["year"] != row["year"]]
            n = len(others)
            if n >= min_baseline_years:
                base = float(others["harmonized_activity"].median())
            else:
                base = np.nan
            value = float(row["harmonized_activity"])
            diff = value - base if not np.isnan(base) else np.nan
            pct = diff / base * 100 if (not np.isnan(base) and base > 0) else np.nan
            rows.append({
                "region": region, "year": int(row["year"]), "month": int(month),
                "harmonized_activity": value,
                "is_estimated": bool(row["is_estimated"]),
                "source_flag": row["source_flag"],
                "historical_median": base,
                "baseline_years": n,
                "baseline_start_year": int(others["year"].min()) if n else None,
                "baseline_end_year": int(others["year"].max()) if n else None,
                "baseline_estimated_years": int(others["is_estimated"].sum()),
                "anomaly_abs": diff,
                "anomaly_pct": pct,
                "anomaly_label": anomaly_label(value, base, pct, band),
            })
    out = pd.DataFrame(rows)
    out["baseline_method"] = "leave_one_out_same_calendar_month_median"
    out["near_band_pct"] = band
    return out.sort_values(["region", "year", "month"]).reset_index(drop=True)
