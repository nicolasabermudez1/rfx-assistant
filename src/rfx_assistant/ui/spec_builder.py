"""Spec Builder tab.

Chatbot asks the user what they want to buy, Gemini generates a structured
technical specification table for any spend category. Multiple personas can
collaborate on the table, and either can send an email reminder to the other.
"""
from __future__ import annotations

import copy
import time
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from rfx_assistant import agents
from rfx_assistant.branding import DARK_BLUE, DEEP_PURPLE, LIGHT_PURPLE, MINT_PINK, WARN

# ---------------------------------------------------------------------------
# Personas
# ---------------------------------------------------------------------------

PERSONAS: dict[str, dict] = {
    "procurement": {
        "name": "Priya Rai",
        "role": "Senior Category Manager",
        "initials": "PR",
        "color": DARK_BLUE,
        "email": "priya.rai@centrica.com",
    },
    "business": {
        "name": "Mark Hendricks",
        "role": "IT Infrastructure Director",
        "initials": "MH",
        "color": DEEP_PURPLE,
        "email": "mark.hendricks@centrica.com",
    },
}

# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _init():
    st.session_state.setdefault("sb_persona", "procurement")
    st.session_state.setdefault("sb_messages", [])
    st.session_state.setdefault("sb_spec", None)
    st.session_state.setdefault("sb_stage", 0)
    st.session_state.setdefault("sb_activity", [])
    st.session_state.setdefault("sb_reminder_drafted", False)
    st.session_state.setdefault("sb_reminder_sent", False)
    st.session_state.setdefault("sb_generating", False)


def _push_activity(action: str, persona_key: str, icon: str = "✏️"):
    p = PERSONAS[persona_key]
    st.session_state.sb_activity.insert(0, {
        "t": datetime.now(tz=timezone.utc).isoformat(),
        "actor": p["name"],
        "icon": icon,
        "action": action,
    })


def _human_time(iso: str) -> str:
    try:
        t = datetime.fromisoformat(iso)
        secs = (datetime.now(tz=timezone.utc) - t).total_seconds()
        if secs < 60:
            return "just now"
        if secs < 3600:
            return f"{int(secs // 60)}m ago"
        return f"{int(secs // 3600)}h ago"
    except Exception:
        return iso


# ---------------------------------------------------------------------------
# Chatbot logic
# ---------------------------------------------------------------------------

_GREETING = (
    "Hi! I'm your RFx Assistant. **What are you looking to procure?** "
    "Describe it in a few words — it could be anything from software licences "
    "to industrial batteries to professional services."
)


def _bot_reply_for_stage(stage: int, user_msg: str) -> tuple[str, bool]:
    """Return (bot reply text, should_generate_now)."""
    if stage == 0:
        return (
            f"Got it — **{user_msg.strip()}**. A couple of quick questions "
            f"to build the right spec:\n\n"
            f"**What is the approximate scale or volume?** "
            f"(e.g. number of units, sites, users, or estimated contract value)",
            False,
        )
    if stage == 1:
        return (
            "Thanks. One more:\n\n"
            "**Any key constraints or standards that must be met?** "
            "(e.g. regulatory requirements, certifications, timeline, geographic scope) "
            "— or type **none** to proceed.",
            False,
        )
    # stage 2 — ready to generate
    return (
        "Perfect — I have everything I need. "
        "**Building your technical specification now…**",
        True,
    )


# ---------------------------------------------------------------------------
# Public render
# ---------------------------------------------------------------------------

def render():
    _init()

    me = st.session_state.sb_persona
    other = "business" if me == "procurement" else "procurement"
    my_p = PERSONAS[me]
    other_p = PERSONAS[other]

    # ---- Persona switcher header ----
    col_title, col_persona = st.columns([3, 1])
    with col_title:
        st.markdown("### Spec Builder")
        st.caption(
            "Describe what you're buying — the AI builds a technical specification "
            "table. Edit rows, assign owners, and send reminders to collaborators."
        )
    with col_persona:
        st.markdown("**Viewing as**")
        pick = st.radio(
            "persona",
            options=["procurement", "business"],
            format_func=lambda p: (
                f"{PERSONAS[p]['name'].split()[0]}  "
                f"({PERSONAS[p]['role'].split()[0]})"
            ),
            index=0 if me == "procurement" else 1,
            label_visibility="collapsed",
            key="sb_persona_radio",
        )
        if pick != me:
            st.session_state.sb_persona = pick
            st.rerun()

    st.divider()

    if st.session_state.sb_stage < 4:
        _render_chat()
    else:
        _render_workspace()


