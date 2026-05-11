"""RFx Assistant — Streamlit entry point.

Two tabs:
  0 · Spec Builder   — chatbot → LLM spec table → multi-user collaboration + email
  1 · Scoring Matrix — editable weighted scoring → collaboration + email reminders

Run with:
    streamlit run src/rfx_assistant/main.py --server.port 8501
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow `streamlit run src/rfx_assistant/main.py` to resolve sibling modules.
_PKG_PARENT = Path(__file__).resolve().parents[1]
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

import streamlit as st
from dotenv import load_dotenv

from rfx_assistant.branding import inject_css, tokens, DARK_BLUE, DEEP_PURPLE
from rfx_assistant.ui import spec_builder, scoring_matrix

# Load .env for local dev; on Streamlit Cloud inject st.secrets into os.environ
load_dotenv()
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str):
            os.environ.setdefault(_k, _v)
except Exception:
    pass

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="RFx Assistant — Centrica",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "theme" not in st.session_state:
    st.session_state.theme = "light"

THEME = st.session_state.theme
st.markdown(inject_css(THEME), unsafe_allow_html=True)
T = tokens(THEME)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        f"""<div style='background:{T["header_grad"]};
        padding:14px 18px;border-radius:10px;margin-bottom:14px'>
        <span style='color:white;font-weight:700;font-size:18px;font-family:Arial'>
        Centrica · RFx Assistant</span><br>
        <span style='color:rgba(255,255,255,0.78);font-size:12px'>
        Procurement Transformation · Workstream 1</span>
        </div>""",
        unsafe_allow_html=True,
    )

    st.markdown("**Appearance**")
    is_dark = st.toggle("🌙  Dark mode", value=(THEME == "dark"))
    new_theme = "dark" if is_dark else "light"
    if new_theme != THEME:
        st.session_state.theme = new_theme
        st.rerun()
    st.caption(f"{'Dark' if THEME == 'dark' else 'Light'} theme · dark blue · light purple · mint pink")

    st.divider()

    st.markdown("**How to use**")
    st.markdown(
        "**1. Spec Builder**\n"
        "Answer three quick questions — the AI generates a full technical "
        "specification table for any spend category. Edit rows inline, "
        "assign owners, and send email reminders to collaborators.\n\n"
        "**2. Scoring Matrix**\n"
        "Add supplier names and score them against weighted criteria. "
        "Criteria are assigned to scorers — chase missing scores with "
        "one-click email reminders."
    )

    st.divider()
    st.caption("Powered by Gemini 2.0 · Centrica Procurement")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_spec, tab_score = st.tabs(["📋  Spec Builder", "📊  Scoring Matrix"])

with tab_spec:
    spec_builder.render()

with tab_score:
    scoring_matrix.render()
