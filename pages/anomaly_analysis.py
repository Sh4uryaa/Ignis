"""Page 5 — Anomaly Analysis against same-month historical medians."""
from __future__ import annotations

import streamlit as st

from components import filters
from components.anomaly_visuals import recent_deviation_chart, same_month_history
from components.data_export import download_csv
from components.metric_cards import metric_row, note
from components.navigation import data_unavailable, page_header
from config.settings import ANOMALY_NEAR_BAND_PCT
from services import analytics_service as A
from services.data_service import DataUnavailable, load_table
from services.region_service import selected_region
from utils.charts import PLOTLY_CONFIG
from utils.formatters import fmt_int, fmt_signed_pct, month_label


def render() -> None:
    region = selected_region()
    page_header("Anomaly Analysis",
                "Each month compared with the same calendar month in other years.", region,
                [f"Near = within ±{ANOMALY_NEAR_BAND_PCT:.0f}%"])
    try:
        anomalies = load_table("anomaly_results")
    except DataUnavailable as exc:
        data_unavailable(exc)
        return
    a = A.for_region(anomalies, region)
    if a.empty:
        st.warning("No complete harmonized months available for anomaly analysis.")
        return

    years = sorted(int(y) for y in a["year"].unique())
    last = a.sort_values(["year", "month"]).iloc[-1]
    year, month = filters.month_picker(years, key="anom_pick",
                                       default=(int(last["year"]), int(last["month"])))
    row = a[(a["year"] == year) & (a["month"] == month)]
    if row.empty:
        st.info(f"{month_label(year, month)} is not a complete harmonized month (partial, "
                "Terra-only or outside the record), so it is excluded from complete-month "
                "comparisons.")
    else:
        r = row.iloc[0]
        metric_row([
            {"label": f"{month_label(year, month)} · harmonized", "value": fmt_int(r["harmonized_activity"]),
             "sub": "Estimated from MODIS" if r["is_estimated"] else "Observed (VIIRS)"},
            {"label": "Historical median (same month)", "value": fmt_int(r["historical_median"]),
             "sub": f"{int(r['baseline_years'])} other years, {int(r['baseline_start_year'])}–"
                    f"{int(r['baseline_end_year'])}"},
            {"label": "Difference", "value": fmt_int(r["anomaly_abs"]) if r["anomaly_abs"] < 0
             else "+" + fmt_int(r["anomaly_abs"]), "sub": fmt_signed_pct(r["anomaly_pct"])},
            {"label": "Assessment", "value": r["anomaly_label"].replace(" historical median", ""),
             "sub": r["anomaly_label"]},
        ])
        st.write("")
        est_share = int(r["baseline_estimated_years"])
        note(f"Baseline: median of every other {month_label(year, month).split()[0]} in the "
             f"harmonized record (leave-one-out). {est_share} of {int(r['baseline_years'])} baseline "
             "years are MODIS-based estimates. An unusual detection count is a statistical "
             "signal about satellite-observed activity — not by itself evidence of an emergency.")

    st.plotly_chart(same_month_history(a, month, year), width="stretch", config=PLOTLY_CONFIG)
    st.plotly_chart(recent_deviation_chart(a), width="stretch", config=PLOTLY_CONFIG)
    st.caption("Colours: orange = above, grey = near, blue = below the same-month median. "
               "Partial and Terra-only months are excluded.")
    download_csv(a, region, "anomalies", "Anomaly results (CSV)")
