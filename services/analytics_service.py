"""Page-level data preparation on top of processed outputs.

Pure pandas (no Streamlit) so it can be unit-tested. No scientific
calculation happens here — values come from the pipeline outputs; this
module only filters, reshapes and summarises them for display.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from config.settings import MODIS_PLATFORMS, VIIRS_PLATFORM_LABEL
from processing.harmonize import FLAG_DESCRIPTIONS, FLAG_ESTIMATED, FLAG_VIIRS
from utils.dates import MONTH_NAMES

SENSOR_OPTIONS: dict[str, tuple[str, ...]] = {
    "MODIS combined (Terra + Aqua)": MODIS_PLATFORMS,
    "MODIS Terra": ("Terra",),
    "MODIS Aqua": ("Aqua",),
    "VIIRS Suomi-NPP": (VIIRS_PLATFORM_LABEL,),
    "All sensors": (*MODIS_PLATFORMS, VIIRS_PLATFORM_LABEL),
}

STATUS_SHORT: dict[str, str] = {
    "terra_only_unharmonized": "Terra-only (not harmonized)",
    "partial_modis_platform_coverage": "Partial platform coverage",
    FLAG_ESTIMATED: "Estimated",
    "estimate_unavailable_no_factor": "No calibration factor",
    "partial_viirs_month": "Partial VIIRS month",
    FLAG_VIIRS: "Observed (VIIRS)",
    "modis_only_after_reference": "MODIS-only (after VIIRS ends)",
    "no_observations": "No observations",
}


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------
def for_region(df: pd.DataFrame, region: str) -> pd.DataFrame:
    return df[df["region"] == region].copy()


def with_date(df: pd.DataFrame) -> pd.DataFrame:
    """Add a month-start ``date`` column from year/month."""
    out = df.copy()
    out["date"] = pd.to_datetime(dict(year=out["year"], month=out["month"], day=1))
    return out


def between_years(df: pd.DataFrame, start: int, end: int) -> pd.DataFrame:
    return df[(df["year"] >= start) & (df["year"] <= end)]


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------
def latest_complete_common_month(totals: pd.DataFrame, region: str) -> tuple[int, int] | None:
    """Latest month where combined MODIS and VIIRS both have complete coverage."""
    t = totals[(totals["region"] == region) & (totals["modis_combined_coverage"] == "complete")
               & (totals["viirs_snpp_coverage"] == "complete")]
    if t.empty:
        return None
    last = t.sort_values(["year", "month"]).iloc[-1]
    return int(last["year"]), int(last["month"])


def sensor_totals(totals: pd.DataFrame, region: str) -> dict[str, float]:
    """Total retained detections per platform for a region (all months)."""
    t = totals[totals["region"] == region]
    return {
        "terra": float(t["modis_terra_count"].sum()),
        "aqua": float(t["modis_aqua_count"].sum()),
        "modis_combined": float(t["modis_terra_count"].sum() + t["modis_aqua_count"].sum()),
        "viirs": float(t["viirs_snpp_count"].sum()),
    }


def harmonized_record_summary(h: pd.DataFrame) -> dict[str, object]:
    """Counts of estimated / observed / excluded months in a region's series."""
    est = h[h["source_flag"] == FLAG_ESTIMATED]
    obs = h[h["source_flag"] == FLAG_VIIRS]
    usable = pd.concat([est, obs]).sort_values(["year", "month"])
    return {
        "estimated_months": int(len(est)),
        "observed_months": int(len(obs)),
        "excluded_months": int(len(h) - len(est) - len(obs)),
        "first": (int(usable.iloc[0]["year"]), int(usable.iloc[0]["month"])) if len(usable) else None,
        "last": (int(usable.iloc[-1]["year"]), int(usable.iloc[-1]["month"])) if len(usable) else None,
    }


def seasonal_summary(h: pd.DataFrame) -> pd.DataFrame:
    """Median harmonized activity per calendar month (complete months only)."""
    u = h[h["source_flag"].isin([FLAG_ESTIMATED, FLAG_VIIRS])]
    g = u.groupby("month")["harmonized_activity"]
    out = pd.DataFrame({"median": g.median(), "years": g.size()}).reindex(range(1, 13))
    out["month_name"] = list(MONTH_NAMES)
    return out.reset_index()


