"""Sidebar brand, persistent region selector, page header and page registry."""
from __future__ import annotations

from typing import Callable

import streamlit as st

from config.settings import APP_NAME, APP_TAGLINE, CONFIDENCE_POLICY_LABEL, REGIONS
from services.data_service import PIPELINE_COMMAND, DataUnavailable
from services.region_service import REGION_KEY, selected_region

_PAGES_KEY = "_ignis_pages"


def build_navigation(page_specs: list[tuple[Callable[[], None], str, str, str]]):
    """Create st.navigation from (render_fn, title, icon, url_path) tuples.

    The first entry is the default landing page. Page objects are kept in
    session state so other pages can ``go_to`` them.
    """
    pages = {}
    for i, (fn, title, icon, url) in enumerate(page_specs):
        pages[url] = st.Page(fn, title=title, icon=icon, url_path=url, default=(i == 0))
    st.session_state[_PAGES_KEY] = pages
    return st.navigation(list(pages.values()), position="sidebar")


def go_to(url_path: str) -> None:
    """Switch to another IGNIS page by its url path."""
    st.switch_page(st.session_state[_PAGES_KEY][url_path])


def render_sidebar() -> str:
    """Brand block and the region selector shared by every page."""
    with st.sidebar:
        st.html(f'<div class="ignis-brand">{APP_NAME[:-1]}<span>{APP_NAME[-1]}</span></div>'
                f'<div class="ignis-tagline">{APP_TAGLINE}</div><div class="ignis-accent"></div>')
        selected_region()  # initialises session state before the keyed widget
        st.radio("Study region", REGIONS, key=REGION_KEY, horizontal=True,
                 help="Every page and export uses this region.")
        st.caption(f"Confidence policy: **{CONFIDENCE_POLICY_LABEL}**  \n"
                   "All detection types included by default.")
    return st.session_state[REGION_KEY]


def page_header(title: str, subtitle: str, region: str, extra_chips: list[str] | None = None) -> None:
    """Page title with region and data-status chips."""
    chips = f'<span class="ignis-chip region">{region}</span>'
    chips += "".join(f'<span class="ignis-chip">{c}</span>' for c in (extra_chips or []))
    st.html(f'<p class="ignis-page-title">{title}</p><p class="ignis-page-sub">{subtitle}</p>'
            f'<div class="ignis-accent"></div><div>{chips}</div>')


def data_unavailable(exc: DataUnavailable) -> None:
    """Empty state shown when processed outputs are missing."""
    st.warning("Processed data not found: " + ", ".join(p.name for p in exc.paths))
    st.markdown("IGNIS reads precomputed outputs. Place the NASA archives in "
                "`data/raw/incoming/` and run the preprocessing pipeline:")
    st.code(PIPELINE_COMMAND, language="bash")
