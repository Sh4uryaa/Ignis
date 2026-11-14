"""Confidence classification and Nominal + High policy (synthetic data)."""
import pandas as pd
import pytest

from processing.clean_data import (
    classify_modis_confidence,
    classify_viirs_confidence,
    passes_confidence_policy,
)


def test_modis_low_excluded_nominal_high_included():
    conf = pd.Series([str(v) for v in range(0, 101)], dtype="string")
    mask = passes_confidence_policy("MODIS", conf)
    assert not mask.iloc[:30].any()        # 0-29 excluded
    assert mask.iloc[30:].all()            # 30-100 included
    assert int(mask.sum()) == 71


def test_modis_class_boundaries():
    conf = pd.Series(["0", "29", "30", "79", "80", "100"])
    assert classify_modis_confidence(conf).tolist() == [
        "low", "low", "nominal", "nominal", "high", "high"]


def test_modis_invalid_values_are_unknown_not_dropped():
    conf = pd.Series(["abc", "101", "-1", None], dtype="string")
    assert (classify_modis_confidence(conf) == "unknown").all()
    assert not passes_confidence_policy("MODIS", conf).any()


def test_viirs_policy():
    conf = pd.Series(["l", "n", "h", "x"], dtype="string")
    assert passes_confidence_policy("VIIRS", conf).tolist() == [False, True, True, False]
    assert classify_viirs_confidence(conf).tolist() == ["low", "nominal", "high", "unknown"]


def test_unknown_sensor_raises():
    with pytest.raises(ValueError):
        passes_confidence_policy("GOES", pd.Series(["n"]))
