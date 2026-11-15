"""CSV download buttons with descriptive, region-specific filenames.

Exports always come from the full processed tables (never from sampled map
data) and keep status, partial-month, satellite, confidence-policy and
calibration columns.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

EXPORT_NAMES: dict[str, str] = {
    "monthly_sensor_counts": "monthly_sensor_counts",
    "harmonized": "harmonized_history",
    "calibration_factors": "calibration_factors",
    "validation": "validation_results",
    "anomalies": "anomaly_results",
    "detection_types": "detection_type_breakdown",
    "calibrated": "calibrated_modis_comparison",
}


def export_filename(region: str, kind: str, years: tuple[int, int] | None = None) -> str:
    base = f"ignis_{region.lower()}_{EXPORT_NAMES[kind]}"
    if years:
        base += f"_{years[0]}-{years[1]}"
    return base + ".csv"


def download_csv(df: pd.DataFrame, region: str, kind: str, label: str,
                 years: tuple[int, int] | None = None, key: str | None = None) -> None:
    st.download_button(
        label=f"⬇ {label}",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=export_filename(region, kind, years),
        mime="text/csv",
        key=key or f"dl_{kind}_{region}",
        help=f"{len(df):,} rows",
    )