def type_distribution(breakdown: pd.DataFrame, region: str) -> pd.DataFrame:
    """Total detections by sensor and detection type for a region."""
    b = breakdown[breakdown["region"] == region]
    return (b.groupby(["sensor", "detection_type", "detection_type_label"])["detection_count"]
            .sum().reset_index().sort_values(["sensor", "detection_type"]))


def coverage_timeline(report: dict) -> pd.DataFrame:
    """Observation record per satellite from the quality report."""
    cov = report.get("satellite_observation_coverage", {})
    rows = [{"satellite": s, "start": pd.Timestamp(v[0]), "end": pd.Timestamp(v[1])}
            for s, v in cov.items()]
    order = {"Terra": 0, "Aqua": 1, VIIRS_PLATFORM_LABEL: 2}
    return pd.DataFrame(rows).sort_values("satellite", key=lambda s: s.map(order))


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------
def calendar_frame(h: pd.DataFrame, unc: pd.DataFrame) -> pd.DataFrame:
    """Harmonized rows enriched with interval bounds and a short status."""
    u = unc[["region", "year", "month", "lower_bound", "upper_bound"]]
    out = h.merge(u, on=["region", "year", "month"], how="left")
    out["status"] = out["source_flag"].map(STATUS_SHORT).fillna(out["source_flag"])
    out["status_long"] = out["source_flag"].map(FLAG_DESCRIPTIONS).fillna(out["source_flag"])
    return out


def calendar_matrix(frame: pd.DataFrame, value: str) -> pd.DataFrame:
    """Year × month pivot of one column (rows: years ascending, cols 1-12)."""
    years = range(int(frame["year"].min()), int(frame["year"].max()) + 1)
    return (frame.pivot_table(index="year", columns="month", values=value, aggfunc="first",
                              dropna=False)
            .reindex(index=years, columns=range(1, 13)))


def month_record(frame: pd.DataFrame, year: int, month: int) -> dict | None:
    r = frame[(frame["year"] == year) & (frame["month"] == month)]
    return None if r.empty else r.iloc[0].to_dict()


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------
def filter_detections(det: pd.DataFrame, region: str, start: pd.Timestamp, end: pd.Timestamp,
                      sensor_option: str, types: list[int] | None) -> pd.DataFrame:
    """Region, date window, sensor and detection-type filter (no sampling)."""
    sats = SENSOR_OPTIONS[sensor_option]
    m = ((det["region"] == region) & (det["acq_date"] >= start) & (det["acq_date"] <= end)
         & det["satellite"].isin(sats))
    if types is not None:
        m &= det["detection_type"].isin(types)
    return det.loc[m]


def deterministic_sample(df: pd.DataFrame, max_points: int) -> tuple[pd.DataFrame, int]:
    """Every k-th row in acquisition order; returns (sample, k). k=1 means no sampling."""
    if len(df) <= max_points:
        return df, 1
    k = math.ceil(len(df) / max_points)
    ordered = df.sort_values(["acq_datetime_utc", "latitude", "longitude"], kind="mergesort")
    return ordered.iloc[::k], k


def map_records(df: pd.DataFrame, colors: dict[str, list[int]]) -> pd.DataFrame:
    """Columns needed by the PyDeck point layer, with tooltip-ready strings."""
    out = pd.DataFrame({
        "lon": df["longitude"].to_numpy(),
        "lat": df["latitude"].to_numpy(),
        "date": df["acq_date"].dt.strftime("%Y-%m-%d").to_numpy(),
        "time": (df["acq_time"].astype(str).str[:2] + ":" + df["acq_time"].astype(str).str[2:]
                 + " UTC").to_numpy(),
        "sensor": df["sensor"].astype(str).to_numpy(),
        "satellite": df["satellite"].astype(str).to_numpy(),
        "dtype": (df["detection_type"].astype(str) + " – "
                  + df["detection_type_label"].astype(str)).to_numpy(),
        "confidence": df["confidence_raw"].astype(str).to_numpy(),
        "frp": np.where(df["frp"].notna(), df["frp"].round(1).astype(str) + " MW", "n/a"),
        "lat_s": df["latitude"].round(4).astype(str).to_numpy(),
        "lon_s": df["longitude"].round(4).astype(str).to_numpy(),
    })
    out["color"] = [colors.get(s, [200, 200, 200, 200]) for s in out["sensor"]]
    return out


