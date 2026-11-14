"""Reusable filter controls."""
from __future__ import annotations

import datetime as dt

import streamlit as st

from config.settings import DETECTION_TYPE_LABELS
from services.analytics_service import SENSOR_OPTIONS
from utils.dates import MONTH_NAMES


def year_range(label: str, lo: int, hi: int, key: str, default: tuple[int, int] | None = None
               ) -> tuple[int, int]:
    return st.slider(label, min_value=lo, max_value=hi, value=default or (lo, hi), key=key)


def date_window(lo: dt.date, hi: dt.date, default: tuple[dt.date, dt.date], key: str
                ) -> tuple[dt.date, dt.date]:
    """Start/end date inputs constrained to the data range."""
    c1, c2 = st.columns(2)
    # Only pass a default when the widget has no state yet (other pages may preset it).
    for suffix, val in (("start", default[0]), ("end", default[1])):
        st.session_state.setdefault(f"{key}_{suffix}", val)
    start = c1.date_input("Start date", min_value=lo, max_value=hi, key=f"{key}_start")
    end = c2.date_input("End date", min_value=lo, max_value=hi, key=f"{key}_end")
    if start > end:
        st.error("Start date is after end date.")
    return start, end


def sensor_select(key: str, default: str = "All sensors") -> str:
    opts = list(SENSOR_OPTIONS)
    return st.selectbox("Sensor", opts, index=opts.index(default), key=key)


def detection_type_select(available: list[int], key: str) -> list[int] | None:
    """Detection-type filter; None means all types (the default policy)."""
    labels = {"All detection types": None}
    for t in sorted(available):
        labels[f"Type {t} – {DETECTION_TYPE_LABELS.get(t, 'Unknown')}"] = [t]
    choice = st.selectbox("Detection type", list(labels), key=key)
    return labels[choice]


def month_picker(years: list[int], key: str, default: tuple[int, int] | None = None
                 ) -> tuple[int, int]:
    c1, c2 = st.columns(2)
    d_year = default[0] if default and default[0] in years else years[-1]
    st.session_state.setdefault(f"{key}_year", d_year)
    st.session_state.setdefault(f"{key}_month", default[1] if default else 11)
    if st.session_state[f"{key}_year"] not in years:  # e.g. after switching region
        st.session_state[f"{key}_year"] = d_year
    year = c1.selectbox("Year", years, key=f"{key}_year")
    month = c2.selectbox("Month", list(range(1, 13)),
                         format_func=lambda m: MONTH_NAMES[m - 1], key=f"{key}_month")
    return int(year), int(month)
