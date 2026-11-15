"""Page data preparation (synthetic data)."""
import numpy as np
import pandas as pd

from services.analytics_service import (
    deterministic_sample,
    filter_detections,
    grid_cell_counts,
    harmonized_record_summary,
    latest_complete_common_month,
    seasonal_summary,
)


def _det(n=100):
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "region": pd.Categorical(["Punjab"] * (n // 2) + ["Haryana"] * (n - n // 2)),
        "satellite": pd.Categorical(rng.choice(["Terra", "Aqua", "Suomi-NPP"], n)),
        "acq_date": pd.to_datetime("2020-01-01") + pd.to_timedelta(rng.integers(0, 60, n), "D"),
        "acq_datetime_utc": pd.to_datetime("2020-01-01", utc=True)
                            + pd.to_timedelta(np.arange(n), "h"),
        "detection_type": rng.choice([0, 2], n),
        "latitude": rng.uniform(30, 31, n), "longitude": rng.uniform(75, 76, n),
        "cell_id": rng.choice(["a", "b", "c"], n),
        "cell_lat": 30.5, "cell_lon": 75.5,
    })


def test_filter_detections_by_region_date_sensor_type():
    d = _det()
    out = filter_detections(d, "Punjab", pd.Timestamp("2020-01-10"), pd.Timestamp("2020-02-10"),
                            "MODIS combined (Terra + Aqua)", [0])
    assert set(out["region"]) <= {"Punjab"}
    assert set(out["satellite"]) <= {"Terra", "Aqua"}
    assert set(out["detection_type"]) <= {0}
    assert out["acq_date"].between("2020-01-10", "2020-02-10").all()
    allm = filter_detections(d, "Punjab", pd.Timestamp("2019-01-01"), pd.Timestamp("2021-01-01"),
                             "All sensors", None)
    terra = filter_detections(d, "Punjab", pd.Timestamp("2019-01-01"), pd.Timestamp("2021-01-01"),
                              "MODIS Terra", None)
    aqua = filter_detections(d, "Punjab", pd.Timestamp("2019-01-01"), pd.Timestamp("2021-01-01"),
                             "MODIS Aqua", None)
    comb = filter_detections(d, "Punjab", pd.Timestamp("2019-01-01"), pd.Timestamp("2021-01-01"),
                             "MODIS combined (Terra + Aqua)", None)
    assert len(comb) == len(terra) + len(aqua) <= len(allm)


def test_deterministic_sample_is_repeatable_and_bounded():
    d = _det(1000)
    s1, k = deterministic_sample(d, 100)
    s2, _ = deterministic_sample(d, 100)
    assert k == 10 and len(s1) <= 100
    pd.testing.assert_frame_equal(s1, s2)
    same, k1 = deterministic_sample(d, 5000)
    assert k1 == 1 and len(same) == 1000


def test_grid_cell_counts_preserve_total():
    d = _det(300)
    g = grid_cell_counts(d)
    assert g["count"].sum() == 300


def _h():
    rows = []
    for y in (2011, 2012, 2013):
        for m in range(1, 13):
            flag = ("estimated_from_modis" if y == 2011 else
                    "partial_viirs_month" if (y, m) == (2012, 1) else "viirs_reference")
            rows.append({"region": "Punjab", "year": y, "month": m, "source_flag": flag,
                         "harmonized_activity": np.nan if flag == "partial_viirs_month" else m * 10.0,
                         "modis_combined_coverage": "complete",
                         "viirs_snpp_coverage": "none" if y == 2011 else
                         ("partial" if (y, m) == (2012, 1) else "complete")})
    return pd.DataFrame(rows)


def test_record_summary_and_latest_month():
    h = _h()
    s = harmonized_record_summary(h)
    assert s["estimated_months"] == 12 and s["observed_months"] == 23 and s["excluded_months"] == 1
    assert latest_complete_common_month(h, "Punjab") == (2013, 12)


def test_seasonal_summary_excludes_partial():
    s = seasonal_summary(_h()).set_index("month")
    assert s.loc[1, "years"] == 2       # Jan 2012 partial excluded
    assert s.loc[5, "median"] == 50.0
