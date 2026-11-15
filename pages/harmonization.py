"""Page 3 — Harmonization and Comparison."""
from __future__ import annotations

import streamlit as st

from components import filters
from components.calibration_charts import (
    factor_chart,
    overpass_chart,
    ratio_strip,
    validation_timeseries,
    validation_wape_chart,
)
from components.comparison_charts import harmonized_chart, platform_chart, raw_sensor_chart
from components.data_export import download_csv
from components.metric_cards import metric_row, note
from components.navigation import data_unavailable, page_header
from config.settings import (
    MIN_MONTHLY_DETECTIONS,
    MIN_VALID_YEAR_PAIRS,
    REGIONS,
    STABLE_ORBIT_CV_YEARS,
    TRAINING_END,
    TRAINING_START,
    VALIDATION_END,
    VALIDATION_START,
)
from services import analytics_service as A
from services.data_service import DataUnavailable, load_table
from services.region_service import selected_region
from utils.charts import PLOTLY_CONFIG
from utils.formatters import fmt_int, fmt_pct, fmt_signed_pct


def render() -> None:
    region = selected_region()
    page_header("Harmonization & Comparison",
                "How MODIS and VIIRS differ, how they are calibrated, and how well it works.", region,
                [f"Training {TRAINING_START} → {TRAINING_END}",
                 f"Validation {VALIDATION_START} → {VALIDATION_END}"])
    try:
        totals = load_table("monthly_region_totals")
        h = load_table("harmonized_monthly")
        unc = load_table("uncertainty_intervals")
        factors = load_table("calibration_factors")
        pairs = load_table("training_pairs")
        val = load_table("validation_results")
        metrics = load_table("validation_metrics")
        cv = load_table("validation_cv_metrics")
        overpass = load_table("overpass_times")
    except DataUnavailable as exc:
        data_unavailable(exc)
        return

    lo, hi = int(h["year"].min()), int(h["year"].max())
    years = filters.year_range("Years shown", lo, hi, key="harm_years")
    t = A.with_date(A.between_years(A.for_region(totals, region), *years))
    hr = A.with_date(A.between_years(A.calendar_frame(A.for_region(h, region), unc), *years))

    tab1, tab2, tab3, tab4 = st.tabs(["Sensor comparison", "Harmonized series",
                                      "Calibration factors", "Validation"])
    with tab1:
        note("Combined MODIS (Terra + Aqua) and VIIRS S-NPP raw monthly counts. Only months each "
             "sensor observed completely are drawn; partial months are left as gaps, never zeros.")
        st.plotly_chart(raw_sensor_chart(t), width="stretch", config=PLOTLY_CONFIG)
        st.plotly_chart(platform_chart(t), width="stretch", config=PLOTLY_CONFIG)
        st.caption("Before July 2002 only Terra was observing; those months are Terra-only and are "
                   "never treated as combined MODIS.")

    with tab2:
        st.plotly_chart(harmonized_chart(hr, height=460), width="stretch", config=PLOTLY_CONFIG)
        note("<b>Dashed + shaded</b>: estimated VIIRS-equivalent activity = combined MODIS × the "
             "month's calibration factor. The band is the <b>95% bootstrap calibration-factor "
             "uncertainty interval</b> — it reflects uncertainty in the factor only, not satellite "
             "measurement error, cloud omission or fire variability. <b>Solid</b>: direct VIIRS "
             "observations; the calibration band does not apply there, though VIIRS observations "
             "still carry their own observational uncertainty. × marks months that are not on the "
             "harmonized scale (Terra-only or partial). No smoothing is applied at the transition.")
        download_csv(hr.drop(columns=["date", "status", "status_long"]), region, "harmonized",
                     "Harmonized monthly activity (CSV)", years)

    with tab3:
        note(f"For each calendar month: ratio = VIIRS ÷ combined MODIS in every complete training "
             f"month ({TRAINING_START} → {TRAINING_END}) where both sensors have at least "
             f"{MIN_MONTHLY_DETECTIONS} detections. The factor is the <b>median</b> of those yearly "
             f"ratios and needs at least {MIN_VALID_YEAR_PAIRS} valid years; otherwise no factor is "
             "produced. Because two MODIS satellites (roughly four overpasses a day) are compared "
             "with one VIIRS satellite (roughly two), the factor captures differences in "
             "observation opportunities as well as detection sensitivity.")
        c1, c2 = st.columns(2)
        for col, r in zip((c1, c2), REGIONS):
            with col:
                st.plotly_chart(factor_chart(factors[factors["region"] == r], r), width="stretch",
                                config=PLOTLY_CONFIG)
        st.plotly_chart(ratio_strip(pairs, factors, region), width="stretch", config=PLOTLY_CONFIG)
        unavailable = factors[factors["validation_status"] != "available"]
        if unavailable.empty:
            st.success("All 24 region-month factors have enough valid training years.")
        else:
            st.warning("Factors unavailable:")
            st.dataframe(unavailable[["region", "calendar_month", "unavailable_reason"]],
                         hide_index=True)
        with st.expander("Factor table"):
            st.dataframe(factors[factors["region"] == region], hide_index=True, width="stretch")
        download_csv(factors[factors["region"] == region], region, "calibration_factors",
                     "Calibration factors (CSV)")

    with tab4:
        _validation(region, val, metrics, cv, overpass)


