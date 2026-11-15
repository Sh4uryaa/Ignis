"""Landing hero for the Overview page: IGNIS introduction + interactive 3D globe.

Layout: two-column grid (text left, globe right) using Streamlit columns.
On narrow screens the columns stack naturally.

The interactive globe is rendered by ``components/globe.py`` which embeds
``components/globe.html`` via ``st.components.v1.html()``.
"""
from __future__ import annotations

from html import escape

import streamlit as st

from config.settings import APP_DESCRIPTION, APP_HEADLINE, APP_NAME

STATS_ANCHOR = "overview-dashboard"


def render_hero(
    meta: str = "",
    cta_label: str = "Explore Historical Analysis",
    cta_anchor: str = STATS_ANCHOR,
    **_kwargs,          # absorb any legacy keyword args silently
) -> None:
    """Two-column hero: copy (left) + interactive 3D globe (right)."""
    from components.globe import render_globe  # noqa: PLC0415

    meta_html = f'<div class="ig-hero-meta">{escape(meta)}</div>' if meta else ""

    col_copy, col_globe = st.columns([1.1, 1.0], gap="large")

    with col_copy:
        st.html(f"""
<div class="ig-hero-copy" style="padding: 1.5rem 0 1rem;">
  <div class="ig-eyebrow">NASA MODIS · VIIRS · Satellite fire record</div>
  <h1 class="ig-hero-brand">{APP_NAME[:-1]}<span>{APP_NAME[-1]}</span></h1>
  <p class="ig-hero-headline">{escape(APP_HEADLINE)}</p>
  <p class="ig-hero-text">{escape(APP_DESCRIPTION)}</p>
  <a class="ig-hero-cta" href="#{cta_anchor}">{escape(cta_label)} <span aria-hidden="true">↓</span></a>
  {meta_html}
</div>""")

    with col_globe:
        st.html('<div style="height:0.4rem;"></div>')
        render_globe(height=500, key="ignis_hero_globe")
