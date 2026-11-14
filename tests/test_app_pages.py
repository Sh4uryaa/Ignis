"""Every page renders without exceptions, and missing data gives an empty state.

Uses Streamlit's AppTest (headless). Rendering with real data is skipped
when the pipeline outputs have not been generated.
"""
import pytest
from streamlit.testing.v1 import AppTest

from config.settings import PROCESSED_DIR
from processing.build_outputs import OUTPUT_FILES

PAGES = ["overview", "historical_map", "harmonization", "activity_calendar",
         "anomaly_analysis", "methodology"]
HAS_DATA = (PROCESSED_DIR / OUTPUT_FILES["harmonized_monthly"]).exists() and \
           (PROCESSED_DIR / OUTPUT_FILES["detections"]).exists()


def _page_script(page: str, region: str) -> None:
    import importlib

    import streamlit as st

    st.session_state["region"] = region
    importlib.import_module(f"pages.{page}").render()


def _run(page: str, region: str = "Punjab") -> AppTest:
    # AppTest runs in this process, so monkeypatched module attributes apply.
    at = AppTest.from_function(_page_script, args=(page, region), default_timeout=120)
    return at.run()


@pytest.fixture
def no_outputs(tmp_path, monkeypatch):
    import services.data_service as ds
    monkeypatch.setattr(ds, "PROCESSED_DIR", tmp_path)
    monkeypatch.setattr(ds, "QUALITY_REPORT_PATH", tmp_path / "quality_report.json")


@pytest.mark.skipif(not HAS_DATA, reason="processed outputs not generated")
@pytest.mark.parametrize("region", ["Punjab", "Haryana"])
@pytest.mark.parametrize("page", PAGES)
def test_page_renders_with_real_data(page, region):
    at = _run(page, region)
    assert not at.exception, at.exception
    text = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
    assert "Processed data not found" not in " ".join(w.value for w in at.warning)
    assert text  # something rendered


@pytest.mark.parametrize("page", [p for p in PAGES if p != "historical_map"])
def test_missing_outputs_show_pipeline_command(page, no_outputs):
    at = _run(page)
    assert not at.exception, at.exception
    assert any("Processed data not found" in w.value for w in at.warning)
    assert any("run_pipeline" in c.value for c in at.code)


def test_map_missing_detections_shows_empty_state(no_outputs):
    at = _run("historical_map")
    assert not at.exception, at.exception
    msgs = [w.value for w in at.warning] + [e.value for e in at.error]
    assert any("Processed data not found" in m or "boundary" in m.lower() for m in msgs)


def test_map_missing_boundary_never_substitutes_rectangle(tmp_path, monkeypatch):
    import services.region_service as rs
    monkeypatch.setattr(rs, "REGION_BOUNDARY_FILES",
                        {"Punjab": tmp_path / "punjab.geojson", "Haryana": tmp_path / "haryana.geojson"})
    at = _run("historical_map")
    assert not at.exception, at.exception
    assert any("boundary files are missing" in e.value and "never substituted" in e.value
               for e in at.error)
    assert not at.get("deck_gl_json_chart")  # no map drawn