def _validation(region, val, metrics, cv, overpass) -> None:
    m = metrics[metrics["region"] == region]
    if m.empty or m["n_months"].max() == 0:
        st.warning("Not enough complete validation months to evaluate the calibration.")
        return
    mi = m.set_index("comparison")
    raw, cal = mi.loc["raw_modis"], mi.loc["calibrated_seasonal"]
    improved = cal["wape_pct"] < raw["wape_pct"]
    metric_row([
        {"label": "Held-out months", "value": fmt_int(cal["n_months"]),
         "sub": f"{VALIDATION_START} → {VALIDATION_END}, complete overlap"},
        {"label": "WAPE raw → calibrated",
         "value": f"{fmt_pct(raw['wape_pct'])} → {fmt_pct(cal['wape_pct'])}",
         "sub": "Improves on raw MODIS" if improved else "Does NOT improve on raw MODIS"},
        {"label": "Relative bias (calibrated)", "value": fmt_signed_pct(cal["relative_bias_pct"], 1),
         "sub": f"Raw MODIS: {fmt_signed_pct(raw['relative_bias_pct'], 1)}"},
        {"label": "MAE / RMSE (calibrated)",
         "value": f"{fmt_int(cal['mae'])} / {fmt_int(cal['rmse'])}",
         "sub": f"Raw: {fmt_int(raw['mae'])} / {fmt_int(raw['rmse'])}"},
    ])
    st.write("")
    c1, c2 = st.columns([2, 3])
    with c1:
        st.plotly_chart(validation_wape_chart(m, "Independent hold-out error"), width="stretch",
                        config=PLOTLY_CONFIG)
    with c2:
        v = A.with_date(A.for_region(val, region))
        st.plotly_chart(validation_timeseries(v), width="stretch", config=PLOTLY_CONFIG)

    const = mi.loc["constant_factor"] if "constant_factor" in mi.index else None
    msg = (f"Calibration reduces the gap to VIIRS from {fmt_pct(raw['wape_pct'])} to "
           f"{fmt_pct(cal['wape_pct'])} WAPE in held-out months." if improved else
           "Calibration did not reduce error relative to raw MODIS in the held-out months.")
    if const is not None and const["wape_pct"] <= cal["wape_pct"]:
        msg += (f" In this period a single constant factor did slightly better "
                f"({fmt_pct(const['wape_pct'])}), so seasonality did not add value here.")
    note(msg + " Held-out accuracy is limited by MODIS orbit drift: after 2022 Terra and Aqua "
         "observe at different times of day than during training (chart below), which changes the "
         "MODIS/VIIRS ratio. This affects the validation years, not the 2002–2011 backcast, when "
         "MODIS overpass times matched the training period.")

    st.markdown("##### Diagnostics")
    d1, d2 = st.columns([3, 2])
    with d1:
        st.plotly_chart(overpass_chart(overpass), width="stretch", config=PLOTLY_CONFIG)
    with d2:
        cvm = cv[cv["region"] == region]
        st.plotly_chart(validation_wape_chart(
            cvm, f"Supplementary: stable-orbit CV {STABLE_ORBIT_CV_YEARS[0]}–{STABLE_ORBIT_CV_YEARS[1]}"),
            width="stretch", config=PLOTLY_CONFIG)
        st.caption("Leave-one-year-out within training years while MODIS orbits were stable. "
                   "Supplementary only — it re-uses training-period data and does not replace "
                   "the independent hold-out above.")
    download_csv(A.for_region(val, region), region, "validation", "Validation results (CSV)")
    with st.expander("All validation metrics"):
        st.dataframe(m, hide_index=True, width="stretch")
