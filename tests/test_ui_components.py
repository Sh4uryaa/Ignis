"""UI building blocks: region registry, calendar fire bins, sensor coverage rows."""
import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from components.activity_heatmap import bin_colors, bin_labels, calendar_heatmap, fire_bins
from components.sensor_coverage import sensor_rows
from config import settings as S
from config.regions import REGION_REGISTRY, REGIONS_BY_KEY, region_label
from processing.build_outputs import OUTPUT_FILES


def test_registry_drives_settings():
    assert S.REGIONS == tuple(r.key for r in REGION_REGISTRY) == ("Punjab", "Haryana")
    assert S.REGION_ISO_CODES == {"Punjab": "IN-PB", "Haryana": "IN-HR"}
    assert {k: p.name for k, p in S.REGION_BOUNDARY_FILES.items()} == {
        "Punjab": "punjab.geojson", "Haryana": "haryana.geojson"}
    assert region_label("Haryana") == "Haryana, India"
    assert region_label("Unknown") == "Unknown"
    assert set(REGIONS_BY_KEY) == set(S.REGIONS)


def test_fire_bins_monotonic_and_zero_is_lowest():
    v = pd.Series([0, 0, 1, 5, 10, 50, 100, 500, 1000, 5000, np.nan])
    thresholds, bins = fire_bins(v)
    assert thresholds == sorted(thresholds) and len(set(thresholds)) == len(thresholds)
    assert bins[0] == 0 and bins[1] == 0               # true zeros -> lowest colour
    assert np.isnan(bins[-1])                          # missing stays missing, never zero
    finite = bins[~np.isnan(bins)]
    assert (np.diff(finite) >= 0).all()                # more detections never get a lighter bin
    assert len(bin_labels(thresholds)) == len(thresholds) + 1


def test_bin_colors_run_yellow_to_red():
    assert bin_colors(6) == list(S.FIRE_SCALE)
    c3 = bin_colors(3)
    assert c3[0] == S.FIRE_SCALE[0] and c3[-1] == S.FIRE_SCALE[-1]


def test_sensor_rows_collapse_platforms():
    cov = pd.DataFrame({"satellite": ["Terra", "Aqua", "Suomi-NPP"],
                        "start": pd.to_datetime(["2000-11-01", "2002-07-18", "2012-01-20"]),
                        "end": pd.to_datetime(["2026-08-22", "2026-08-27", "2026-07-31"])})
    rows = sensor_rows(cov).set_index("sensor")
    assert list(rows.index) == ["MODIS", "VIIRS"]
    assert rows.loc["MODIS", "start"] == pd.Timestamp("2000-11-01")
    assert rows.loc["MODIS", "end"] == pd.Timestamp("2026-08-27")
    assert "Terra" in rows.loc["MODIS", "detail"] and "Aqua" in rows.loc["MODIS", "detail"]


real = pytest.mark.skipif(not (S.PROCESSED_DIR / OUTPUT_FILES["harmonized_monthly"]).exists(),
                          reason="processed outputs not generated")


@real
def test_calendar_never_colours_missing_months():
    from services.analytics_service import calendar_frame, for_region
    h = pd.read_csv(S.PROCESSED_DIR / OUTPUT_FILES["harmonized_monthly"])
    u = pd.read_csv(S.PROCESSED_DIR / OUTPUT_FILES["uncertainty_intervals"])
    frame = calendar_frame(for_region(h, "Punjab"), u)
    fig, legend = calendar_heatmap(frame)
    activity = fig.data[2].z                           # the fire-coloured layer
    not_harmonized = frame[frame["harmonized_activity"].isna()]
    years = [str(y) for y in range(int(frame.year.min()), int(frame.year.max()) + 1)]
    for _, r in not_harmonized.iterrows():
        assert np.isnan(activity[years.index(str(int(r.year)))][int(r.month) - 1])
    assert len(legend) == 6


def _html_text(at) -> str:
    return " ".join(h.proto.body for h in at.get("html"))


@real
def test_full_app_renders_with_top_navigation():
    at = AppTest.from_file(str(S.PROJECT_ROOT / "app.py"), default_timeout=120).run()
    assert not at.exception, at.exception
    region_box = [s for s in at.selectbox if s.key == "region"]
    assert len(region_box) == 1 and region_box[0].value == "Punjab"
    assert region_box[0].options == ["Punjab, India", "Haryana, India"]
    assert len(at.get("page_link")) == 6                 # top navigation, no sidebar menu
    html = _html_text(at)
    assert "ig-hero" in html and "Punjab, India at a glance" in html


@real
def test_selected_region_drives_the_page():
    # AppTest cannot rerun st.navigation apps, so the region is set before the run.
    at = AppTest.from_file(str(S.PROJECT_ROOT / "app.py"), default_timeout=120)
    at.session_state["region"] = "Haryana"
    at.run()
    assert not at.exception, at.exception
    assert [s.value for s in at.selectbox if s.key == "region"] == ["Haryana"]
    assert "Haryana, India at a glance" in _html_text(at)


# ---------------------------------------------------------------------------
# Overview: Monthly Fire Activity (one year, January–December)
# ---------------------------------------------------------------------------
def _year_inputs():
    t = pd.read_csv(S.PROCESSED_DIR / OUTPUT_FILES["monthly_region_totals"])
    h = pd.read_csv(S.PROCESSED_DIR / OUTPUT_FILES["harmonized_monthly"])
    return t, h


def _visible(fig):
    return [tr for tr in fig.data if tr.showlegend is not False]