def grid_cell_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate filtered detections to common 1 km grid cells (lon, lat, count)."""
    g = df.groupby("cell_id", observed=True).agg(lon=("cell_lon", "first"),
                                                 lat=("cell_lat", "first"),
                                                 count=("cell_id", "size"))
    return g.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Overview: one year, January–December
# ---------------------------------------------------------------------------
_COVERAGE_TEXT = {"complete": "complete month", "partial": "partial month",
                  "none": "not observing", "terra_only": "Terra only — no combined MODIS",
                  "aqua_only": "Aqua only — no combined MODIS"}


def latest_complete_year(totals: pd.DataFrame, region: str) -> int | None:
    """Latest year in which MODIS combined and VIIRS are complete in all 12 months."""
    t = totals[(totals["region"] == region) & (totals["modis_combined_coverage"] == "complete")
               & (totals["viirs_snpp_coverage"] == "complete")]
    full = t.groupby("year")["month"].nunique()
    full = full[full == 12]
    return int(full.index.max()) if not full.empty else None


_PERIOD_TEXT = {
    "historical_backcast": "before VIIRS (this is the harmonized estimate)",
    "training_in_sample": "training year — in-sample",
    "validation_out_of_sample": "held-out year — out-of-sample",
    "not_a_comparison_month": "no complete VIIRS month to compare",
}


def year_monthly_activity(totals: pd.DataFrame, harmonized: pd.DataFrame, region: str,
                          year: int, calibrated: pd.DataFrame | None = None) -> pd.DataFrame:
    """Twelve rows (Jan–Dec) of processed counts and statuses for one region-year.

    Values are copied from the processed tables unchanged. A sensor that did
    not observe a month gives NaN (never 0); partial months keep their real
    count and are flagged; months outside the record are labelled as such.
    Also returns Terra and Aqua separately and, if ``calibrated`` (the
    calibrated_modis_monthly table) is given, calibrated MODIS.
    """
    months = pd.DataFrame({"month": range(1, 13)})
    t = totals[(totals["region"] == region) & (totals["year"] == year)]
    h = harmonized[(harmonized["region"] == region) & (harmonized["year"] == year)]
    f = months.merge(t, on="month", how="left").merge(
        h[["month", "harmonized_activity", "source_flag"]], on="month", how="left")
    in_record = f["modis_combined_coverage"].notna()

    out = pd.DataFrame({"month": f["month"], "month_name": [
        pd.Timestamp(2000, m, 1).strftime("%B") for m in f["month"]]})
    out["modis"] = f["modis_combined_count"].astype(float)
    out["modis_status"] = np.where(
        in_record, f["modis_combined_coverage"].map(_COVERAGE_TEXT).fillna("not observing"),
        "outside the satellite record")
    out["viirs"] = f["viirs_snpp_count"].astype(float)
    out["viirs_status"] = np.where(
        in_record, f["viirs_snpp_coverage"].map(_COVERAGE_TEXT).fillna("not observing"),
        "outside the satellite record")
    usable = f["source_flag"].isin([FLAG_ESTIMATED, FLAG_VIIRS])
    out["harmonized"] = f["harmonized_activity"].astype(float).where(usable)
    out["harmonized_status"] = np.select(
        [f["source_flag"] == FLAG_ESTIMATED, f["source_flag"] == FLAG_VIIRS, in_record],
        ["estimated (MODIS × calibration factor)", "observed (= actual VIIRS)",
         f["source_flag"].map(STATUS_SHORT).fillna("not harmonized").str.lower()],
        default="outside the satellite record")
    out["harmonized_completeness"] = np.where(usable, "complete month",
                                              np.where(in_record, "not on the harmonized scale",
                                                       "outside the satellite record"))
    for key, count, cov in (("terra", "modis_terra_count", "modis_terra_coverage"),
                            ("aqua", "modis_aqua_count", "modis_aqua_coverage")):
        out[key] = f[count].astype(float)
        out[f"{key}_status"] = np.where(
            in_record, f[cov].map(_COVERAGE_TEXT).fillna("not observing"),
            "outside the satellite record")
    if calibrated is not None:
        c = calibrated[(calibrated["region"] == region) & (calibrated["year"] == year)]
        c = months.merge(c[["month", "calibrated_modis", "comparison_period"]], on="month", how="left")
        out["calibrated"] = c["calibrated_modis"].astype(float)
        out["calibrated_status"] = c["comparison_period"].map(_PERIOD_TEXT).fillna(
            "no calibrated value (incomplete MODIS month or no factor)")
    return out
