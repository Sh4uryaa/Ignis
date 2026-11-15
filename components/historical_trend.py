"""Month-by-month (January–December) line charts for one selected year.

Used on the Overview (MODIS, VIIRS, harmonized) and on Harmonization &
Comparison (adds Terra, Aqua and calibrated MODIS). Data comes from
``analytics_service.year_monthly_activity`` and is plotted unchanged.

From the VIIRS reference period the harmonized record equals VIIRS, and
before it equals calibrated MODIS, so lines can coincide; the harmonized
line is always drawn last, dashed, with its own markers, and is never
offset. Months a sensor did not observe are gaps (never zero). Partial
months keep their real count and get a hollow marker.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from config.settings import COLORS
from utils.charts import style_figure

MONTHS = [pd.Timestamp(2000, m, 1).strftime("%B") for m in range(1, 13)]

# Drawing order follows the order of keys passed in; keep "harmonized" last.
SERIES = {
    "modis": {"name": "MODIS (Terra + Aqua)", "color": COLORS["modis"], "width": 2,
              "dash": "solid", "symbol": "circle", "size": 6, "kind": "observed"},
    "terra": {"name": "MODIS Terra", "color": COLORS["terra"], "width": 1.6,
              "dash": "solid", "symbol": "circle", "size": 5, "kind": "observed"},
    "aqua": {"name": "MODIS Aqua", "color": COLORS["aqua"], "width": 1.6,
             "dash": "solid", "symbol": "circle", "size": 5, "kind": "observed"},
    "viirs": {"name": "VIIRS Suomi-NPP", "color": COLORS["viirs"], "width": 2.4,
              "dash": "solid", "symbol": "circle", "size": 7, "kind": "observed"},
    "calibrated": {"name": "Calibrated MODIS (MODIS × factor)", "color": COLORS["calibrated"],
                   "width": 2, "dash": "solid", "symbol": "square", "size": 6,
                   "kind": "calibrated estimate"},
    "harmonized": {"name": "Harmonized record", "color": COLORS["harmonized"], "width": 2,
                   "dash": "dash", "symbol": "diamond", "size": 8, "kind": None},
}

NOTE_LABELS = {
    "modis": "Combined MODIS (Terra + Aqua)", "terra": "MODIS Terra", "aqua": "MODIS Aqua",
    "viirs": "VIIRS Suomi-NPP", "calibrated": "Calibrated MODIS",
    "harmonized": "The harmonized record",
}


def _symbols(base: str, status: pd.Series) -> list[str]:
    """Hollow marker for partial months so they read differently at a glance."""
    return [f"{base}-open" if s == "partial month" else base for s in status]


def _hover(key: str, f: pd.DataFrame) -> tuple[np.ndarray, str]:
    s = SERIES[key]
    if key == "harmonized":
        custom = f[["harmonized_status", "harmonized_completeness"]].to_numpy()
        return custom, ("Harmonized: <b>%{y:,.0f}</b> · %{customdata[0]} · %{customdata[1]}"
                        "<extra></extra>")
    custom = f[[f"{key}_status"]].to_numpy()
    return custom, (f"{s['name']}: <b>%{{y:,.0f}}</b> · {s['kind']} · %{{customdata[0]}}"
                    "<extra></extra>")


def monthly_series_chart(year_frame: pd.DataFrame, region_label: str, year: int,
                         keys: list[str], height: int = 400) -> go.Figure:
    """Jan–Dec lines for the given series keys (see ``SERIES``) in one region-year."""
    f = year_frame
    fig = go.Figure()
    # Invisible first trace: puts "Region · Year" at the top of the unified tooltip.
    fig.add_trace(go.Scatter(
        x=MONTHS, y=np.zeros(12), mode="markers", marker={"opacity": 0, "size": 1},
        showlegend=False, name="", hovertemplate=f"<b>{region_label} · {year}</b><extra></extra>"))
    for key in keys:
        s = SERIES[key]
        custom, template = _hover(key, f)
        statuses = f[f"{key}_status"] if key != "harmonized" else pd.Series([""] * 12)
        fig.add_trace(go.Scatter(
            x=MONTHS, y=f[key], mode="lines+markers", name=s["name"], connectgaps=False,
            line={"color": s["color"], "width": s["width"], "dash": s["dash"]},
            marker={"color": s["color"], "size": s["size"],
                    "symbol": _symbols(s["symbol"], statuses),
                    "line": {"width": 1.2, "color": s["color"]}},
            customdata=custom, hovertemplate=template))
    fig = style_figure(fig, None, height, "Hotspot detections per month")
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=MONTHS,
                     range=[-0.4, 11.4], showgrid=False, tickfont={"size": 11})
    fig.update_layout(hovermode="x unified", legend_traceorder="normal")
    return fig


def monthly_activity_chart(year_frame: pd.DataFrame, region_label: str, year: int,
                           height: int = 400) -> go.Figure:
    """Overview chart: MODIS, VIIRS and the harmonized record."""
    return monthly_series_chart(year_frame, region_label, year,
                                ["modis", "viirs", "harmonized"], height)


def availability_notes(year_frame: pd.DataFrame, year: int,
                       keys: tuple[str, ...] = ("modis", "viirs", "harmonized")) -> list[str]:
    """Plain-language notes about gaps and partial months in the selected year."""
    f = year_frame
    notes = []
    for key in keys:
        missing = f.loc[f[key].isna(), "month_name"].tolist()
        if len(missing) == 12:
            notes.append(f"{NOTE_LABELS[key]} has no values in {year} — shown as a gap, not zero.")
        elif missing:
            notes.append(f"{NOTE_LABELS[key]} is unavailable for {_span(missing)} {year} "
                         "(gap, not zero).")
    for key in keys:
        if key in ("harmonized", "calibrated"):
            continue
        partial = f.loc[f[f"{key}_status"] == "partial month", "month_name"].tolist()
        if partial:
            notes.append(f"{NOTE_LABELS[key]}: {', '.join(partial)} {year} is a partial month "
                         "(hollow marker).")
    return notes


def _span(months: list[str]) -> str:
    return months[0] if len(months) == 1 else f"{months[0]}–{months[-1]}" \
        if MONTHS.index(months[-1]) - MONTHS.index(months[0]) == len(months) - 1 \
        else ", ".join(months)
