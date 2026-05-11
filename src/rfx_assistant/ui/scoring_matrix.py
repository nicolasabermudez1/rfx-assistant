"""Scoring Matrix tab.

Multi-user editable scoring table. Each criterion is assigned to a scorer.
Any persona can chase pending scorers via a simulated email reminder.
Weighted scores are auto-calculated as rows are filled in.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from rfx_assistant.branding import DARK_BLUE, DEEP_PURPLE, MINT_PINK, WARN

# ---------------------------------------------------------------------------
# Personas (3 for scoring: procurement, business, sme)
# ---------------------------------------------------------------------------

PERSONAS: dict[str, dict] = {
    "procurement": {
        "name": "Priya Rai",
        "role": "Category Manager",
        "initials": "PR",
        "color": DARK_BLUE,
        "email": "priya.rai@centrica.com",
    },
    "business": {
        "name": "Mark Hendricks",
        "role": "Business Sponsor",
        "initials": "MH",
        "color": DEEP_PURPLE,
        "email": "mark.hendricks@centrica.com",
    },
    "sme": {
        "name": "Neil Gallagher",
        "role": "Technical SME",
        "initials": "NG",
        "color": "#2A8C5A",
        "email": "neil.gallagher@centrica.com",
    },
}

PERSONA_KEYS = list(PERSONAS.keys())

_DEFAULT_CRITERIA: list[dict] = [
    {"id": "C-01", "pillar": "Technical",   "criterion": "Technical capability & solution fit",   "weight": 20, "scorer": "sme",         "s_a": None, "s_b": None, "s_c": None},
    {"id": "C-02", "pillar": "Technical",   "criterion": "Implementation approach & timeline",     "weight": 10, "scorer": "sme",         "s_a": None, "s_b": None, "s_c": None},
    {"id": "C-03", "pillar": "Technical",   "criterion": "Business requirements alignment",        "weight": 15, "scorer": "business",    "s_a": None, "s_b": None, "s_c": None},
    {"id": "C-04", "pillar": "Commercial",  "criterion": "Total cost of ownership (10-yr TCO)",   "weight": 20, "scorer": "procurement", "s_a": None, "s_b": None, "s_c": None},
    {"id": "C-05", "pillar": "Commercial",  "criterion": "Pricing structure & transparency",       "weight": 10, "scorer": "procurement", "s_a": None, "s_b": None, "s_c": None},
    {"id": "C-06", "pillar": "Legal",       "criterion": "Contract terms & risk allocation",       "weight":  5, "scorer": "procurement", "s_a": None, "s_b": None, "s_c": None},
    {"id": "C-07", "pillar": "ESG",         "criterion": "Supplier sustainability & ESG",          "weight": 10, "scorer": "business",    "s_a": None, "s_b": None, "s_c": None},
    {"id": "C-08", "pillar": "Commercial",  "criterion": "Financial stability & references",       "weight":  5, "scorer": "procurement", "s_a": None, "s_b": None, "s_c": None},
    {"id": "C-09", "pillar": "Operational", "criterion": "After-sales support & SLA",             "weight":  5, "scorer": "business",    "s_a": None, "s_b": None, "s_c": None},
]

_DEFAULT_SUPPLIERS = ["Supplier A", "Supplier B", "Supplier C"]


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _init():
    st.session_state.setdefault("sm_persona", "procurement")
    # sm_criteria starts empty — populated by Spec Builder when spec is generated
    st.session_state.setdefault("sm_criteria", [])
    st.session_state.setdefault("sm_suppliers", list(_DEFAULT_SUPPLIERS))
    st.session_state.setdefault("sm_activity", [])
    for pk in PERSONA_KEYS:
        st.session_state.setdefault(f"sm_drafted_{pk}", False)
        st.session_state.setdefault(f"sm_sent_{pk}", False)


def _push_activity(action: str, persona_key: str, icon: str = "✏️"):
    p = PERSONAS[persona_key]
    st.session_state.sm_activity.insert(0, {
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
# Public render
# ---------------------------------------------------------------------------

def render():
    _init()

    me = st.session_state.sm_persona
    my_p = PERSONAS[me]
    criteria: list[dict] = st.session_state.sm_criteria
    suppliers: list[str] = st.session_state.sm_suppliers
    spec = st.session_state.get("sb_spec")

    # ---- Header + persona switcher ----
    col_title, col_persona = st.columns([3, 1])
    with col_title:
        st.markdown("### Scoring Matrix")
        if spec:
            st.caption(
                f"Criteria tailored for **{spec['category']}** — "
                "score suppliers against the dimensions that matter for THIS product."
            )
        else:
            st.caption(
                "Score suppliers against weighted criteria. "
                "Criteria are tailored to the product you're buying."
            )
    with col_persona:
        st.markdown("**Viewing as**")
        pick = st.radio(
            "sm_persona_radio",
            options=PERSONA_KEYS,
            format_func=lambda p: (
                f"{PERSONAS[p]['name'].split()[0]}  "
                f"({PERSONAS[p]['role'].split()[0]})"
            ),
            index=PERSONA_KEYS.index(me),
            label_visibility="collapsed",
            key="sm_persona_radio",
        )
        if pick != me:
            st.session_state.sm_persona = pick
            st.rerun()

    st.divider()

    # ---- Empty state: prompt user to build a spec first ----
    if not criteria:
        if spec and spec.get("scoring_criteria"):
            # Spec exists but criteria not synced — sync now
            st.session_state.sm_criteria = [dict(c) for c in spec["scoring_criteria"]]
            criteria = st.session_state.sm_criteria
        else:
            st.info(
                "**No scoring criteria yet.** "
                "Head over to **📋 Spec Builder** and describe what you're buying — "
                "the AI will generate a product-specific spec table AND a tailored "
                "scoring matrix. They'll appear here automatically."
            )
            col_a, col_b = st.columns([1, 1])
            with col_a:
                if st.button(
                    "Load generic criteria (skip Spec Builder)",
                    use_container_width=True,
                ):
                    st.session_state.sm_criteria = [dict(c) for c in _DEFAULT_CRITERIA]
                    st.rerun()
            return

    # Re-sync from spec if criteria don't match
    if spec and spec.get("scoring_criteria"):
        spec_ids = {c["id"] for c in spec["scoring_criteria"]}
        current_ids = {c["id"] for c in criteria}
        if spec_ids != current_ids:
            col_l, col_r = st.columns([4, 1])
            col_l.warning(
                f"Scoring criteria differ from the latest spec ({spec['category']}). "
                "Click → to re-sync."
            )
            if col_r.button("🔄  Sync to spec", use_container_width=True):
                st.session_state.sm_criteria = [dict(c) for c in spec["scoring_criteria"]]
                for k in list(st.session_state.keys()):
                    if k.startswith("sm_sent_") or k.startswith("sm_drafted_"):
                        st.session_state[k] = False
                st.rerun()

    # ---- Supplier name config ----
    with st.expander("Configure supplier names", expanded=False):
        s_cols = st.columns(3)
        for i, col in enumerate(s_cols):
            suppliers[i] = col.text_input(
                f"Supplier {i + 1}",
                value=suppliers[i],
                key=f"sm_sup_{i}",
            )
        st.session_state.sm_suppliers = suppliers

    col_matrix, col_collab = st.columns([2.6, 1])

    # ---- LEFT: scoring table ----
    with col_matrix:
        st.markdown("##### Scoring table")
        st.caption(
            "Scores are 1–10. Leave blank if not yet assessed. "
            "Total weight should sum to 100%."
        )

        scorer_names = [PERSONAS[p]["name"] for p in PERSONA_KEYS]
        name_to_key = {v["name"]: k for k, v in PERSONAS.items()}

        df = pd.DataFrame([
            {
                "ID": c["id"],
                "Pillar": c["pillar"],
                "Criterion": c["criterion"],
                "Weight (%)": int(c.get("weight") or 0),
                "Scorer": PERSONAS[c["scorer"]]["name"],
                suppliers[0]: c.get("s_a"),
                suppliers[1]: c.get("s_b"),
                suppliers[2]: c.get("s_c"),
            }
            for c in criteria
        ])

        col_cfg = {
            "ID": st.column_config.TextColumn("ID", width=60, disabled=True),
            "Pillar": st.column_config.SelectboxColumn(
                "Pillar", width=105,
                options=["Technical", "Commercial", "Legal", "Operational", "ESG"],
            ),
            "Criterion": st.column_config.TextColumn("Criterion", width=220),
            "Weight (%)": st.column_config.NumberColumn(
                "Weight %", min_value=0, max_value=100, step=1, width=80,
            ),
            "Scorer": st.column_config.SelectboxColumn(
                "Scorer", width=135,
                options=scorer_names,
            ),
            suppliers[0]: st.column_config.NumberColumn(
                suppliers[0], min_value=1, max_value=10, step=1, width=95,
            ),
            suppliers[1]: st.column_config.NumberColumn(
                suppliers[1], min_value=1, max_value=10, step=1, width=95,
            ),
            suppliers[2]: st.column_config.NumberColumn(
                suppliers[2], min_value=1, max_value=10, step=1, width=95,
            ),
        }

        edited = st.data_editor(
            df,
            column_config=col_cfg,
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            key="sm_editor",
        )

        # Sync edited rows back
        new_criteria: list[dict] = []
        auto_id = len(criteria) + 1
        changed = False
        for idx, row in edited.iterrows():
            row_id = str(row.get("ID") or "")
            if not row_id:
                row_id = f"C-{auto_id:02d}"
                auto_id += 1
            scorer_key = name_to_key.get(str(row.get("Scorer", "")), "procurement")
            s_a = row[suppliers[0]] if pd.notna(row[suppliers[0]]) else None
            s_b = row[suppliers[1]] if pd.notna(row[suppliers[1]]) else None
            s_c = row[suppliers[2]] if pd.notna(row[suppliers[2]]) else None
            new_c = {
                "id": row_id,
                "pillar": str(row.get("Pillar", "Technical")),
                "criterion": str(row.get("Criterion", "")),
                "weight": int(row.get("Weight (%)") or 0),
                "scorer": scorer_key,
                "s_a": s_a,
                "s_b": s_b,
                "s_c": s_c,
            }
            # Check for change vs original
            if idx < len(criteria):
                orig = criteria[idx]
                if any(orig.get(k) != new_c[k] for k in new_c):
                    changed = True
            else:
                changed = True
            new_criteria.append(new_c)

        if changed:
            st.session_state.sm_criteria = new_criteria
            criteria = new_criteria
            _push_activity("updated the scoring matrix", me, icon="✏️")

        # Weight total warning
        total_w = sum(c.get("weight") or 0 for c in criteria)
        if total_w != 100:
            st.warning(f"Weights sum to {total_w}% — they should total 100%.")

        # Weighted scores (only criteria that have at least one score)
        scored = [c for c in criteria if c.get("s_a") is not None or c.get("s_b") is not None or c.get("s_c") is not None]
        if scored:
            def weighted_avg(key: str) -> float | None:
                rows = [c for c in scored if c.get(key) is not None and c.get("weight")]
                if not rows:
                    return None
                denom = sum(c["weight"] for c in rows)
                if not denom:
                    return None
                return sum((c[key] or 0) * c["weight"] for c in rows) / denom

            wa = weighted_avg("s_a")
            wb = weighted_avg("s_b")
            wc = weighted_avg("s_c")

            st.markdown("**Weighted scores (scored criteria only)**")
            sc1, sc2, sc3 = st.columns(3)
            sc1.metric(suppliers[0], f"{wa:.1f} / 10" if wa is not None else "—")
            sc2.metric(suppliers[1], f"{wb:.1f} / 10" if wb is not None else "—")
            sc3.metric(suppliers[2], f"{wc:.1f} / 10" if wc is not None else "—")

        # Download
        csv = edited.to_csv(index=False)
        st.download_button(
            "⬇  Download scoring matrix",
            data=csv,
            file_name="scoring_matrix.csv",
            mime="text/csv",
        )

    # ---- RIGHT: collaboration panel ----
    with col_collab:
        st.markdown("##### Collaboration")

        # My pending rows
        my_pending = [
            c for c in criteria
            if c.get("scorer") == me
            and (c.get("s_a") is None or c.get("s_b") is None or c.get("s_c") is None)
        ]
        if my_pending:
            st.info(f"**{len(my_pending)} criterion / criteria** need your scores.")
        st.write("")

        # Pending by other scorers
        other_pending: dict[str, list[dict]] = {}
        for c in criteria:
            sk = c.get("scorer", "procurement")
            if sk == me:
                continue
            if c.get("s_a") is None or c.get("s_b") is None or c.get("s_c") is None:
                other_pending.setdefault(sk, []).append(c)

        if other_pending:
            for scorer_key, rows in other_pending.items():
                sp = PERSONAS[scorer_key]
                sent_key = f"sm_sent_{scorer_key}"
                drafted_key = f"sm_drafted_{scorer_key}"

                if st.session_state.get(sent_key):
                    st.success(f"✅ Reminder sent to {sp['name'].split()[0]}")
                else:
                    with st.expander(
                        f"🟠 {sp['name'].split()[0]} — {len(rows)} row(s) pending",
                        expanded=True,
                    ):
                        for r in rows[:5]:
                            st.markdown(f"- {r['criterion']}")
                        if len(rows) > 5:
                            st.caption(f"+ {len(rows) - 5} more")

                        if st.button(
                            f"📧  Remind {sp['name'].split()[0]}",
                            key=f"sm_btn_{scorer_key}",
                            use_container_width=True,
                        ):
                            st.session_state[drafted_key] = not st.session_state.get(drafted_key, False)

                        if st.session_state.get(drafted_key):
                            rows_txt = "\n".join(
                                f"  - {r['criterion']} (weight {r['weight']}%)"
                                for r in rows[:6]
                            )
                            body = (
                                f"Hi {sp['name'].split()[0]},\n\n"
                                f"Your scores are needed on {len(rows)} "
                                f"criterion / criteria in the RFx scoring matrix:\n\n"
                                f"{rows_txt}\n\n"
                                f"Please log in and add your scores (1–10) "
                                f"for each of the three suppliers.\n\n"
                                f"Thanks,\n{my_p['name']}"
                            )
                            st.caption(f"To: {sp['email']}")
                            st.text_area(
                                "body",
                                value=body,
                                height=170,
                                key=f"sm_body_{scorer_key}",
                                label_visibility="collapsed",
                            )
                            if st.button(
                                "➤  Send",
                                type="primary",
                                key=f"sm_send_{scorer_key}",
                                use_container_width=True,
                            ):
                                with st.spinner("Sending…"):
                                    time.sleep(0.5)
                                st.session_state[sent_key] = True
                                st.session_state[drafted_key] = False
                                _push_activity(
                                    f"sent scoring reminder to {sp['name']}",
                                    me, icon="📧",
                                )
                                st.toast(f"Reminder sent to {sp['name']}", icon="📧")
                                st.rerun()
        else:
            st.success("All scorers have submitted their scores! ✓")

        # Activity feed
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
