"""IGNIS — Streamlit entry point.

Only configures the app, loads global styles, draws the shared top bar and
dispatches to the selected page. All data processing lives in
``processing/``; page layouts live in ``pages/``.

Run:  streamlit run app.py
"""
import streamlit as st

from components.navigation import build_navigation, render_top_bar
from components.styles import load_global_styles
from config.settings import APP_NAME, APP_TAGLINE
from pages import (
    activity_calendar,
    anomaly_analysis,
    harmonization,
    historical_map,
    methodology,
    overview,
)

st.set_page_config(page_title=f"{APP_NAME} — {APP_TAGLINE}", page_icon="🔥", layout="wide",
                   initial_sidebar_state="collapsed")
load_global_styles()

navigation = build_navigation([
    (overview.render, "Overview", ":material/dashboard:", "overview"),
    (historical_map.render, "Historical Fire Map", ":material/map:", "map"),
    (harmonization.render, "Harmonization & Comparison", ":material/compare_arrows:", "harmonization"),
    (activity_calendar.render, "Burning Activity Calendar", ":material/calendar_month:", "calendar"),
    (anomaly_analysis.render, "Anomaly Analysis", ":material/insights:", "anomalies"),
    (methodology.render, "Methodology & Data Quality", ":material/science:", "methodology"),
])
render_top_bar(navigation)
navigation.run()
