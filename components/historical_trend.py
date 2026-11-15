"""Three-line historical chart: raw MODIS, raw VIIRS and the harmonized record.

Values are plotted exactly as processed. From the start of the VIIRS
reference period the harmonized record *is* the VIIRS observation, so the
two lines coincide; the harmonized line is drawn last and dashed so it
stays visible on top, and is never offset.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from config.settings import COLORS
from processing.harmonize import FLAG_ESTIMATED, FLAG_VIIRS
from utils.charts import style_figure


def _complete(t: pd.DataFrame, count: str, coverage: str) -> pd.Series:
    """Counts only for months the sensor observed completely (others are gaps)."""
    return t[count].astype(float).where(t[coverage] == "complete")


def historical_trend_chart(t: pd.DataFrame, h: pd.DataFrame, height: int = 430) -> go.Figure:
    """``t``: monthly region totals with ``date``; ``h``: harmonized rows with ``date``."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=t["date"], y=_complete(t, "modis_combined_count", "modis_combined_coverage"),
        mode="lines", name="MODIS Terra + Aqua (raw)",
        line={"color": COLORS["modis"], "width": 1.6}, hovertemplate="%{y:,.0f}"))
    fig.add_trace(go.Scatter(
        x=t["date"], y=_complete(t, "viirs_snpp_count", "viirs_snpp_coverage"),
        mode="lines", name="VIIRS Suomi-NPP (raw)",
        line={"color": COLORS["viirs"], "width": 2.6}, hovertemplate="%{y:,.0f}"))
    usable = h["source_flag"].isin([FLAG_ESTIMATED, FLAG_VIIRS])
    kind = np.where(h["source_flag"] == FLAG_ESTIMATED, "estimated from MODIS",
                    "= VIIRS reference")
    fig.add_trace(go.Scatter(
        x=h["date"], y=h["harmonized_activity"].where(usable), mode="lines",
        name="Harmonized record", customdata=kind,
        line={"color": COLORS["harmonized"], "width": 1.8, "dash": "dash"},
        hovertemplate="%{y:,.0f} (%{customdata})"))
    ref = h.loc[h["source_flag"] == FLAG_VIIRS, "date"]
    if not ref.empty:
        fig.add_vline(x=ref.min(), line={"color": COLORS["text_muted"], "width": 1, "dash": "dot"})
        fig.add_annotation(x=ref.min(), y=1, yref="paper", text="VIIRS reference period →",
                           showarrow=False, xanchor="left", yanchor="top",
                           font={"color": COLORS["text_muted"], "size": 11})
    fig = style_figure(fig, None, height, "Hotspot detections per month")
    fig.update_xaxes(type="date", title_text=None)
    fig.update_traces(connectgaps=False)
    return fig
