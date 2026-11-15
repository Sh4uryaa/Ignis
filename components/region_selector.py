"""Searchable study-region selector driven by the region registry."""
from __future__ import annotations

import streamlit as st

from config.regions import REGION_REGISTRY, region_label
from services.region_service import REGION_KEY, selected_region


def region_selector() -> str:
    """Type-to-search dropdown of registered regions; returns the selected key.

    Options and labels come from ``config/regions.py`` so new regions appear
    here without UI changes. The value is stored in session state under
    ``REGION_KEY`` and read by every page.
    """
    selected_region()  # initialise state before the keyed widget is created
    with st.container(key="ignis_region", width=300):
        st.selectbox(
            "Study region",
            options=[r.key for r in REGION_REGISTRY],
            format_func=region_label,
            key=REGION_KEY,
            placeholder="Search or select a region",
            help="Type to search. Every page, chart and export uses this region.",
        )
    return st.session_state[REGION_KEY]
