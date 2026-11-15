"""Page 4 — Burning Activity Calendar (signature visualization)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from components import filters
from components.activity_heatmap import calendar_heatmap
from components.data_export import download_csv
from components.metric_cards import metric_row, note
from components.navigation import data_unavailable, go_to, page_header
from pages.historical_map import MAP_FOCUS_KEY
from services import analytics_service as A
from services.data_service import DataUnavailable, load_table
from services.region_service import selected_region
from utils.charts import PLOTLY_CONFIG
from utils.dates import MONTH_NAMES
from utils.formatters import fmt_int, fmt_num, month_label

SELECTED_KEY = "calendar_selected"

STATUS_TABLE = [
    ("Nov 2000 – Jun 2002", "Terra-only — raw, not on the harmonized scale"),
    ("Jul 2002", "Partial platform coverage (Aqua starts 18 Jul)"),
    ("Aug 2002 – Dec 2011", "Estimated VIIRS-equivalent activity (MODIS × factor)"),
    ("Jan 2012", "Partial VIIRS reference month (VIIRS starts 20 Jan)"),
    ("Feb 2012 – Jul 2026", "Direct VIIRS S-NPP reference observations"),
    ("Aug 2026", "MODIS-only partial period after the VIIRS archive ends"),
]


def render() -> None:
    region = selected_region()
    page_header("Burning Activity Calendar",
                "Harmonized monthly hotspot activity on the VIIRS S-NPP reference scale.", region)
    try:
        h = load_table("harmonized_monthly")
        unc = load_table("uncertainty_intervals")
    except DataUnavailable as exc:
        data_unavailable(exc)
        return

    frame = A.calendar_frame(A.for_region(h, region), unc)
    c1, c2 = st.columns([3, 1])
    with c2:
        log_scale = st.toggle("Log colour scale", value=True,
                              help="Burning-season peaks are ~1000× quiet months; a log scale keeps "
                                   "both readable. Hover shows the actual values.")
    with c1:
        st.caption("Grey cells are months that exist but are not on the harmonized scale "
                   "(Terra-only, partial or unavailable) — they are never shown as zero. "
                   "○ marks months estimated from MODIS. Click a cell to inspect it.")

    event = st.plotly_chart(calendar_heatmap(frame, log_scale), width="stretch",
                            config=PLOTLY_CONFIG, on_select="rerun", selection_mode="points",
                            key=f"calendar_{region}")
    _capture_click(event)

    st.markdown("#### Month detail")
    years = sorted(int(y) for y in frame["year"].unique())
    default = st.session_state.get(SELECTED_KEY) or _default_month(frame)
    year, month = filters.month_picker(years, key="cal_pick", default=default)
    _month_detail(frame, region, year, month)

    with st.expander("Calendar statuses"):
        st.dataframe(pd.DataFrame(STATUS_TABLE, columns=["Period", "Status"]), hide_index=True,
                     width="stretch")
        st.caption("Periods are derived from the data's own coverage; this table summarises them.")
    download_csv(frame.drop(columns=["status_long"]), region, "harmonized",
                 "Harmonized calendar data (CSV)")


def _default_month(frame: pd.DataFrame) -> tuple[int, int]:
    obs = frame[frame["harmonized_activity"].notna()].sort_values(["year", "month"])
    nov = obs[obs["month"] == 11]
    r = (nov if not nov.empty else obs).iloc[-1]
    return int(r["year"]), int(r["month"])


def _capture_click(event) -> None:
    """Store a clicked heatmap cell as the selected month and sync the pickers."""
    try:
        points = event.selection.points  # type: ignore[union-attr]
    except AttributeError:
        return
    if not points:
        return
    p = points[0]
    x, y = p.get("x"), p.get("y")
    if x in MONTH_NAMES and y is not None:
        sel = (int(y), MONTH_NAMES.index(x) + 1)
        if st.session_state.get(SELECTED_KEY) != sel:
            st.session_state[SELECTED_KEY] = sel
            st.session_state["cal_pick_year"], st.session_state["cal_pick_month"] = sel


def _month_detail(frame: pd.DataFrame, region: str, year: int, month: int) -> None:
    r = A.month_record(frame, year, month)
    if r is None:
        st.info(f"No record for {month_label(year, month)} in {region}.")
        return
    interval = (f"{fmt_int(r['lower_bound'])} – {fmt_int(r['upper_bound'])}"
                if pd.notna(r.get("lower_bound")) else "Not applicable")
    metric_row([
        {"label": f"{month_label(year, month)} · harmonized", "accent": True,
         "value": fmt_int(r["harmonized_activity"]), "sub": r["status"]},
        {"label": "MODIS combined", "value": fmt_int(r["modis_combined_count"]),
         "sub": f"Terra {fmt_int(r['modis_terra_count'])} · Aqua {fmt_int(r['modis_aqua_count'])}"},
        {"label": "VIIRS S-NPP", "value": fmt_int(r["viirs_snpp_count"]), "sub": "Raw count"},
        {"label": "Calibration factor", "value": fmt_num(r["calibration_factor"]),
         "sub": f"95% calibration-factor interval: {interval}"},
    ])
    st.write("")
    note(r["status_long"] + (". Raw counts from different sensors are not comparable with each "
                             "other; only the harmonized value is on a common scale."))
    if st.button(f"View {month_label(year, month)} on the map", icon=":material/map:"):
        st.session_state[MAP_FOCUS_KEY] = (year, month)
        go_to("map")
