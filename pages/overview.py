"""Page 1 — Overview: landing hero, then the selected region's summary."""
from __future__ import annotations

import streamlit as st

from components.hero import STATS_ANCHOR, render_hero
from components.historical_trend import availability_notes, monthly_activity_chart
from components.metric_cards import metric_row, note, section_title
from components.navigation import data_unavailable
from components.sensor_coverage import sensor_coverage_chart
from components.summary_charts import detection_type_chart, seasonal_chart
from config.regions import region_label
from services import analytics_service as A
from services.data_service import DataUnavailable, load_quality_report, load_table
from services.region_service import selected_region
from utils.charts import PLOTLY_CONFIG
from utils.formatters import fmt_int, fmt_pct, month_label


def render() -> None:
    region = selected_region()
<<<<<<< HEAD

=======
>>>>>>> 398ae2ebb76ff5f8e2778bebf4e4de063c8316c0
    try:
        totals = load_table("monthly_region_totals")
        h = load_table("harmonized_monthly")
        factors = load_table("calibration_factors")
        metrics = load_table("validation_metrics")
        types = load_table("detection_type_breakdown")
        report = load_quality_report()
    except DataUnavailable as exc:
        render_hero()
        data_unavailable(exc)
        return

    cov = A.coverage_timeline(report)
    all_detections = (totals[["modis_terra_count", "modis_aqua_count", "viirs_snpp_count"]]
                      .sum().sum())
<<<<<<< HEAD
    render_hero(
        meta=f"{fmt_int(all_detections)} satellite detections · "
             f"{cov['start'].min():%Y}–{cov['end'].max():%Y} · "
             f"{len(totals['region'].unique())} study regions",
    )
=======
    render_hero(meta=f"{fmt_int(all_detections)} satellite detections · "
                     f"{cov['start'].min():%Y}–{cov['end'].max():%Y} · "
                     f"{len(totals['region'].unique())} study regions")
>>>>>>> 398ae2ebb76ff5f8e2778bebf4e4de063c8316c0

    hr = A.with_date(A.for_region(h, region))
    rec = A.harmonized_record_summary(hr)
    sens = A.sensor_totals(totals, region)
    latest = A.latest_complete_common_month(totals, region)
    latest_row = A.month_record(hr, *latest) if latest else None

    section_title(f"{region_label(region)} at a glance",
                  "Change the study region from the selector at the top of the page.",
                  anchor=STATS_ANCHOR)
    span = (f"{month_label(*rec['first'])} – {month_label(*rec['last'])}"
            if rec["first"] else "—")
    metric_row([
        {"label": "Raw observation coverage",
         "value": f"{cov['start'].min():%Y} – {cov['end'].max():%Y}",
         "sub": "All sensors, including Terra-only years"},
        {"label": "MODIS detections", "value": fmt_int(sens["modis_combined"]),
         "sub": f"Terra {fmt_int(sens['terra'])} · Aqua {fmt_int(sens['aqua'])}"},
        {"label": "VIIRS S-NPP detections", "value": fmt_int(sens["viirs"]),
         "sub": "Raw — not comparable to MODIS"},
        {"label": "Harmonized record",
         "value": f"{rec['estimated_months'] + rec['observed_months']} months",
         "sub": f"{span} · {rec['estimated_months']} estimated · {rec['observed_months']} observed"},
        {"label": "Latest complete common month",
         "value": month_label(*latest) if latest else "—",
         "sub": (f"Harmonized {fmt_int(latest_row['harmonized_activity'])}" if latest_row else ""),
         "tag": "VIIRS observed" if latest_row else ""},
    ])

    _monthly_activity(totals, h, region)

    section_title("Sensor coverage")
    st.plotly_chart(sensor_coverage_chart(cov), width="stretch", config=PLOTLY_CONFIG)
    st.caption("MODIS = Terra (from Nov 2000) plus Aqua (from Jul 2002). VIIRS = Suomi-NPP. "
               "Hover a bar for platform dates.")

    c1, c2 = st.columns(2, gap="large")
    with c1:
        section_title("Seasonal pattern", "Median harmonized activity per calendar month.")
        st.plotly_chart(seasonal_chart(A.seasonal_summary(hr)), width="stretch",
                        config=PLOTLY_CONFIG)
    with c2:
        section_title("Detection types", "All types are included in every count.")
        st.plotly_chart(detection_type_chart(A.type_distribution(types, region)), width="stretch",
                        config=PLOTLY_CONFIG)

    _calibration_summary(factors, metrics, region)


def _monthly_activity(totals, harmonized, region: str) -> None:
    """Monthly Fire Activity: one selected year, January–December, three series."""
    section_title("Monthly Fire Activity",
                  "Compare MODIS, VIIRS and harmonized hotspot detections throughout the year.")
    years = sorted((int(y) for y in totals.loc[totals["region"] == region, "year"].unique()),
                   reverse=True)
    default = A.latest_complete_year(totals, region) or years[0]
    st.session_state.setdefault("overview_year", default)
    if st.session_state["overview_year"] not in years:
        st.session_state["overview_year"] = default
    year = st.selectbox("Year", years, key="overview_year", width=160,
                        help="Defaults to the latest year with complete MODIS and VIIRS months.")
    frame = A.year_monthly_activity(totals, harmonized, region, int(year))
    st.plotly_chart(monthly_activity_chart(frame, region_label(region), int(year)),
                    width="stretch", config=PLOTLY_CONFIG)
    gaps = availability_notes(frame, int(year))
    if gaps:
        st.caption(" ".join(gaps))
    note("MODIS (1 km) misses many small fires that VIIRS (375 m) detects, so the raw lines sit on "
         "different scales. The <b>harmonized record</b> puts every year on the VIIRS scale: before "
         "2012 it is an <b>estimate</b> (MODIS × seasonal calibration factor); from the VIIRS "
         "reference period onward it <b>equals the actual VIIRS observation</b>, so the teal and "
         "orange lines overlap. Counts are satellite detections, not unique fires. The full "
         "multi-year comparison is on Harmonization & Comparison.")


def _calibration_summary(factors, metrics, region: str) -> None:
    f = factors[factors["region"] == region]
    m = metrics[metrics["region"] == region].set_index("comparison")
    available = int((f["validation_status"] == "available").sum())
    section_title("Calibration & validation",
                  "How well calibrated MODIS reproduces VIIRS in months never used for fitting.")
    cards = [
        {"label": "Seasonal factors available", "value": f"{available} / 12",
         "sub": f"Training {f['training_start'].iloc[0]} → {f['training_end'].iloc[0]}"},
    ]
    if {"raw_modis", "calibrated_seasonal"} <= set(m.index):
        raw, cal = m.loc["raw_modis", "wape_pct"], m.loc["calibrated_seasonal", "wape_pct"]
        cards.append({"label": "Held-out error (WAPE)",
                      "value": f"{fmt_pct(raw)} → {fmt_pct(cal)}",
                      "sub": f"Raw MODIS → calibrated, {m.loc['calibrated_seasonal', 'validation_start']}"
                             f" → {m.loc['calibrated_seasonal', 'validation_end']}",
                      "tag": "Improves on raw" if cal < raw else "No improvement"})
    metric_row(cards)
    st.caption("Held-out error is higher than in the training years. When it changes, and the "
               "possible role of Terra/Aqua overpass-time drift, is examined on "
               "Harmonization & Comparison.")
