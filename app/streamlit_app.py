# implements FR7/FR8 — app shell only (page config, theme, navigation); no dashboard/detection logic here
"""Entry point: page config, theme, and navigation between Dashboard and Upload & Detect."""

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")  # must precede any torch-importing page

from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Smart City Traffic ANPR",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

_css_path = Path(__file__).resolve().parent / "assets" / "style.css"
if _css_path.exists():
    st.markdown(f"<style>{_css_path.read_text()}</style>", unsafe_allow_html=True)

pg = st.navigation(
    [
        st.Page("pages/dashboard.py", title="Dashboard", icon="📊", default=True),
        st.Page("pages/upload_detect.py", title="Upload & Detect", icon="📤"),
    ]
)
pg.run()