# ---------------------------------------------------------------------------
# Chatbot phase
# ---------------------------------------------------------------------------

def _render_chat():
    msgs = st.session_state.sb_messages

    # Seed greeting on first load
    if not msgs:
        msgs.append({"role": "assistant", "content": _GREETING})

    # Display history
    for m in msgs:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # If we're ready to generate, do it now (before showing the input)
    if st.session_state.sb_stage == 3 and not st.session_state.sb_generating:
        st.session_state.sb_generating = True
        with st.spinner("Calling Gemini to build your specification…"):
            spec = agents.generate_spec_from_conversation(msgs)
        st.session_state.sb_spec = spec
        st.session_state.sb_stage = 4
        st.session_state.sb_generating = False
        _push_activity(
            f"generated spec for '{spec['category']}' "
            f"({len(spec['requirements'])} requirements)",
            st.session_state.sb_persona,
            icon="🤖",
        )
        st.rerun()
        return

    # Chat input (only while still in chat phase)
    if st.session_state.sb_stage < 3:
        if prompt := st.chat_input("Type your answer…"):
            stage = st.session_state.sb_stage
            msgs.append({"role": "user", "content": prompt})
            reply, generate_now = _bot_reply_for_stage(stage, prompt)
            msgs.append({"role": "assistant", "content": reply})
            st.session_state.sb_stage = stage + 1
            st.rerun()


# ---------------------------------------------------------------------------
# Workspace phase (spec table + collaboration)
# ---------------------------------------------------------------------------

