"""GitHub-style burning-activity calendar: years × months of square cells.

Colour = harmonized monthly activity on a yellow → orange → red fire scale.
Bins are quantiles of the selected region's monthly values (one scale for
all years, so years are comparable); hover always shows the actual count.

Months that are not on the harmonized scale are never coloured as zero:
unavailable months are dark grey, partial months a lighter neutral grey.
Estimated (MODIS-based) months carry a small dot.
"""
from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from config.settings import COLORS, FIRE_SCALE
from services.analytics_service import calendar_matrix
from utils.dates import MONTH_NAMES

CELL_PX = 26        # square cell size
GAP_PX = 4          # gap between cells
LEFT_PX = 46        # room for year labels
TOP_PX = 26         # room for month labels


def _nice(v: float) -> float:
    """Round a threshold to 2 significant figures for readable legends."""
    if v <= 0:
        return 0.0
    mag = 10 ** (np.floor(np.log10(v)) - 1)
    return float(np.round(v / mag) * mag)


def fire_bins(values: pd.Series | np.ndarray, n_colors: int = len(FIRE_SCALE)
              ) -> tuple[list[float], np.ndarray]:
    """Quantile thresholds and per-value bin index (NaN stays NaN).

    Returns ``(thresholds, bins)``: ``thresholds`` are the upper edges of all
    but the last bin (strictly increasing, rounded); ``bins`` are integers in
    ``0 .. len(thresholds)``. Zero always falls in the lowest bin.
    """
    v = np.asarray(values, dtype=float)
    finite = v[np.isfinite(v)]
    if finite.size == 0:
        return [], np.full(v.shape, np.nan)
    qs = np.quantile(finite, np.linspace(0, 1, n_colors + 1)[1:-1])
    thresholds = sorted({_nice(q) for q in qs if q > 0})
    bins = np.where(np.isfinite(v), np.searchsorted(thresholds, v, side="left"), np.nan)
    return thresholds, bins


def bin_labels(thresholds: list[float]) -> list[str]:
    edges = [0.0, *thresholds]
    labels = [f"{edges[i]:,.0f}–{edges[i + 1]:,.0f}" for i in range(len(thresholds))]
    labels.append(f"> {thresholds[-1]:,.0f}" if thresholds else "all")
    return labels


def bin_colors(n_bins: int) -> list[str]:
    """Spread n bins over the fire scale (always ending at the deepest red)."""
    if n_bins >= len(FIRE_SCALE):
        return list(FIRE_SCALE)
    idx = np.round(np.linspace(0, len(FIRE_SCALE) - 1, n_bins)).astype(int)
    return [FIRE_SCALE[i] for i in idx]


def completeness(row: pd.Series) -> str:
    if row["source_flag"] in ("estimated_from_modis", "viirs_reference"):
        return "Complete month"
    if row["is_partial_month"]:
        return "Partial month — not on the harmonized scale"
    return "Not available on the harmonized scale"


def _fmt(v, digits=0) -> str:
    return "—" if pd.isna(v) else f"{float(v):,.{digits}f}"


def _hover(frame: pd.DataFrame) -> pd.Series:
    def one(r) -> str:
        kind = ("Estimated (MODIS × factor)" if r["is_estimated"] else
                "Observed (VIIRS reference)" if r["source_flag"] == "viirs_reference" else
                "Not harmonized")
        return (f"<b>{r['region']} · {MONTH_NAMES[int(r['month']) - 1]} {int(r['year'])}</b><br>"
                f"Harmonized activity: <b>{_fmt(r['harmonized_activity'])}</b><br>"
                f"MODIS: {_fmt(r['modis_combined_count'])} "
                f"(Terra {_fmt(r['modis_terra_count'])} · Aqua {_fmt(r['modis_aqua_count'])})<br>"
                f"VIIRS S-NPP: {_fmt(r['viirs_snpp_count'])}<br>"
                f"Calibration factor: {_fmt(r['calibration_factor'], 2)}<br>"
                f"{kind}<br>{completeness(r)}")
    return frame.apply(one, axis=1)


def _discrete_scale(colors: list[str]) -> list[list]:
    n = len(colors)
    if n == 1:
        return [[0, colors[0]], [1, colors[0]]]
    scale = []
    for i, c in enumerate(colors):
        scale += [[i / n, c], [(i + 1) / n, c]]
    return scale


