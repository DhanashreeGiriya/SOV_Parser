"""
Auto-extracted module: ui/phase2_review.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from sov_app.feedback.header_feedback import save_feedback
from sov_app.header_mapping.models import LockedSchema, MappingDecision
from sov_app.ui.common import _human_basis, _match_type_display, safe_join, to_excel_bytes

def render_phase2(sov, system, auto_threshold):
    if "phase1_result" not in st.session_state:
        st.info("Complete Phase 1 first.", icon="ℹ️")
        return None

    st.markdown("Review mappings. Override or accept individual columns. Lock the schema to proceed to transformation.")

    result   = st.session_state["phase1_result"]
    mappings = result["mappings"]
    raw_hdrs = result["raw_headers"]

    # ------------------------------------------------------------------
    # FORCE EVERY COLUMN INTO REVIEW
    # ------------------------------------------------------------------
    needs_review = mappings.copy()

    # No auto-accepted columns anymore
    auto_accept = []

    c1, c2 = st.columns(2)
    c1.metric(
        "Auto-accepted",
        len(auto_accept),
        help=f"Confidence ≥ {auto_threshold}% — no action needed"
    )
    c2.metric("Needs review", len(needs_review))

    if "overrides" not in st.session_state:
        st.session_state["overrides"] = {}

    if needs_review:
        st.markdown("---")

        b1, b2, b3, b4 = st.columns(4)

        with b1:
            if st.button("🔴  Missing / Required", use_container_width=True, key="flt_red"):
                st.session_state["review_filter"] = "red"

        with b2:
            if st.button("🟡  Low Confidence", use_container_width=True, key="flt_yellow"):
                st.session_state["review_filter"] = "yellow"

        with b3:
            if st.button("🟢  Medium / High Confidence", use_container_width=True, key="flt_green"):
                st.session_state["review_filter"] = "green"

        with b4:
            if st.button("⬜  Show All", use_container_width=True, key="flt_all"):
                st.session_state["review_filter"] = "all"

        af = st.session_state.get("review_filter", "all")

        filter_labels = {
            "red":    "🔴 Missing or required fields (0% confidence)",
            "yellow": "🟡 Low confidence (1–59%)",
            "green":  "🟢 Medium / High confidence (60–100%)",
            "all":    "Showing all columns for review",
        }

        st.markdown(
            f'<p style="font-size:.78rem;color:var(--muted);margin:.3rem 0 .8rem">'
            f'{filter_labels.get(af,"")}</p>',
            unsafe_allow_html=True
        )

        if af == "red":
            display = [
                m for m in needs_review
                if m.confidence == 0 or m.flag in (
                    "missing_required",
                    "missing_source",
                    "missing"
                )
            ]

        elif af == "yellow":
            display = [
                m for m in needs_review
                if 0 < m.confidence < 60
            ]

        elif af == "green":
            display = [
                m for m in needs_review
                if m.confidence >= 60
            ]

        else:
            display = needs_review

        if not display:
            st.info("No columns match this filter.", icon="ℹ️")

        else:
            for m in display:

                icon = (
                    "🔴"
                    if (
                        m.confidence == 0
                        or m.flag in (
                            "missing_required",
                            "missing_source",
                            "missing"
                        )
                    )
                    else (
                        "🟡"
                        if m.confidence < 60
                        else "🟢"
                    )
                )

                label, _, _ = _match_type_display(m.match_type)

                src_display = (
                    safe_join(m.source_cols)
                    if m.source_cols
                    else "nothing"
                )

                with st.expander(
                    f"{icon} **{m.output_col}** · {label} · {m.confidence}% confidence",
                    expanded=(
                        m.confidence == 0
                        or m.flag in (
                            "missing_required",
                            "missing_source",
                            "missing"
                        )
                    )
                ):

                    cl, cr = st.columns([2, 3])

                    with cl:
                        st.markdown(f"**Currently mapped to:** `{src_display}`")

                        if m.flag:
                            st.markdown(f"**Issue:** `{m.flag}`")

                        ai_r = getattr(m, "ai_reasoning", "")

                        if ai_r:
                            st.markdown(f"**Validation note:** *{ai_r}*")

                        basis = _human_basis(m)

                        if basis:
                            st.markdown(f"**Why:** {basis}")

                        if len(m.source_cols) > 1:
                            st.markdown(
                                f"**All source columns:** "
                                f"{safe_join(f'`{s}`' for s in m.source_cols)}"
                            )

                    with cr:
                        kp = f"rev_{m.output_col}"

                        action = st.selectbox(
                            "Action",
                            ["accept", "override", "mark as unavailable"],
                            key=f"{kp}_action"
                        )

                        if action == "override":

                            chosen = st.multiselect(
                                "Choose source column(s)",
                                raw_hdrs,
                                default=m.source_cols,
                                key=f"{kp}_cols"
                            )

                            reason = st.text_input(
                                "Reason for change",
                                key=f"{kp}_reason"
                            )

                            st.session_state["overrides"][m.output_col] = {
                                "action": "override",
                                "source_cols": chosen,
                                "reason": reason
                            }

                        elif action == "mark as unavailable":

                            reason = st.text_input(
                                "Reason (optional)",
                                key=f"{kp}_reason2"
                            )

                            st.session_state["overrides"][m.output_col] = {
                                "action": "unavailable",
                                "source_cols": [],
                                "reason": reason
                            }

                        else:
                            st.session_state["overrides"][m.output_col] = {
                                "action": "accept",
                                "source_cols": m.source_cols,
                                "reason": ""
                            }

    else:
        st.success(
            "All columns meet the confidence threshold — no manual review needed.",
            icon="✅"
        )

    st.markdown("---")

    reviewer = st.text_input(
        "Reviewer name",
        "analyst",
        key="reviewer_name"
    )

    template_name = st.text_input(
        "Template name (for reuse)",
        "SOV_template",
        key="template_name"
    )

    if st.button("🔒  Lock Mapping → Proceed to Transform", use_container_width=True):

        import datetime

        overrides = st.session_state.get("overrides", {})

        orig_src = {
            m.output_col: list(m.source_cols)
            for m in mappings
        }

        for m in mappings:

            if m.output_col in overrides:

                ov = overrides[m.output_col]

                m.source_cols = ov["source_cols"]

                if ov["action"] == "unavailable":
                    m.flag = "unavailable"
                    m.notes += " | Marked unavailable"

                elif ov["action"] == "override":
                    m.flag = ""
                    m.match_type = "human_override"
                    m.confidence = 100
                    m.notes = f"Override: {ov['reason']}"

        now = datetime.datetime.utcnow().isoformat()

        decisions = []

        for m in mappings:

            ov = overrides.get(m.output_col, {})

            decisions.append(
                sov.MappingDecision(
                    output_col=m.output_col,
                    original_source=orig_src[m.output_col],
                    original_confidence=m.confidence,
                    original_match_type=m.match_type,
                    decision=ov.get("action", "auto"),
                    final_source=m.source_cols,
                    override_reason=ov.get("reason", ""),
                    reviewer=reviewer,
                    timestamp=now
                )
            )
        locked = sov.LockedSchema(
            target_system=system,
            sov_file=st.session_state.get("uploaded_name", ""),
            template_name=template_name,
            review_timestamp=now,
            reviewer=reviewer,
            decisions=decisions,
            raw_headers=raw_hdrs
        )

        st.session_state["locked_schema"] = locked
    
        try:
            import sov_app.feedback.header_feedback as _fb
            n_saved = _fb.save_feedback(locked, mappings)
            if n_saved:
                st.toast(
                    f"💡 {n_saved} feedback rule(s) saved — future mappings will use these",
                    icon="🧠")
        except Exception:
            pass   # feedback is best-effort; never block the main flow

        st.success("Mapping locked. Proceed to Transform.", icon="🔒")

    if "locked_schema" in st.session_state:

        ls = st.session_state["locked_schema"]

        st.info(
            f"Locked by **{ls.reviewer}** · "
            f"`{ls.review_timestamp[:19]}` · "
            f"Template: `{ls.template_name}`",
            icon="🔒"
        )

        audit_df = pd.DataFrame([d.to_dict() for d in ls.decisions])

        st.download_button(
            "↓  Audit Trail (.xlsx)",
            data=to_excel_bytes(audit_df),
            file_name="mapping_audit_trail.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

        return ls

    return None

