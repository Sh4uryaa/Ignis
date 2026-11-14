"""Compact metric cards in the IGNIS style."""
from __future__ import annotations

from html import escape

import streamlit as st


def metric_card(label: str, value: str, sub: str = "", accent: bool = False) -> None:
    cls = "ignis-card accent" if accent else "ignis-card"
    st.html(f'<div class="{cls}"><div class="label">{escape(label)}</div>'
            f'<div class="value">{escape(value)}</div>'
            f'<div class="sub">{escape(sub)}</div></div>')


def metric_row(cards: list[dict]) -> None:
    """Render cards side by side; each dict holds metric_card kwargs."""
    for col, card in zip(st.columns(len(cards)), cards):
        with col:
            metric_card(**card)


def note(text: str) -> None:
    """Amber side-ruled explanatory note (accepts simple inline HTML)."""
    st.html(f'<div class="ignis-note">{text}</div>')
