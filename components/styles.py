"""Load the centralized IGNIS stylesheet (assets/styles.css)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import streamlit as st

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


@lru_cache(maxsize=4)
def read_asset(name: str) -> str:
    """Read a text asset (CSS / SVG) from the assets folder."""
    return (ASSETS_DIR / name).read_text(encoding="utf-8")


def load_global_styles() -> None:
    """Inject the global stylesheet once per run."""
    st.html(f"<style>{read_asset('styles.css')}</style>")
