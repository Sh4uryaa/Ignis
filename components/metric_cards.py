"""Compact metric cards, notes and section titles in the IGNIS style."""
from __future__ import annotations

from html import escape

import streamlit as st


def metric_card(label: str, value: str, sub: str = "", tag: str = "") -> None:
    """One statistic. ``tag`` adds a small orange status label (no decorative lines)."""
    tag_html = f'<div class="tag">{escape(tag)}</div>' if tag else ""
    st.html(f'<div class="ig-card"><div class="label">{escape(label)}</div>'
            f'<div class="value">{escape(value)}</div>'
            f'<div class="sub">{escape(sub)}</div>{tag_html}</div>')


def metric_row(cards: list[dict]) -> None:
    """Render cards side by side, wrapping onto new lines on narrow screens.

    Each dict holds metric_card kwargs. The keyed flex container lets CSS give
    cards a minimum width (see ``[class*="st-key-igcards_"]`` in styles.css).
    """
    key = "igcards_" + "_".join(str(abs(hash(c["label"])) % 10**6) for c in cards)
    with st.container(key=key, horizontal=True, wrap=True, gap="small"):
        for card in cards:
            metric_card(**card)


def note(text: str) -> None:
    """Quiet explanatory note (accepts simple inline HTML)."""
    st.html(f'<div class="ig-note">{text}</div>')


def section_title(title: str, subtitle: str = "", anchor: str = "") -> None:
    """Section heading using typography and spacing only (no divider lines)."""
    anchor_attr = f' id="{escape(anchor)}"' if anchor else ""
    sub = f'<p class="ig-section-sub">{escape(subtitle)}</p>' if subtitle else ""
    st.html(f'<div{anchor_attr} class="ig-section-title">{escape(title)}</div>{sub}')
