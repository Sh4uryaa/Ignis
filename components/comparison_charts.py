"""Sensor comparison and harmonized-series charts (Plotly).

Inputs are prepared frames from the services layer; nothing is computed
here beyond plotting.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from config.settings import COLORS
from processing.harmonize import FLAG_ESTIMATED, FLAG_VIIRS
from utils.charts import BAND_FILL, line, style_figure


def _complete(series: pd.Series, coverage: pd.Series) -> pd.Series:
    """Hide counts from months a sensor did not observe completely."""
    return series.astype(float).where(coverage == "complete")


def raw_sensor_chart(t: pd.DataFrame, height: int = 380) -> go.Figure:
    """Chart 1 — raw combined MODIS vs VIIRS monthly counts (complete months)."""
    fig = go.Figure()
    fig.add_trace(line(t["date"], _complete(t["modis_combined_count"], t["modis_combined_coverage"]),
                       "modis", hovertemplate="%{y:,.0f}"))
    fig.add_trace(line(t["date"], _complete(t["viirs_snpp_count"], t["viirs_snpp_coverage"]),
                       "viirs", hovertemplate="%{y:,.0f}"))
    both = t[(t["modis_combined_coverage"] == "complete") & (t["viirs_snpp_coverage"] == "complete")]
    if not both.empty:
        x0 = both["date"].min()
        fig.add_vline(x=x0, line={"color": COLORS["text_muted"], "width": 1, "dash": "dot"})
        fig.add_annotation(x=x0, y=1, yref="paper", text="Complete overlap begins",
                           showarrow=False, xanchor="left", yanchor="top",
                           font={"color": COLORS["text_muted"], "size": 11})
    return style_figure(fig, "Raw monthly detections by sensor", height, "Detections per month")


def harmonized_chart(h: pd.DataFrame, title: str = "Harmonized monthly activity",
                     height: int = 420, show_band: bool = True, show_flags: bool = True) -> go.Figure:
    """Chart 2 — estimates (dashed, with calibration band) then VIIRS reference (solid)."""
    est = h["source_flag"] == FLAG_ESTIMATED
    obs = h["source_flag"] == FLAG_VIIRS
    fig = go.Figure()
    if show_band and "lower_bound" in h:
        b = h[est & h["lower_bound"].notna()]
        fig.add_trace(go.Scatter(x=b["date"], y=b["upper_bound"], mode="lines", line={"width": 0},
                                 hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(x=b["date"], y=b["lower_bound"], mode="lines", line={"width": 0},
                                 fill="tonexty", fillcolor=BAND_FILL, hoverinfo="skip",
                                 name="95% bootstrap calibration-factor interval"))
    custom = np.stack([h["lower_bound"] if "lower_bound" in h else np.full(len(h), np.nan),
                       h["upper_bound"] if "upper_bound" in h else np.full(len(h), np.nan)], axis=1)
    fig.add_trace(line(h["date"], h["harmonized_activity"].where(est), "estimate",
                       customdata=custom,
                       hovertemplate="%{y:,.0f} (interval %{customdata[0]:,.0f}–%{customdata[1]:,.0f})"))
    fig.add_trace(line(h["date"], h["harmonized_activity"].where(obs), "observed",
                       hovertemplate="%{y:,.0f}"))
    if show_flags:
        flagged = h[~(est | obs)]
        if not flagged.empty:
            fig.add_trace(go.Scatter(
                x=flagged["date"], y=np.zeros(len(flagged)), mode="markers",
                marker={"symbol": "x-thin", "size": 8, "line": {"width": 1.5, "color": COLORS["text_muted"]}},
                name="Not harmonized (Terra-only / partial)",
                customdata=flagged[["status"]].to_numpy() if "status" in flagged else None,
                hovertemplate="%{customdata[0]}" if "status" in flagged else "Not harmonized"))
    if obs.any() and est.any():
        x0 = h.loc[obs, "date"].min()
        fig.add_vline(x=x0, line={"color": COLORS["text_muted"], "width": 1, "dash": "dot"})
        fig.add_annotation(x=x0, y=1, yref="paper", text="VIIRS reference begins",
                           showarrow=False, xanchor="left", yanchor="top",
                           font={"color": COLORS["text_muted"], "size": 11})
    return style_figure(fig, title, height, "VIIRS-equivalent detections / month")


def platform_chart(t: pd.DataFrame, height: int = 360) -> go.Figure:
    """Chart 3 — Terra and Aqua stacked; stack height is the combined MODIS count."""
    fig = go.Figure()
    for key, col in (("terra", "modis_terra_count"), ("aqua", "modis_aqua_count")):
        c = COLORS[key]
        fig.add_trace(go.Scatter(x=t["date"], y=t[col].astype(float), mode="lines",
                                 stackgroup="modis", line={"width": 0.5, "color": c},
                                 fillcolor=c, name=f"MODIS {key.title()}",
                                 hovertemplate="%{y:,.0f}"))
    fig.add_trace(go.Scatter(x=t["date"], y=t["modis_combined_count"].astype(float), mode="lines",
                             line={"color": COLORS["text"], "width": 1, "dash": "dot"},
                             name="Combined (Terra + Aqua)", hovertemplate="%{y:,.0f}"))
    return style_figure(fig, "How the combined MODIS count is built", height, "Detections per month")


def four_series_chart(t: pd.DataFrame, cal: pd.DataFrame, h: pd.DataFrame,
                      periods: dict[str, tuple[str, str]], height: int = 500) -> go.Figure:
    """Raw MODIS, raw VIIRS, calibrated MODIS and the final harmonized record.

    ``t``: region totals with ``date``; ``cal``: calibrated MODIS series with
    ``date``; ``h``: harmonized rows (calendar_frame) with ``date``;
    ``periods``: {"training": (start, end), "validation": (start, end)} as
    "YYYY-MM". Values are plotted unchanged. The harmonized line equals the
    purple line before the VIIRS reference and the orange line after it, so
    it is drawn last and dashed rather than offset.
    """
    fig = go.Figure()
    shade = {"training": ("rgba(167,139,250,0.05)", "Training years · in-sample"),
             "validation": ("rgba(167,139,250,0.13)", "Held-out years · out-of-sample")}
    for name, (start, end) in periods.items():
        fill, label = shade[name]
        x0 = pd.Timestamp(start + "-01")
        x1 = pd.Timestamp(end + "-01") + pd.offsets.MonthEnd(0)
        fig.add_vrect(x0=x0, x1=x1, fillcolor=fill, line_width=0, layer="below")
        fig.add_annotation(x=x0, y=1, yref="paper", text=label, showarrow=False, xanchor="left",
                           yanchor="top", xshift=4, font={"color": COLORS["text_muted"], "size": 10})

    fig.add_trace(line(t["date"], _complete(t["modis_combined_count"], t["modis_combined_coverage"]),
                       "modis", name="Raw MODIS Terra + Aqua", hovertemplate="%{y:,.0f}",
                       line={"color": COLORS["modis"], "width": 1.3}))
    fig.add_trace(line(t["date"], _complete(t["viirs_snpp_count"], t["viirs_snpp_coverage"]),
                       "viirs", name="Actual VIIRS Suomi-NPP", hovertemplate="%{y:,.0f}",
                       line={"color": COLORS["viirs"], "width": 2.6}))
    from processing.harmonize import PERIOD_DESCRIPTIONS
    fig.add_trace(line(cal["date"], cal["calibrated_modis"], "calibrated",
                       name="Calibrated MODIS", customdata=cal["comparison_period"].map(PERIOD_DESCRIPTIONS).to_numpy(),
                       hovertemplate="%{y:,.0f} (%{customdata})",
                       line={"color": COLORS["calibrated"], "width": 1.8}))

    est = h["source_flag"] == FLAG_ESTIMATED
    obs = h["source_flag"] == FLAG_VIIRS
    b = h[est & h["lower_bound"].notna()] if "lower_bound" in h else h.iloc[0:0]
    fig.add_trace(go.Scatter(x=b["date"], y=b["upper_bound"], mode="lines", line={"width": 0},
                             hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=b["date"], y=b["lower_bound"], mode="lines", line={"width": 0},
                             fill="tonexty", fillcolor=BAND_FILL, hoverinfo="skip",
                             name="95% bootstrap calibration-factor interval"))
    kind = np.where(est, "estimate = calibrated MODIS", "= actual VIIRS")
    fig.add_trace(go.Scatter(
        x=h["date"], y=h["harmonized_activity"].where(est | obs), mode="lines",
        name="Final harmonized record", customdata=kind,
        line={"color": COLORS["harmonized"], "width": 1.4, "dash": "dash"},
        hovertemplate="%{y:,.0f} (%{customdata})"))
    fig = style_figure(fig, None, height, "Hotspot detections per month")
    fig.update_xaxes(type="date")
    # Plotly reverses legends that contain filled traces; keep series order 1-4.
    fig.update_layout(legend_traceorder="normal")
    return fig
