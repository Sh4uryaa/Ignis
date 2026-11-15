"""Month/period helpers shared by processing and the app."""
from __future__ import annotations

import pandas as pd

MONTH_NAMES: tuple[str, ...] = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def to_period(value: str | pd.Timestamp | pd.Period) -> pd.Period:
    """Convert 'YYYY-MM', a timestamp or a period to a monthly Period."""
    return pd.Period(value, freq="M")


def month_range(start: str | pd.Period, end: str | pd.Period) -> pd.PeriodIndex:
    """Inclusive monthly PeriodIndex between two months."""
    return pd.period_range(to_period(start), to_period(end), freq="M")


def in_period(year: pd.Series, month: pd.Series, start: str, end: str) -> pd.Series:
    """Boolean mask: (year, month) within the inclusive [start, end] months."""
    key = year.astype(int) * 100 + month.astype(int)
    s, e = to_period(start), to_period(end)
    return (key >= s.year * 100 + s.month) & (key <= e.year * 100 + e.month)


def month_label(year: int, month: int) -> str:
    """Human label such as 'Nov 2000'."""
    return f"{MONTH_NAMES[int(month) - 1]} {int(year)}"
