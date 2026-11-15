<<<<<<< HEAD
"""Landing hero for the Overview page: IGNIS introduction + interactive 3D globe.

Layout: two-column grid (text left, globe right) using Streamlit columns.
On narrow screens the columns stack naturally.

The interactive globe is rendered by ``components/globe.py`` which embeds
``components/globe.html`` via ``st.components.v1.html()``.
"""
from __future__ import annotations

=======
"""Landing hero for the Overview page: IGNIS introduction + glowing Earth.

Markup lives here, styling in assets/styles.css, the globe in
assets/earth_hero.svg. The globe is an illustration, not fire data.
"""
from __future__ import annotations

import base64
from functools import lru_cache
>>>>>>> 398ae2ebb76ff5f8e2778bebf4e4de063c8316c0
from html import escape

import streamlit as st

<<<<<<< HEAD
=======
from components.styles import read_asset
>>>>>>> 398ae2ebb76ff5f8e2778bebf4e4de063c8316c0
from config.settings import APP_DESCRIPTION, APP_HEADLINE, APP_NAME

STATS_ANCHOR = "overview-dashboard"


<<<<<<< HEAD
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
=======
@lru_cache(maxsize=1)
def _globe_data_uri() -> str:
    """The globe SVG as a data URI.

    st.html sanitizes inline <svg>, so the illustration is embedded as an
    image; its glow animation is defined inside the SVG itself.
    """
    raw = read_asset("earth_hero.svg").encode("utf-8")
    return "data:image/svg+xml;base64," + base64.b64encode(raw).decode("ascii")


def render_hero(meta: str = "", cta_label: str = "Explore Historical Analysis",
                cta_anchor: str = STATS_ANCHOR) -> None:
    """Two-column hero (stacks on narrow screens). The CTA scrolls to ``cta_anchor``."""
    meta_html = f'<div class="ig-hero-meta">{escape(meta)}</div>' if meta else ""
    st.html(f"""
<section class="ig-hero">
  <div class="ig-hero-copy">
    <div class="ig-eyebrow">NASA MODIS · VIIRS · Satellite fire record</div>
    <h1 class="ig-hero-brand">{APP_NAME[:-1]}<span>{APP_NAME[-1]}</span></h1>
    <p class="ig-hero-headline">{escape(APP_HEADLINE)}</p>
    <p class="ig-hero-text">{escape(APP_DESCRIPTION)}</p>
    <a class="ig-hero-cta" href="#{cta_anchor}">{escape(cta_label)} <span aria-hidden="true">↓</span></a>
    {meta_html}
  </div>
  <div class="ig-hero-visual"><img class="ig-globe" src="{_globe_data_uri()}"
       alt="Illustration of the Earth with a warm glowing rim"></div>
</section>""")
>>>>>>> 398ae2ebb76ff5f8e2778bebf4e4de063c8316c0
