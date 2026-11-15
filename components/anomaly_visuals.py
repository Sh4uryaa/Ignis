"""Anomaly charts: same-month history and recent deviations."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from config.settings import COLORS
from processing.calculate_anomalies import ABOVE, BELOW, NEAR
from utils.charts import DIVERGING, style_figure
from utils.dates import MONTH_NAMES

LABEL_COLORS = {ABOVE: DIVERGING["above"], NEAR: DIVERGING["near"], BELOW: DIVERGING["below"]}


def same_month_history(a: pd.DataFrame, month: int, highlight_year: int | None,
                       height: int = 360) -> go.Figure:
    """Harmonized activity for one calendar month across years vs its median."""
    s = a[a["month"] == month].sort_values("year")
    colors = [LABEL_COLORS.get(l, COLORS["text_muted"]) for l in s["anomaly_label"]]
    line_w = [2 if y == highlight_year else 0 for y in s["year"]]
    fig = go.Figure(go.Bar(
        x=s["year"].astype(str), y=s["harmonized_activity"],
        marker={"color": colors, "cornerradius": 4,
                "line": {"color": COLORS["text"], "width": line_w}},
        customdata=np.stack([s["historical_median"], s["anomaly_pct"], s["anomaly_label"],
                             np.where(s["is_estimated"], "Estimated", "Observed")], axis=1),
        hovertemplate=("%{x}: %{y:,.0f} (%{customdata[3]})<br>Median of other years: "
                       "%{customdata[0]:,.0f}<br>Deviation: %{customdata[1]:+.0f}%<br>"
                       "%{customdata[2]}<extra></extra>"),
        name=MONTH_NAMES[month - 1]))
    med = float(s["harmonized_activity"].median()) if len(s) else np.nan
    if np.isfinite(med):
        fig.add_hline(y=med, line={"color": COLORS["text"], "width": 1, "dash": "dot"},
                      annotation_text="All-years median", annotation_position="top left",
                      annotation_font={"color": COLORS["text_muted"], "size": 11})
    fig = style_figure(fig, f"Every {MONTH_NAMES[month - 1]} in the harmonized record", height,
                       "Harmonized activity", legend=False)
    fig.update_layout(hovermode="closest", bargap=0.25)
    return fig


def recent_deviation_chart(a: pd.DataFrame, months_back: int = 36, height: int = 320) -> go.Figure:
    """Percent deviation from same-month median for the most recent months."""
    s = a.sort_values(["year", "month"]).tail(months_back).copy()
    s["date"] = pd.to_datetime(dict(year=s["year"], month=s["month"], day=1))
    pct = s["anomaly_pct"].clip(-100, 300)
    fig = go.Figure(go.Bar(
        x=s["date"], y=pct,
        marker={"color": [LABEL_COLORS.get(l, COLORS["text_muted"]) for l in s["anomaly_label"]],
                "cornerradius": 3},
        customdata=np.stack([s["harmonized_activity"], s["historical_median"], s["anomaly_pct"],
                             s["anomaly_label"]], axis=1),
        hovertemplate=("%{x|%b %Y}: %{customdata[0]:,.0f} vs median %{customdata[1]:,.0f}"
                       "<br>%{customdata[2]:+.0f}% · %{customdata[3]}<extra></extra>")))
    fig.add_hline(y=0, line={"color": COLORS["text_muted"], "width": 1})
    fig = style_figure(fig, f"Deviation from same-month median — last {months_back} months", height,
                       "% vs same-month median (clipped at +300%)", legend=False)
    fig.update_yaxes(rangemode="normal")
    fig.update_layout(hovermode="closest")
    return fig
