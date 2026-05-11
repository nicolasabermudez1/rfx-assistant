"""RFx Assistant — Streamlit entry point.

Welcome form gates the app on first visit. After identity is captured, the
user gets two tabs:
  0 · Spec Builder   — chatbot → LLM spec table → multi-user collaboration + email
  1 · Scoring Matrix — editable weighted scoring → collaboration + email reminders

Run with:
    streamlit run src/rfx_assistant/main.py --server.port 8501
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_PKG_PARENT = Path(__file__).resolve().parents[1]
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

import streamlit as st
from dotenv import load_dotenv

from rfx_assistant import agents
from rfx_assistant.branding import inject_css, tokens
from rfx_assistant.ui import spec_builder, scoring_matrix, team

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
    page_title="RFx Assistant",
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
# Sidebar (always rendered — even on welcome screen)
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        f"""<div style='background:{T["header_grad"]};
        padding:14px 18px;border-radius:10px;margin-bottom:14px'>
        <span style='color:white;font-weight:700;font-size:18px;font-family:Arial'>
        RFx Assistant</span><br>
        <span style='color:rgba(255,255,255,0.78);font-size:12px'>
        AI-powered procurement spec & scoring</span>
        </div>""",
        unsafe_allow_html=True,
    )

    st.markdown("**Appearance**")
    is_dark = st.toggle("🌙  Dark mode", value=(THEME == "dark"))
    new_theme = "dark" if is_dark else "light"
    if new_theme != THEME:
        st.session_state.theme = new_theme
        st.rerun()

    st.divider()

    if team.is_set_up():
        team.render_sidebar_panel()
        st.divider()

    st.markdown("**How to use**")
    st.markdown(
        "**1. Spec Builder** — answer three quick questions; the AI generates "
        "a product-specific spec table and scoring matrix.\n\n"
        "**2. Scoring Matrix** — score suppliers against the AI-generated criteria, "
        "and chase any pending team scores with one-click email reminders."
    )

    st.divider()
    _key_check = getattr(agents, "gemini_key_available", None)
    _has_key = bool(_key_check()) if callable(_key_check) else bool(os.getenv("GEMINI_API_KEY"))
    if _has_key:
        st.success("🟢  Live AI active (Gemini 2.0)")
    else:
        st.warning(
            "🟡  Demo mode — no `GEMINI_API_KEY` set. "
            "Spec will use product-specific templates instead of live AI."
        )

# ---------------------------------------------------------------------------
# Welcome gate / main content
# ---------------------------------------------------------------------------

if not team.render_welcome():
    # Welcome form is showing — don't render the tabs yet
    st.stop()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_spec, tab_score = st.tabs(["📋  Spec Builder", "📊  Scoring Matrix"])

with tab_spec:
    spec_builder.render()

with tab_score:
    scoring_matrix.render()
