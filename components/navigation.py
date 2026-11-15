"""Top navigation bar, page registry and page header.

The bar sits in normal document flow (not fixed), so it scrolls away with
the page. Streamlit's own navigation menu is hidden.
"""
from __future__ import annotations

from typing import Callable

import streamlit as st

from components.region_selector import region_selector
from config.settings import APP_NAME, CONFIDENCE_POLICY_LABEL
from services.data_service import PIPELINE_COMMAND, DataUnavailable

_PAGES_KEY = "_ignis_pages"


def build_navigation(page_specs: list[tuple[Callable[[], None], str, str, str]]):
    """Register pages from (render_fn, title, icon, url_path) tuples.

    The first entry is the default landing page. Navigation UI is drawn by
    ``render_top_bar``; Streamlit's sidebar menu is hidden.
    """
    pages = {}
    for i, (fn, title, icon, url) in enumerate(page_specs):
        pages[url] = st.Page(fn, title=title, icon=icon, url_path=url, default=(i == 0))
    st.session_state[_PAGES_KEY] = pages
    return st.navigation(list(pages.values()), position="hidden")


def go_to(url_path: str) -> None:
    """Switch to another IGNIS page by its url path."""
    st.switch_page(st.session_state[_PAGES_KEY][url_path])


def render_top_bar(current) -> str:
    """Brand, page links and the region selector. Returns the selected region.

    ``current`` is the page returned by ``st.navigation``; its link is wrapped
    in a keyed container so CSS can mark it active (Streamlit itself exposes
    no stable active-link attribute).
    """
    pages = st.session_state[_PAGES_KEY]
    with st.container(key="ignis_topbar"):
        with st.container(key="ignis_brandrow", horizontal=True, vertical_alignment="bottom",
                          horizontal_alignment="distribute"):
            st.html(f'<div class="ig-brand">{APP_NAME[:-1]}<span>{APP_NAME[-1]}</span></div>'
                    f'<div class="ig-brand-sub">Harmonized satellite fire record</div>',
                    width="content")
            region = region_selector()
        with st.container(key="ignis_nav", horizontal=True, vertical_alignment="center", gap="small"):
            for page in pages.values():
                if page.url_path == current.url_path:
                    with st.container(key="ignis_nav_active", width="content"):
                        st.page_link(page, label=page.title)
                else:
                    st.page_link(page, label=page.title)
    return region


def page_header(title: str, subtitle: str, region: str, extra_chips: list[str] | None = None) -> None:
    """Page title, subtitle and status chips — hierarchy through type, not lines."""
    from config.regions import region_label

    chips = f'<span class="ig-chip region">{region_label(region)}</span>'
    chips += f'<span class="ig-chip">{CONFIDENCE_POLICY_LABEL}</span>'
    chips += "".join(f'<span class="ig-chip">{c}</span>' for c in (extra_chips or []))
    st.html(f'<p class="ig-page-title">{title}</p><p class="ig-page-sub">{subtitle}</p>'
            f'<div>{chips}</div>')


def data_unavailable(exc: DataUnavailable) -> None:
    """Empty state shown when processed outputs are missing."""
    st.warning("Processed data not found: " + ", ".join(p.name for p in exc.paths))
    st.markdown("IGNIS reads precomputed outputs. Place the NASA archives in "
                "`data/raw/incoming/` and run the preprocessing pipeline:")
    st.code(PIPELINE_COMMAND, language="bash")
