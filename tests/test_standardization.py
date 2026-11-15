"""Schema standardization (synthetic data)."""
import pandas as pd

from processing.clean_data import apply_confidence_policy
from processing.standardize import satellite_date_coverage, standardize


def _raw(rows):
    cols = ["latitude", "longitude", "brightness", "scan", "track", "acq_date", "acq_time",
            "satellite", "instrument", "confidence", "version", "bright_t31", "frp",
            "daynight", "type"]
    return pd.DataFrame(rows, columns=cols).astype("string")


MODIS = _raw([
    ["30.5", "75.5", "310", "1", "1", "2002-07-18", "637", "Aqua", "MODIS", "50", "6.03", "290", "10", "D", "0"],
    ["30.5", "75.5", "310", "1", "1", "2002-07-18", "0005", "Terra", "MODIS", "10", "61.03", "290", "5", "N", "2"],
    ["30.5", "75.5", "310", "1", "1", "2002-07-19", "1200", "Terra", "MODIS", "90", "6.03", "290", "7", "D", "1"],
])


def test_standardize_fields():
    df, warnings = standardize(MODIS, "MODIS")
    assert df["acq_time"].tolist() == ["0637", "0005", "1200"]
    assert str(df["acq_datetime_utc"].iloc[0]) == "2002-07-18 06:37:00+00:00"
    assert df["year"].tolist() == [2002] * 3 and df["month"].tolist() == [7] * 3
    assert df["satellite"].astype(str).tolist() == ["Aqua", "Terra", "Terra"]
    assert df["version"].astype(str).tolist() == ["6.03", "61.03", "6.03"]
    assert df["confidence_raw"].tolist() == ["50", "10", "90"]
    assert df["confidence_class"].astype(str).tolist() == ["nominal", "low", "high"]
    assert df["detection_type_label"].astype(str).tolist() == [
        "Presumed vegetation fire", "Other static land source", "Active volcano"]
    assert warnings == []


def test_viirs_satellite_alias_and_unknown_type_preserved():
    raw = _raw([["30", "75", "300", "0.4", "0.4", "2012-01-20", "0729", "SNPP", "SNPP",
                 "n", "2", "290", "3", "D", "7"]])
    df, warnings = standardize(raw, "VIIRS")
    assert df["satellite"].astype(str).iloc[0] == "Suomi-NPP"
    assert df["satellite_raw"].astype(str).iloc[0] == "SNPP"
    assert int(df["detection_type"].iloc[0]) == 7
    assert df["detection_type_label"].astype(str).iloc[0] == "Unknown (7)"
    assert any("unknown detection types" in w for w in warnings)


def test_unknown_satellite_reported():
    raw = MODIS.copy()
    raw.loc[0, "satellite"] = "X"
    df, warnings = standardize(raw, "MODIS")
    assert df["satellite"].astype(str).iloc[0] == "Unknown (X)"
    assert any("unknown satellite" in w for w in warnings)


def test_confidence_policy_counts_and_types_retained():
    df, _ = standardize(MODIS, "MODIS")
    kept, stats = apply_confidence_policy(df)
    assert stats["MODIS"] == {"input": 3, "retained": 2, "excluded_low_confidence": 1,
                              "excluded_unknown_confidence": 0}
    # All detection types are retained by the policy; only confidence filters.
    assert sorted(kept["detection_type"].tolist()) == [0, 1]


def test_satellite_coverage_from_data():
    df, _ = standardize(MODIS, "MODIS")
    cov = satellite_date_coverage(df)
    assert cov["Terra"][0] == pd.Timestamp("2002-07-18")
    assert cov["Terra"][1] == pd.Timestamp("2002-07-19")
