"""Sensor diagnostics that help interpret calibration and validation.

``overpass_times`` summarises the time of day at which each satellite made
its daytime detections, per year. Terra and Aqua stopped orbit maintenance
in the 2020s and drifted to earlier / later overpass times, while Suomi-NPP
did not; a shift here changes what part of the daily fire cycle MODIS sees
and can therefore change the MODIS/VIIRS ratio.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config.settings import IST_OFFSET_HOURS


def _decimal_hours(hhmm: pd.Series) -> pd.Series:
    t = hhmm.astype(str).astype(int)
    return t // 100 + (t % 100) / 60


def _fmt(hours: float) -> str:
    h = hours % 24
    return f"{int(h):02d}:{int(round((h % 1) * 60)) % 60:02d}"


def overpass_times(detections: pd.DataFrame) -> pd.DataFrame:
    """Median and interquartile daytime detection time by satellite and year.

    Uses daytime (``daynight == 'D'``) detections in the study regions.
    Detection times also reflect when fires burn, so this is an indicator of
    overpass timing rather than an exact orbital equator-crossing time.
    """
    d = detections[detections["daynight"].astype(str) == "D"]
    hours = _decimal_hours(d["acq_time"])
    g = hours.groupby([d["satellite"].astype(str), d["year"].astype(int)])
    out = pd.DataFrame({
        "median_hour_utc": g.median(),
        "q25_hour_utc": g.quantile(0.25),
        "q75_hour_utc": g.quantile(0.75),
        "daytime_detections": g.size(),
    })
    out.index.names = ["satellite", "year"]
    out = out.reset_index()
    out["median_hour_ist"] = out["median_hour_utc"] + IST_OFFSET_HOURS
    out["median_time_ist"] = out["median_hour_ist"].map(_fmt)
    first = out.sort_values("year").groupby("satellite")["median_hour_utc"].transform(
        lambda s: s.iloc[: min(5, len(s))].median())
    out["shift_vs_early_years_min"] = np.round((out["median_hour_utc"] - first) * 60).astype(int)
    return out.sort_values(["satellite", "year"]).reset_index(drop=True)
