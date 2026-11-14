"""Global CSS for the IGNIS look (dark charcoal, orange accents)."""
from __future__ import annotations

import streamlit as st

from config.settings import COLORS as C

_CSS = f"""
<style>
.stApp {{ background: {C['background']}; }}
.block-container {{ padding-top: 2.2rem; max-width: 1280px; }}
h1, h2, h3, h4 {{ color: {C['text']}; letter-spacing: -0.01em; }}
section[data-testid="stSidebar"] {{ background: {C['surface']}; border-right: 1px solid {C['border']}; }}
.ignis-brand {{ font-weight: 800; font-size: 1.6rem; letter-spacing: 0.12em; color: {C['text']}; }}
.ignis-brand span {{ color: {C['primary']}; }}
.ignis-tagline {{ color: {C['text_muted']}; font-size: 0.8rem; margin-top: -0.2rem; }}
.ignis-accent {{ height: 3px; width: 56px; background: {C['primary']}; border-radius: 2px; margin: 0.4rem 0 0.9rem; }}
.ignis-page-title {{ font-size: 1.9rem; font-weight: 700; color: {C['text']}; margin: 0; }}
.ignis-page-sub {{ color: {C['text_muted']}; margin: 0.15rem 0 0; }}
.ignis-chip {{ display: inline-block; padding: 0.15rem 0.6rem; border-radius: 999px; font-size: 0.78rem;
  border: 1px solid {C['border']}; color: {C['text_muted']}; margin-right: 0.4rem; }}
.ignis-chip.region {{ border-color: {C['primary']}; color: {C['primary']}; font-weight: 600; }}
.ignis-card {{ background: {C['surface']}; border: 1px solid {C['border']}; border-radius: 10px;
  padding: 0.9rem 1rem; height: 100%; }}
.ignis-card .label {{ color: {C['text_muted']}; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; }}
.ignis-card .value {{ color: {C['text']}; font-size: 1.55rem; font-weight: 700; margin-top: 0.2rem; line-height: 1.2; }}
.ignis-card .sub {{ color: {C['text_muted']}; font-size: 0.8rem; margin-top: 0.25rem; }}
.ignis-card.accent {{ border-top: 3px solid {C['primary']}; }}
.ignis-note {{ background: rgba(224,164,88,0.08); border-left: 3px solid {C['secondary']};
  padding: 0.6rem 0.9rem; border-radius: 4px; color: {C['text_muted']}; font-size: 0.88rem; }}
.ignis-legend {{ display: flex; flex-wrap: wrap; gap: 1rem; color: {C['text_muted']}; font-size: 0.82rem; margin-top: 0.4rem; }}
.ignis-legend i {{ display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 0.35rem; vertical-align: -1px; }}
.ignis-legend i.line {{ border-radius: 2px; height: 3px; width: 18px; vertical-align: 3px; }}
hr {{ border-color: {C['border']}; }}
div[data-testid="stMetricValue"] {{ color: {C['text']}; }}
</style>
"""


def load_global_styles() -> None:
    """Inject the global stylesheet once per run."""
    st.html(_CSS)
