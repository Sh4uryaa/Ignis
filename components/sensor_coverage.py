"""Two-row sensor coverage timeline: MODIS (Terra + Aqua family) and VIIRS."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from config.settings import COLORS, MODIS_PLATFORMS, VIIRS_PLATFORM_LABEL
from utils.charts import style_figure


def sensor_rows(cov: pd.DataFrame) -> pd.DataFrame:
    """Collapse per-satellite coverage into MODIS and VIIRS rows (display only).

    ``cov`` has satellite, start, end. Platform detail is kept in ``detail``.
    """
    rows = []
    modis = cov[cov["satellite"].isin(MODIS_PLATFORMS)]
    if not modis.empty:
        parts = [f"{r.satellite} {r.start:%d %b %Y} – {r.end:%d %b %Y}"
                 for r in modis.sort_values("start").itertuples()]
        rows.append({"sensor": "MODIS", "start": modis["start"].min(), "end": modis["end"].max(),
                     "color": COLORS["modis"], "detail": "<br>".join(parts)})
    viirs = cov[cov["satellite"] == VIIRS_PLATFORM_LABEL]
    if not viirs.empty:
        r = viirs.iloc[0]
        rows.append({"sensor": "VIIRS", "start": r["start"], "end": r["end"],
                     "color": COLORS["viirs"],
                     "detail": f"Suomi-NPP {r['start']:%d %b %Y} – {r['end']:%d %b %Y}"})
    return pd.DataFrame(rows)


def sensor_coverage_chart(cov: pd.DataFrame, height: int = 150) -> go.Figure:
    rows = sensor_rows(cov)
    fig = go.Figure()
    for _, r in rows.iterrows():
        ms = (r["end"] - r["start"]).total_seconds() * 1000
        fig.add_trace(go.Bar(
            y=[r["sensor"]], x=[ms], base=[r["start"]], orientation="h", width=0.26,
            marker={"color": r["color"], "cornerradius": 6},
            hovertemplate=f"<b>{r['sensor']}</b><br>{r['detail']}<extra></extra>", showlegend=False))
        for x, anchor in ((r["start"], "right"), (r["end"], "left")):
            fig.add_annotation(x=x, y=r["sensor"], text=f"{x:%Y}", showarrow=False,
                               xanchor=anchor, xshift=-6 if anchor == "right" else 6,
                               font={"color": COLORS["text_muted"], "size": 11})
    fig = style_figure(fig, None, height, legend=False)
    lo = rows["start"].min() - pd.DateOffset(years=2)
    hi = rows["end"].max() + pd.DateOffset(years=2)
    fig.update_xaxes(type="date", range=[lo, hi], showgrid=False)
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)", rangemode="normal",
                     tickfont={"color": COLORS["text"], "size": 13})
    fig.update_layout(hovermode="closest", bargap=0.5)
    return fig
