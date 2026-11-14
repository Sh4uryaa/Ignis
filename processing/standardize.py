"""Convert raw FIRMS columns into the IGNIS internal schema.

Original values are preserved (raw confidence, version string, satellite
code) alongside standardized fields. Unknown satellite codes or detection
types are kept and labelled — never silently dropped.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from config.settings import DETECTION_TYPE_LABELS, VIIRS_PLATFORM_ALIASES, VIIRS_PLATFORM_LABEL
from processing.clean_data import classify_confidence

logger = logging.getLogger(__name__)

# FIRMS satellite codes -> IGNIS platform names.
SATELLITE_NAMES: dict[str, str] = {
    "Terra": "Terra", "T": "Terra",
    "Aqua": "Aqua", "A": "Aqua",
    **{alias: VIIRS_PLATFORM_LABEL for alias in VIIRS_PLATFORM_ALIASES},
}

STANDARD_COLUMNS: tuple[str, ...] = (
    "sensor", "satellite", "satellite_raw", "latitude", "longitude",
    "acq_date", "acq_time", "acq_datetime_utc", "year", "month",
    "confidence_raw", "confidence_class", "detection_type", "detection_type_label",
    "frp", "brightness", "bright_t31", "scan", "track", "daynight", "version",
)


def detection_type_label(code: int | float) -> str:
    """Readable label for a FIRMS detection type; unknown codes are explicit."""
    if pd.isna(code):
        return "Unknown (missing)"
    return DETECTION_TYPE_LABELS.get(int(code), f"Unknown ({int(code)})")


def standardize(raw: pd.DataFrame, sensor: str) -> tuple[pd.DataFrame, list[str]]:
    """Standardize one sensor's typed FIRMS frame.

    Returns the standardized frame and a list of warnings.
    """
    warnings: list[str] = []
    out = pd.DataFrame(index=raw.index)
    out["sensor"] = sensor

    sat_raw = raw["satellite"].astype("object")
    sat = sat_raw.map(SATELLITE_NAMES)
    unknown_sat = sat.isna()
    if unknown_sat.any():
        codes = sorted(sat_raw[unknown_sat].astype(str).unique())
        warnings.append(f"{sensor}: {int(unknown_sat.sum())} rows with unknown satellite codes {codes}")
        sat = sat.fillna("Unknown (" + sat_raw.astype(str) + ")")
    out["satellite"] = sat
    out["satellite_raw"] = sat_raw

    out["latitude"] = raw["latitude"].astype("float64")
    out["longitude"] = raw["longitude"].astype("float64")

    date = pd.to_datetime(raw["acq_date"], format="%Y-%m-%d", errors="coerce")
    hhmm = raw["acq_time"].astype("object").str.zfill(4)
    dt = pd.to_datetime(raw["acq_date"].astype("object") + " " + hhmm,
                        format="%Y-%m-%d %H%M", errors="coerce", utc=True)
    bad = date.isna() | dt.isna()
    if bad.any():
        warnings.append(f"{sensor}: {int(bad.sum())} rows with unparseable date/time")
    out["acq_date"] = date
    out["acq_time"] = hhmm
    out["acq_datetime_utc"] = dt
    out["year"] = date.dt.year.astype("Int16")
    out["month"] = date.dt.month.astype("Int8")

    out["confidence_raw"] = raw["confidence"].astype("string")
    out["confidence_class"] = classify_confidence(sensor, raw["confidence"])

    dtype = pd.to_numeric(raw["type"], errors="coerce").astype("Int16")
    out["detection_type"] = dtype
    labels = {c: detection_type_label(c) for c in dtype.dropna().unique()}
    out["detection_type_label"] = dtype.map(labels).fillna("Unknown (missing)")
    unknown_types = sorted(int(c) for c in labels if int(c) not in DETECTION_TYPE_LABELS)
    if unknown_types:
        warnings.append(f"{sensor}: unknown detection types preserved {unknown_types}")

    for col in ("frp", "brightness", "bright_t31"):
        out[col] = pd.to_numeric(raw[col], errors="coerce").astype("float32")
    for col in ("scan", "track"):
        out[col] = pd.to_numeric(raw[col], errors="coerce").astype("float32")
    out["daynight"] = raw["daynight"].astype("string")
    out["version"] = raw["version"].astype("string")  # keep "6.03" vs "61.03" exact

    for col in ("sensor", "satellite", "satellite_raw", "confidence_class",
                "detection_type_label", "daynight", "version"):
        out[col] = out[col].astype("category")
    return out[list(STANDARD_COLUMNS)], warnings


def satellite_date_coverage(df: pd.DataFrame) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    """First and last observation date per satellite, from the data itself."""
    g = df.groupby("satellite", observed=True)["acq_date"]
    return {str(s): (lo, hi) for s, lo, hi in zip(g.min().index, g.min(), g.max())}


def finite_coordinates(df: pd.DataFrame) -> pd.Series:
    """Mask of rows with finite latitude/longitude."""
    return np.isfinite(df["latitude"]) & np.isfinite(df["longitude"])
