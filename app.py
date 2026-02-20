"""
ILM Tools – Multi-page Streamlit application entry point.

Pages are discovered automatically from the pages/ directory.
This file handles global config and the optional password gate.
"""

import os

import streamlit as st

# ── Page config ──────────────────────────────────────────────────
st.set_page_config(page_title="ILM Tools", layout="wide")

# ── Password gate ────────────────────────────────────────────────
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")

if APP_PASSWORD:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("ILM Tools")
        pwd = st.text_input("Enter team password", type="password")
        if pwd:
            if pwd == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.stop()

# ── Home page ────────────────────────────────────────────────────
st.title("ILM Tools")
st.markdown(
    "Select a tool from the sidebar to get started:\n\n"
    "- **ILM Banner Generator** — Create banner ads for ILM brands\n"
    "- **Just Dropped Generator** — Create Instagram Story frames for Amazon channels"
)
