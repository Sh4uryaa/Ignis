"""Bootstrap calibration-factor intervals (synthetic data)."""
import numpy as np
import pandas as pd
import pytest

from processing.harmonize import calibration_factors, harmonize, training_pairs
from processing.uncertainty import bootstrap_median_interval, factor_intervals, uncertainty_intervals
from tests.phase5_fixtures import make_totals


def _noisy_totals(seed=1):
    t = make_totals()
    rng = np.random.default_rng(seed)
    ref = t.viirs_snpp_coverage == "complete"
    t.loc[ref, "viirs_snpp_count"] = (t.loc[ref, "viirs_snpp_count"]
                                      * rng.uniform(0.8, 1.2, ref.sum())).round()
    return t


def test_bootstrap_reproducible_with_seed():
    r = np.array([4.1, 4.5, 4.9, 5.2, 5.0, 4.7])
    a = bootstrap_median_interval(r, 2000, 0.95, np.random.default_rng(42))
    b = bootstrap_median_interval(r, 2000, 0.95, np.random.default_rng(42))
    assert a == b
    assert r.min() <= a[0] <= np.median(r) <= a[1] <= r.max()


def test_identical_ratios_give_zero_width():
    lo, hi = bootstrap_median_interval(np.full(7, 3.0), 500)
    assert lo == hi == 3.0


def test_factor_intervals_deterministic_and_bracket_factor():
    pairs = training_pairs(_noisy_totals())
    a, b = factor_intervals(pairs), factor_intervals(pairs)
    pd.testing.assert_frame_equal(a, b)
    f = calibration_factors(pairs).merge(a, on=["region", "calendar_month"])
    assert ((f.factor_lower <= f.calibration_factor) & (f.calibration_factor <= f.factor_upper)).all()


def test_insufficient_pairs_no_interval():
    t = _noisy_totals()
    t.loc[(t.month == 3) & (t.year >= 2016), "modis_combined_count"] = 0   # only 4 valid years
    iv = factor_intervals(training_pairs(t)).set_index(["region", "calendar_month"])
    assert np.isnan(iv.loc[("Punjab", 3), "factor_lower"])
    assert iv.loc[("Punjab", 3), "interval_status"].startswith("unavailable")


def test_intervals_only_on_estimated_months():
    t = _noisy_totals()
    pairs = training_pairs(t)
    h = harmonize(t, calibration_factors(pairs))
    u = uncertainty_intervals(h, factor_intervals(pairs))
    assert (u.year * 100 + u.month).max() < 201201          # never on VIIRS reference
    assert len(u) == int(h.is_estimated.sum())
    assert ((u.lower_bound <= u.harmonized_estimate) & (u.harmonized_estimate <= u.upper_bound)).all()
    assert (u.interval_level == 0.95).all()
    assert u.uncertainty_scope.str.contains("calibration-factor").all()
