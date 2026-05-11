"""Spec co-author workspace.

A collaborative interface where the Category Manager (Procurement) and the
Business Stakeholder co-author the RFP spec with help from the agent. Solves
the workshop pain point of "tiny spec issues require chasing across the business"
by automating the chase (email + magic link + scheduled reminders) and giving
the business stakeholder a chat surface with the agent so they can contribute
without learning Ariba.
"""
from __future__ import annotations

import copy
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import streamlit as st

from rfx_assistant import data_loader as dl
from rfx_assistant.branding import (
    NAVY, MINT, LAVENDER, PALE_LAVENDER, PURPLE, WARN, NEGATIVE,
)
from rfx_assistant.ui import things


# -------------------------------------------------------------------
# Status vocabulary
# -------------------------------------------------------------------

STATUS = {
    "not_started":         {"label": "Not started",        "pill": "pill-pale",     "icon": "⚪"},
    "procurement_drafted": {"label": "Procurement drafted","pill": "pill-lavender", "icon": "🟣"},
    "awaiting_business":   {"label": "Awaiting business",  "pill": "pill-amber",    "icon": "🟠"},
    "business_in_review":  {"label": "Business reviewing", "pill": "pill-purple",   "icon": "🔵"},
    "signed_off":          {"label": "Signed off",         "pill": "pill-mint",     "icon": "🟢"},
}


# -------------------------------------------------------------------
# Session state setup
# -------------------------------------------------------------------

def _ensure_state():
    ws = st.session_state.get("collab_workspace")
    if ws is None:
        ws = copy.deepcopy(dl.spec_workspace())
        st.session_state.collab_workspace = ws
    st.session_state.setdefault("collab_persona", "procurement")
    st.session_state.setdefault("collab_focus_section", ws["sections"][2]["id"])  # opens on a pending one
    st.session_state.setdefault("collab_email_drafted", False)
    st.session_state.setdefault("collab_link_issued", True)
    st.session_state.setdefault("collab_reminder_cadence", "Off")
    st.session_state.setdefault("collab_chat_history", list(ws["agent_chat_seed"]["history"]))
    st.session_state.setdefault("collab_toast", None)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _human_time(iso: str) -> str:
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return iso
    delta = datetime.now(tz=timezone.utc) - t
    if delta < timedelta(minutes=1):
        return "just now"
    if delta < timedelta(hours=1):
        return f"{int(delta.total_seconds() // 60)}m ago"
    if delta < timedelta(days=1):
        return f"{int(delta.total_seconds() // 3600)}h ago"
    return t.strftime("%d %b · %H:%M")


# -------------------------------------------------------------------
# Atomic UI fragments
# -------------------------------------------------------------------

def _avatar_chip(persona: dict, *, size: int = 28, with_name: bool = False) -> str:
    initials = persona.get("avatar_initials") or persona["name"][:2]
    color = persona.get("avatar_color", PURPLE)
    name_html = (
        f"<span style='margin-left:8px;font-weight:600;color:{NAVY};font-size:13px'>"
        f"{persona['name']}</span>"
        if with_name else ""
    )
    return (
        f"<span style='display:inline-flex;align-items:center;vertical-align:middle'>"
        f"<span style='width:{size}px;height:{size}px;border-radius:50%;"
        f"background:{color};color:white;display:inline-flex;align-items:center;"
        f"justify-content:center;font-size:{int(size*0.42)}px;font-weight:700;"
        f"font-family:Arial;border:2px solid white;box-shadow:0 0 0 1px {color}40'>"
        f"{initials}</span>{name_html}</span>"
    )


def _status_pill(status_key: str) -> str:
    s = STATUS.get(status_key, STATUS["not_started"])
    return f"<span class='centrica-pill {s['pill']}'>{s['icon']} {s['label']}</span>"


