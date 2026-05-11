"""Team / identity helpers.

The user enters their own name + role + (optional) teammate at the welcome
screen. The whole rest of the app reads identity from session_state.team
instead of any hard-coded persona constants. This module centralises the
helper functions both Spec Builder and Scoring Matrix rely on.
"""
from __future__ import annotations

import streamlit as st

from rfx_assistant.branding import DARK_BLUE, DEEP_PURPLE, MINT_PINK, WARN, LIGHT_PURPLE

# Role keys returned by the LLM / fallbacks and mapped to display labels.
ROLE_LABELS: dict[str, str] = {
    "procurement": "Procurement",
    "business":    "Business / Sponsor",
    "sme":         "Technical SME",
    "legal":       "Legal",
    "finance":     "Finance",
    "other":       "Other",
}
ROLE_KEYS: list[str] = list(ROLE_LABELS.keys())
ROLE_DROPDOWN: list[str] = [ROLE_LABELS[k] for k in ROLE_KEYS]

# Distinct colour per role for avatars.
ROLE_COLORS: dict[str, str] = {
    "procurement": DARK_BLUE,
    "business":    DEEP_PURPLE,
    "sme":         "#2A8C5A",
    "legal":       "#C07A00",
    "finance":     "#8A2BE2",
    "other":       LIGHT_PURPLE,
}


def label_to_key(label: str) -> str:
    for k, v in ROLE_LABELS.items():
        if v == label:
            return k
    return "other"


def key_to_label(key: str) -> str:
    return ROLE_LABELS.get(key, key.title())


# ---------------------------------------------------------------------------
# Session state accessors
# ---------------------------------------------------------------------------

def init_state():
    st.session_state.setdefault("team", [])
    st.session_state.setdefault("me_id", None)


def get_team() -> list[dict]:
    return st.session_state.get("team", [])


def get_me() -> dict | None:
    me_id = st.session_state.get("me_id")
    return next((t for t in get_team() if t.get("id") == me_id), None)


def is_set_up() -> bool:
    return bool(get_me())


def user_by_id(uid: str | None) -> dict | None:
    if not uid:
        return None
    return next((t for t in get_team() if t.get("id") == uid), None)


def user_by_name(name: str) -> dict | None:
    if not name:
        return None
    return next((t for t in get_team() if t.get("name") == name), None)


def first_user_for_role(role: str) -> dict | None:
    """Return the first team member with this role key, or None.

    Falls back through related roles so a spec row owned by 'business'
    still finds a 'sme' if no explicit business member exists.
    """
    team = get_team()
    if not team:
        return None
    u = next((t for t in team if t.get("role") == role), None)
    if u:
        return u
    if role == "procurement":
        for r in ("finance", "legal"):
            u = next((t for t in team if t.get("role") == r), None)
            if u:
                return u
    elif role == "business":
        for r in ("sme", "other"):
            u = next((t for t in team if t.get("role") == r), None)
            if u:
                return u
    elif role == "sme":
        for r in ("business", "other"):
            u = next((t for t in team if t.get("role") == r), None)
            if u:
                return u
    return team[0]


def centrica_email(name: str) -> str:
    """Derive an @centrica.com address from a person's name.

    'Jane Smith'  -> 'jane.smith@centrica.com'
    'Jane'        -> 'jane@centrica.com'
    ''            -> 'team@centrica.com'
    Reminders always use this — colleagues are Centrica employees.
    """
    parts = [p for p in (name or "").lower().split() if p]
    if not parts:
        return "team@centrica.com"
    safe = [
        "".join(ch for ch in p if ch.isalnum() or ch == "-")
        for p in parts
    ]
    safe = [s for s in safe if s]
    if not safe:
        return "team@centrica.com"
    return f"{'.'.join(safe)}@centrica.com"


def initials(name: str) -> str:
    parts = (name or "?").split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return (parts[0][:2] if parts else "?").upper()


def avatar_color(user: dict) -> str:
    return ROLE_COLORS.get(user.get("role", "other"), LIGHT_PURPLE)


def add_user(name: str, email: str, role_key: str) -> dict:
    """Append a new team member and return it. Assigns a unique id."""
    team = st.session_state.team
    next_n = len(team) + 1
    user = {
        "id": f"u{next_n}",
        "name": name.strip(),
        "email": (email or "").strip()
                  or f"{name.strip().lower().replace(' ', '.')}@example.com",
        "role": role_key,
    }
    team.append(user)
    return user


