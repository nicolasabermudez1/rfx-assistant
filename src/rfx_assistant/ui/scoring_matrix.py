"""Scoring Matrix tab.

Multi-user editable scoring table. Criteria are inherited from the spec
the user built in the Spec Builder tab. Each criterion is assigned to a
scorer (team member). Any user can chase pending scorers — they pick the
specific criteria to include, and the email is sent to firstname.lastname
@centrica.com automatically.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from rfx_assistant.ui import team

# Fallback criteria for users who skip the Spec Builder.
_FALLBACK_CRITERIA: list[dict] = [
    {"id": "SC-01", "pillar": "Technical",   "criterion": "Technical capability & fit-for-purpose",  "weight": 25, "scorer": "sme"},
    {"id": "SC-02", "pillar": "Technical",   "criterion": "Build quality & reliability",             "weight": 15, "scorer": "sme"},
    {"id": "SC-03", "pillar": "Commercial",  "criterion": "Total cost of ownership (TCO)",           "weight": 20, "scorer": "procurement"},
    {"id": "SC-04", "pillar": "Commercial",  "criterion": "Warranty, support & SLA",                 "weight": 15, "scorer": "procurement"},
    {"id": "SC-05", "pillar": "Legal",       "criterion": "Compliance & regulatory fit",             "weight": 10, "scorer": "procurement"},
    {"id": "SC-06", "pillar": "ESG",         "criterion": "Supplier ESG credentials",                "weight": 10, "scorer": "business"},
    {"id": "SC-07", "pillar": "Operational", "criterion": "Integration & deployment ease",           "weight":  5, "scorer": "business"},
]

_DEFAULT_SUPPLIERS = ["Supplier A", "Supplier B", "Supplier C"]


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def _init():
    st.session_state.setdefault("sm_criteria", [])
    st.session_state.setdefault("sm_suppliers", list(_DEFAULT_SUPPLIERS))
    st.session_state.setdefault("sm_activity", [])
    st.session_state.setdefault("sm_reminder_drafted", {})
    st.session_state.setdefault("sm_reminder_sent", {})


def _active_user() -> dict | None:
    # Always the logged-in user — no persona switching.
    return team.get_me()


def _push_activity(action: str, actor: dict, icon: str = "✏️"):
    st.session_state.sm_activity.insert(0, {
        "t": datetime.now(tz=timezone.utc).isoformat(),
        "actor": actor.get("name", "?") if actor else "?",
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


def _with_original(c: dict) -> dict:
    """Ensure a criterion has an 'original' snapshot (for the track-changes view)."""
    if "original" not in c:
        c["original"] = {
            "pillar":    c.get("pillar"),
            "criterion": c.get("criterion"),
            "weight":    c.get("weight"),
            "scorer":    c.get("scorer") or c.get("scorer_name"),
        }
    return c


def _scorer_name(role_or_name: str) -> str:
    """Map a stored 'scorer' (role key or name) to a team-member display name."""
    members = team.get_team()
    if not members:
        return role_or_name or "Unassigned"
    # If it matches an existing team-member name, use it
    if any(m["name"] == role_or_name for m in members):
        return role_or_name
    # Else treat as a role key and look up first matching team member
    u = team.first_user_for_role(role_or_name or "procurement")
    return u["name"] if u else members[0]["name"]


def _data_editor_tall(df, col_cfg, *, num_rows: str, key: str, height: int):
    try:
        return st.data_editor(
            df, column_config=col_cfg, use_container_width=True,
            num_rows=num_rows, hide_index=True, row_height=72,
            height=height, key=key,
        )
    except TypeError:
        return st.data_editor(
            df, column_config=col_cfg, use_container_width=True,
            num_rows=num_rows, hide_index=True, height=height, key=key,
        )


# ---------------------------------------------------------------------------
# Public render
# ---------------------------------------------------------------------------

def render():
    _init()
    me = _active_user()
    if not me:
        st.warning("Please set up your profile on the welcome screen first.")
        return

    criteria: list[dict] = st.session_state.sm_criteria
    suppliers: list[str] = st.session_state.sm_suppliers
    spec = st.session_state.get("sb_spec")
    members = team.get_team()

    st.markdown("### Scoring Matrix")
    if spec:
        st.caption(
            f"Criteria tailored for **{spec['category']}** — "
            "score suppliers against the dimensions that matter for THIS product."
        )
    else:
        st.caption(
            "Score suppliers against weighted criteria. "
            "Criteria are tailored to the product you built in the Spec Builder."
        )

    st.divider()

    # Empty state
    if not criteria:
        if spec and spec.get("scoring_criteria"):
            st.session_state.sm_criteria = [_with_original(dict(c)) for c in spec["scoring_criteria"]]
            criteria = st.session_state.sm_criteria
        else:
            st.info(
                "**No scoring criteria yet.** "
                "Head to **📋 Spec Builder**, describe what you're buying, and the AI "
                "will generate product-specific scoring criteria automatically."
            )
            if st.button("Load generic criteria (skip Spec Builder)", use_container_width=False):
                st.session_state.sm_criteria = [dict(c) for c in _FALLBACK_CRITERIA]
                st.rerun()
            return

    # Sync prompt when spec criteria diverge
    if spec and spec.get("scoring_criteria"):
        spec_ids = {c["id"] for c in spec["scoring_criteria"]}
        current_ids = {c["id"] for c in criteria}
        if spec_ids != current_ids:
            c_l, c_r = st.columns([4, 1])
            c_l.warning(
                f"Scoring criteria differ from the latest spec ({spec['category']}). "
                "Click → to re-sync."
            )
            if c_r.button("🔄  Sync to spec", use_container_width=True):
                st.session_state.sm_criteria = [_with_original(dict(c)) for c in spec["scoring_criteria"]]
                for k in list(st.session_state.keys()):
                    if k.startswith("sm_sent_") or k.startswith("sm_drafted_"):
                        st.session_state[k] = False
                st.rerun()

    # Supplier config
    with st.expander("Configure supplier names", expanded=False):
        s_cols = st.columns(3)
        for i, col in enumerate(s_cols):
            suppliers[i] = col.text_input(
                f"Supplier {i + 1}", value=suppliers[i], key=f"sm_sup_{i}",
            )
        st.session_state.sm_suppliers = suppliers

    col_matrix, col_collab = st.columns([2.6, 1])

    # ---- LEFT: scoring table ----
    with col_matrix:
        st.markdown("##### Scoring table")
        st.caption(
            "Scores are 1–10. Leave blank if not yet assessed. Total weight should sum to 100%."
        )

        # Resolve each scorer entry to a team-member name (for display)
        member_names = [m["name"] for m in members] if members else ["Unassigned"]
        for c in criteria:
            stored = c.get("scorer", "")
            c["scorer_name"] = _scorer_name(stored) if stored not in member_names else stored
            c.setdefault("last_edited_by", "AI")
            c.setdefault("last_edited_at", datetime.now(tz=timezone.utc).isoformat())
            _with_original(c)

        def _edit_badge(c: dict) -> str:
            by = c.get("last_edited_by", "AI")
            at = c.get("last_edited_at", "")
            if by == "AI":
                return "🤖 AI · drafted"
            return f"✏️ {by.split()[0]} · {_human_time(at)}" if at else f"✏️ {by.split()[0]}"

        df = pd.DataFrame([
            {
                "ID": c["id"],
                "Pillar": c.get("pillar", "Technical"),
                "Criterion": c.get("criterion", ""),
                "Weight (%)": int(c.get("weight") or 0),
                "Scorer": c["scorer_name"],
                suppliers[0]: c.get("s_a"),
                suppliers[1]: c.get("s_b"),
                suppliers[2]: c.get("s_c"),
                "Last edit": _edit_badge(c),
            }
            for c in criteria
        ])

        col_cfg = {
            "ID": st.column_config.TextColumn("ID", width="small", disabled=True),
            "Pillar": st.column_config.SelectboxColumn(
                "Pillar", width="small",
                options=["Technical", "Commercial", "Legal", "Operational", "ESG"],
            ),
            "Criterion": st.column_config.TextColumn("Criterion", width="large"),
            "Weight (%)": st.column_config.NumberColumn(
                "Weight %", min_value=0, max_value=100, step=1, width="small",
            ),
            "Scorer": st.column_config.SelectboxColumn(
                "Scorer", width="medium", options=member_names,
            ),
            suppliers[0]: st.column_config.NumberColumn(
                suppliers[0], min_value=1, max_value=10, step=1, width="small",
            ),
            suppliers[1]: st.column_config.NumberColumn(
                suppliers[1], min_value=1, max_value=10, step=1, width="small",
            ),
            suppliers[2]: st.column_config.NumberColumn(
                suppliers[2], min_value=1, max_value=10, step=1, width="small",
            ),
            "Last edit": st.column_config.TextColumn(
                "Last edit", width="medium", disabled=True,
                help="🤖 AI = drafted by agent. ✏️ Name = edited by that user.",
            ),
        }

        edited = _data_editor_tall(
            df, col_cfg, num_rows="dynamic",
            key="sm_editor",
            height=min(700, 100 + 80 * len(df)),
        )

        # Sync back, preserving / updating attribution per row
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        new_criteria: list[dict] = []
        auto_id = len(criteria) + 1
        changed = False
        for idx, row in edited.iterrows():
            row_id = str(row.get("ID") or "")
            if not row_id:
                row_id = f"SC-{auto_id:02d}"
                auto_id += 1
            scorer_name = str(row.get("Scorer", "")).strip() or (member_names[0] if member_names else "Unassigned")
            s_a = row[suppliers[0]] if pd.notna(row[suppliers[0]]) else None
            s_b = row[suppliers[1]] if pd.notna(row[suppliers[1]]) else None
            s_c = row[suppliers[2]] if pd.notna(row[suppliers[2]]) else None
            orig = criteria[idx] if idx < len(criteria) else {}
            new_c = {
                "id": row_id,
                "pillar": str(row.get("Pillar", "Technical")),
                "criterion": str(row.get("Criterion", "")),
                "weight": int(row.get("Weight (%)") or 0),
                "scorer": scorer_name,
                "scorer_name": scorer_name,
                "s_a": s_a, "s_b": s_b, "s_c": s_c,
                "last_edited_by": orig.get("last_edited_by", "AI"),
                "last_edited_at": orig.get("last_edited_at", now_iso),
                "original": orig.get("original"),  # preserve AI snapshot
            }
            # Compare core fields (excluding attribution) to detect a user edit
            core_keys = ("pillar", "criterion", "weight", "scorer", "s_a", "s_b", "s_c")
            if any(orig.get(k) != new_c[k] for k in core_keys):
                new_c["last_edited_by"] = me["name"]
                new_c["last_edited_at"] = now_iso
                changed = True
            elif not orig:
                changed = True
            new_criteria.append(new_c)

        if changed:
            st.session_state.sm_criteria = new_criteria
            criteria = new_criteria
            _push_activity("updated the scoring matrix", me, icon="✏️")

        total_w = sum(c.get("weight") or 0 for c in criteria)
        if total_w != 100:
            st.warning(f"Weights sum to {total_w}% — they should total 100%.")

        scored = [
            c for c in criteria
            if c.get("s_a") is not None or c.get("s_b") is not None or c.get("s_c") is not None
        ]
        if scored:
            def weighted_avg(key: str) -> float | None:
                rows = [c for c in scored if c.get(key) is not None and c.get("weight")]
                if not rows:
                    return None
                denom = sum(c["weight"] for c in rows)
                if not denom:
                    return None
                return sum((c[key] or 0) * c["weight"] for c in rows) / denom

            wa, wb, wc = weighted_avg("s_a"), weighted_avg("s_b"), weighted_avg("s_c")
            st.markdown("**Weighted scores (scored criteria only)**")
            sc1, sc2, sc3 = st.columns(3)
            sc1.metric(suppliers[0], f"{wa:.1f} / 10" if wa is not None else "—")
            sc2.metric(suppliers[1], f"{wb:.1f} / 10" if wb is not None else "—")
            sc3.metric(suppliers[2], f"{wc:.1f} / 10" if wc is not None else "—")

        csv = edited.to_csv(index=False)
        st.download_button(
            "⬇  Download scoring matrix",
            data=csv,
            file_name="scoring_matrix.csv",
            mime="text/csv",
        )

        # ---- Track Changes panel (Word-style diff vs AI draft) ----
        _CRIT_TRACK_FIELDS = (
            ("criterion", "Criterion"),
            ("pillar",    "Pillar"),
            ("weight",    "Weight (%)"),
            ("scorer",    "Scorer"),
        )
        crit_changes = []
        for c in criteria:
            orig = c.get("original") or {}
            diffs = []
            for key, label in _CRIT_TRACK_FIELDS:
                old = orig.get(key)
                new = c.get(key) if key != "scorer" else (c.get("scorer_name") or c.get("scorer"))
                if str(old or "") != str(new or ""):
                    diffs.append((label, old, new))
            if diffs:
                crit_changes.append((c, diffs))

        st.write("")
        if crit_changes:
            with st.expander(
                f"📝  Track changes — {len(crit_changes)} criterion / criteria edited since the AI draft",
                expanded=True,
            ):
                st.caption(
                    "Each entry shows what the AI originally drafted vs the current "
                    "version, like Word's track-changes view."
                )
                for c, diffs in crit_changes:
                    by = c.get("last_edited_by", "Unknown")
                    at = _human_time(c.get("last_edited_at", "")) if c.get("last_edited_at") else ""
                    actor_label = (
                        f"<b>{by.split()[0] if by != 'AI' else by}</b>"
                        f" · <span style='color:var(--muted);font-size:11px'>{at}</span>"
                    )
                    st.markdown(
                        f"<div style='border-left:3px solid var(--brand-deep-purple);"
                        f"padding:8px 14px;margin:8px 0;background:var(--surface-2);"
                        f"border-radius:6px'>"
                        f"<div style='font-weight:700;font-size:13px'>"
                        f"{c['id']} · {c.get('criterion','')}</div>"
                        f"<div style='font-size:11px;color:var(--muted);margin-bottom:6px'>"
                        f"edited by {actor_label}</div>"
                        + "".join(
                            f"<div style='font-size:13px;margin:4px 0'>"
                            f"<b>{label}:</b><br>"
                            f"<del style='color:#b3303f;background:#ffe9eb;"
                            f"padding:2px 6px;border-radius:3px;text-decoration:line-through;"
                            f"margin-right:6px;display:inline-block'>"
                            f"{(str(old) if old not in (None, '') else '—')}</del>"
                            f"<ins style='color:#0a6e2a;background:#dcf6e3;"
                            f"padding:2px 6px;border-radius:3px;text-decoration:none;"
                            f"display:inline-block'>"
                            f"{(str(new) if new not in (None, '') else '—')}</ins>"
                            f"</div>"
                            for (label, old, new) in diffs
                        )
                        + "</div>",
                        unsafe_allow_html=True,
                    )
        else:
            st.caption(
                "📝  *Track changes will appear here once anyone edits a criterion — "
                "every change is logged against its author.*"
            )

    # ---- RIGHT: collaboration ----
    with col_collab:
        st.markdown("##### Collaboration")

        # Rows the active user must score
        my_pending = [
            c for c in criteria
            if c.get("scorer_name") == me["name"]
            and (c.get("s_a") is None or c.get("s_b") is None or c.get("s_c") is None)
        ]
        if my_pending:
            st.info(f"**{len(my_pending)} criterion / criteria** need your scores.")

        # Pending by other team members
        pending_by_user: dict[str, list[dict]] = {}
        for c in criteria:
            scorer = c.get("scorer_name", "")
            if not scorer or scorer == me["name"]:
                continue
            if (c.get("s_a") is None or c.get("s_b") is None or c.get("s_c") is None):
                pending_by_user.setdefault(scorer, []).append(c)

        if not pending_by_user:
            if len(members) <= 1:
                st.caption(
                    "Add a teammate from the sidebar (Manage team) so they can be "
                    "assigned criteria to score."
                )
            else:
                st.success("All scorers have submitted! ✓")
        else:
            for scorer_name, rows in pending_by_user.items():
                target = team.user_by_name(scorer_name)
                target_id = target["id"] if target else scorer_name
                sent = st.session_state.sm_reminder_sent.get(target_id, False)
                drafted = st.session_state.sm_reminder_drafted.get(target_id, False)

                if sent:
                    st.success(f"✅ Reminder sent to {scorer_name.split()[0]}")
                else:
                    with st.expander(
                        f"🟠 {scorer_name.split()[0]} — {len(rows)} pending",
                        expanded=True,
                    ):
                        for r in rows[:5]:
                            st.markdown(f"- {r['criterion']}")
                        if len(rows) > 5:
                            st.caption(f"+ {len(rows) - 5} more")

                        if st.button(
                            f"📧  Draft reminder to {scorer_name.split()[0]}",
                            key=f"sm_draft_{target_id}",
                            use_container_width=True,
                        ):
                            st.session_state.sm_reminder_drafted[target_id] = not drafted

                        if st.session_state.sm_reminder_drafted.get(target_id):
                            st.caption("**Pick the criteria to include in the reminder:**")
                            selected = []
                            for r in rows:
                                sel_key = f"sm_pick_{target_id}_{r['id']}"
                                if sel_key not in st.session_state:
                                    st.session_state[sel_key] = True
                                if st.checkbox(
                                    f"`{r['id']}` · {r['criterion']} ({r.get('weight', 0)}%)",
                                    key=sel_key,
                                ):
                                    selected.append(r)

                            if not selected:
                                st.warning("Select at least one criterion.")
                            else:
                                to_addr = team.centrica_email(scorer_name)
                                rows_txt = "\n".join(
                                    f"  - {r['id']} · {r['criterion']} (weight {r.get('weight', 0)}%)"
                                    for r in selected
                                )
                                cat = (spec or {}).get("category", "the current RFx")
                                body = (
                                    f"Hi {scorer_name.split()[0]},\n\n"
                                    f"Quick reminder — the following criteria need your "
                                    f"scores (1-10) for each of the three suppliers in "
                                    f"the '{cat}' scoring matrix:\n\n"
                                    f"{rows_txt}\n\n"
                                    f"Please log in and submit your scores.\n\n"
                                    f"Thanks,\n{me['name']}"
                                )
                                st.caption(f"**To:** {to_addr}")
                                st.text_area(
                                    "body", value=body, height=190,
                                    key=f"sm_body_{target_id}",
                                    label_visibility="collapsed",
                                )
                                if st.button(
                                    f"➤  Send reminder ({len(selected)} criterion{'a' if len(selected) != 1 else ''})",
                                    type="primary",
                                    key=f"sm_send_{target_id}",
                                    use_container_width=True,
                                ):
                                    with st.spinner("Sending via Outlook…"):
                                        time.sleep(0.6)
                                    st.session_state.sm_reminder_sent[target_id] = True
                                    st.session_state.sm_reminder_drafted[target_id] = False
                                    _push_activity(
                                        f"sent scoring reminder ({len(selected)} item(s)) to {scorer_name} <{to_addr}>",
                                        me, icon="📧",
                                    )
                                    st.toast(f"Reminder sent to {to_addr}", icon="📧")
                                    st.rerun()

        st.divider()
        st.markdown("**Activity**")
        feed = st.session_state.sm_activity
        if not feed:
            st.caption("No activity yet.")
        for ev in feed[:10]:
            st.markdown(
                f"{ev['icon']} **{ev['actor']}** {ev['action']}  \n"
                f"<span style='color:var(--muted);font-size:11px'>"
                f"{_human_time(ev['t'])}</span>",
                unsafe_allow_html=True,
            )