def _owner_for(section: dict, personas: dict) -> list[dict]:
    owner = section["owner"]
    co = section.get("co_owner")
    out = []
    if owner == "both":
        out = [personas["procurement"], personas["business"]]
    elif owner in personas:
        out = [personas[owner]]
    if co and co in personas:
        out.append(personas[co])
    return out


def _push_activity(action: str, actor: str, actor_role: str, icon: str = "✏️"):
    ws = st.session_state.collab_workspace
    ws["activity"].insert(0, {
        "t": _now_iso(),
        "actor": actor,
        "actor_role": actor_role,
        "icon": icon,
        "action": action,
    })


# -------------------------------------------------------------------
# Public render
# -------------------------------------------------------------------

def render():
    _ensure_state()
    ws = st.session_state.collab_workspace
    personas = ws["personas"]

    # ---- Top banner with persona switcher + progress ----
    sections = ws["sections"]
    n_total = len(sections)
    n_done = sum(1 for s in sections if s["status"] == "signed_off")
    n_pending_business = sum(1 for s in sections if s["status"] == "awaiting_business")
    n_open_questions = sum(len(s.get("ai_questions", [])) for s in sections)

    me_id = st.session_state.collab_persona
    me = personas[me_id]
    other_id = "business" if me_id == "procurement" else "procurement"
    other = personas[other_id]

    # ----- header strip -----
    bg = (
        f"linear-gradient(135deg,{NAVY} 0%,{PURPLE} 100%)" if me_id == "procurement"
        else f"linear-gradient(135deg,{PURPLE} 0%,{LAVENDER} 100%)"
    )
    welcome = (
        f"Welcome back, <b>{me['name']}</b> — you have "
        f"<b>{n_pending_business if me_id == 'business' else n_total - n_done}</b> "
        f"section(s) waiting on you."
    )
    st.markdown(
        f"""
        <div style='background:{bg};color:white;padding:18px 22px;border-radius:14px;
        box-shadow:0 4px 18px rgba(15,32,103,0.18);margin-bottom:14px'>
            <div style='display:flex;justify-content:space-between;align-items:center;gap:18px'>
                <div>
                    <div style='font-size:12px;letter-spacing:0.06em;text-transform:uppercase;
                    opacity:0.75;font-family:Arial'>
                        Spec co-author workspace · {ws['title']}
                    </div>
                    <div style='font-size:18px;margin-top:4px'>{welcome}</div>
                </div>
                <div style='display:flex;align-items:center;gap:18px'>
                    <div style='text-align:center'>
                        <div style='font-size:28px;font-weight:800;font-family:Arial'>{n_done}/{n_total}</div>
                        <div style='font-size:11px;opacity:0.85'>sections signed off</div>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- Persona switcher row ----
    sw_l, sw_c, sw_r = st.columns([1.3, 1.1, 2.2])
    with sw_l:
        st.markdown("**Viewing as**")
        persona_pick = st.radio(
            "View as",
            options=["procurement", "business"],
            format_func=lambda p: f"👤  {personas[p]['name']} ({personas[p]['role'].split('—')[0].strip()})",
            index=0 if me_id == "procurement" else 1,
            label_visibility="collapsed",
            horizontal=False,
            key="collab_persona_radio",
        )
        if persona_pick != me_id:
            st.session_state.collab_persona = persona_pick
            _push_activity(f"opened the spec workspace", personas[persona_pick]["name"], persona_pick, icon="👁")
            st.rerun()
    with sw_c:
        st.markdown("**Quick stats**")
        st.markdown(
            f"""
            <div style='line-height:1.9'>
                <span class='centrica-pill pill-mint'>🟢 {n_done} signed off</span><br>
                <span class='centrica-pill pill-amber'>🟠 {n_pending_business} awaiting business</span><br>
                <span class='centrica-pill pill-purple'>❓ {n_open_questions} agent questions open</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with sw_r:
        st.markdown("**Live presence (last 10 min)**")
        present = [personas["procurement"], personas["business"], personas["sme"], {"name": "Agent", "avatar_initials": "AI", "avatar_color": MINT}]
        chips = "".join(_avatar_chip(p) for p in present)
        st.markdown(
            f"""
            <div style='display:flex;align-items:center;gap:6px;padding:10px 14px;
            background:var(--card);border:1px solid var(--border);border-radius:10px;min-height:54px'>
                {chips}
                <span style='margin-left:auto;color:{MINT};font-weight:600;font-size:12px'>● live</span>
            </div>
            <div style='font-size:11px;color:var(--muted);margin-top:4px'>
                Mark joined via magic link 22 min ago · Neil is editing Performance reqs
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.progress(n_done / n_total)
    st.write("")

    # ---- "Since you last visited" banner — persona-aware ----
    if me_id == "business":
        st.markdown(
            f"""
            <div class='centrica-card centrica-card-amber'>
                <b>Since your last visit (yesterday 16:42)</b> — Priya rebalanced the Evaluation weighting
                (Innovation -2%), Neil tightened the F-Gas threshold to GWP 675, and the Agent has 3 new
                questions for you across <b>Acceptance criteria</b> and <b>Risks</b>.
                <span class='centrica-pill pill-purple' style='margin-left:8px'>open the section to respond</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class='centrica-card centrica-card-lavender'>
                <b>Since your last visit (~30 min ago)</b> — Mark signed off Business need, Neil edited
                Performance requirements. <b>2 sections still need Mark's input</b> before RFP issue
                next Monday — use the chase panel on the right to nudge.
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.write("")

    # ---- toast ----
    if st.session_state.collab_toast:
        st.toast(st.session_state.collab_toast, icon="✉️")
        st.session_state.collab_toast = None

    # ---- Main 3-column workspace ----
    col_sections, col_detail, col_chase = st.columns([1.05, 2.1, 1.3], gap="medium")

    # === LEFT: sections list ===
    with col_sections:
        st.markdown("##### Spec sections")
        for sec in sections:
            owners = _owner_for(sec, personas)
            owner_chips = "".join(_avatar_chip(o, size=20) for o in owners)
            is_focused = sec["id"] == st.session_state.collab_focus_section
            mine = (
                me_id in (sec["owner"], sec.get("co_owner"))
                or sec["owner"] == "both"
            )
            border = NAVY if is_focused else "var(--border-soft)"
            bg = "var(--surface-2)" if is_focused else "var(--card)"
            mine_dot = (
                f"<span style='float:right;background:{MINT};color:{NAVY};font-size:10px;"
                f"font-weight:700;padding:2px 7px;border-radius:8px'>YOU</span>"
                if mine and not is_focused else ""
            )

            st.markdown(
                f"""
                <div style='background:{bg};border:1px solid {border};border-left:4px solid {NAVY if mine else LAVENDER};
                border-radius:8px;padding:10px 12px;margin-bottom:6px;cursor:pointer'>
                    <div style='font-weight:600;color:{NAVY};font-size:13px'>{sec['title']}{mine_dot}</div>
                    <div style='margin-top:6px;display:flex;justify-content:space-between;align-items:center'>
                        <div>{owner_chips}</div>
                        <div>{_status_pill(sec['status'])}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Open", key=f"open_{sec['id']}", use_container_width=True):
                st.session_state.collab_focus_section = sec["id"]
                st.rerun()

    # === CENTRE: focused section detail ===
    with col_detail:
        focused = next((s for s in sections if s["id"] == st.session_state.collab_focus_section), sections[0])
        owners = _owner_for(focused, personas)
        is_mine = me_id in (focused["owner"], focused.get("co_owner")) or focused["owner"] == "both"

        st.markdown(
            f"""
            <div style='background:var(--card);border:1px solid var(--border);border-top:4px solid {NAVY};
            border-radius:10px;padding:18px 22px'>
                <div style='display:flex;justify-content:space-between;align-items:flex-start;gap:14px'>
                    <div>
                        <div style='font-size:12px;color:{PURPLE};font-weight:600;letter-spacing:0.04em;text-transform:uppercase'>
                            Section · {focused['id']}
                        </div>
                        <h3 style='margin:4px 0 0 0'>{focused['title']}</h3>
                        <div style='margin-top:8px'>{"".join(_avatar_chip(o, size=22, with_name=True) + "&nbsp;&nbsp;" for o in owners)}</div>
                    </div>
                    <div style='text-align:right'>
                        {_status_pill(focused['status'])}<br>
                        <span class='small-muted'>Last edit: {focused['last_edited_by']} · {_human_time(focused['last_edited_at'])}</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Editable content (markdown). When the user is "the owner", show edit toggle.
        st.write("")
        edit_key = f"edit_{focused['id']}"
        edit_mode = st.session_state.get(edit_key, False)
        c_l, c_r = st.columns([5, 1.2])
        c_l.markdown("##### Section content")
        if is_mine and not edit_mode:
            if c_r.button("✏️  Edit", key=f"toggle_{focused['id']}", use_container_width=True):
                st.session_state[edit_key] = True
                st.rerun()
        elif edit_mode:
            if c_r.button("💾  Save", key=f"save_{focused['id']}", type="primary", use_container_width=True):
                new_text = st.session_state.get(f"text_{focused['id']}", focused["content"])
                if new_text != focused["content"]:
                    focused["content"] = new_text
                    focused["last_edited_by"] = me["name"]
                    focused["last_edited_at"] = _now_iso()
                    if focused["status"] == "awaiting_business" and me_id == "business":
                        focused["status"] = "business_in_review"
                    _push_activity(f"edited {focused['title']}", me["name"], me_id, icon="✏️")
                st.session_state[edit_key] = False
                st.rerun()

        if edit_mode:
            st.text_area(
                "Edit section",
                value=focused["content"],
                key=f"text_{focused['id']}",
                height=260,
                label_visibility="collapsed",
            )
        else:
            st.markdown(
                f"<div class='centrica-card'>{focused['content'].replace(chr(10), '  '+chr(10))}</div>",
                unsafe_allow_html=True,
            )

        # ---- AI questions ----
        if focused.get("ai_questions"):
            st.markdown("##### Open questions from the agent")
            owner_name = (
                personas['business']['name'].split(' ')[0]
                if focused['owner'] == 'business' else 'team'
            )
            things.inline(
                f"I've got <b>{len(focused['ai_questions'])}</b> question(s) for {owner_name} — "
                f"answers below auto-merge into the spec.",
                pose="question", size="sm",
            )
            for q in focused["ai_questions"]:
                st.markdown(
                    f"""
                    <div class='centrica-card centrica-card-amber'>
                        🤖 <b>Agent → {focused['owner'].title() if focused['owner'] != 'both' else 'Mark + Priya'}</b>
                        <span class='small-muted'>· {q['id']} · {_human_time(q['at'])}</span><br>
                        {q['text']}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if me_id in (focused["owner"], focused.get("co_owner")) or focused["owner"] == "both":
                    ans_key = f"ans_{q['id']}"
                    ans = st.text_input(
                        f"Answer {q['id']}",
                        key=ans_key,
                        placeholder="Type your answer — the agent will reformat it into the spec",
                        label_visibility="collapsed",
                    )
                    if ans and st.button(f"Submit answer to {q['id']}", key=f"submit_{q['id']}"):
                        focused["ai_questions"] = [x for x in focused["ai_questions"] if x["id"] != q["id"]]
                        focused["comments"].append({
                            "by": me["name"], "by_role": me_id,
                            "at": _now_iso(),
                            "text": f"Answered {q['id']}: {ans}",
                        })
                        if not focused["ai_questions"]:
                            focused["status"] = "business_in_review"
                        _push_activity(f"answered {q['id']} on {focused['title']}", me["name"], me_id, icon="✅")
                        st.session_state.collab_toast = f"Agent received your answer to {q['id']} and updated the spec."
                        st.rerun()

        # ---- Comments ----
        st.markdown("##### Comments")
        if not focused["comments"]:
            st.markdown("<div class='small-muted'>No comments yet.</div>", unsafe_allow_html=True)
        for c in focused["comments"]:
            avatar_p = personas.get(c["by_role"], {"name": c["by"], "avatar_initials": c["by"][:2], "avatar_color": PURPLE})
            st.markdown(
                f"""
                <div style='display:flex;gap:10px;margin:8px 0'>
                    <div>{_avatar_chip(avatar_p)}</div>
                    <div style='flex:1;background:var(--card);border:1px solid var(--border);border-radius:8px;padding:8px 12px'>
                        <div style='font-weight:600;font-size:13px;color:{NAVY}'>
                            {c['by']} <span class='small-muted'>· {_human_time(c['at'])}</span>
                        </div>
                        <div style='font-size:13px;margin-top:4px'>{c['text']}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        new_comment = st.text_input(
            "Add comment",
            key=f"newc_{focused['id']}",
            placeholder=f"Comment as {me['name']}…",
            label_visibility="collapsed",
        )
        c1, c2, c3 = st.columns([1, 1, 1.6])
        if c1.button("💬 Add comment", key=f"addc_{focused['id']}"):
            if new_comment.strip():
                focused["comments"].append({
                    "by": me["name"], "by_role": me_id,
                    "at": _now_iso(),
                    "text": new_comment.strip(),
                })
                _push_activity(f"commented on {focused['title']}", me["name"], me_id, icon="💬")
                st.session_state.collab_toast = "Comment added — visible to both stakeholders."
                st.rerun()
        if focused["status"] != "signed_off" and is_mine:
            if c2.button("✓  Sign off this section", key=f"sign_{focused['id']}", type="primary"):
                focused["status"] = "signed_off"
                _push_activity(f"signed off {focused['title']}", me["name"], me_id, icon="✓")
                st.session_state.collab_toast = f"{focused['title']} signed off."
                st.rerun()
        elif focused["status"] == "signed_off":
            c2.success("Signed off")

        # ---- Talk-to-the-agent chat ----
        st.markdown("---")
        st.markdown(
            f"##### {ws['agent_chat_seed']['title']}"
            f"  <span class='small-muted'>{ws['agent_chat_seed']['sub']}</span>",
            unsafe_allow_html=True,
        )
        things.inline(
            "Just talk normally — I'll reformat your words into the right spec section and "
            "show the diff above for sign-off.",
            pose="phone", size="sm",
        )
        chat_history = st.session_state.collab_chat_history
        for m in chat_history:
            if m["role"] == "agent":
                avatar = things.avatar("guide", "xs")
            elif m["role"] == "business":
                avatar = "👷"
            else:
                avatar = "🧑‍💼"
            bg_col = "var(--surface-2)" if m["role"] != "agent" else "var(--card)"
            border_col = PURPLE if m["role"] != "agent" else MINT
            label = (
                "Thing" if m["role"] == "agent"
                else (personas['business']['name'] if m['role'] == 'business'
                      else personas['procurement']['name'])
            )
            avatar_html = (
                avatar if m["role"] == "agent"
                else f"<span style='font-size:18px'>{avatar}</span>"
            )
            st.markdown(
                f"""
                <div style='background:{bg_col};border:1px solid var(--border);border-left:3px solid {border_col};
                border-radius:8px;padding:10px 14px;margin:6px 0;font-size:13px;display:flex;gap:10px;align-items:flex-start'>
                    <div style='flex-shrink:0'>{avatar_html}</div>
                    <div style='flex:1'>
                        <b style='color:{NAVY}'>{label}</b>
                        <div style='margin-top:4px;color:var(--text)'>{m['text']}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        chat_in = st.text_input(
            "Talk to agent",
            key=f"chat_{focused['id']}",
            placeholder=(
                "e.g. 'Push the burn-in to 100% IT load — Mitie were right'  →  agent updates the spec"
                if me_id == "business" else
                "e.g. 'Add a clause requiring quarterly PUE reporting'  →  agent suggests insertion point"
            ),
            label_visibility="collapsed",
        )
        if st.button("Send to agent", key=f"chat_send_{focused['id']}"):
            if chat_in.strip():
                chat_history.append({"role": me_id, "text": chat_in.strip()})
                # Mocked agent response
                agent_reply = _mock_agent_reply(chat_in.strip(), focused, me_id)
                chat_history.append({"role": "agent", "text": agent_reply})
                _push_activity(f"chatted with agent about {focused['title']}", me["name"], me_id, icon="💬")
                st.session_state.collab_toast = "Agent picked up your input."
                st.rerun()

    # === RIGHT: org-wide pending actions + chase board + activity feed ===

    _PENDING_BOARD = [
        {
            "name": "Mark Hendricks", "role": "IT Infrastructure Director",
            "email": "mark.hendricks@centrica.com", "initials": "MH", "color": NAVY,
            "blocking": "🚦 Blocking: RFP issue next Monday",
            "items": [
                "Q1 — Acceptance criteria: pre-approved auditor list",
                "Q2 — Acceptance criteria: 80% vs 100% burn-in load",
                "Q3 — Risks: Cardiff PUE waiver decision (accept/hold)",
            ],
            "has_magic_link": True,
            "email_subject": "5 minutes please — IT-INF-DC-COOL-2026 spec needs your input",
            "email_body": ws["email_template"]["body"],
            "email_to": "mark.hendricks@centrica.com",
            "email_cc": "neil.gallagher@centrica.com",
            "chase_key": "mark",
        },
        {
            "name": "Neil Gallagher", "role": "Principal Critical-Facilities Engineer",
            "email": "neil.gallagher@centrica.com", "initials": "NG", "color": "#2A8C5A",
            "blocking": "🚦 Blocking: SME scoring — Procurement Council 28 Jul",
            "items": [
                "Score 5 TECHNICAL criteria in Score Matrix (Tab 3)",
                "Score 2 SUSTAIN criteria in Score Matrix (Tab 3)",
                "Confirm burn-in load on Acceptance criteria (co-owner)",
            ],
            "has_magic_link": False,
            "email_subject": "SME scoring needed — IT-INF-DC-COOL-2026",
            "email_body": (
                "Hi Neil,\n\nThe 3 bids are in and normalised. I need your scores on the Technical "
                "and Sustainability pillars before the Procurement Council on 28 July. Your rows are "
                "pre-highlighted in the scoring matrix.\n\n"
                "  → Score the bids: https://rfx.centrica.com/score/IT-INF-DC-COOL-2026?token=ng-sme\n\n"
                "Shouldn't take more than 45 minutes.\n\nThanks,\nPriya"
            ),
            "email_to": "neil.gallagher@centrica.com",
            "email_cc": "mark.hendricks@centrica.com",
            "chase_key": "neil",
        },
        {
            "name": "Aisha Bello", "role": "TPRM Lead",
            "email": "aisha.bello@centrica.com", "initials": "AB", "color": "#C07A00",
            "blocking": "🚦 Blocking: Award decision — 4 Aug 2026",
            "items": [
                "TPRM profile: Helios Critical Infrastructure plc",
                "TPRM profile: NorthernAir Solutions GmbH (F-Gas tier-2 flag)",
            ],
            "has_magic_link": False,
            "email_subject": "TPRM needed before award — IT-INF-DC-COOL-2026",
            "email_body": (
                "Hi Aisha,\n\nWe need TPRM sign-off on two suppliers before the Procurement Council "
                "pack goes out:\n\n  • Helios Critical Infrastructure plc\n"
                "  • NorthernAir Solutions GmbH (tier-2 F-Gas flag)\n\n"
                "  → TPRM portal: https://tprm.centrica.com/review/IT-INF-DC-COOL-2026\n\n"
                "We need this by 18 July.\n\nThanks,\nPriya"
            ),
            "email_to": "aisha.bello@centrica.com",
            "email_cc": "",
            "chase_key": "aisha",
        },
        {
            "name": "Rob Fenwick", "role": "ESG & Sustainability Director",
            "email": "rob.fenwick@centrica.com", "initials": "RF", "color": PURPLE,
            "blocking": "🚦 Blocking: Procurement Council sign-off",
            "items": [
                "ESG sign-off: Cardiff PUE waiver (1.25 → 1.28)",
                "Carbon review: NorthernAir R-454B refrigerant exposure",
            ],
            "has_magic_link": False,
            "email_subject": "ESG sign-off needed — Cardiff PUE waiver & R-454B",
            "email_body": (
                "Hi Rob,\n\nTwo ESG items need your sign-off before the award recommendation:\n\n"
                "  1. Cardiff PUE waiver: agent recommends accepting 1.28 (vs 1.25 target), "
                "conditional on annual review — Welsh Water dry-cooler constraint.\n"
                "  2. NorthernAir R-454B spot price up 12% in 30 days — lifecycle carbon risk OK?\n\n"
                "  → ESG review pack: https://rfx.centrica.com/esg/IT-INF-DC-COOL-2026\n\n"
                "Thanks,\nPriya"
            ),
            "email_to": "rob.fenwick@centrica.com",
            "email_cc": "neil.gallagher@centrica.com",
            "chase_key": "rob",
        },
    ]

    with col_chase:
        things.inline(
            "I track every open action across the whole stakeholder team — "
            "email, magic link, auto-reminders, or a Teams ping. No spreadsheet.",
            pose="phone", size="sm",
        )
        st.markdown("##### Pending actions — by stakeholder")

        for entry in _PENDING_BOARD:
            sent_key = f"chase_sent_{entry['chase_key']}"
            drafted_key = f"chase_drafted_{entry['chase_key']}"
            st.session_state.setdefault(sent_key, False)
            st.session_state.setdefault(drafted_key, False)

            chased = st.session_state[sent_key]
            label = (
                f"✅ {entry['name']} — chased"
                if chased else
                f"🟠 {entry['name']} · {len(entry['items'])} item{'s' if len(entry['items']) != 1 else ''}"
            )

            with st.expander(label, expanded=not chased):
                st.caption(entry["blocking"])
                for item in entry["items"]:
                    st.markdown(f"- {item}")

                btn_cols = st.columns(2) if not entry["has_magic_link"] else st.columns(3)
                if btn_cols[0].button("📧 Email", key=f"draft_{entry['chase_key']}", use_container_width=True):
                    st.session_state[drafted_key] = not st.session_state[drafted_key]
                if btn_cols[1].button("💬 Teams", key=f"teams_{entry['chase_key']}", use_container_width=True):
                    _push_activity(
                        f"pinged {entry['name']} in Teams",
                        personas["procurement"]["name"], "procurement", icon="💬",
                    )
                    st.session_state.collab_toast = f"Teams message sent to @{entry['name'].replace(' ','')}."
                    st.rerun()
                if entry["has_magic_link"] and len(btn_cols) > 2:
                    if btn_cols[2].button("🔗 Link", key=f"link_{entry['chase_key']}", use_container_width=True):
                        _push_activity(
                            f"re-issued magic link to {entry['name']}",
                            personas["procurement"]["name"], "procurement", icon="🔗",
                        )
                        st.session_state.collab_toast = f"Fresh magic link issued to {entry['name']}."
                        st.rerun()

                if st.session_state[drafted_key]:
                    st.markdown("**✉️ AI-drafted email — ready to send**")
                    st.caption(
                        f"To: {entry['email_to']}"
                        + (f"  ·  Cc: {entry['email_cc']}" if entry['email_cc'] else "")
                    )
                    st.info(f"**Subject:** {entry['email_subject']}")
                    st.text_area(
                        "Body",
                        value=entry["email_body"],
                        height=160,
                        key=f"email_body_{entry['chase_key']}",
                        label_visibility="collapsed",
                    )
                    if st.button("➤ Send now", key=f"send_{entry['chase_key']}", type="primary", use_container_width=True):
                        with st.spinner("Sending via Centrica Outlook…"):
                            time.sleep(0.8)
                        _push_activity(
                            f"sent chase email to {entry['name']}",
                            personas["procurement"]["name"], "procurement", icon="📧",
                        )
                        st.session_state[drafted_key] = False
                        st.session_state[sent_key] = True
                        st.session_state.collab_toast = (
                            f"Email sent to {entry['email_to']} — "
                            "they can respond without logging into Ariba."
                        )
                        st.rerun()

        # ---- Auto-reminder cadence ----
        st.divider()
        st.markdown("**Auto-reminder cadence** — all open actions")
        cad = st.selectbox(
            "Cadence",
            options=["Off", "Every 3 days", "Every 24 hours", "Daily until done"],
            index=["Off", "Every 3 days", "Every 24 hours", "Daily until done"].index(
                st.session_state.collab_reminder_cadence
            ),
            label_visibility="collapsed",
        )
        if cad != st.session_state.collab_reminder_cadence:
            st.session_state.collab_reminder_cadence = cad
            if cad != "Off":
                _push_activity(
                    f"set auto-reminder cadence to '{cad}' for all open actions",
                    personas["procurement"]["name"], "procurement", icon="⏰",
                )
                st.session_state.collab_toast = f"Auto-reminder set to '{cad}' — all 4 stakeholders will be nudged."
            st.rerun()

        # ---- Activity feed ----
        st.divider()
        st.markdown("##### Activity feed")
        st.caption("Every action by every stakeholder + the agent, in real time.")
        for ev in ws["activity"][:14]:
            actor_color = personas.get(ev["actor_role"], {}).get("avatar_color", MINT)
            st.markdown(
                f"{ev['icon']} **{ev['actor']}** {ev['action']}  \n"
                f"<span style='color:var(--muted);font-size:11px'>{_human_time(ev['t'])}</span>",
                unsafe_allow_html=True,
            )


# -------------------------------------------------------------------
# Mocked agent reply
# -------------------------------------------------------------------

def _mock_agent_reply(user_text: str, section: dict, role: str) -> str:
    text = user_text.lower()
    if any(w in text for w in ("burn-in", "100%", "burn in")):
        return (
            "Updated Item 2 of the Acceptance criteria to '14-day burn-in at 100% of design IT load' "
            "and added a note in the comment thread crediting Mitie's prior experience. Q1 is still open — "
            "do you want me to seed the auditor list with Arup / WSP / Cundall?"
        )
    if "arup" in text or "wsp" in text or "cundall" in text or "auditor" in text:
        return (
            "Locked the pre-approved auditor list as Arup, WSP and Cundall, mirroring the Hams Hall "
            "refresh contract. Both your open questions on Acceptance criteria are now resolved — "
            "marking the section as 'Business reviewing'."
        )
    if "cardiff" in text or "waiver" in text or "pue" in text:
        return (
            "Recording a 0.03 PUE waiver for Cardiff (1.25 → 1.28), conditional on annual review and "
            "without prejudice to other clusters. Added a note to the Risks section and flagged Rob "
            "Fenwick (ESG) for visibility — no approval blocker but he should know."
        )
    if "weighting" in text or "evaluation" in text:
        return (
            f"I can re-balance the evaluation weighting within the constraint that Procurement-scored "
            f"pillars stay at 60% and SME-scored pillars at 40% — confirm the change you want and I'll "
            f"surface it for {('Mark' if role == 'procurement' else 'Priya')} to co-sign."
        )
    return (
        f"Got it — captured against '{section['title']}'. I'll surface a draft amendment in the section above "
        f"for {('Mark' if role == 'procurement' else 'Priya')} to review."
    )
