"""IGNIS — Streamlit entry point.

Only configures the app, loads global styles, initialises state and
dispatches to the selected page. All data processing lives in
``processing/``; page layouts live in ``pages/``.

Run:  streamlit run app.py
"""
import streamlit as st

from config.settings import APP_NAME, APP_TAGLINE
from components.navigation import build_navigation, render_sidebar
from components.styles import load_global_styles
from pages import (
    activity_calendar,
    anomaly_analysis,
    harmonization,
    historical_map,
    methodology,
    overview,
)

st.set_page_config(page_title=f"{APP_NAME} — {APP_TAGLINE}", page_icon="🔥", layout="wide")
load_global_styles()

navigation = build_navigation([
    (overview.render, "Overview", ":material/dashboard:", "overview"),
    (historical_map.render, "Historical Fire Map", ":material/map:", "map"),
    (harmonization.render, "Harmonization & Comparison", ":material/compare_arrows:", "harmonization"),
    (activity_calendar.render, "Burning Activity Calendar", ":material/calendar_month:", "calendar"),
    (anomaly_analysis.render, "Anomaly Analysis", ":material/insights:", "anomalies"),
    (methodology.render, "Methodology & Data Quality", ":material/science:", "methodology"),
])
render_sidebar()
navigation.run()
