"""Number and label formatting for display."""
from __future__ import annotations

import math

from utils.dates import month_label  # re-exported for pages

__all__ = ["fmt_int", "fmt_num", "fmt_pct", "fmt_signed_pct", "month_label", "is_missing"]


def is_missing(value) -> bool:
    try:
        return value is None or (isinstance(value, float) and math.isnan(value)) or \
            str(value) in ("<NA>", "nan", "NaT")
    except (TypeError, ValueError):
        return False


def fmt_int(value, missing: str = "—") -> str:
    """Thousands-separated integer, or a dash when missing."""
    if is_missing(value):
        return missing
    return f"{int(round(float(value))):,}"


def fmt_num(value, digits: int = 2, missing: str = "—") -> str:
    if is_missing(value):
        return missing
    return f"{float(value):,.{digits}f}"


def fmt_pct(value, digits: int = 1, missing: str = "—") -> str:
    if is_missing(value):
        return missing
    return f"{float(value):.{digits}f}%"


def fmt_signed_pct(value, digits: int = 0, missing: str = "—") -> str:
    if is_missing(value):
        return missing
    return f"{float(value):+.{digits}f}%"
