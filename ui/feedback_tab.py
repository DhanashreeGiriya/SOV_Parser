"""
Auto-extracted module: ui/feedback_tab.py
"""

from __future__ import annotations

import streamlit as st

from sov_app.feedback.header_feedback import clear_feedback, delete_feedback_rule, get_feedback_summary, save_feedback
from sov_app.header_mapping.schema import TARGET_SCHEMA_AIR

def render_feedback_tab():
    """
    Feedback Rules tab — display, add, delete, and export learned mapping rules.
    Rules are created automatically when a reviewer overrides a column and locks
    the schema.  They are applied in Pass 0 of the next mapping run, before the
    reference dictionary and semantic matching passes.
    """
    st.markdown(
        '<p style="font-size:.85rem;color:#1a1a2e;margin-bottom:.8rem">'
        'Feedback rules are learned automatically when you override a mapping and lock the schema. '
        'They take priority over all other matching methods in future runs — teaching the system '
        "your organisation's specific column naming conventions.</p>",
        unsafe_allow_html=True)

    try:
        import sov_app.feedback.header_feedback as _fb
    except ImportError:
        st.error("`sov_feedback.py` not found — place it in the same directory as this app.",
                 icon="🚫")
        return

    # ── Summary metrics ───────────────────────────────────────────────────────
    rules = _fb.get_feedback_summary()
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Rules",            len(rules))
    col2.metric("Fields Covered",         len({r["output_col"] for r in rules}))
    col3.metric("Source Columns Learned", 
            sum(len(r.get("source_cols", [r["source_col"]])) for r in rules))

    if not rules:
        st.info(
            "No feedback rules yet. Override a column mapping in the **Review** tab "
            "and lock the schema — the system will learn from your decisions automatically.",
            icon="💡")
    else:
        st.markdown("---")

        # ── Filter controls ───────────────────────────────────────────────────
        fc1, fc2 = st.columns([2, 2])
        with fc1:
            field_filter = st.selectbox(
                "Filter by target field",
                ["All fields"] + sorted({r["output_col"] for r in rules}),
                key="fb_field_filter")
        with fc2:
            scope_opts = ["All scopes", "global"] + sorted(
                {r["scope"] for r in rules if r["scope"] != "_global"})
            scope_filter = st.selectbox("Filter by scope", scope_opts, key="fb_scope_filter")

        display_rules = rules
        if field_filter != "All fields":
            display_rules = [r for r in display_rules if r["output_col"] == field_filter]
        if scope_filter not in ("All scopes", "global"):
            display_rules = [r for r in display_rules if r["scope"] == scope_filter]
        elif scope_filter == "global":
            display_rules = [r for r in display_rules if r["scope"] == "_global"]
        
        st.markdown(
            f'<p style="font-size:.78rem;color:var(--muted)">'
            f'Showing {len(display_rules)} of {len(rules)} rules</p>',
            unsafe_allow_html=True)

        # ── Rules table ───────────────────────────────────────────────────────
        HDR_COLS = "180px 210px 68px 68px 1fr 80px 130px"
        rows_html = []
        for r in display_rules:
            conf      = r["confidence"]
            conf_col  = "#10b981" if conf >= 92 else "#f59e0b"
            scope_lbl = "global" if r["scope"] == "_global" else r["scope"]
            scope_css = (
                "background:rgba(21,101,192,.1);color:#1565c0"
                if r["scope"] == "_global"
                else "background:rgba(139,92,246,.1);color:#6d28d9"
            )
            # Add this after scope_css / scope_lbl is defined:
            origin     = r.get("origin", "human")
            origin_lbl = "🤖 AI learned" if origin == "ai_autolearn" else "👤 Human"
            origin_css = (
                "background:rgba(139,92,246,.1);color:#6d28d9"
                if origin == "ai_autolearn"
                else "background:rgba(16,185,129,.1);color:#065f46"
            )
            reason    = r.get("reason") or "—"
            short_rsn = (reason[:55] + "…") if len(reason) > 55 else reason
            last_seen = (r.get("last_seen") or "")[:10]
            rows_html.append(
                f'<div style="display:grid;grid-template-columns:{HDR_COLS};'
                f'border-bottom:1px solid var(--border);align-items:center">'
                f'<div style="padding:.45rem .8rem;font-family:var(--mono);font-size:.78rem;'
                f'color:#1565c0;font-weight:600">{r["output_col"]}</div>'
                f'<div style="padding:.45rem .8rem;font-family:var(--mono);font-size:.76rem;color:#1a1a2e">'
                 + " + ".join(
                f'<span style="background:#f0f4f8;border-radius:3px;padding:.05rem .3rem">{s}</span>'
                for s in r.get("source_cols", [r["source_col"]])
                 )
                 + f'</div>'
                f'<div style="padding:.45rem .6rem;text-align:center">'
                f'<span style="font-family:var(--mono);font-size:.8rem;font-weight:700;'
                f'color:{conf_col}">{conf}%</span></div>'
                f'<div style="padding:.45rem .6rem;text-align:center">'
                f'<span style="font-family:var(--mono);font-size:.76rem;color:#6c757d">'
                f'{r["uses"]}×</span></div>'
                f'<div style="padding:.45rem .8rem;font-size:.73rem;color:#94a3b8;'
                f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap" '
                f'title="{reason}">{short_rsn}</div>'
                f'<div style="padding:.45rem .6rem;font-size:.7rem;color:#9ca3af;'
                f'text-align:center">{last_seen}</div>'
                f'<div style="padding:.45rem .8rem"><span style="font-size:.65rem;'
                f'font-weight:600;padding:.12rem .4rem;border-radius:3px;'
                f'{scope_css}">{scope_lbl}</span></div>'
                f'<div style="padding:.45rem .8rem">'
                f'<span style="font-size:.65rem;font-weight:600;padding:.12rem .4rem;'
                f'border-radius:3px;{scope_css}">{scope_lbl}</span> '
                f'<span style="font-size:.62rem;padding:.1rem .35rem;border-radius:3px;'
                f'margin-left:.3rem;{origin_css}">{origin_lbl}</span>'
                f'</div>'
                f'</div>'
            )

        hdr_cell = lambda lbl, extra="": (
            f'<div style="padding:.5rem .8rem;font-size:.67rem;color:var(--muted);'
            f'font-weight:600;text-transform:uppercase;letter-spacing:.06em{extra}">{lbl}</div>'
        )
        table_html = (
            f'<div style="border:1px solid var(--border);border-radius:6px;'
            f'overflow:hidden;margin-top:.5rem">'
            f'<div style="display:grid;grid-template-columns:{HDR_COLS};'
            f'background:#f8f9fa;border-bottom:2px solid #dee2e6">'
            + hdr_cell("Target Field")
            + hdr_cell("Source Column Learned")
            + hdr_cell("Conf.", ";text-align:center")
            + hdr_cell("Uses",  ";text-align:center")
            + hdr_cell("Reason")
            + hdr_cell("Date",  ";text-align:center")
            + hdr_cell("Scope")
            + f'</div>{"".join(rows_html)}</div>'
        )
        st.markdown(table_html, unsafe_allow_html=True)
        
        # ── Delete individual rules ───────────────────────────────────────────
        st.markdown("---")
        st.markdown("**Remove a rule**")
        del_opts = [
            f'{r["output_col"]} ← {r["source_col"]} ({r["scope"]})'
            for r in display_rules
        ]
        if del_opts:
            del_choice = st.selectbox("Select rule to delete", del_opts, key="fb_del_choice")
            del_rule   = display_rules[del_opts.index(del_choice)]
            if st.button("🗑  Delete Selected Rule", key="fb_del_btn"):
                scope_key = "" if del_rule["scope"] == "_global" else del_rule["scope"]
                if _fb.delete_feedback_rule(del_rule["norm_key"], template_name=scope_key):
                    st.success(
                        f'Rule deleted: `{del_rule["source_col"]}` → `{del_rule["output_col"]}`',
                        icon="✅")
                    st.rerun()
                else:
                    st.warning("Rule not found — it may have already been removed.")

    # ── Manually add a rule ───────────────────────────────────────────────────
    st.markdown("---")
    with st.expander("➕  Manually add a feedback rule", expanded=False):
        st.markdown(
            '<p style="font-size:.8rem;color:#6c757d">Add a rule without going through the full '
            'review cycle — useful for known column naming conventions in your organisation.</p>',
            unsafe_allow_html=True)
        ma1, ma2, ma3 = st.columns(3)
        with ma1:
            manual_src = st.text_input(
                "Source column name (from your SOV)", key="fb_manual_src",
                placeholder="e.g. Personal Property Value $")
        with ma2:
            try:
                import sov_header_mapping as _sov
                schema_fields = [s["output_col"] for s in _sov.TARGET_SCHEMA_AIR]
            except Exception:
                schema_fields = ["(load pipeline first)"]
            manual_target = st.selectbox("Target field", schema_fields, key="fb_manual_target")
        with ma3:
            manual_reason = st.text_input(
                "Reason / note", key="fb_manual_reason",
                placeholder="e.g. Client uses this name for building value")
        if st.button("Save Manual Rule", key="fb_manual_save"):
            if manual_src.strip():
                from types import SimpleNamespace as _NS
                _fb.save_feedback(
                    _NS(template_name="_global",
                        decisions=[_NS(
                            output_col=manual_target,
                            final_source=[manual_src.strip()],
                            decision="override",
                            override_reason=manual_reason.strip(),
                            reviewer="manual")]),
                    [])
                st.success(
                    f"Rule saved: `{manual_src.strip()}` → `{manual_target}` "
                    "(applies in Pass 0 on the next mapping run)", icon="🧠")
                st.rerun()
            else:
                st.warning("Please enter a source column name.")

    # ── Export rules ──────────────────────────────────────────────────────────
    if rules:
        st.markdown("---")
        import json as _json
        st.download_button(
            "↓  Export Rules (.json)",
            data=_json.dumps(_fb.get_feedback_summary(), indent=2, default=str),
            file_name="sov_feedback_rules.json",
            mime="application/json")

    # ── Danger zone ───────────────────────────────────────────────────────────
    st.markdown("---")
    with st.expander("⚠️  Danger zone — clear all rules", expanded=False):
        st.warning("This will delete ALL feedback rules permanently and cannot be undone.")
        if st.button("🔴  Clear ALL Feedback Rules", key="fb_clear_all"):
            n = _fb.clear_feedback()
            st.success(f"Cleared {n} rule(s).", icon="✅")
            st.rerun()