# ---------------------------------------------------------------------------
# Welcome screen
# ---------------------------------------------------------------------------

def render_welcome() -> bool:
    """Render the gating welcome form. Returns True if user is already set up."""
    init_state()
    if is_set_up():
        return True

    st.markdown("# 👋  Welcome to RFx Assistant")
    st.markdown(
        "Tell us who you are before we begin — the AI uses this to address "
        "the spec, scoring matrix and email reminders properly."
    )
    st.write("")

    with st.form("welcome_form", clear_on_submit=False):
        st.markdown("##### About you")
        c1, c2 = st.columns(2)
        name = c1.text_input(
            "Your name *", placeholder="e.g. Nicolas Bermudez", key="welcome_name",
        )
        email = c2.text_input(
            "Your email", placeholder="e.g. nicolas@example.com", key="welcome_email",
        )
        role_label = st.selectbox(
            "Your role on this RFx",
            ROLE_DROPDOWN,
            index=0,
            key="welcome_role",
        )

        st.markdown("---")
        st.markdown("##### Add a teammate  *(optional — you can add more later)*")
        st.caption(
            "Adding a teammate lets you try the collaboration flow straight away — "
            "spec rows can be assigned to them, and you can send email reminders to "
            "them when their parts are pending."
        )
        c3, c4 = st.columns(2)
        tm_name = c3.text_input(
            "Teammate name", placeholder="e.g. Jane Smith", key="welcome_tm_name",
        )
        tm_email = c4.text_input(
            "Teammate email", placeholder="e.g. jane@example.com", key="welcome_tm_email",
        )
        tm_role_label = st.selectbox(
            "Teammate role",
            ROLE_DROPDOWN,
            index=1,
            key="welcome_tm_role",
        )

        submitted = st.form_submit_button(
            "→  Get started",
            type="primary",
            use_container_width=True,
        )

        if submitted:
            if not name.strip():
                st.error("Please enter your name to continue.")
                return False

            st.session_state.team = []
            me = add_user(name, email, label_to_key(role_label))
            st.session_state.me_id = me["id"]

            if tm_name.strip():
                add_user(tm_name, tm_email, label_to_key(tm_role_label))

            st.rerun()
    return False


# ---------------------------------------------------------------------------
# Sidebar panel (always visible once set up)
# ---------------------------------------------------------------------------

def render_sidebar_panel():
    init_state()
    team = get_team()
    me = get_me()
    if not me:
        return

    st.markdown("**Team**")
    for t in team:
        is_me = (t["id"] == me["id"])
        suffix = " *(you)*" if is_me else ""
        color = avatar_color(t)
        inits = initials(t["name"])
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:8px;margin:4px 0'>"
            f"<span style='width:26px;height:26px;border-radius:50%;background:{color};"
            f"color:white;display:inline-flex;align-items:center;justify-content:center;"
            f"font-weight:700;font-size:11px;font-family:Arial'>{inits}</span>"
            f"<span><b>{t['name']}</b>{suffix}<br>"
            f"<small style='color:var(--muted)'>{key_to_label(t['role'])}</small></span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with st.expander("Manage team", expanded=False):
        st.markdown("**Add a teammate**")
        c1, c2 = st.columns(2)
        nm = c1.text_input("Name", key="add_tm_name")
        em = c2.text_input("Email", key="add_tm_email")
        role_lbl = st.selectbox("Role", ROLE_DROPDOWN, key="add_tm_role")
        if st.button("➕  Add teammate", use_container_width=True):
            if nm.strip():
                add_user(nm, em, label_to_key(role_lbl))
                # Clear inputs for next add
                for k in ("add_tm_name", "add_tm_email"):
                    if k in st.session_state:
                        st.session_state[k] = ""
                st.rerun()

        if len(team) > 1:
            st.markdown("**Remove**")
            removable = [t for t in team if t["id"] != me["id"]]
            if removable:
                target = st.selectbox(
                    "Remove teammate",
                    options=[t["id"] for t in removable],
                    format_func=lambda i: next(t["name"] for t in removable if t["id"] == i),
                    key="remove_tm_select",
                )
                if st.button("🗑  Remove selected", use_container_width=True):
                    st.session_state.team = [t for t in team if t["id"] != target]
                    st.rerun()

        st.divider()
        if st.button("↺  Reset everything (incl. spec & team)", use_container_width=True):
            keys_to_keep = {"theme"}
            for k in list(st.session_state.keys()):
                if k not in keys_to_keep:
                    del st.session_state[k]
            st.rerun()


