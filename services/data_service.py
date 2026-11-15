"""Cached loading of processed pipeline outputs for the website.

The website never re-runs the pipeline; it only reads ``data/processed``.
Missing outputs raise ``DataUnavailable`` so pages can show an empty state
with the command that generates them.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from config.settings import PROCESSED_DIR, QUALITY_REPORT_PATH
from processing.build_outputs import OUTPUT_FILES

PIPELINE_COMMAND = "python -m scripts.run_pipeline"


class DataUnavailable(RuntimeError):
    """A processed output needed by a page is missing."""

    def __init__(self, paths: list[Path]):
        self.paths = paths
        super().__init__(", ".join(p.name for p in paths))


def _path(key: str) -> Path:
    return PROCESSED_DIR / OUTPUT_FILES[key]


def require(*keys: str) -> None:
    """Raise DataUnavailable if any of the named outputs is missing."""
    missing = [_path(k) for k in keys if not _path(k).exists()]
    if missing:
        raise DataUnavailable(missing)


@st.cache_data(show_spinner=False)
def _read_csv(path: str, mtime: float) -> pd.DataFrame:
    return pd.read_csv(path)


def load_table(key: str) -> pd.DataFrame:
    """Load a small CSV output (cached; refreshed when the file changes)."""
    require(key)
    p = _path(key)
    return _read_csv(str(p), p.stat().st_mtime)


@st.cache_resource(show_spinner="Loading detections…")
def _read_detections(path: str, mtime: float) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["acq_date"] = pd.to_datetime(df["acq_date"])
    for c in ("region", "sensor", "satellite", "detection_type_label", "confidence_class"):
        df[c] = df[c].astype("category")
    return df


def load_detections() -> pd.DataFrame:
    """All retained detections for the map (shared, read-only — never mutate).

    Reads the compact, git-committed ``map_detections.parquet`` so a fresh
    clone works without re-running the pipeline; falls back to the full local
    ``detections.parquet`` if only that exists.
    """
    key = "map_detections" if _path("map_detections").exists() else "detections"
    if not _path(key).exists():
        raise DataUnavailable([_path("map_detections")])
    p = _path(key)
    return _read_detections(str(p), p.stat().st_mtime)


@st.cache_data(show_spinner=False)
def _read_json(path: str, mtime: float) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_quality_report() -> dict:
    if not QUALITY_REPORT_PATH.exists():
        raise DataUnavailable([QUALITY_REPORT_PATH])
    return _read_json(str(QUALITY_REPORT_PATH), QUALITY_REPORT_PATH.stat().st_mtime)
