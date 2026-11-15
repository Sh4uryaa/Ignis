"""Small overview charts: coverage timeline, detection types, seasonality."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from config.settings import COLORS
from utils.charts import style_figure

SAT_COLORS = {"Terra": COLORS["terra"], "Aqua": COLORS["aqua"], "Suomi-NPP": COLORS["viirs"]}


def coverage_timeline(cov: pd.DataFrame, height: int = 220) -> go.Figure:
    """Observation record of each satellite as horizontal bars."""
    fig = go.Figure()
    for _, r in cov.iterrows():
        days = (r["end"] - r["start"]).days
        fig.add_trace(go.Bar(
            y=[r["satellite"]], x=[days * 86_400_000], base=[r["start"]], orientation="h",
            marker={"color": SAT_COLORS.get(r["satellite"], COLORS["text_muted"]), "cornerradius": 4},
            hovertemplate=(f"{r['satellite']}: {r['start']:%d %b %Y} – {r['end']:%d %b %Y}"
                           "<extra></extra>"), showlegend=False))
    fig = style_figure(fig, "Sensor coverage", height, legend=False)
    fig.update_xaxes(type="date")
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)", rangemode="normal")
    fig.update_layout(hovermode="closest", bargap=0.45)
    return fig


def detection_type_chart(t: pd.DataFrame, height: int = 260) -> go.Figure:
    """Detections by type, one bar group per sensor (log axis: types differ 100×)."""
    fig = go.Figure()
    for sensor, color in (("MODIS", COLORS["modis"]), ("VIIRS", COLORS["viirs"])):
        s = t[t["sensor"] == sensor]
        fig.add_trace(go.Bar(
            x=[f"Type {d}" for d in s["detection_type"]], y=s["detection_count"], name=sensor,
            marker={"color": color, "cornerradius": 4},
            customdata=s[["detection_type_label"]].to_numpy(),
            hovertemplate="%{customdata[0]}: %{y:,}<extra>" + sensor + "</extra>"))
    fig = style_figure(fig, "Detection types (all included)", height, "Detections (log scale)")
    fig.update_yaxes(type="log", rangemode="normal")
    fig.update_layout(hovermode="closest", bargap=0.35, bargroupgap=0.1)
    return fig


def seasonal_chart(s: pd.DataFrame, height: int = 260) -> go.Figure:
    """Median harmonized activity per calendar month."""
    fig = go.Figure(go.Bar(
        x=s["month_name"], y=s["median"], marker={"color": COLORS["primary"], "cornerradius": 4},
        customdata=s[["years"]].to_numpy(),
        hovertemplate="%{x}: median %{y:,.0f} (%{customdata[0]} years)<extra></extra>"))
    fig = style_figure(fig, "Typical year (median per month)", height, "Harmonized activity",
                       legend=False)
    fig.update_layout(hovermode="closest", bargap=0.3)
    return fig
