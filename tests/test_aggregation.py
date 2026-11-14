"""Monthly aggregation, coverage flags and the common grid (synthetic data)."""
import numpy as np
import pandas as pd
import pytest

from processing.aggregate import (
    assign_grid_cells,
    detection_type_breakdown,
    monthly_region_totals,
    monthly_sensor_counts,
    validate_projection,
)
from processing.coverage import monthly_coverage, observation_gaps


def _det(region, date, sat, dtype=0, sensor=None, lat=30.5, lon=75.5):
    sensor = sensor or ("VIIRS" if sat == "Suomi-NPP" else "MODIS")
    d = pd.Timestamp(date)
    return {"region": region, "sensor": sensor, "satellite": sat, "acq_date": d,
            "year": d.year, "month": d.month, "detection_type": dtype,
            "latitude": lat, "longitude": lon, "frp": 1.0}


# Terra from 2002-06-01, Aqua from 2002-07-18, VIIRS from 2002-08-15 (synthetic).
COVERAGE = {"Terra": (pd.Timestamp("2002-06-01"), pd.Timestamp("2002-09-30")),
            "Aqua": (pd.Timestamp("2002-07-18"), pd.Timestamp("2002-09-30")),
            "Suomi-NPP": (pd.Timestamp("2002-08-15"), pd.Timestamp("2002-09-30"))}


@pytest.fixture
def detections():
    rows = [
        _det("Punjab", "2002-06-10", "Terra"),
        _det("Punjab", "2002-07-20", "Terra"), _det("Punjab", "2002-07-21", "Aqua"),
        _det("Punjab", "2002-08-01", "Terra"), _det("Punjab", "2002-08-02", "Terra", dtype=2),
        _det("Punjab", "2002-08-03", "Aqua"), _det("Punjab", "2002-08-20", "Suomi-NPP"),
        _det("Haryana", "2002-08-05", "Aqua"),
        _det("Punjab", "2002-09-03", "Suomi-NPP"),
    ]
    return pd.DataFrame(rows)


@pytest.fixture
def coverage():
    return monthly_coverage(COVERAGE, pd.Period("2002-06"), pd.Period("2002-09"))


def _row(t, region, month):
    return t[(t.region == region) & (t.month == month)].iloc[0]


def test_coverage_status(coverage):
    c = coverage.set_index(["satellite", "month"])["coverage_status"]
    assert c[("Terra", 6)] == "complete"
    assert c[("Aqua", 6)] == "none"
    assert c[("Aqua", 7)] == "partial"
    assert c[("Aqua", 8)] == "complete"
    assert c[("Suomi-NPP", 8)] == "partial"


def test_monthly_totals_and_combined(detections, coverage):
    t = monthly_region_totals(detections, coverage)
    aug = _row(t, "Punjab", 8)
    assert (aug.modis_terra_count, aug.modis_aqua_count) == (2, 1)
    assert aug.modis_combined_count == aug.modis_terra_count + aug.modis_aqua_count == 3
    assert aug.modis_combined_coverage == "complete"
    assert aug.viirs_snpp_coverage == "partial"


def test_terra_only_not_treated_as_combined(detections, coverage):
    jun = _row(monthly_region_totals(detections, coverage), "Punjab", 6)
    assert jun.modis_terra_count == 1
    assert pd.isna(jun.modis_aqua_count) and pd.isna(jun.modis_combined_count)
    assert jun.modis_combined_coverage == "terra_only"


def test_partial_month_flagged(detections, coverage):
    jul = _row(monthly_region_totals(detections, coverage), "Punjab", 7)
    assert jul.modis_combined_coverage == "partial"
    assert jul.modis_combined_count == 2


def test_missing_is_not_zero(detections, coverage):
    t = monthly_region_totals(detections, coverage)
    # Haryana Sep: all sensors observing, no detections -> true zeros.
    sep = _row(t, "Haryana", 9)
    assert sep.modis_terra_count == 0 and sep.viirs_snpp_count == 0
    # Haryana Jun: VIIRS not yet observing -> missing, not zero.
    assert pd.isna(_row(t, "Haryana", 6).viirs_snpp_count)


def test_regional_grouping(detections, coverage):
    t = monthly_region_totals(detections, coverage)
    assert _row(t, "Haryana", 8).modis_aqua_count == 1
    assert _row(t, "Punjab", 8).modis_aqua_count == 1


def test_monthly_sensor_counts_platform_and_type(detections):
    m = monthly_sensor_counts(detections)
    aug_terra = m[(m.region == "Punjab") & (m.month == 8) & (m.satellite == "Terra")]
    assert dict(zip(aug_terra.detection_type, aug_terra.detection_count)) == {0: 1, 2: 1}
    assert m.detection_count.sum() == len(detections)
    assert (m.confidence_policy == "nominal_high").all()


def test_type_breakdown_labels(detections):
    b = detection_type_breakdown(detections)
    assert set(b.detection_type_label) == {"Presumed vegetation fire", "Other static land source"}
    assert b.detection_count.sum() == len(detections)


def test_grid_cells_1km():
    df = pd.DataFrame({"latitude": [30.5, 30.5, 30.52], "longitude": [75.5, 75.5001, 75.5]})
    g = assign_grid_cells(df)
    assert g.cell_id.iloc[0] == g.cell_id.iloc[1]      # ~10 m apart -> same cell
    assert g.cell_id.iloc[0] != g.cell_id.iloc[2]      # ~2.2 km apart -> different cell
    assert abs(g.cell_lat.iloc[0] - 30.5) < 0.01 and abs(g.cell_lon.iloc[0] - 75.5) < 0.01


def test_projection_zone_check():
    validate_projection(np.array([73.8, 77.7]))
    with pytest.raises(ValueError):
        validate_projection(np.array([78.5]))


def test_observation_gaps():
    df = pd.DataFrame({"satellite": ["Terra"] * 3,
                       "acq_date": pd.to_datetime(["2002-01-01", "2002-01-02", "2002-02-15"])})
    gaps = observation_gaps(df, min_gap_days=20)
    assert gaps == [{"satellite": "Terra", "last_detection_before": "2002-01-02",
                     "next_detection": "2002-02-15", "days_without_detection": 43}]
