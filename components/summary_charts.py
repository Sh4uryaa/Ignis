"""Small overview charts: detection types and seasonality.

(Sensor coverage lives in components/sensor_coverage.py.) Titles are given
by the page's section headings, so these figures carry none.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from config.settings import COLORS
from utils.charts import style_figure


def detection_type_chart(t: pd.DataFrame, height: int = 280) -> go.Figure:
    """Detections by type, one bar group per sensor (log axis: types differ 100×)."""
    fig = go.Figure()
    for sensor, color in (("MODIS", COLORS["modis"]), ("VIIRS", COLORS["viirs"])):
        s = t[t["sensor"] == sensor]
        fig.add_trace(go.Bar(
            x=[f"Type {d}" for d in s["detection_type"]], y=s["detection_count"], name=sensor,
            marker={"color": color, "cornerradius": 4},
            customdata=s[["detection_type_label"]].to_numpy(),
            hovertemplate="%{customdata[0]}: %{y:,}<extra>" + sensor + "</extra>"))
    fig = style_figure(fig, None, height, "Detections (log scale)")
    fig.update_yaxes(type="log", rangemode="normal")
    fig.update_layout(hovermode="closest", bargap=0.35, bargroupgap=0.1)
    return fig


def seasonal_chart(s: pd.DataFrame, height: int = 280) -> go.Figure:
    """Median harmonized activity per calendar month (harmonized colour)."""
    fig = go.Figure(go.Bar(
        x=s["month_name"], y=s["median"], marker={"color": COLORS["harmonized"], "cornerradius": 4},
        customdata=s[["years"]].to_numpy(),
        hovertemplate="%{x}: median %{y:,.0f} (%{customdata[0]} years)<extra></extra>"))
    fig = style_figure(fig, None, height, "Harmonized activity", legend=False)
    fig.update_layout(hovermode="closest", bargap=0.3)
    return fig
