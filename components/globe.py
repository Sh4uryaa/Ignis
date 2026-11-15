"""IGNIS — Interactive 3D Globe Component.

Renders a globe.gl WebGL Earth with an orange fire-backglow inside a
Streamlit iframe.  No hotspot markers — purely decorative / cinematic.

Usage::

    from components.globe import render_globe
    render_globe(height=500)
"""
from __future__ import annotations

from pathlib import Path

import streamlit.components.v1 as components

_HERE = Path(__file__).resolve().parent
_HTML_PATH = _HERE / "globe.html"


def render_globe(height: int = 500, key: str = "ignis_globe") -> None:
    """Embed the interactive 3-D globe in the current Streamlit column.

    Parameters
    ----------
    height:
        Iframe height in pixels.
    key:
        Streamlit component key (keep unique if you place multiple globes).
    """
    html_content = _HTML_PATH.read_text(encoding="utf-8")
    components.html(html_content, height=height, scrolling=False)
