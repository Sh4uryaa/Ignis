"""Sensor observation coverage by month.

Coverage is derived from the data (first/last observation of each
satellite), never hard-coded. It is what lets IGNIS distinguish a true
zero-detection month from a month with no observations at all.
"""
from __future__ import annotations

import pandas as pd

COMPLETE, PARTIAL, NONE = "complete", "partial", "none"


def monthly_coverage(
    coverage: dict[str, tuple[pd.Timestamp, pd.Timestamp]],
    start: pd.Period,
    end: pd.Period,
) -> pd.DataFrame:
    """Per satellite and month: days covered and complete/partial/none status.

    A satellite covers a month completely when its observation record spans
    every day of that month.
    """
    rows = []
    for sat, (first, last) in coverage.items():
        first, last = pd.Timestamp(first).normalize(), pd.Timestamp(last).normalize()
        for p in pd.period_range(start, end, freq="M"):
            m0, m1 = p.start_time.normalize(), p.end_time.normalize()
            lo, hi = max(m0, first), min(m1, last)
            days = max(0, (hi - lo).days + 1)
            status = COMPLETE if days == p.days_in_month else (PARTIAL if days else NONE)
            rows.append({"satellite": sat, "year": p.year, "month": p.month,
                         "days_in_month": p.days_in_month, "days_covered": days,
                         "coverage_status": status})
    return pd.DataFrame(rows)


def observation_gaps(df: pd.DataFrame, min_gap_days: int = 20) -> list[dict]:
    """Runs of >= ``min_gap_days`` consecutive days with no detection at all.

    Computed over the full download area and all confidence levels. A gap may
    be a data outage *or* genuinely no fire, so these are reported for review
    rather than used to change coverage status.
    """
    gaps = []
    for sat, dates in df.groupby("satellite", observed=True)["acq_date"]:
        d = pd.Series(sorted(dates.dt.normalize().unique()))
        diff = d.diff().dt.days
        for i in diff[diff > min_gap_days].index:
            gaps.append({"satellite": str(sat),
                         "last_detection_before": d[i - 1].strftime("%Y-%m-%d"),
                         "next_detection": d[i].strftime("%Y-%m-%d"),
                         "days_without_detection": int(diff[i] - 1)})
    return gaps
