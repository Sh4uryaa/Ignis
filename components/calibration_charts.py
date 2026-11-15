"""Calibration-factor, ratio, validation and diagnostic charts (Plotly)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from config.settings import COLORS
from utils.charts import line, style_figure
from utils.dates import MONTH_NAMES

COMPARISON_LABELS = {"raw_modis": "Raw MODIS", "calibrated_seasonal": "Seasonal calibration",
                     "constant_factor": "Single constant factor"}


def factor_chart(f: pd.DataFrame, region: str, height: int = 340) -> go.Figure:
    """Chart 4 — 12 monthly factors with bootstrap interval and pair counts."""
    f = f.sort_values("calendar_month")
    # Valid year-pair counts sit under each month name (readable, not inside bars).
    x = [f"{MONTH_NAMES[m - 1]}<br><span style='font-size:10px'>n={n}</span>"
         for m, n in zip(f["calendar_month"], f["valid_training_pairs"])]
    err_hi = f["factor_upper"] - f["calibration_factor"]
    err_lo = f["calibration_factor"] - f["factor_lower"]
    fig = go.Figure(go.Bar(
        x=x, y=f["calibration_factor"], marker={"color": COLORS["harmonized"], "cornerradius": 4},
        error_y={"type": "data", "symmetric": False, "array": err_hi, "arrayminus": err_lo,
                 "color": COLORS["text_muted"], "thickness": 1.2, "width": 4},
        customdata=np.stack([f["factor_lower"], f["factor_upper"], f["valid_training_pairs"],
                             f["validation_status"]], axis=1),
        hovertemplate=("Factor %{y:.2f}<br>95% bootstrap: %{customdata[0]:.2f}–%{customdata[1]:.2f}"
                       "<br>Valid year pairs: %{customdata[2]}<br>Status: %{customdata[3]}<extra></extra>"),
        name="Calibration factor"))
    fig = style_figure(fig, f"{region} — monthly calibration factors (VIIRS ÷ MODIS)", height,
                       "Factor r_m", legend=False)
    fig.update_layout(hovermode="closest", bargap=0.35)
    return fig


def ratio_strip(pairs: pd.DataFrame, factors: pd.DataFrame, region: str, height: int = 320) -> go.Figure:
    """Distribution of annual training ratios per calendar month, with the median."""
    p = pairs[(pairs["region"] == region) & pairs["is_valid_pair"]]
    fig = go.Figure(go.Scatter(
        x=[MONTH_NAMES[m - 1] for m in p["month"]], y=p["ratio"], mode="markers",
        marker={"color": COLORS["text_muted"], "size": 8, "opacity": 0.8,
                "line": {"width": 1, "color": COLORS["background"]}},
        customdata=np.stack([p["year"], p["modis_combined_count"], p["viirs_snpp_count"]], axis=1),
        hovertemplate=("%{customdata[0]}: ratio %{y:.2f}<br>MODIS %{customdata[1]:,} · "
                       "VIIRS %{customdata[2]:,}<extra></extra>"),
        name="Training year ratio"))
    f = factors[factors["region"] == region].sort_values("calendar_month")
    fig.add_trace(go.Scatter(x=[MONTH_NAMES[m - 1] for m in f["calendar_month"]],
                             y=f["calibration_factor"], mode="markers",
                             marker={"symbol": "line-ew", "size": 22,
                                     "line": {"width": 3, "color": COLORS["harmonized"]}},
                             name="Median (factor)", hovertemplate="Median %{y:.2f}<extra></extra>"))
    fig = style_figure(fig, "Year-by-year VIIRS/MODIS ratios in training", height, "Ratio")
    fig.update_layout(hovermode="closest")
    return fig


def validation_wape_chart(metrics: pd.DataFrame, title: str, height: int = 300) -> go.Figure:
    """WAPE by comparison (one measure, one axis)."""
    m = metrics.copy()
    m["label"] = m["comparison"].map(COMPARISON_LABELS)
    colors = {"raw_modis": COLORS["modis"], "calibrated_seasonal": COLORS["calibrated"],
              "constant_factor": COLORS["text_muted"]}
    fig = go.Figure(go.Bar(
        x=m["label"], y=m["wape_pct"], marker={"color": [colors[c] for c in m["comparison"]],
                                               "cornerradius": 4},
        text=[f"{v:.1f}%" for v in m["wape_pct"]], textposition="outside",
        textfont={"color": COLORS["text"]},
        customdata=np.stack([m["mae"], m["rmse"], m["relative_bias_pct"], m["n_months"]], axis=1),
        hovertemplate=("WAPE %{y:.1f}%<br>MAE %{customdata[0]:,.0f} · RMSE %{customdata[1]:,.0f}"
                       "<br>Bias %{customdata[2]:+.1f}% · n=%{customdata[3]}<extra></extra>")))
    fig = style_figure(fig, title, height, "WAPE (%) — lower is better", legend=False)
    fig.update_layout(hovermode="closest", bargap=0.45)
    fig.update_yaxes(range=[0, max(100, float(m["wape_pct"].max()) * 1.15)])
    return fig


def validation_timeseries(v: pd.DataFrame, height: int = 360) -> go.Figure:
    """Observed VIIRS vs raw and calibrated MODIS in the held-out months."""
    fig = go.Figure()
    fig.add_trace(line(v["date"], v["actual_viirs_count"], "viirs", name="Observed VIIRS",
                       hovertemplate="%{y:,.0f}", mode="lines+markers", marker={"size": 6}))
    fig.add_trace(line(v["date"], v["predicted_viirs_equivalent"], "calibrated",
                       name="Calibrated MODIS (prediction)", hovertemplate="%{y:,.0f}"))
    fig.add_trace(go.Scatter(x=v["date"], y=v["modis_combined_count"], mode="lines",
                             line={"color": COLORS["modis"], "width": 1.5, "dash": "dot"},
                             name="Raw MODIS", hovertemplate="%{y:,.0f}"))
    return style_figure(fig, "Held-out months: observed vs predicted", height, "Detections per month")


def overpass_chart(o: pd.DataFrame, height: int = 340) -> go.Figure:
    """Median daytime detection time (IST) by satellite and year."""
    keys = {"Terra": "terra", "Aqua": "aqua", "Suomi-NPP": "viirs"}
    fig = go.Figure()
    for sat, key in keys.items():
        s = o[o["satellite"] == sat]
        if s.empty:
            continue
        fig.add_trace(line(s["year"], s["median_hour_ist"], key, name=sat,
                           mode="lines+markers", marker={"size": 6},
                           customdata=s[["median_time_ist", "shift_vs_early_years_min"]].to_numpy(),
                           hovertemplate="%{customdata[0]} IST (%{customdata[1]:+d} min)"))
    fig = style_figure(fig, "Median daytime detection time by year (IST)", height, "Local time (IST)")
    ticks = np.arange(9, 17.01, 1)
    fig.update_yaxes(tickvals=ticks, ticktext=[f"{int(t):02d}:00" for t in ticks],
                     rangemode="normal", range=[9, 16.5])
    return fig


def yearly_error_chart(y: pd.DataFrame, region: str, height: int = 320) -> go.Figure:
    """Calibrated MODIS vs VIIRS WAPE per year: in-sample (muted) vs out-of-sample."""
    s = y[y["region"] == region].sort_values("year")
    held_out = s["comparison_period"] == "validation_out_of_sample"
    colors = np.where(held_out, COLORS["calibrated"], "rgba(167,139,250,0.38)")
    fig = go.Figure(go.Bar(
        x=s["year"].astype(str), y=s["wape_pct"], marker={"color": colors, "cornerradius": 4},
        customdata=np.stack([np.where(held_out, "out-of-sample", "in-sample"), s["n_months"],
                             s["relative_bias_pct"], s["mae"]], axis=1),
        hovertemplate=("%{x}: WAPE %{y:.1f}% (%{customdata[0]}, %{customdata[1]} months)"
                       "<br>Bias %{customdata[2]:+.1f}% · MAE %{customdata[3]:,.0f}<extra></extra>")))
    fig = style_figure(fig, f"{region} — calibrated MODIS error vs VIIRS, by year", height,
                       "WAPE (%) — lower is better", legend=False)
    fig.update_layout(hovermode="closest", bargap=0.3)
    return fig