def _render_workspace():
    spec = st.session_state.sb_spec
    me = st.session_state.sb_persona
    other = "business" if me == "procurement" else "procurement"
    my_p = PERSONAS[me]
    other_p = PERSONAS[other]
    reqs: list[dict] = spec["requirements"]

    # Summary header
    st.markdown(f"**{spec['category']}** — {spec['summary']}")

    # KPI strip
    n_total = len(reqs)
    n_mine = sum(1 for r in reqs if r.get("owner") == me)
    n_approved = sum(1 for r in reqs if r.get("status", "").lower() == "approved")
    n_draft = n_total - n_approved

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Requirements", n_total)
    m2.metric("Assigned to you", n_mine)
    m3.metric("Approved", n_approved)
    m4.metric("Draft / Review", n_draft)

    st.write("")

    col_table, col_side = st.columns([2.6, 1])

    # ---- LEFT: editable spec table ----
    with col_table:
        st.markdown("##### Specification table")
        st.caption("Click any cell to edit. Owner and Status columns drive collaboration tracking.")

        owner_display = {
            "procurement": my_p["name"] if me == "procurement" else other_p["name"],
            "business": other_p["name"] if me == "procurement" else my_p["name"],
        }
        proc_name = PERSONAS["procurement"]["name"]
        biz_name = PERSONAS["business"]["name"]

        df = pd.DataFrame([
            {
                "ID": r["id"],
                "Section": r.get("section", "Technical"),
                "Requirement": r.get("title", ""),
                "Description & Acceptance Criteria": r.get("description", ""),
                "Priority": r.get("priority", "Must"),
                "Owner": proc_name if r.get("owner") == "procurement" else biz_name,
                "Status": r.get("status", "Draft").capitalize(),
                "Comments": r.get("comments", ""),
            }
            for r in reqs
        ])

        col_cfg = {
            "ID": st.column_config.TextColumn("ID", width=75, disabled=True),
            "Section": st.column_config.SelectboxColumn(
                "Section", width=110,
                options=["Technical", "Commercial", "Legal", "Operational", "ESG"],
            ),
            "Requirement": st.column_config.TextColumn("Requirement", width=155),
            "Description & Acceptance Criteria": st.column_config.TextColumn(
                "Description & Acceptance Criteria", width=330,
            ),
            "Priority": st.column_config.SelectboxColumn(
                "Priority", width=90,
                options=["Must", "Should", "Could"],
            ),
            "Owner": st.column_config.SelectboxColumn(
                "Owner", width=140,
                options=[proc_name, biz_name],
            ),
            "Status": st.column_config.SelectboxColumn(
                "Status", width=115,
                options=["Draft", "Under Review", "Approved"],
            ),
            "Comments": st.column_config.TextColumn("Comments", width=180),
        }

        edited = st.data_editor(
            df,
            column_config=col_cfg,
            use_container_width=True,
            num_rows="fixed",
            hide_index=True,
            key="sb_spec_editor",
        )

        # Sync edits back to session state
        changed = False
        for i, row in edited.iterrows():
            if i >= len(reqs):
                break
            new_owner = "procurement" if row["Owner"] == proc_name else "business"
            new_status = str(row["Status"]).capitalize()
            r = reqs[i]
            if (
                r.get("section") != row["Section"]
                or r.get("title") != row["Requirement"]
                or r.get("description") != row["Description & Acceptance Criteria"]
                or r.get("priority") != row["Priority"]
                or r.get("owner") != new_owner
                or r.get("status", "Draft").capitalize() != new_status
                or r.get("comments", "") != row["Comments"]
            ):
                r["section"] = row["Section"]
                r["title"] = row["Requirement"]
                r["description"] = row["Description & Acceptance Criteria"]
                r["priority"] = row["Priority"]
                r["owner"] = new_owner
                r["status"] = new_status
                r["comments"] = row["Comments"]
                changed = True

        if changed:
            _push_activity("updated the specification table", me, icon="✏️")

        btn_l, btn_r = st.columns([1, 1])
        with btn_l:
            csv = edited.to_csv(index=False)
            st.download_button(
                "⬇  Download as CSV",
                data=csv,
                file_name=f"{spec['category'].replace(' ', '_')}_spec.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with btn_r:
            if st.button("↺  Start new spec", use_container_width=True):
                for k in ["sb_messages", "sb_spec", "sb_stage", "sb_activity",
                          "sb_reminder_drafted", "sb_reminder_sent", "sb_generating"]:
                    st.session_state.pop(k, None)
                st.rerun()

    # ---- RIGHT: collaboration panel ----
    with col_side:
        st.markdown("##### Collaboration")

        other_draft = [
            r for r in reqs
            if r.get("owner") == other
            and r.get("status", "Draft").lower() not in ("approved",)
        ]
        my_draft = [
            r for r in reqs
            if r.get("owner") == me
            and r.get("status", "Draft").lower() not in ("approved",)
        ]

        if my_draft:
            st.info(f"**{len(my_draft)} row(s) assigned to you** still need your input.")

        st.write("")

        if other_draft:
            if st.session_state.sb_reminder_sent:
                st.success(f"✅ Reminder sent to {other_p['name']}")
            else:
                st.warning(
                    f"**{other_p['name']}** has **{len(other_draft)} requirement(s)** "
                    f"pending their review."
                )
                if st.button(
                    f"📧  Remind {other_p['name'].split()[0]}",
                    use_container_width=True,
                    key="sb_draft_btn",
                ):
                    st.session_state.sb_reminder_drafted = not st.session_state.sb_reminder_drafted

                if st.session_state.sb_reminder_drafted:
                    rows_txt = "\n".join(
                        f"  - {r['title']}" for r in other_draft[:6]
                    )
                    extra = len(other_draft) - 6
                    if extra > 0:
                        rows_txt += f"\n  ...and {extra} more"

                    body = (
                        f"Hi {other_p['name'].split()[0]},\n\n"
                        f"Quick reminder — there are {len(other_draft)} requirement(s) "
                        f"in the '{spec['category']}' spec that still need your sign-off:\n\n"
                        f"{rows_txt}\n\n"
                        f"Please log in to the RFx Assistant, review each row, "
                        f"and update the Status to 'Approved' (or add comments).\n\n"
                        f"Thanks,\n{my_p['name']}"
                    )
                    st.caption(f"To: {other_p['email']}")
                    st.text_area(
                        "body",
                        value=body,
                        height=210,
                        key="sb_email_body",
                        label_visibility="collapsed",
                    )
                    if st.button(
                        "➤  Send reminder",
                        type="primary",
                        use_container_width=True,
                        key="sb_send_btn",
                    ):
                        with st.spinner("Sending via Outlook…"):
                            time.sleep(0.7)
                        st.session_state.sb_reminder_sent = True
                        st.session_state.sb_reminder_drafted = False
                        _push_activity(
                            f"sent reminder to {other_p['name']}",
                            me, icon="📧",
                        )
                        st.toast(f"Reminder sent to {other_p['name']}", icon="📧")
                        st.rerun()
        else:
            st.success(f"All of {other_p['name'].split()[0]}'s requirements are approved! ✓")

        # Activity feed
        st.divider()
        st.markdown("**Activity**")
        feed = st.session_state.sb_activity
        if not feed:
            st.caption("No activity yet.")
        for ev in feed[:10]:
            st.markdown(
                f"{ev['icon']} **{ev['actor']}** {ev['action']}  \n"
                f"<span style='color:var(--muted);font-size:11px'>"
                f"{_human_time(ev['t'])}</span>",
                unsafe_allow_html=True,
            )
