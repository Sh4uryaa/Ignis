"""CSV exports: filenames, region filtering and preserved columns."""
import io

import pandas as pd
import pytest

from components.data_export import export_filename
from config.settings import PROCESSED_DIR
from processing.build_outputs import OUTPUT_FILES
from services.analytics_service import between_years, for_region


def test_export_filenames():
    assert export_filename("Punjab", "harmonized") == "ignis_punjab_harmonized_history.csv"
    assert export_filename("Haryana", "validation") == "ignis_haryana_validation_results.csv"
    assert export_filename("Punjab", "calibration_factors") == "ignis_punjab_calibration_factors.csv"
    assert export_filename("Punjab", "harmonized", (2005, 2010)) == \
        "ignis_punjab_harmonized_history_2005-2010.csv"


def test_region_and_year_filters_on_synthetic_frame():
    df = pd.DataFrame({"region": ["Punjab", "Haryana", "Punjab"], "year": [2004, 2004, 2020],
                       "x": [1, 2, 3]})
    p = between_years(for_region(df, "Punjab"), 2000, 2010)
    assert p["x"].tolist() == [1]


REQUIRED_COLUMNS = {
    "harmonized_monthly": {"region", "year", "month", "modis_terra_count", "modis_aqua_count",
                           "modis_combined_count", "viirs_snpp_count", "harmonized_activity",
                           "calibration_factor", "source_flag", "is_estimated",
                           "is_partial_month", "confidence_policy"},
    "calibration_factors": {"region", "calendar_month", "calibration_factor",
                            "pooled_ratio_diagnostic", "training_start", "training_end",
                            "valid_training_pairs", "minimum_detection_threshold", "method",
                            "validation_status"},
    "uncertainty_intervals": {"region", "year", "month", "harmonized_estimate", "lower_bound",
                              "upper_bound", "interval_level", "interval_method",
                              "valid_training_pairs", "uncertainty_scope"},
    "monthly_sensor_counts": {"region", "year", "month", "sensor", "satellite", "detection_type",
                              "confidence_policy", "detection_count"},
    "validation_results": {"region", "year", "month", "actual_viirs_count",
                           "modis_combined_count", "predicted_viirs_equivalent", "raw_error",
                           "calibrated_error", "calibration_factor"},
    "detection_type_breakdown": {"region", "sensor", "satellite", "detection_type",
                                 "detection_type_label", "confidence_policy", "detection_count"},
    "calibrated_modis": {"region", "year", "month", "modis_combined_count", "viirs_snpp_count",
                         "calibration_factor", "calibrated_modis", "comparison_period",
                         "is_complete_overlap", "absolute_error", "relative_error_pct",
                         "confidence_policy"},
    "anomaly_results": {"region", "year", "month", "harmonized_activity", "historical_median",
                        "anomaly_abs", "anomaly_pct", "anomaly_label", "source_flag"},
}

real = pytest.mark.skipif(not (PROCESSED_DIR / OUTPUT_FILES["harmonized_monthly"]).exists(),
                          reason="processed outputs not generated")


@real
@pytest.mark.parametrize("key", sorted(REQUIRED_COLUMNS))
def test_processed_outputs_follow_contract(key):
    df = pd.read_csv(PROCESSED_DIR / OUTPUT_FILES[key])
    assert REQUIRED_COLUMNS[key] <= set(df.columns)


@real
@pytest.mark.parametrize("key", sorted(REQUIRED_COLUMNS))
def test_region_export_round_trips_exactly(key):
    """An exported region CSV equals the processed rows for that region."""
    df = pd.read_csv(PROCESSED_DIR / OUTPUT_FILES[key])
    for region in ("Punjab", "Haryana"):
        sub = for_region(df, region)
        assert set(sub["region"]) == {region}
        back = pd.read_csv(io.StringIO(sub.to_csv(index=False)))
        pd.testing.assert_frame_equal(back.reset_index(drop=True),
                                      df[df["region"] == region].reset_index(drop=True),
                                      check_dtype=False)


@real
def test_uncertainty_only_on_estimated_months():
    h = pd.read_csv(PROCESSED_DIR / OUTPUT_FILES["harmonized_monthly"])
    u = pd.read_csv(PROCESSED_DIR / OUTPUT_FILES["uncertainty_intervals"])
    m = u.merge(h, on=["region", "year", "month"])
    assert m["is_estimated"].all()
    assert (m["source_flag"] == "estimated_from_modis").all()


@real
def test_monthly_counts_consistent_between_outputs():
    """Per-satellite sums in monthly_sensor_counts equal monthly_region_totals."""
    c = pd.read_csv(PROCESSED_DIR / OUTPUT_FILES["monthly_sensor_counts"])
    t = pd.read_csv(PROCESSED_DIR / OUTPUT_FILES["monthly_region_totals"])
    s = c.groupby(["region", "year", "month", "satellite"])["detection_count"].sum().unstack()
    t = t.set_index(["region", "year", "month"])
    for sat, col in (("Terra", "modis_terra_count"), ("Aqua", "modis_aqua_count"),
                     ("Suomi-NPP", "viirs_snpp_count")):
        joined = s[sat].dropna().to_frame("a").join(t[col])
        assert (joined["a"] == joined[col]).all()
    combined = t["modis_combined_count"].dropna()
    assert (combined == t.loc[combined.index, "modis_terra_count"]
            + t.loc[combined.index, "modis_aqua_count"]).all()