def calendar_heatmap(frame: pd.DataFrame) -> tuple[go.Figure, list[tuple[str, str]]]:
    """Figure plus legend entries [(colour, label), ...] for ``calendar_legend_html``."""
    f = frame.copy()
    f["hover"] = _hover(f)
    thresholds, bins = fire_bins(f["harmonized_activity"])
    f["bin"] = bins
    colors = bin_colors(len(thresholds) + 1)

    status = calendar_matrix(f, "source_flag")
    years = [str(y) for y in status.index]
    months = list(MONTH_NAMES)
    present = status.notna().to_numpy()
    values = calendar_matrix(f, "bin").to_numpy(dtype=float)
    partial = calendar_matrix(f, "is_partial_month").fillna(False).astype(bool).to_numpy()
    estimated = calendar_matrix(f, "is_estimated").fillna(False).astype(bool).to_numpy()
    unavailable = present & np.isnan(values) & ~partial
    partial_cells = present & np.isnan(values) & partial

    fig = go.Figure()
    common = {"x": months, "y": years, "xgap": GAP_PX, "ygap": GAP_PX, "showscale": False,
              "hoverinfo": "skip"}
    fig.add_trace(go.Heatmap(z=np.where(unavailable, 1.0, np.nan),
                             colorscale=[[0, COLORS["missing"]], [1, COLORS["missing"]]], **common))
    fig.add_trace(go.Heatmap(z=np.where(partial_cells, 1.0, np.nan),
                             colorscale=[[0, COLORS["partial"]], [1, COLORS["partial"]]], **common))
    fig.add_trace(go.Heatmap(z=values, zmin=-0.5, zmax=len(colors) - 0.5,
                             colorscale=_discrete_scale(colors), **common))

    def cells(mask):
        yy, mm = np.where(mask)
        return [months[i] for i in mm], [years[i] for i in yy]

    ex, ey = cells(estimated)
    fig.add_trace(go.Scatter(x=ex, y=ey, mode="markers", hoverinfo="skip", showlegend=False,
                             marker={"symbol": "circle", "size": 4, "color": "rgba(255,255,255,0.9)",
                                     "line": {"width": 1, "color": "rgba(0,0,0,0.55)"}}))
    # Transparent click/hover layer: heatmaps emit no selection events in Streamlit.
    hover = calendar_matrix(f, "hover").to_numpy()
    cx, cy = cells(present)
    hy, hm = np.where(present)
    fig.add_trace(go.Scatter(
        x=cx, y=cy, mode="markers", showlegend=False, name="cells",
        marker={"symbol": "square", "size": CELL_PX, "color": "rgba(0,0,0,0)"},
        selected={"marker": {"opacity": 1}}, unselected={"marker": {"opacity": 1}},
        text=[hover[a, b] for a, b in zip(hy, hm)], hovertemplate="%{text}<extra></extra>"))

    step = CELL_PX + GAP_PX
    fig.update_layout(
        width=LEFT_PX + 12 * step + 10, height=TOP_PX + len(years) * step + 10,
        margin={"l": LEFT_PX, "r": 10, "t": TOP_PX, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"color": COLORS["text_muted"], "size": 11,
              "family": "Inter, system-ui, -apple-system, Segoe UI, sans-serif"},
        # Keep the default dragmode: in "pan" mode Plotly does not select on click.
        # Axes are fixedrange, so users still cannot zoom.
        hovermode="closest", clickmode="event+select", showlegend=False,
        hoverlabel={"bgcolor": COLORS["surface"], "bordercolor": COLORS["border"],
                    "font": {"color": COLORS["text"]}},
    )
    # Pin ranges to the grid so marker sizes never add padding around the cells.
    fig.update_xaxes(side="top", type="category", showgrid=False, zeroline=False,
                     tickfont={"size": 10}, fixedrange=True, range=[-0.5, 11.5])
    fig.update_yaxes(type="category", showgrid=False, zeroline=False,
                     tickfont={"size": 10}, fixedrange=True, range=[len(years) - 0.5, -0.5])
    return fig, list(zip(colors, bin_labels(thresholds)))


def calendar_legend_html(entries: list[tuple[str, str]]) -> str:
    """Compact 'Less … More' legend with bin ranges, plus status swatches.

    A grid keeps 'Less', the colour squares and 'More' on one row at any
    column width; range labels sit on a second row under their squares.
    """
    n = len(entries)
    muted = "font-size:11px;color:#9AA3B2"
    squares = "".join(
        f'<i title="{escape(label)} detections" style="justify-self:center;width:16px;height:16px;'
        f'border-radius:3px;background:{c}"></i>' for c, label in entries)
    labels = "".join(
        f'<span style="justify-self:center;font-size:9px;color:#9AA3B2;white-space:nowrap">'
        f'{escape(label)}</span>' for _, label in entries)
    grid = (f'<div style="display:grid;grid-template-columns:auto repeat({n}, minmax(0, 1fr)) auto;'
            f'align-items:center;column-gap:4px;row-gap:3px;max-width:400px;margin-top:4px">'
            f'<span style="{muted}">Less</span>{squares}<span style="{muted}">More</span>'
            f'<span></span>{labels}<span></span></div>')
    status = (f'<span><i class="sq" style="background:{COLORS["missing"]}"></i>Not available</span>'
              f'<span><i class="sq" style="background:{COLORS["partial"]}"></i>Partial month</span>'
              '<span><i style="background:#fff;width:6px;height:6px;border:1px solid #000;'
              'vertical-align:1px"></i>Estimated from MODIS</span>')
    return f'{grid}<div class="ig-legend">{status}</div>'
