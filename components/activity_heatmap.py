"""Month-by-year harmonized activity calendar (Plotly heatmap).

Harmonized months use a Viridis scale. Months that are not on the
harmonized scale (Terra-only, partial, unavailable) are drawn as neutral
grey cells with their status, never as zero. Estimated months carry a small
marker so estimated and observed values are distinguishable without colour.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from config.settings import COLORS
from services.analytics_service import calendar_matrix
from utils.charts import style_figure
from utils.dates import MONTH_NAMES


def _fmt(v, digits=0) -> str:
    return "—" if pd.isna(v) else f"{float(v):,.{digits}f}"


def _hover_text(frame: pd.DataFrame) -> pd.DataFrame:
    def row_text(r) -> str:
        interval = (f"{_fmt(r['lower_bound'])}–{_fmt(r['upper_bound'])}"
                    if pd.notna(r.get("lower_bound")) else "n/a")
        kind = "Estimated" if r["is_estimated"] else (
            "Observed" if r["source_flag"] == "viirs_reference" else "Not harmonized")
        return (f"<b>{r['region']} · {MONTH_NAMES[int(r['month']) - 1]} {int(r['year'])}</b><br>"
                f"Harmonized activity: <b>{_fmt(r['harmonized_activity'])}</b><br>"
                f"MODIS Terra: {_fmt(r['modis_terra_count'])} · Aqua: {_fmt(r['modis_aqua_count'])}"
                f" · Combined: {_fmt(r['modis_combined_count'])}<br>"
                f"VIIRS S-NPP: {_fmt(r['viirs_snpp_count'])}<br>"
                f"Calibration factor: {_fmt(r['calibration_factor'], 2)}<br>"
                f"95% calibration-factor interval: {interval}<br>"
                f"Status: {r['status']} ({kind})")
    f = frame.copy()
    f["hover"] = f.apply(row_text, axis=1)
    return f


def calendar_heatmap(frame: pd.DataFrame, log_scale: bool = True, height: int | None = None
                     ) -> go.Figure:
    """Build the calendar figure from ``analytics_service.calendar_frame`` output."""
    f = _hover_text(frame)
    values = calendar_matrix(f, "harmonized_activity")
    hover = calendar_matrix(f, "hover")
    status = calendar_matrix(f, "source_flag")
    years = [str(y) for y in values.index]
    months = list(MONTH_NAMES)

    z = values.to_numpy(dtype=float)
    zplot = np.log10(z + 1) if log_scale else z
    vmax = np.nanmax(z) if np.isfinite(z).any() else 1
    fig = go.Figure()
    # Neutral layer for months that exist but are not on the harmonized scale.
    not_h = (status.notna() & values.isna()).to_numpy()
    fig.add_trace(go.Heatmap(
        z=np.where(not_h, 1.0, np.nan), x=months, y=years,
        colorscale=[[0, "#3A404D"], [1, "#3A404D"]], showscale=False, xgap=2, ygap=2,
        text=hover.to_numpy(), hovertemplate="%{text}<extra></extra>", name="Not harmonized"))
    if log_scale:
        ticks = [v for v in [0, 10, 100, 1_000, 10_000, 100_000] if v <= vmax * 1.01]
        colorbar = {"tickvals": np.log10(np.array(ticks) + 1), "ticktext": [f"{t:,}" for t in ticks]}
    else:
        colorbar = {}
    colorbar.update({"title": {"text": "Detections", "side": "right"}, "thickness": 12,
                     "outlinewidth": 0, "tickfont": {"color": COLORS["text_muted"]}})
    fig.add_trace(go.Heatmap(
        z=zplot, x=months, y=years, colorscale="Viridis", xgap=2, ygap=2,
        zmin=0, zmax=float(np.log10(vmax + 1) if log_scale else vmax),
        text=hover.to_numpy(), hovertemplate="%{text}<extra></extra>",
        colorbar=colorbar, name="Harmonized activity"))
    # Estimated-month marker (secondary encoding, not colour).
    est = calendar_matrix(f, "is_estimated").fillna(False).astype(bool)
    ey, em = np.where(est.to_numpy())
    fig.add_trace(go.Scatter(
        x=[months[i] for i in em], y=[years[i] for i in ey], mode="markers",
        marker={"symbol": "circle-open", "size": 5, "color": "rgba(255,255,255,0.75)",
                "line": {"width": 1}},
        name="Estimated from MODIS", hoverinfo="skip"))
    # Transparent clickable cells: Plotly heatmaps emit no selection events in
    # Streamlit, scatter points do. They also carry the hover text.
    present = status.notna().to_numpy()
    py, pm = np.where(present)
    htext = hover.to_numpy()
    fig.add_trace(go.Scatter(
        x=[months[i] for i in pm], y=[years[i] for i in py], mode="markers",
        marker={"symbol": "square", "size": 22, "color": "rgba(0,0,0,0)"},
        selected={"marker": {"opacity": 1}}, unselected={"marker": {"opacity": 1}},
        text=[htext[a, b] for a, b in zip(py, pm)], hovertemplate="%{text}<extra></extra>",
        name="cells", showlegend=False))
    for trace in fig.data[:2]:  # hover handled by the clickable layer
        trace.hoverinfo = "skip"
        trace.hovertemplate = None
    # The ○ marker is explained in the page caption; a legend would collide with top month labels.
    fig = style_figure(fig, None, height or max(420, 22 * len(years) + 80), legend=False)
    fig.update_layout(hovermode="closest", clickmode="event+select")
    fig.update_yaxes(autorange="reversed", type="category", gridcolor="rgba(0,0,0,0)",
                     rangemode="normal")
    fig.update_xaxes(side="top", type="category")
    return fig
