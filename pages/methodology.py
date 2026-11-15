"""Page 6 — Methodology and Data Quality."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from components.data_export import download_csv
from components.metric_cards import metric_row, note
from components.navigation import data_unavailable, page_header
from config import settings as S
from services import analytics_service as A
from services.data_service import DataUnavailable, load_quality_report, load_table
from services.region_service import boundary_provenance, selected_region
from utils.formatters import fmt_int

PIPELINE_STEPS = [
    ("Archive ingestion", "Historical FIRMS archive CSVs extracted from the ZIPs; NRT files ignored."),
    ("Standardization", "Common schema; dates/times parsed; original confidence, version and satellite codes kept."),
    ("Confidence filtering", "MODIS confidence ≥ 30; VIIRS n/h. Low-confidence detections excluded and counted."),
    ("Geographic filtering", "Point-in-polygon against real state boundaries; outside detections excluded and counted."),
    ("Grid & monthly aggregation", "1 km UTM 43N grid for maps; monthly counts by region, satellite and type."),
    ("Sensor comparison", "Combined Terra+Aqua MODIS vs VIIRS S-NPP over complete overlapping months."),
    ("Seasonal calibration", "Median VIIRS/MODIS ratio per region and calendar month (training years)."),
    ("Validation", "Factors applied to held-out months and compared with observed VIIRS."),
    ("Historical reconstruction", "Pre-2012 MODIS × factor, with bootstrap calibration-factor intervals."),
    ("Dashboard", "Streamlit reads the precomputed outputs; nothing is recomputed per click."),
]


def render() -> None:
    region = selected_region()
    page_header("Methodology & Data Quality", "What IGNIS does, how, and how far to trust it.", region)
    try:
        report = load_quality_report()
    except DataUnavailable as exc:
        data_unavailable(exc)
        return

    tabs = st.tabs(["Why harmonize", "Data sources", "Pipeline", "Calibration", "Uncertainty",
                    "Data quality", "Limitations", "Downloads"])
    with tabs[0]:
        _why()
    with tabs[1]:
        _sources(report)
    with tabs[2]:
        for i, (name, desc) in enumerate(PIPELINE_STEPS, 1):
            st.markdown(f"**{i}. {name}** — {desc}")
        st.code("python -m scripts.run_pipeline", language="bash")
    with tabs[3]:
        _calibration(report)
    with tabs[4]:
        _uncertainty()
    with tabs[5]:
        _quality(report, region)
    with tabs[6]:
        _limitations()
    with tabs[7]:
        _downloads(region)


def _why() -> None:
    st.markdown(
        "NASA's **MODIS** (Terra, Aqua) and **VIIRS** (Suomi-NPP) instruments both detect active "
        "fires, but differently:\n\n"
        "| | MODIS | VIIRS (375 m) |\n|---|---|---|\n"
        "| Active-fire pixel | ~1 km | ~375 m |\n"
        "| Small-fire sensitivity | Lower | Higher |\n"
        "| Satellites used here | Terra (2000–) + Aqua (2002–) | Suomi-NPP (2012–) |\n\n"
        "VIIRS detects many small fires that MODIS misses, so raw counts jump when VIIRS appears. "
        "A rise in raw detections can therefore reflect a change of instrument rather than more "
        "burning. IGNIS converts the pre-VIIRS MODIS record to an estimated VIIRS-equivalent scale "
        "so the full 2002–2026 record can be read as one series.")
    note("VIIRS is used as the <b>reference</b> scale, not as ground truth.")


def _sources(report: dict) -> None:
    rows = []
    for key, inp in report.get("inputs", {}).items():
        stats = report["raw_statistics"][key]
        rows.append({"Sensor": inp["collection"], "Archive": inp["archive"],
                     "CSV used": inp["archive_csv"], "Ignored (NRT)": ", ".join(inp["ignored_csvs"]),
                     "Records": f"{stats['total_rows']:,}",
                     "Coverage": f"{stats['first_date']} → {stats['last_date']}"})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.markdown(
        "Source: **NASA FIRMS** archive downloads (standard-quality historical products).\n\n"
        "**Confidence** — MODIS: 0–29 low, 30–79 nominal, 80–100 high. VIIRS: l / n / h. "
        "The two scales are not equivalent; each sensor's own nominal + high classes are kept.\n\n"
        "**Detection types** — 0 presumed vegetation fire, 1 active volcano, 2 other static land "
        "source, 3 offshore. All types are included by default.")
    prov = boundary_provenance()
    if prov:
        st.markdown(f"**State boundaries** — {prov['name']} ({prov['admin_level']}), from "
                    f"{prov['upstream_source']}. Licence: {prov['license']}. CRS {prov['crs']}. "
                    f"Downloaded {prov['downloaded_at'][:10]}.")


def _calibration(report: dict) -> None:
    st.markdown("**Monthly ratio** for year *y* and calendar month *m*:")
    st.latex(r"r_{y,m} = \frac{V_{y,m}}{M_{y,m}}")
    st.markdown("**Seasonal factor** — the median across training years:")
    st.latex(r"r_m = \operatorname{median}_y\left(r_{y,m}\right)")
    st.markdown("**Historical reconstruction** (before VIIRS) and **reference period**:")
    st.latex(r"H_{y,m} = M_{y,m} \times r_m \quad\text{(2002–2011)},\qquad H_{y,m} = V_{y,m}\quad\text{(2012 onward)}")
    st.markdown(
        f"*V* = VIIRS S-NPP detections, *M* = combined Terra + Aqua MODIS detections, computed "
        f"separately for Punjab and Haryana. Training uses complete months **{S.TRAINING_START} → "
        f"{S.TRAINING_END}**; validation uses **{S.VALIDATION_START} → {S.VALIDATION_END}**, never "
        f"used for fitting. A year counts only if both sensors have ≥ {S.MIN_MONTHLY_DETECTIONS} "
        f"detections, and a factor needs ≥ {S.MIN_VALID_YEAR_PAIRS} such years. MODIS and VIIRS "
        "counts are never added together.")
    st.markdown("**Validation metrics** (V = observed VIIRS, V̂ = calibrated MODIS):")
    st.latex(r"\text{WAPE} = \frac{\sum_i |V_i-\hat V_i|}{\sum_i V_i}\times 100,\quad "
             r"\text{Bias} = \frac{\sum_i (\hat V_i - V_i)}{\sum_i V_i}\times 100")
    st.markdown("plus MAE and RMSE. Raw MODIS-vs-VIIRS error is reported alongside, so the effect "
                "of calibration is visible — including if it does not help.")
    note("Known issue: from 2022 Terra and Aqua drift from their original overpass times, which "
         "lowers accuracy in the 2023–2026 hold-out. A supplementary leave-one-year-out check over "
         f"{S.STABLE_ORBIT_CV_YEARS[0]}–{S.STABLE_ORBIT_CV_YEARS[1]} (stable orbits) is shown on the "
         "Harmonization page; it does not replace the independent hold-out.")


def _uncertainty() -> None:
    st.markdown(
        f"For each region and calendar month the valid training-year ratios are resampled with "
        f"replacement {S.BOOTSTRAP_ITERATIONS:,} times (fixed seed {S.BOOTSTRAP_SEED}); the 2.5th "
        "and 97.5th percentiles of the resampled medians give the factor interval, applied as")
    st.latex(r"\left[\,M_{y,m}\, r_{m,\text{lower}},\; M_{y,m}\, r_{m,\text{upper}}\,\right]")
    note("This is a <b>95% bootstrap calibration-factor uncertainty interval</b>. It does not "
         "include satellite measurement uncertainty, cloud-related omission, detection-algorithm "
         "uncertainty, spatial heterogeneity, temporal fire variability or every difference "
         "between instruments. It is not a prediction interval.")
    st.markdown(
        "From February 2012 the series uses direct VIIRS observations, so no calibration band is "
        "drawn. Those values still carry observational uncertainty — the calibration-factor "
        "uncertainty simply does not apply to them. January 2012 is a partial VIIRS month and is "
        "not treated as a complete observation.")


def _quality(report: dict, region: str) -> None:
    conf = report["confidence_policy"]["counts"]
    geo = report["geographic_filter"]["counts_after_confidence_filter"]
    retained = report["retained"]
    cards = []
    for sensor in ("MODIS", "VIIRS"):
        c = conf.get(sensor, {})
        r = retained.get(sensor, {})
        cards.append({"label": f"{sensor} input → retained",
                      "value": f"{fmt_int(c.get('input'))} → {fmt_int(r.get('retained_total'))}",
                      "sub": f"Low confidence excluded {fmt_int(c.get('excluded_low_confidence'))}"})
    outside = sum(v.get(S.OUTSIDE_REGION_LABEL, 0) for v in geo.values())
    cards.append({"label": "Outside study area", "value": fmt_int(outside),
                  "sub": "Excluded after confidence filter"})
    metric_row(cards)
    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Satellite × region (Nominal + High)**")
        st.dataframe(pd.DataFrame(geo).T.fillna(0).astype(int), width="stretch")
        st.markdown("**Satellite observation coverage**")
        st.dataframe(pd.DataFrame(report["satellite_observation_coverage"], index=["first", "last"]).T,
                     width="stretch")
    with c2:
        for sensor, r in retained.items():
            st.markdown(f"**{sensor} retained — detection types / versions**")
            st.dataframe(pd.DataFrame({"type": r["by_detection_type"]}).T, width="stretch")
            st.dataframe(pd.DataFrame({"version": r["by_version"]}).T, width="stretch")
    st.markdown("**Checks against expected source statistics**")
    rows = []
    for sensor, checks in report.get("expectation_checks", {}).items():
        for c in checks:
            rows.append({"Sensor": sensor, "Check": c["check"], "Match": "✓" if c["match"] else "✗",
                         "Note": c.get("explanation", "")})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    gaps = report.get("observation_gaps_over_20_days", [])
    with st.expander(f"Periods of 20+ days without any detection ({len(gaps)})"):
        st.caption("Mostly monsoon and mid-winter. They may be genuinely quiet periods or data "
                   "outages — they are reported, not altered.")
        st.dataframe(pd.DataFrame(gaps), hide_index=True, width="stretch")
    warnings = report.get("warnings", [])
    if warnings:
        st.markdown("**Processing warnings**")
        for w in warnings:
            st.markdown(f"- {w}")
    st.caption(f"Report generated {report.get('processing_date', '')}.")


def _limitations() -> None:
    st.markdown(
        "- Hotspot detections are **not unique wildfire events**; one fire can be detected many "
        "times, and a grid-cell count is not a fire count.\n"
        "- MODIS and VIIRS have different detection characteristics; the calibration is a "
        "regional, empirical adjustment, not a physical conversion.\n"
        "- VIIRS is a **reference instrument, not ground truth**.\n"
        "- Combined Terra + Aqua sampling (two satellites) differs from one VIIRS satellite's "
        "overpasses; the factor absorbs this difference too.\n"
        "- Terra and Aqua orbits drifted after 2022, reducing comparability in recent years.\n"
        "- Uncertainty bands cover only the calibration factor, as described on the Uncertainty tab.\n"
        "- Missing observations are **never** interpreted as zero fire activity.\n"
        "- Anomalies describe unusual satellite-detected activity, not emergencies.")


def _downloads(region: str) -> None:
    st.markdown(f"All downloads are for **{region}** and come from the full processed tables "
                "(never sampled map data).")
    specs = [("monthly_sensor_counts", "monthly_sensor_counts", "Monthly sensor counts"),
             ("harmonized_monthly", "harmonized", "Harmonized monthly activity"),
             ("calibration_factors", "calibration_factors", "Calibration factors"),
             ("validation_results", "validation", "Validation results"),
             ("anomaly_results", "anomalies", "Anomaly results"),
             ("detection_type_breakdown", "detection_types", "Detection-type breakdown")]
    cols = st.columns(3)
    for i, (table, kind, label) in enumerate(specs):
        try:
            df = A.for_region(load_table(table), region)
        except DataUnavailable:
            cols[i % 3].caption(f"{label}: not available")
            continue
        with cols[i % 3]:
            download_csv(df, region, kind, label, key=f"meth_dl_{kind}")
