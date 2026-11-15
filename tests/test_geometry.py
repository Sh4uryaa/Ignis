"""Region assignment and boundary handling (synthetic squares only)."""
import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import box

from config.settings import OUTSIDE_REGION_LABEL, REGION_BOUNDARY_FILES
from processing.geo_filter import (
    BoundaryError,
    assign_regions,
    download_area_coverage,
    load_region_boundaries,
    select_states,
    validate_boundaries,
)


@pytest.fixture
def boundaries():
    # Punjab: lon 74-75, lat 30-31. Haryana: lon 75-76, lat 29-30 (touch at a corner).
    return gpd.GeoDataFrame({"region": ["Punjab", "Haryana"]},
                            geometry=[box(74, 30, 75, 31), box(75, 29, 76, 30)],
                            crs="EPSG:4326")


def test_points_assigned_to_correct_state(boundaries):
    lat = np.array([30.5, 29.5, 28.0, 30.5])
    lon = np.array([74.5, 75.5, 74.5, 75.5])
    labels = assign_regions(lat, lon, boundaries)
    assert labels.tolist() == ["Punjab", "Haryana", OUTSIDE_REGION_LABEL, OUTSIDE_REGION_LABEL]


def test_border_point_counted_once(boundaries):
    labels = assign_regions(np.array([30.0]), np.array([75.0]), boundaries)  # shared corner
    assert labels.tolist() == ["Punjab"]


def test_validate_requires_epsg4326(boundaries):
    with pytest.raises(BoundaryError):
        validate_boundaries(boundaries.to_crs("EPSG:32643"))


def test_validate_rejects_overlap():
    g = gpd.GeoDataFrame({"region": ["Punjab", "Haryana"]},
                         geometry=[box(74, 30, 75, 31), box(74.5, 30, 75.5, 31)],
                         crs="EPSG:4326")
    with pytest.raises(BoundaryError, match="overlap"):
        validate_boundaries(g)


def test_select_states_by_iso():
    src = gpd.GeoDataFrame(
        {"shapeISO": ["IN-PB", "IN-HR", "IN-DL"], "shapeName": ["Punjab", "Haryāna", "Delhi"]},
        geometry=[box(74, 30, 75, 31), box(75, 29, 76, 30), box(77, 28, 77.3, 28.8)],
        crs="EPSG:4326")
    out = select_states(src)
    assert out["region"].tolist() == ["Punjab", "Haryana"]
    assert out.crs.to_string() == "EPSG:4326"


def test_coverage_reports_missing_area(boundaries):
    area = box(74, 29, 75.5, 31)  # covers all of Punjab, half of Haryana
    cov = download_area_coverage(boundaries, area)
    # Shared edges reproject with tiny curvature differences, hence the tolerance.
    assert cov["Punjab"]["percent_covered"] == pytest.approx(100.0, abs=0.5)
    assert cov["Haryana"]["percent_covered"] == pytest.approx(50.0, abs=1.0)


def test_missing_boundary_file_raises(tmp_path):
    with pytest.raises(BoundaryError, match="prepare_boundaries"):
        load_region_boundaries({"Punjab": tmp_path / "nope.geojson"})


@pytest.mark.skipif(not all(p.exists() for p in REGION_BOUNDARY_FILES.values()),
                    reason="real boundary files not built")
def test_real_boundaries_valid_and_epsg4326():
    b = load_region_boundaries()
    assert b.crs.to_string() == "EPSG:4326"
    diag = validate_boundaries(b)
    # Official areas: Punjab ~50,362 km2, Haryana ~44,212 km2.
    assert diag["Punjab"]["area_km2"] == pytest.approx(50_362, rel=0.01)
    assert diag["Haryana"]["area_km2"] == pytest.approx(44_212, rel=0.01)
