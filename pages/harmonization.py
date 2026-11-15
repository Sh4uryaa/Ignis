"""Page 3 — Harmonization and Comparison."""
from __future__ import annotations

import streamlit as st

from components.calibration_charts import (
    factor_chart,
    overpass_chart,
    ratio_strip,
    validation_timeseries,
    validation_wape_chart,
    yearly_error_chart,
)
from components.comparison_charts import four_series_chart, platform_chart, raw_sensor_chart
from components.historical_trend import availability_notes, monthly_series_chart
from components.data_export import download_csv
from components.metric_cards import metric_row, note, section_title
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
from config.regions import region_label
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
        calibrated = load_table("calibrated_modis")
        cal_periods = load_table("calibrated_period_metrics")
        cal_years = load_table("calibrated_yearly_metrics")
    except DataUnavailable as exc:
        data_unavailable(exc)
        return

    # One year, January–December (same style as the Overview chart).
    year_options = sorted((int(y) for y in totals.loc[totals["region"] == region, "year"].unique()),
                          reverse=True)
    default_year = A.latest_complete_year(totals, region) or year_options[0]
    st.session_state.setdefault("harm_year", default_year)
    if st.session_state["harm_year"] not in year_options:
        st.session_state["harm_year"] = default_year
    year = int(st.selectbox("Year", year_options, key="harm_year", width=160,
                            help="Month-by-month view of one year. The full multi-year timeline "
                                 "is in the expander under each chart."))
    frame = A.year_monthly_activity(totals, h, region, year, calibrated)
    label = region_label(region)

    # Full-record frames for the multi-year expanders and the downloads.
    t = A.with_date(A.for_region(totals, region))
    hr = A.with_date(A.calendar_frame(A.for_region(h, region), unc))
    cal = A.with_date(A.for_region(calibrated, region))

    tab1, tab2, tab3, tab4 = st.tabs(["Sensor comparison", "Calibrated & harmonized series",
                                      "Calibration factors", "Validation"])
    with tab1:
        section_title(f"Raw monthly detections by sensor — {year}",
                      "Combined MODIS (Terra + Aqua) and VIIRS Suomi-NPP, January to December.")
        st.plotly_chart(monthly_series_chart(frame, label, year, ["modis", "viirs"]),
                        width="stretch", config=PLOTLY_CONFIG)
        section_title(f"How the combined MODIS count is built — {year}",
                      "Combined MODIS (gold) is the sum of Terra (blue) and Aqua (pink); "
                      "Terra and Aqua are drawn on top so they stay visible where one dominates.")
        st.plotly_chart(monthly_series_chart(frame, label, year, ["modis", "terra", "aqua"],
                                             height=340), width="stretch", config=PLOTLY_CONFIG)
        notes = availability_notes(frame, year, ("modis", "terra", "aqua", "viirs"))
        if notes:
            st.caption(" ".join(notes))
        note("Raw counts are not on a common scale: VIIRS (375 m) detects many small fires that "
             "MODIS (1 km) misses. Months a sensor did not observe are gaps, never zeros; partial "
             "months keep their real count with a hollow marker. Before July 2002 only Terra was "
             "observing, so there is no combined MODIS value for those months.")
        with st.expander("Full timeline, 2000–2026"):
            st.plotly_chart(raw_sensor_chart(t), width="stretch", config=PLOTLY_CONFIG)
            st.plotly_chart(platform_chart(t), width="stretch", config=PLOTLY_CONFIG)

    with tab2:
        section_title(f"Calibrated and harmonized activity — {year}",
                      "Raw MODIS, actual VIIRS, calibrated MODIS and the final harmonized record.")
        st.plotly_chart(monthly_series_chart(frame, label, year,
                                             ["modis", "viirs", "calibrated", "harmonized"]),
                        width="stretch", config=PLOTLY_CONFIG)
        statuses = frame["calibrated_status"].dropna().unique().tolist()
        notes = availability_notes(frame, year, ("modis", "viirs", "calibrated", "harmonized"))
        st.caption(f"{year}: calibrated MODIS is "
                   + "; ".join(sorted(set(statuses))) + ". " + " ".join(notes))
        note("<b>The calibrated MODIS line shows what the model predicts on the VIIRS reference "
             "scale. The final harmonized line uses actual VIIRS observations once they become "
             "available.</b> Calibrated MODIS = combined Terra + Aqua × that calendar month's factor "
             f"(fitted on {TRAINING_START} → {TRAINING_END} only). Before VIIRS it <i>is</i> the "
             "harmonized estimate, so the teal and purple lines coincide; from the VIIRS reference "
             "period the harmonized line equals actual VIIRS, so teal and orange coincide. "
             f"{TRAINING_START[:4]}–{TRAINING_END[:4]} are training years (in-sample); "
             f"{VALIDATION_START[:4]}–{VALIDATION_END[:4]} are held out (out-of-sample).")
        with st.expander("Full timeline, 2002–2026, with the calibration-uncertainty band"):
            periods = {"training": (TRAINING_START, TRAINING_END),
                       "validation": (VALIDATION_START, VALIDATION_END)}
            st.plotly_chart(four_series_chart(t, cal, hr, periods), width="stretch",
                            config=PLOTLY_CONFIG)
            st.caption("Lightly shaded years are in-sample, darker shaded years are held out. The "
                       "teal band is the 95% bootstrap calibration-factor uncertainty interval on "
                       "pre-2012 estimates only — factor uncertainty, not measurement error, cloud "
                       "omission or fire variability.")
        c1, c2 = st.columns(2)
        with c1:
            download_csv(cal.drop(columns=["date"]), region, "calibrated",
                         "Calibrated MODIS comparison (CSV)")
        with c2:
            download_csv(hr.drop(columns=["date", "status", "status_long"]), region, "harmonized",
                         "Final harmonized record (CSV)")

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
        _validation(region, val, metrics, cv, overpass, cal_periods, cal_years)


