"""Shared Plotly styling for the dark IGNIS theme.

Sensor colours follow the entity everywhere: MODIS orange, VIIRS amber.
MODIS-derived estimates are additionally dashed so identity never relies on
colour alone.
"""
from __future__ import annotations

import plotly.graph_objects as go

from config.settings import COLORS

GRID = "#232833"
AXIS = "#3A404D"

SERIES_STYLE = {
    "terra": {"color": COLORS["terra"], "name": "MODIS Terra"},
    "aqua": {"color": COLORS["aqua"], "name": "MODIS Aqua"},
    "modis": {"color": COLORS["modis"], "name": "MODIS combined (Terra + Aqua)"},
    "viirs": {"color": COLORS["viirs"], "name": "VIIRS Suomi-NPP"},
    "estimate": {"color": COLORS["modis"], "name": "Estimated (MODIS × factor)", "dash": "dash"},
    "observed": {"color": COLORS["viirs"], "name": "Observed (VIIRS reference)", "dash": "solid"},
}
DIVERGING = {"above": "#FF6B1A", "near": "#6B7280", "below": "#4C8DD6"}
BAND_FILL = "rgba(255,107,26,0.35)"


def style_figure(fig: go.Figure, title: str | None = None, height: int = 380,
                 y_title: str | None = None, x_title: str | None = None,
                 legend: bool = True) -> go.Figure:
    """Apply the IGNIS dark layout with recessive grid and axes."""
    fig.update_layout(
        title={"text": title, "font": {"size": 15, "color": COLORS["text"]}, "x": 0} if title else None,
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": COLORS["text_muted"], "size": 12},
        margin={"l": 10, "r": 10, "t": (40 if title else 8) + (34 if legend else 0), "b": 10},
        hovermode="x unified",
        hoverlabel={"bgcolor": COLORS["surface"], "bordercolor": COLORS["border"],
                    "font": {"color": COLORS["text"]}},
        showlegend=legend,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0,
                "bgcolor": "rgba(0,0,0,0)", "font": {"color": COLORS["text_muted"]}},
    )
    fig.update_xaxes(showgrid=False, linecolor=AXIS, tickcolor=AXIS, zeroline=False,
                     title_text=x_title)
    fig.update_yaxes(gridcolor=GRID, gridwidth=1, linecolor=AXIS, zeroline=False,
                     title_text=y_title, rangemode="tozero")
    return fig


def line(x, y, key: str, name: str | None = None, hovertemplate: str | None = None,
         customdata=None, connectgaps: bool = False, **kw) -> go.Scatter:
    """A 2 px line in the series' identity colour."""
    s = SERIES_STYLE[key]
    kw.setdefault("mode", "lines")
    return go.Scatter(x=x, y=y, name=name or s["name"],
                      line={"color": s["color"], "width": 2, "dash": s.get("dash", "solid")},
                      connectgaps=connectgaps, hovertemplate=hovertemplate,
                      customdata=customdata, **kw)


PLOTLY_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}
