"""Page 1 — Overview of the selected region."""
from __future__ import annotations

import streamlit as st

from components.comparison_charts import harmonized_chart
from components.metric_cards import metric_row, note
from components.navigation import data_unavailable, go_to, page_header
from components.summary_charts import coverage_timeline, detection_type_chart, seasonal_chart
from config.settings import APP_SUBTITLE, APP_TAGLINE
from services import analytics_service as A
from services.data_service import DataUnavailable, load_quality_report, load_table
from services.region_service import selected_region
from utils.charts import PLOTLY_CONFIG
from utils.formatters import fmt_int, fmt_pct, month_label


def render() -> None:
    region = selected_region()
    try:
        totals = load_table("monthly_region_totals")
        h = load_table("harmonized_monthly")
        unc = load_table("uncertainty_intervals")
        factors = load_table("calibration_factors")
        metrics = load_table("validation_metrics")
        types = load_table("detection_type_breakdown")
        report = load_quality_report()
    except DataUnavailable as exc:
        page_header("IGNIS", APP_TAGLINE, region)
        data_unavailable(exc)
        return

    hr = A.with_date(A.calendar_frame(A.for_region(h, region), unc))
    rec = A.harmonized_record_summary(hr)
    sens = A.sensor_totals(totals, region)
    latest = A.latest_complete_common_month(totals, region)
    cov = A.coverage_timeline(report)

    page_header("IGNIS", f"{APP_TAGLINE} — {APP_SUBTITLE}", region,
                [f"Data {cov['start'].min():%b %Y} – {cov['end'].max():%b %Y}",
                 "Nominal + High confidence"])

    latest_row = A.month_record(hr, *latest) if latest else None
    metric_row([
        {"label": "Historical coverage",
         "value": f"{cov['start'].min():%Y} – {cov['end'].max():%Y}",
         "sub": f"{cov['start'].min():%d %b %Y} to {cov['end'].max():%d %b %Y}"},
        {"label": "MODIS detections (Terra + Aqua)", "value": fmt_int(sens["modis_combined"]),
         "sub": f"Terra {fmt_int(sens['terra'])} · Aqua {fmt_int(sens['aqua'])}"},
        {"label": "VIIRS S-NPP detections", "value": fmt_int(sens["viirs"]),
         "sub": "Raw counts — not comparable to MODIS"},
        {"label": "Harmonized record", "accent": True,
         "value": f"{rec['estimated_months'] + rec['observed_months']} months",
         "sub": f"{rec['estimated_months']} estimated · {rec['observed_months']} observed"},
        {"label": "Latest complete common month",
         "value": month_label(*latest) if latest else "—",
         "sub": (f"Harmonized {fmt_int(latest_row['harmonized_activity'])} (VIIRS observed)"
                 if latest_row else "")},
    ])
    st.write("")
    note("Raw detection counts from different sensors are <b>not</b> directly comparable — VIIRS "
         "(375 m) detects many smaller fires that MODIS (1 km) misses. The harmonized record "
         "expresses everything on the VIIRS S-NPP scale: dashed values are estimates from MODIS, "
         "solid values are VIIRS observations. Counts are satellite detections, not unique fires.")

    st.plotly_chart(harmonized_chart(hr, "Historical activity trend (harmonized)", height=400),
                    width="stretch", config=PLOTLY_CONFIG)

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(seasonal_chart(A.seasonal_summary(hr)), width="stretch", config=PLOTLY_CONFIG)
    with c2:
        st.plotly_chart(detection_type_chart(A.type_distribution(types, region)), width="stretch",
                        config=PLOTLY_CONFIG)

    c3, c4 = st.columns([3, 2])
    with c3:
        st.plotly_chart(coverage_timeline(cov), width="stretch", config=PLOTLY_CONFIG)
    with c4:
        _calibration_status(factors, metrics, region)

    st.divider()
    b1, b2, b3 = st.columns(3)
    if b1.button("Open the historical fire map", icon=":material/map:", width="stretch"):
        go_to("map")
    if b2.button("Open the activity calendar", icon=":material/calendar_month:", width="stretch"):
        go_to("calendar")
    if b3.button("See how harmonization works", icon=":material/compare_arrows:", width="stretch"):
        go_to("harmonization")


def _calibration_status(factors, metrics, region: str) -> None:
    f = factors[factors["region"] == region]
    available = int((f["validation_status"] == "available").sum())
    m = metrics[metrics["region"] == region].set_index("comparison")
    st.markdown("##### Calibration status")
    st.markdown(f"- Seasonal factors available: **{available} / 12** months")
    st.markdown(f"- Training: **{f['training_start'].iloc[0]} → {f['training_end'].iloc[0]}**")
    if {"raw_modis", "calibrated_seasonal"} <= set(m.index):
        raw, cal = m.loc["raw_modis", "wape_pct"], m.loc["calibrated_seasonal", "wape_pct"]
        verdict = "improves on" if cal < raw else "does **not** improve on"
        st.markdown(f"- Held-out 2023–2026 error (WAPE): raw MODIS **{fmt_pct(raw)}** → "
                    f"calibrated **{fmt_pct(cal)}** — calibration {verdict} raw counts")
    st.caption("Held-out accuracy is reduced by Terra/Aqua orbit drift after 2022 — see "
               "Harmonization & Comparison.")
