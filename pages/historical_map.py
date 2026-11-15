"""Page 2 — Historical Fire Map (PyDeck)."""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from components import filters
from components.fire_map import (
    HEX_TOOLTIP,
    POINT_TOOLTIP,
    SENSOR_RGBA,
    boundary_layers,
    build_deck,
    color_by_count,
    density_layer,
    legend_html,
    point_layer,
)
from components.metric_cards import metric_row, note
from components.navigation import data_unavailable, page_header
from config.settings import CONFIDENCE_POLICY_LABEL, MAP_MAX_POINTS, REGIONS
from services import analytics_service as A
from services.data_service import DataUnavailable, load_detections
from services.region_service import boundary_geojson, missing_boundaries, region_bounds, selected_region
from utils.formatters import fmt_int

# Set by the calendar page ("view this month on the map").
MAP_FOCUS_KEY = "map_focus_month"


def _default_window(hi: dt.date) -> tuple[dt.date, dt.date]:
    """Latest Oct–Nov burning season in the data."""
    year = hi.year if hi >= dt.date(hi.year, 11, 30) else hi.year - 1
    return dt.date(year, 10, 1), dt.date(year, 11, 30)


def render() -> None:
    region = selected_region()
    page_header("Historical Fire Map", "Hotspot detections inside the actual state boundary.",
                region, [CONFIDENCE_POLICY_LABEL])
    if missing_boundaries():
        st.error("State boundary files are missing: " + ", ".join(missing_boundaries()) +
                 ". Run `python -m scripts.prepare_boundaries`. A rectangle is never substituted.")
        return
    try:
        det = load_detections()
    except DataUnavailable as exc:
        data_unavailable(exc)
        return

    lo, hi = det["acq_date"].min().date(), det["acq_date"].max().date()
    focus = st.session_state.pop(MAP_FOCUS_KEY, None)
    if focus:  # coming from the calendar
        y, m = focus
        start = dt.date(y, m, 1)
        end = (pd.Timestamp(start) + pd.offsets.MonthEnd(0)).date()
        st.session_state["map_start"], st.session_state["map_end"] = start, min(end, hi)

    with st.container(border=True):
        c1, c2, c3 = st.columns([2.2, 1.4, 1.6])
        with c1:
            start, end = filters.date_window(lo, hi, _default_window(hi), key="map")
        with c2:
            sensor = filters.sensor_select("map_sensor")
        with c3:
            types = filters.detection_type_select(
                sorted(int(t) for t in det["detection_type"].dropna().unique()), "map_types")
        mode = st.segmented_control("Display", ["Auto", "Density (1 km grid)", "Individual points"],
                                    default="Auto", key="map_mode")
    if start > end:
        return

    sub = A.filter_detections(det, region, pd.Timestamp(start), pd.Timestamp(end), sensor, types)
    n = len(sub)
    density = (mode == "Density (1 km grid)") or (mode == "Auto" and n > MAP_MAX_POINTS)

    by_sensor = sub["sensor"].astype(str).value_counts()
    metric_row([
        {"label": "Detections in selection", "value": fmt_int(n), "accent": True,
         "sub": f"{start:%d %b %Y} – {end:%d %b %Y}"},
        {"label": "MODIS", "value": fmt_int(by_sensor.get("MODIS", 0)), "sub": "Terra + Aqua"},
        {"label": "VIIRS S-NPP", "value": fmt_int(by_sensor.get("VIIRS", 0)), "sub": "375 m"},
        {"label": "Sensor filter", "value": sensor.split(" (")[0], "sub": "Detection types: " +
         ("all" if types is None else ", ".join(map(str, types)))},
    ])
    if n and sensor == "All sensors":
        st.caption("MODIS and VIIRS are shown together for exploration only; their raw counts are "
                   "on different scales and are not added in any harmonized metric.")

    geo = {r: boundary_geojson(r) for r in REGIONS}
    layers = boundary_layers(geo, region)
    bins = None
    if n == 0:
        st.info("No detections match these filters. This is an empty selection, not evidence of "
                "zero fire activity if a sensor was not observing in this window.")
        tooltip = None
    elif density:
        cells = A.grid_cell_counts(sub)
        cells["color"], bins = color_by_count(cells["count"])
        layers.append(density_layer(cells))
        tooltip = HEX_TOOLTIP
    else:
        sample, k = A.deterministic_sample(sub, MAP_MAX_POINTS)
        layers.append(point_layer(A.map_records(sample, SENSOR_RGBA)))
        tooltip = POINT_TOOLTIP
        if k > 1:
            note(f"Showing <b>{fmt_int(len(sample))}</b> of <b>{fmt_int(n)}</b> detections "
                 f"(every {k}th in time order) for speed. All totals on this page use the full "
                 "record — sampling never changes reported counts.")

    st.pydeck_chart(build_deck(layers, region_bounds(region), tooltip), height=560)
    st.html(legend_html("VIIRS" != sensor[:5], "VIIRS" in sensor or sensor == "All sensors",
                        density and n > 0, bins))
    if density and n:
        st.caption(f"Density view: all {fmt_int(n)} detections aggregated to the common 1 km grid "
                   f"({fmt_int(len(cells))} cells). Cell counts are detections, not unique fires.")