def _validation(region, val, metrics, cv, overpass, cal_periods, cal_years) -> None:
    m = metrics[metrics["region"] == region]
    if m.empty or m["n_months"].max() == 0:
        st.warning("Not enough complete validation months to evaluate the calibration.")
        return
    mi = m.set_index("comparison")
    raw, cal = mi.loc["raw_modis"], mi.loc["calibrated_seasonal"]
    improved = cal["wape_pct"] < raw["wape_pct"]
    section_title("Calibrated MODIS vs actual VIIRS — held-out months",
                  f"{VALIDATION_START} → {VALIDATION_END}: factors were never fitted on these months.")
    metric_row([
        {"label": "Held-out months", "value": fmt_int(cal["n_months"]),
         "sub": "Complete overlapping months"},
        {"label": "WAPE (raw MODIS → calibrated)",
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

    with st.expander("Month-by-month held-out comparison"):
        table = A.for_region(val, region)[[
            "year", "month", "actual_viirs_count", "predicted_viirs_equivalent",
            "calibrated_absolute_error", "calibrated_relative_error_pct", "calibration_factor"]]
        st.dataframe(table.rename(columns={
            "actual_viirs_count": "Actual VIIRS", "predicted_viirs_equivalent": "Calibrated MODIS",
            "calibrated_absolute_error": "Absolute error",
            "calibrated_relative_error_pct": "Relative error (%)",
            "calibration_factor": "Factor"}).round(1), hide_index=True, width="stretch")
        st.caption("Relative error is blank when actual VIIRS is 0 (undefined).")

    const = mi.loc["constant_factor"] if "constant_factor" in mi.index else None
    msg = (f"Calibration reduces the gap to VIIRS from {fmt_pct(raw['wape_pct'])} to "
           f"{fmt_pct(cal['wape_pct'])} WAPE in held-out months." if improved else
           "Calibration did not reduce error relative to raw MODIS in the held-out months.")
    if const is not None and const["wape_pct"] <= cal["wape_pct"]:
        msg += (f" In this period a single constant factor did slightly better "
                f"({fmt_pct(const['wape_pct'])}), so seasonality did not add value here.")
    note(msg)

    section_title("Does performance change after 2022?",
                  "Calibrated MODIS error against actual VIIRS, every year with complete overlap.")
    p = cal_periods[cal_periods["region"] == region].set_index("comparison_period")
    y = cal_years[cal_years["region"] == region].sort_values("year")
    d1, d2 = st.columns([3, 2])
    with d1:
        st.plotly_chart(yearly_error_chart(cal_years, region), width="stretch", config=PLOTLY_CONFIG)
    with d2:
        st.plotly_chart(overpass_chart(overpass), width="stretch", config=PLOTLY_CONFIG)
    if {"training_in_sample", "validation_out_of_sample"} <= set(p.index):
        tr, va = p.loc["training_in_sample"], p.loc["validation_out_of_sample"]
        pre = y[y["comparison_period"] == "training_in_sample"]["wape_pct"]
        note(f"In the training years ({tr['first_month']} → {tr['last_month']}) calibrated MODIS is "
             f"within <b>{fmt_pct(tr['wape_pct'])}</b> WAPE of VIIRS overall (yearly "
             f"{fmt_pct(pre.min())}–{fmt_pct(pre.max())}) — but these years are <b>in-sample</b>, "
             f"so this is a fit, not a test. In the held-out years ({va['first_month']} → "
             f"{va['last_month']}) WAPE is <b>{fmt_pct(va['wape_pct'])}</b> with bias "
             f"{fmt_signed_pct(va['relative_bias_pct'], 1)}. The change coincides with Terra and "
             "Aqua drifting to different overpass times (right), which alters which part of the "
             "daily fire cycle MODIS samples; it also coincides with changes in burning itself "
             "(e.g. the decline in Punjab's stubble-burning detections). The data show <i>when</i> "
             "performance changes but cannot attribute it to a single cause, and MODIS "
             "observations remain valid detections. 2026 covers January–July only.")
    d3, d4 = st.columns([3, 2])
    with d3:
        st.markdown("##### Calibrated MODIS vs VIIRS by period")
        st.dataframe(p.reset_index()[["comparison_period", "first_month", "last_month", "n_months",
                                      "mae", "rmse", "wape_pct", "relative_bias_pct"]].round(1),
                     hide_index=True, width="stretch")
        st.caption("Leave-one-year-out (right) refits the factors without each year in turn — a "
                   "fairer in-period check than the in-sample fit, but still supplementary to the "
                   "independent hold-out.")
    with d4:
        cvm = cv[cv["region"] == region]
        st.plotly_chart(validation_wape_chart(
            cvm, f"Supplementary: leave-one-year-out {STABLE_ORBIT_CV_YEARS[0]}–{STABLE_ORBIT_CV_YEARS[1]}"),
            width="stretch", config=PLOTLY_CONFIG)
    download_csv(A.for_region(val, region), region, "validation", "Validation results (CSV)")
    with st.expander("All validation metrics"):
        st.dataframe(m, hide_index=True, width="stretch")
