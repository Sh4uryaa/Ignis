"""Selected-region state and boundary geometry for maps."""
from __future__ import annotations

import json

import streamlit as st

from config.settings import (
    BOUNDARY_PROVENANCE_PATH,
    DEFAULT_REGION,
    REGION_BOUNDARY_FILES,
    REGIONS,
)

REGION_KEY = "region"


def selected_region() -> str:
    """The region currently analysed (persisted in session state)."""
    if st.session_state.get(REGION_KEY) not in REGIONS:
        st.session_state[REGION_KEY] = DEFAULT_REGION
    return st.session_state[REGION_KEY]


def missing_boundaries() -> list[str]:
    return [str(p) for p in REGION_BOUNDARY_FILES.values() if not p.exists()]


@st.cache_data(show_spinner=False)
def boundary_geojson(region: str) -> dict:
    """GeoJSON FeatureCollection for one state (EPSG:4326)."""
    path = REGION_BOUNDARY_FILES[region]
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def boundary_provenance() -> dict | None:
    if not BOUNDARY_PROVENANCE_PATH.exists():
        return None
    return json.loads(BOUNDARY_PROVENANCE_PATH.read_text(encoding="utf-8"))


def region_bounds(region: str) -> list[float] | None:
    prov = boundary_provenance()
    if not prov:
        return None
    return prov.get("diagnostics", {}).get(region, {}).get("bounds_wgs84")
