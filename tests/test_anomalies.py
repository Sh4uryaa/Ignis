"""Same-month anomalies (synthetic data)."""
import numpy as np
import pandas as pd
import pytest

from processing.calculate_anomalies import ABOVE, BELOW, NEAR, anomaly_label, calculate_anomalies


def _harmonized(values_by_year, month=11, flag="viirs_reference", region="Punjab"):
    return pd.DataFrame([{"region": region, "year": y, "month": month, "harmonized_activity": v,
                          "is_estimated": flag == "estimated_from_modis", "source_flag": flag}
                         for y, v in values_by_year.items()])


def test_same_month_leave_one_out_median():
    h = pd.concat([_harmonized({2015 + i: 100.0 for i in range(6)} | {2021: 300.0}),
                   _harmonized({2015 + i: 5.0 for i in range(7)}, month=6)])
    a = calculate_anomalies(h).set_index(["month", "year"])
    row = a.loc[(11, 2021)]
    assert row.historical_median == 100.0          # November only, 2021 excluded
    assert row.anomaly_abs == 200.0 and row.anomaly_pct == pytest.approx(200.0)
    assert row.anomaly_label == ABOVE
    assert a.loc[(6, 2015), "historical_median"] == 5.0   # June uses June history


def test_partial_and_unharmonized_months_excluded():
    h = pd.concat([_harmonized({2015 + i: 100.0 for i in range(6)}),
                   _harmonized({2030: 999.0}, flag="partial_viirs_month"),
                   _harmonized({2031: np.nan}, flag="terra_only_unharmonized")])
    a = calculate_anomalies(h)
    assert set(a.year) == set(range(2015, 2021))


def test_zero_baseline_safe():
    h = _harmonized({2015 + i: 0.0 for i in range(6)} | {2021: 4.0})
    a = calculate_anomalies(h).set_index("year")
    assert np.isnan(a.loc[2021, "anomaly_pct"])
    assert a.loc[2021, "anomaly_label"] == ABOVE
    assert a.loc[2015, "anomaly_label"] == NEAR


def test_too_few_baseline_years():
    a = calculate_anomalies(_harmonized({2015: 1.0, 2016: 2.0, 2017: 3.0}))
    assert a.historical_median.isna().all()
    assert (a.anomaly_label == "Insufficient baseline").all()


def test_labels():
    assert anomaly_label(130, 100, 30) == ABOVE
    assert anomaly_label(110, 100, 10) == NEAR
    assert anomaly_label(70, 100, -30) == BELOW
