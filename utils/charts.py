"""Shared Plotly styling for the dark IGNIS theme.

Colours follow the entity everywhere: MODIS gold, VIIRS orange, harmonized
teal. Estimated harmonized values are additionally dashed (observed are
solid) so status never relies on colour alone.
"""
from __future__ import annotations

import plotly.graph_objects as go

from config.settings import COLORS

GRID = "#1E232C"
AXIS = "#333947"

SERIES_STYLE = {
    "terra": {"color": COLORS["terra"], "name": "MODIS Terra"},
    "aqua": {"color": COLORS["aqua"], "name": "MODIS Aqua"},
    "modis": {"color": COLORS["modis"], "name": "MODIS combined (Terra + Aqua)"},
    "viirs": {"color": COLORS["viirs"], "name": "VIIRS Suomi-NPP"},
    "calibrated": {"color": COLORS["calibrated"], "name": "Calibrated MODIS (MODIS × factor)"},
    "estimate": {"color": COLORS["harmonized"], "name": "Harmonized — estimated (MODIS × factor)",
                 "dash": "dash"},
    "observed": {"color": COLORS["harmonized"], "name": "Harmonized — observed (= VIIRS)",
                 "dash": "solid"},
}
# Restrained diverging colours for anomalies (warm above, cool below, grey near).
DIVERGING = {"above": "#E8703A", "near": "#5B6270", "below": "#6E93B8"}
BAND_FILL = "rgba(45,212,191,0.20)"


def style_figure(fig: go.Figure, title: str | None = None, height: int = 380,
                 y_title: str | None = None, x_title: str | None = None,
                 legend: bool = True) -> go.Figure:
    """Apply the IGNIS dark layout with recessive grid and axes.

    Title and legend are positioned in pixels from the top of the figure, so
    a legend that wraps onto two lines never collides with the title.
    """
    title_px = 34 if title else 0
    legend_px = 52 if legend else 0          # room for up to two legend rows
    fig.update_layout(
        title={"text": title, "font": {"size": 15, "color": COLORS["text"]}, "x": 0,
               "xanchor": "left", "y": 1 - 8 / height, "yref": "container",
               "yanchor": "top"} if title else None,
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": COLORS["text_muted"], "size": 12,
              "family": "Inter, system-ui, -apple-system, Segoe UI, sans-serif"},
        margin={"l": 10, "r": 10, "t": 10 + title_px + legend_px, "b": 10},
        hovermode="x unified",
        hoverlabel={"bgcolor": COLORS["surface"], "bordercolor": COLORS["border"],
                    "font": {"color": COLORS["text"]}},
        showlegend=legend,
        legend={"orientation": "h", "yref": "container", "y": 1 - (6 + title_px) / height,
                "yanchor": "top", "xanchor": "left", "x": 0,
                "bgcolor": "rgba(0,0,0,0)", "font": {"color": COLORS["text_muted"]}},
    )
    fig.update_xaxes(showgrid=False, linecolor=AXIS, tickcolor=AXIS, zeroline=False,
                     title_text=x_title)
    fig.update_yaxes(gridcolor=GRID, gridwidth=1, linecolor=AXIS, zeroline=False,
                     title_text=y_title, rangemode="tozero")
    return fig


def line(x, y, key: str, name: str | None = None, hovertemplate: str | None = None,
         customdata=None, connectgaps: bool = False, **kw) -> go.Scatter:
    """A 2 px line in the series' identity colour (``line=`` overrides width/dash)."""
    s = SERIES_STYLE[key]
    kw.setdefault("mode", "lines")
    style = {"color": s["color"], "width": 2, "dash": s.get("dash", "solid")}
    style.update(kw.pop("line", {}) or {})
    return go.Scatter(x=x, y=y, name=name or s["name"], line=style,
                      connectgaps=connectgaps, hovertemplate=hovertemplate,
                      customdata=customdata, **kw)


PLOTLY_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}
