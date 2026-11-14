"""Confidence classification and the default Nominal + High policy.

MODIS and VIIRS confidence values are *not* equivalent: MODIS is a 0-100
number, VIIRS is a categorical l/n/h flag. They are classified separately
and the original value is always preserved by callers.
"""
from __future__ import annotations

import pandas as pd

from config.settings import (
    MODIS_CONFIDENCE_BINS,
    MODIS_MIN_CONFIDENCE,
    VIIRS_ACCEPTED_CONFIDENCE,
    VIIRS_CONFIDENCE_CLASSES,
)


def classify_modis_confidence(conf: pd.Series) -> pd.Series:
    """Map numeric MODIS confidence to low/nominal/high.

    Non-numeric or out-of-range values become ``"unknown"`` so they are
    reported rather than silently dropped.
    """
    num = pd.to_numeric(conf, errors="coerce")
    out = pd.Series("unknown", index=conf.index, dtype="object")
    for label, (lo, hi) in MODIS_CONFIDENCE_BINS.items():
        out[(num >= lo) & (num <= hi)] = label
    return out


def classify_viirs_confidence(conf: pd.Series) -> pd.Series:
    """Map VIIRS l/n/h confidence to low/nominal/high (others -> unknown)."""
    return conf.astype("object").map(VIIRS_CONFIDENCE_CLASSES).fillna("unknown")


def classify_confidence(sensor: str, conf: pd.Series) -> pd.Series:
    """Dispatch to the sensor-specific confidence classifier."""
    if sensor == "MODIS":
        return classify_modis_confidence(conf)
    if sensor == "VIIRS":
        return classify_viirs_confidence(conf)
    raise ValueError(f"Unknown sensor '{sensor}'")


def passes_confidence_policy(sensor: str, conf: pd.Series) -> pd.Series:
    """Boolean mask for the default Nominal + High policy.

    MODIS: 30 <= confidence <= 100. VIIRS: confidence in {"n", "h"}.
    """
    if sensor == "MODIS":
        num = pd.to_numeric(conf, errors="coerce")
        return ((num >= MODIS_MIN_CONFIDENCE) & (num <= 100)).fillna(False).astype(bool)
    if sensor == "VIIRS":
        return conf.astype("object").isin(VIIRS_ACCEPTED_CONFIDENCE)
    raise ValueError(f"Unknown sensor '{sensor}'")


def apply_confidence_policy(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict[str, int]]]:
    """Keep Nominal + High rows of a standardized frame (any mix of sensors).

    Returns the retained rows and, per sensor, counts of retained, excluded
    low-confidence and excluded unknown-confidence rows. The original
    ``confidence_raw`` column is preserved on retained rows.
    """
    keep = pd.Series(False, index=df.index)
    stats: dict[str, dict[str, int]] = {}
    for sensor, idx in df.groupby("sensor", observed=True).groups.items():
        sub = df.loc[idx]
        mask = passes_confidence_policy(str(sensor), sub["confidence_raw"])
        keep.loc[idx] = mask.to_numpy()
        cls = sub["confidence_class"].astype("object")
        stats[str(sensor)] = {
            "input": int(len(sub)),
            "retained": int(mask.sum()),
            "excluded_low_confidence": int((cls == "low").sum()),
            "excluded_unknown_confidence": int(((cls == "unknown") & ~mask.to_numpy()).sum()),
        }
    return df.loc[keep], stats
