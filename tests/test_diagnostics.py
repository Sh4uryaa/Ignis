"""Overpass-time diagnostic (synthetic data)."""
import pandas as pd

from processing.diagnostics import overpass_times


def test_overpass_times_median_and_shift():
    rows = []
    for year, hhmm in [(2010, "0815"), (2011, "0815"), (2025, "0945")]:
        rows += [{"satellite": "Aqua", "year": year, "acq_time": hhmm, "daynight": "D"}] * 3
    rows.append({"satellite": "Aqua", "year": 2025, "acq_time": "2000", "daynight": "N"})  # ignored
    out = overpass_times(pd.DataFrame(rows)).set_index("year")
    assert out.loc[2010, "median_hour_utc"] == 8.25
    assert out.loc[2010, "median_time_ist"] == "13:45"
    assert out.loc[2025, "daytime_detections"] == 3
    assert out.loc[2025, "shift_vs_early_years_min"] == 90
