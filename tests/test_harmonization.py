"""Seasonal calibration and harmonized series (synthetic data)."""
import numpy as np
import pandas as pd
import pytest

from processing.harmonize import (
    FLAG_ESTIMATED,
    FLAG_NO_FACTOR,
    FLAG_PARTIAL_PLATFORM,
    FLAG_PARTIAL_VIIRS,
    FLAG_TERRA_ONLY,
    FLAG_VIIRS,
    calibration_factors,
    harmonize,
    training_pairs,
)
from tests.phase5_fixtures import make_totals


def test_training_window_is_feb2012_to_dec2022():
    p = training_pairs(make_totals())
    keys = p["year"] * 100 + p["month"]
    assert keys.min() == 201202 and keys.max() == 202212   # Jan 2012 partial excluded


def test_factors_recover_known_ratio_per_region():
    f = calibration_factors(training_pairs(make_totals()))
    assert len(f) == 24
    for region in ("Punjab", "Haryana"):
        got = f[f.region == region].set_index("calendar_month")["calibration_factor"]
        assert got.to_dict() == pytest.approx({m: float(m) for m in range(1, 13)})


def test_region_specific_factors():
    t = make_totals()
    t.loc[t.region == "Haryana", "viirs_snpp_count"] *= 2
    f = calibration_factors(training_pairs(t)).set_index(["region", "calendar_month"])
    assert f.loc[("Haryana", 3), "calibration_factor"] == pytest.approx(
        2 * f.loc[("Punjab", 3), "calibration_factor"])


def test_zero_modis_handled_and_insufficient_pairs_reported():
    t = make_totals()
    t.loc[t.month == 7, "modis_combined_count"] = 0      # would divide by zero
    pairs = training_pairs(t)
    assert pairs.loc[pairs.month == 7, "ratio"].isna().all()
    assert (pairs.loc[pairs.month == 7, "exclusion_reason"] == "MODIS count < 5").all()
    f = calibration_factors(pairs).set_index(["region", "calendar_month"])
    assert np.isnan(f.loc[("Punjab", 7), "calibration_factor"])
    assert f.loc[("Punjab", 7), "validation_status"] == "unavailable"
    assert "0 valid year pairs" in f.loc[("Punjab", 7), "unavailable_reason"]
    assert f.loc[("Punjab", 8), "validation_status"] == "available"   # others unaffected


def test_harmonized_series_uses_estimate_then_reference():
    t = make_totals()
    h = harmonize(t, calibration_factors(training_pairs(t)))
    p = h[h.region == "Punjab"].set_index(["year", "month"])
    est = p.loc[(2011, 5)]
    assert est.source_flag == FLAG_ESTIMATED and est.is_estimated
    assert est.harmonized_activity == pytest.approx(100 * 5.0)       # M x r_m
    ref = p.loc[(2015, 5)]
    assert ref.source_flag == FLAG_VIIRS and not ref.is_estimated
    assert ref.harmonized_activity == ref.viirs_snpp_count            # H = V, not M + V
    assert np.isnan(ref.calibration_factor)
    jan12 = p.loc[(2012, 1)]
    assert jan12.source_flag == FLAG_PARTIAL_VIIRS and jan12.is_partial_month
    assert np.isnan(jan12.harmonized_activity)


def test_terra_only_and_partial_platform_not_harmonized():
    t = make_totals()
    sel = (t.year == 2010) & (t.month == 1)
    t.loc[sel, ["modis_aqua_count", "modis_combined_count"]] = np.nan
    t.loc[sel, "modis_combined_coverage"] = "terra_only"
    sel2 = (t.year == 2010) & (t.month == 2)
    t.loc[sel2, "modis_combined_coverage"] = "partial"
    h = harmonize(t, calibration_factors(training_pairs(t))).set_index(["region", "year", "month"])
    assert h.loc[("Punjab", 2010, 1), "source_flag"] == FLAG_TERRA_ONLY
    assert np.isnan(h.loc[("Punjab", 2010, 1), "harmonized_activity"])
    assert h.loc[("Punjab", 2010, 2), "source_flag"] == FLAG_PARTIAL_PLATFORM
    assert np.isnan(h.loc[("Punjab", 2010, 2), "harmonized_activity"])


def test_missing_factor_gives_no_estimate():
    t = make_totals()
    t.loc[(t.month == 7) & (t.year >= 2012), "modis_combined_count"] = 0
    h = harmonize(t, calibration_factors(training_pairs(t))).set_index(["region", "year", "month"])
    row = h.loc[("Punjab", 2011, 7)]
    assert row.source_flag == FLAG_NO_FACTOR and np.isnan(row.harmonized_activity)


def test_no_extrapolation_after_viirs_ends():
    t = make_totals(years=range(2010, 2014))
    last = (t.year == 2013) & (t.month == 12)
    t.loc[last, "viirs_snpp_count"] = np.nan
    t.loc[last, "viirs_snpp_coverage"] = "none"
    t.loc[last, "modis_combined_coverage"] = "partial"
    h = harmonize(t, calibration_factors(training_pairs(t, min_detections=5), min_pairs=1))
    row = h[(h.region == "Punjab") & (h.year == 2013) & (h.month == 12)].iloc[0]
    assert row.source_flag == "modis_only_after_reference"
    assert np.isnan(row.harmonized_activity) and row.is_partial_month
