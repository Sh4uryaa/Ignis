"""Held-out validation metrics (synthetic data)."""
import numpy as np
import pandas as pd
import pytest

from processing.harmonize import calibration_factors, training_pairs
from processing.validate import (
    error_metrics,
    pooled_constant_factors,
    validation_metrics,
    validation_months,
)
from tests.phase5_fixtures import make_totals


def test_error_metrics_formulas():
    m = error_metrics(np.array([10.0, 20.0]), np.array([12.0, 16.0]))
    assert m["mae"] == pytest.approx(3.0)
    assert m["rmse"] == pytest.approx(np.sqrt((4 + 16) / 2))
    assert m["wape_pct"] == pytest.approx(6 / 30 * 100)
    assert m["relative_bias_pct"] == pytest.approx(-2 / 30 * 100)


def test_zero_denominator_safe():
    m = error_metrics(np.array([0.0, 0.0]), np.array([1.0, 2.0]))
    assert np.isnan(m["wape_pct"]) and np.isnan(m["relative_bias_pct"])
    assert m["mae"] == pytest.approx(1.5)


def test_validation_uses_only_jan2023_to_jul2026():
    t = make_totals(years=range(2010, 2027))
    rows = validation_months(t, calibration_factors(training_pairs(t)))
    keys = rows.year * 100 + rows.month
    assert keys.min() == 202301 and keys.max() == 202607


def test_validation_excludes_partial_months():
    t = make_totals(years=range(2010, 2027))
    t.loc[(t.year == 2024) & (t.month == 6), "viirs_snpp_coverage"] = "partial"
    rows = validation_months(t, calibration_factors(training_pairs(t)))
    assert not ((rows.year == 2024) & (rows.month == 6)).any()


def test_calibration_beats_raw_on_exact_synthetic_data():
    t = make_totals(years=range(2010, 2027))
    pairs = training_pairs(t)
    rows = validation_months(t, calibration_factors(pairs),
                             constant_factors=pooled_constant_factors(pairs))
    met = validation_metrics(rows).set_index(["region", "comparison"])
    assert met.loc[("Punjab", "calibrated_seasonal"), "wape_pct"] == pytest.approx(0.0)
    assert met.loc[("Punjab", "raw_modis"), "wape_pct"] > 0
    assert bool(met.loc[("Punjab", "calibrated_seasonal"), "improves_on_raw_wape"])
    assert pd.isna(met.loc[("Punjab", "raw_modis"), "improves_on_raw_wape"])


def test_worse_calibration_is_reported_not_hidden():
    t = make_totals(years=range(2010, 2027), ratio_by_month={m: 1.0 for m in range(1, 13)})
    # Validation-period VIIRS equals MODIS, but training says ratio = 3.
    t.loc[t.year <= 2022, "viirs_snpp_count"] = t.loc[t.year <= 2022, "viirs_snpp_count"] * 3
    rows = validation_months(t, calibration_factors(training_pairs(t)))
    met = validation_metrics(rows).set_index(["region", "comparison"])
    assert not bool(met.loc[("Punjab", "calibrated_seasonal"), "improves_on_raw_wape"])


def test_leave_one_year_out_never_uses_held_out_year():
    from processing.validate import leave_one_year_out
    t = make_totals(years=range(2010, 2023))
    # Corrupt one year: if it leaked into its own fit, its error would shrink.
    t.loc[t.year == 2015, "viirs_snpp_count"] *= 3
    rows = leave_one_year_out(training_pairs(t), 2012, 2021)
    assert sorted(rows.held_out_year.unique()) == list(range(2012, 2022))
    y15 = rows[rows.held_out_year == 2015]
    # Factors fitted on the other (clean) years predict exactly 1/3 of the corrupted VIIRS.
    assert (y15.predicted_viirs_equivalent * 3 == y15.actual_viirs_count).all()
    clean = rows[rows.held_out_year == 2018]
    assert (clean.calibrated_error.abs() < 1e-9).all()
    met = validation_metrics(rows, period=("2012", "2021"), validation_type="supplementary")
    assert (met.validation_type == "supplementary").all()
