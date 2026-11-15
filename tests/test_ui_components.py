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