@real
def test_monthly_chart_months_series_and_colours():
    from components.historical_trend import MONTHS, monthly_activity_chart
    from services.analytics_service import year_monthly_activity
    t, h = _year_inputs()
    fig = monthly_activity_chart(year_monthly_activity(t, h, "Punjab", 2025), "Punjab, India", 2025)
    series = _visible(fig)
    assert [tr.name for tr in series] == ["MODIS (Terra + Aqua)", "VIIRS Suomi-NPP", "Harmonized record"]
    assert [tr.line.color for tr in series] == ["#FACC15", "#F97316", "#2DD4BF"]
    assert all(list(tr.x) == MONTHS for tr in series) and len(MONTHS) == 12
    assert MONTHS[0] == "January" and MONTHS[-1] == "December"
    assert series[-1] is fig.data[-1]                  # harmonized drawn last
    assert series[-1].line.dash == "dash"


@real
def test_monthly_values_are_the_processed_counts():
    from services.analytics_service import year_monthly_activity
    t, h = _year_inputs()
    for region, year in (("Punjab", 2025), ("Haryana", 2008), ("Haryana", 2016)):
        f = year_monthly_activity(t, h, region, year).set_index("month")
        src = t[(t.region == region) & (t.year == year)].set_index("month")
        hs = h[(h.region == region) & (h.year == year)].set_index("month")
        for m in range(1, 13):
            assert f.loc[m, "modis"] == src.loc[m, "modis_combined_count"] or \
                (np.isnan(f.loc[m, "modis"]) and pd.isna(src.loc[m, "modis_combined_count"]))
            assert f.loc[m, "harmonized"] == hs.loc[m, "harmonized_activity"] or \
                (np.isnan(f.loc[m, "harmonized"]) and pd.isna(hs.loc[m, "harmonized_activity"]))


@real
def test_year_and_region_change_all_three_series():
    from services.analytics_service import year_monthly_activity
    t, h = _year_inputs()
    a = year_monthly_activity(t, h, "Punjab", 2025)
    b = year_monthly_activity(t, h, "Punjab", 2021)
    c = year_monthly_activity(t, h, "Haryana", 2025)
    for col in ("modis", "viirs", "harmonized"):
        assert not a[col].equals(b[col]) and not a[col].equals(c[col])


@real
def test_viirs_and_harmonized_overlap_after_2012_and_gaps_are_not_zero():
    from services.analytics_service import latest_complete_year, year_monthly_activity
    t, h = _year_inputs()
    assert latest_complete_year(t, "Punjab") == 2025
    f2016 = year_monthly_activity(t, h, "Punjab", 2016)
    assert (f2016["viirs"] == f2016["harmonized"]).all()            # identical, not offset
    f2008 = year_monthly_activity(t, h, "Punjab", 2008)
    assert f2008["viirs"].isna().all()                              # VIIRS not yet observing: gap
    assert (f2008["harmonized_status"].str.startswith("estimated")).all()
    f2002 = year_monthly_activity(t, h, "Punjab", 2002).set_index("month")
    assert np.isnan(f2002.loc[3, "modis"])                          # Terra-only: no combined MODIS
    assert f2002.loc[7, "modis_status"] == "partial month" and f2002.loc[7, "modis"] == 3
    f2012 = year_monthly_activity(t, h, "Punjab", 2012).set_index("month")
    assert f2012.loc[1, "viirs_status"] == "partial month" and np.isnan(f2012.loc[1, "harmonized"])
    f2026 = year_monthly_activity(t, h, "Punjab", 2026).set_index("month")
    assert f2026.loc[12, "modis_status"] == "outside the satellite record"
    assert np.isnan(f2026.loc[12, "modis"])


@real
def test_harmonization_monthly_chart_series_and_values():
    from components.historical_trend import MONTHS, monthly_series_chart
    from services.analytics_service import year_monthly_activity
    t, h = _year_inputs()
    c = pd.read_csv(S.PROCESSED_DIR / OUTPUT_FILES["calibrated_modis"])
    f = year_monthly_activity(t, h, "Haryana", 2024, c)
    fig = monthly_series_chart(f, "Haryana, India", 2024, ["modis", "viirs", "calibrated", "harmonized"])
    series = _visible(fig)
    assert [tr.line.color for tr in series] == [S.COLORS["modis"], S.COLORS["viirs"],
                                                S.COLORS["calibrated"], S.COLORS["harmonized"]]
    assert series[-1].name == "Harmonized record" and all(list(tr.x) == MONTHS for tr in series)
    src = c[(c.region == "Haryana") & (c.year == 2024)].set_index("month")["calibrated_modis"]
    assert np.allclose(f.set_index("month")["calibrated"], src.reindex(range(1, 13)))
    assert (f["calibrated_status"] == "held-out year — out-of-sample").all()
    f2016 = year_monthly_activity(t, h, "Haryana", 2016, c)
    assert (f2016["calibrated_status"] == "training year — in-sample").all()
    f2008 = year_monthly_activity(t, h, "Haryana", 2008, c)
    assert np.allclose(f2008["calibrated"], f2008["harmonized"])    # before VIIRS they coincide


@real
def test_terra_plus_aqua_equals_combined_in_monthly_view():
    from services.analytics_service import year_monthly_activity
    t, h = _year_inputs()
    for year in (2003, 2015, 2025):
        f = year_monthly_activity(t, h, "Punjab", year)
        assert np.allclose(f["terra"] + f["aqua"], f["modis"])
