"""Landing hero for the Overview page: IGNIS introduction + glowing Earth.

Markup lives here, styling in assets/styles.css, the globe in
assets/earth_hero.svg. The globe is an illustration, not fire data.
"""
from __future__ import annotations

import base64
from functools import lru_cache
from html import escape

import streamlit as st

from components.styles import read_asset
from config.settings import APP_DESCRIPTION, APP_HEADLINE, APP_NAME

STATS_ANCHOR = "overview-dashboard"


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
