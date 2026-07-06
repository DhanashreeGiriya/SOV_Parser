"""
Auto-extracted module: ui/row_feedback_tab.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from sov_app.feedback.row_feedback.apply import build_full_preview
from sov_app.feedback.row_feedback.llm_discovery import call_llm_for_rule_discovery
from sov_app.feedback.row_feedback.llm_transform import call_llm_for_transform
from sov_app.feedback.row_feedback.store import clear_rules, delete_rule, get_rules_summary, load_rules, reorder_rules, save_rule
from sov_app.feedback.row_feedback.transform_lambda import _build_preview
from sov_app.header_mapping.ai_config import _get_azure_cfg_from_secrets
from sov_app.row_processing.export import run_value_transformation
from sov_app.row_processing.process_row import process_row

def render_row_edit_panel(p3, system):
    """
    Prompt → LLM → Preview → Accept / Modify / Decline
    =====================================================
    1. User picks a column and types a natural-language instruction.
    2. LLM returns a Python lambda + before/after preview.
    3. User accepts (saves rule), modifies (re-prompts), or declines.
    4. Accepted rules are stored in sov_row_feedback_store.json and
       auto-applied on every future upload.
    """
    import sov_app.feedback.row_feedback as _rf

    cleaned_df = p3["cleaned_df"]
    raw_df     = st.session_state["phase1_result"]["data_frame"]
    locked     = st.session_state["locked_schema"]
    try:
        import sov_header_mapping as _shm
        cfg = _shm._get_azure_cfg_from_secrets()
    except Exception:
        cfg = {}

    mapped_fields = [
        d.output_col for d in locked.decisions
        if d.final_source and d.decision != "unavailable"
        and d.output_col in cleaned_df.columns
    ]
    if not mapped_fields:
        st.info("No mapped fields available.", icon="ℹ️")
        return

    st.markdown("---")
    st.markdown(
        '<div style="background:rgba(21,101,192,.06);border:1px solid rgba(21,101,192,.2);'
        'border-radius:8px;padding:1rem 1.2rem;margin-bottom:1rem">'
        '<div style="font-family:var(--mono);font-size:.9rem;font-weight:600;color:#1565c0;'
        'margin-bottom:.3rem">✨  Column Transform Studio</div>'
        '<div style="font-size:.8rem;color:#6c757d">'
        'Describe what you want to do to a column in plain English. '
        'The AI will generate a transformation, show you a preview, '
        'and save it as a reusable rule.'
        '</div></div>', unsafe_allow_html=True)

    # ── Column + reviewer picker ──────────────────────────────────────────────
    pc1, pc2 = st.columns([3, 1])
    with pc1:
        edit_field = st.selectbox(
            "Column to transform", mapped_fields, key="cts_field_select")
    with pc2:
        reviewer = st.text_input("Your name", "analyst", key="cts_reviewer")

    # ── Show existing rules for this column (chain awareness) ─────────────────
    existing_rules = _rf.load_rules(edit_field).get(edit_field, [])
    existing_confirmed = [r for r in existing_rules if r.get("confirmed", True)]
    if existing_confirmed:
        chain_html = (
            '<div style="background:rgba(234,179,8,.07);border:1px solid rgba(234,179,8,.25);'
            'border-radius:6px;padding:.6rem 1rem;margin:.4rem 0 .8rem">'
            '<div style="font-size:.72rem;font-weight:700;color:#92400e;margin-bottom:.35rem">'
            f'⛓  {len(existing_confirmed)} existing rule(s) will run BEFORE your new rule</div>'
        )
        for i, r in enumerate(existing_confirmed):
            chain_html += (
                f'<div style="font-size:.7rem;color:#4b5563;margin:.15rem 0">'
                f'<span style="background:#fef3c7;padding:.05rem .3rem;border-radius:2px;'
                f'font-weight:600;color:#92400e">#{i+1}</span>  '
                f'<code style="color:#1565c0;font-size:.68rem">{r["lambda_src"][:70]}</code>'
                f'<span style="color:#9ca3af;margin-left:.3rem">{r.get("prompt","")[:50]}</span>'
                f'</div>'
            )
        chain_html += (
            '<div style="font-size:.68rem;color:#6b7280;margin-top:.35rem;font-style:italic">'
            'Each rule feeds its output to the next. Your new rule sees the result of the chain above.'
            '</div></div>'
        )
        st.markdown(chain_html, unsafe_allow_html=True)

    # Resolve source column for this field to pull RAW samples
    _dec_sel = next((d for d in locked.decisions if d.output_col == edit_field), None)
    _src_col_sel = (_dec_sel.final_source or [""])[0] if _dec_sel else ""

    # Gather sample values from the RAW source column (not cleaned), and keep
    # the POSITIONAL row index of the first occurrence of each unique value
    # so the preview can re-run the code rule on those exact rows (positions
    # match how process_row indexes rows in run_value_transformation).
    sample_row_idxs: list[int] = []
    sample_row_idxs: list[int] = []
    if _src_col_sel and _src_col_sel in raw_df.columns:
        _raw_full = raw_df[_src_col_sel].apply(
            lambda x: "" if (x is None or (isinstance(x, float) and pd.isna(x))) else str(x).strip()
        )
        _seen: dict = {}
        for _pos, _v in enumerate(_raw_full):
            _vs = _v  # already a clean string from apply()
            if _vs and _vs not in _seen:
                _seen[_vs] = _pos
            if len(_seen) >= 12:
                break
        sample_vals     = list(_seen.keys())
        sample_row_idxs = list(_seen.values())
    else:
        _raw_series = cleaned_df[edit_field].dropna()
        sample_vals = _raw_series.astype(str).replace("nan", "").replace("None", "")
        sample_vals = [v for v in sample_vals if v.strip()]
        sample_vals = list(dict.fromkeys(sample_vals))[:12]

    # Show a compact sample card
    if sample_vals:
        sample_chips = "  ".join(
            f'<code style="font-size:.7rem;background:#f3f4f6;'
            f'padding:.1rem .35rem;border-radius:3px">{v[:40]}</code>'
            for v in sample_vals[:6]
        )
        st.markdown(
            f'<div style="margin:.4rem 0 .8rem;font-size:.74rem;color:#6c757d">'
            f'<b>Sample values (original):</b> {sample_chips}</div>',
            unsafe_allow_html=True)
    # ── Prompt input ──────────────────────────────────────────────────────────
    prompt = st.text_area(
        "Describe the transformation",
        placeholder=(
            "e.g.  'Remove everything after the word units'\n"
            "       'Convert to uppercase'\n"
            "       'Strip $ signs and commas, keep numbers only'\n"
            "       'Replace joisted masonry with 119'"
        ),
        height=100,
        key=f"cts_prompt_{edit_field}",
    ).strip()

    reason = st.text_input(
        "Why this change? (optional)",
        placeholder="e.g. pipeline misses suffix stripping for this field",
        key=f"cts_reason_{edit_field}",
    ).strip()

    # ── Generate button ───────────────────────────────────────────────────────
    gen_key    = f"cts_result_{edit_field}"
    accept_key = f"cts_accepted_{edit_field}"
    decline_key = f"cts_declined_{edit_field}"

    c_gen, c_clear = st.columns([2, 1])
    with c_gen:
        if st.button("⚡  Generate transformation", key=f"cts_gen_{edit_field}",
                     use_container_width=True, disabled=not prompt):
            with st.spinner("Asking AI to generate a transformation…"):
                result = _rf.call_llm_for_transform(prompt, edit_field, sample_vals, cfg)
                result["_prompt"]   = prompt
                result["_reason"]   = reason
                result["_src_col"]  = _src_col_sel
                result["_reviewer"] = reviewer
                st.session_state[gen_key] = result
                st.session_state.pop(accept_key, None)
                st.session_state.pop(decline_key, None)
    with c_clear:
        if st.button("✕  Clear", key=f"cts_clear_{edit_field}", use_container_width=True):
            st.session_state.pop(gen_key, None)
            st.session_state.pop(accept_key, None)
            st.session_state.pop(decline_key, None)

    # ── Preview panel ─────────────────────────────────────────────────────────
    result = st.session_state.get(gen_key)

    if result:
        lambda_src  = result.get("lambda_src", "lambda v: v")
        explanation = result.get("explanation", "")
        confidence  = result.get("confidence", 0)
        preview     = result.get("preview", [])
        error       = result.get("error")

        # LLM error banner
        if error:
            st.warning(f"⚠️  {error}", icon="⚠️")

        # Lambda display
        conf_color = "#065f46" if confidence >= 70 else "#92400e" if confidence >= 40 else "#991b1b"
        st.markdown(
            f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;'
            f'padding:.7rem 1rem;margin:.6rem 0">'
            f'<div style="font-size:.68rem;font-weight:700;color:#6b7280;'
            f'text-transform:uppercase;letter-spacing:.06em;margin-bottom:.3rem">'
            f'Generated transformation</div>'
            f'<code style="font-size:.8rem;color:#1565c0;word-break:break-all">'
            f'{lambda_src}</code>'
            f'<div style="font-size:.76rem;color:#4b5563;margin-top:.4rem">'
            f'{explanation}</div>'
            f'<div style="font-size:.7rem;color:{conf_color};margin-top:.25rem;font-weight:600">'
            f'AI confidence: {confidence}%</div>'
            f'</div>', unsafe_allow_html=True)

        # Editable lambda (for Modify flow)
        edited_lambda = st.text_input(
            "✏️  Edit the lambda (advanced)",
            value=lambda_src,
            key=f"cts_lambda_edit_{edit_field}",
            help="Edit the Python lambda directly if the AI suggestion needs tweaking.",
        ).strip()

        if edited_lambda != lambda_src:
            # Re-run preview with edited lambda
            preview = _rf._build_preview(edited_lambda, sample_vals)
            lambda_src = edited_lambda

        # ── Full pipeline preview: row rule(s) + code rule, combined ─────────────
        # Mirrors what clicking "Run Transformation" will actually produce —
        # runs the column's code rule (street parsing, construction lookup,
        # etc.) together with any existing row rules and this candidate rule,
        # in the same order the real pipeline uses.
        if sample_row_idxs:
            full_preview = _rf.build_full_preview(
                raw_df=raw_df,
                locked_schema=locked,
                output_col=edit_field,
                candidate_lambda_src=lambda_src,
                sample_row_indices=sample_row_idxs,
                existing_rules=existing_confirmed,
                target_system=system,
                primary_source_col=_src_col_sel,
            )
            changed_count = sum(1 for p in full_preview if p["changed"])
            total_count   = len(full_preview)
            preview_color = "#065f46" if changed_count > 0 else "#92400e"
            chain_prefix  = (
                f"⛓  {len(existing_confirmed)} prior rule(s) + " if existing_confirmed else ""
            )

            cand_errors = [p["error"] for p in full_preview if p.get("error")]
            if cand_errors:
                st.warning(f"⚠️  Lambda error on some sample rows: {cand_errors[0]}", icon="⚠️")

            st.markdown(
                f'<div style="font-size:.76rem;font-weight:600;color:{preview_color};'
                f'margin:.5rem 0 .25rem">'
                f'{chain_prefix}code rule combined — '
                f'{changed_count} of {total_count} sample rows would change</div>',
                unsafe_allow_html=True)

            import pandas as _pd
            _prev_rows = []
            for p in full_preview:
                changed_marker = "✏️" if p["changed"] else "="
                _prev_rows.append({
                    "Raw value":               p["raw"],
                    "Current pipeline output": p["current_output"],
                    "After this rule":         p["new_output"],
                    "Status":                  changed_marker,
                })
            prev_df = _pd.DataFrame(_prev_rows)

            def _style_status(v):
                if v == "✏️": return "color:#1565c0;font-weight:bold"
                return "color:#9ca3af"

            st.dataframe(
                prev_df.style.map(_style_status, subset=["Status"]),
                use_container_width=True,
                height=min(len(_prev_rows) * 35 + 60, 360),
                hide_index=True,
            )
            st.caption(
                "“Current pipeline output” = today's value (existing row rules + "
                "code rule). “After this rule” = what it becomes once this rule "
                "is accepted and you click Run Transformation."
            )
        elif preview:
            # Fallback only: no resolvable raw source column to map preview
            # rows back to, so the code rule can't be re-run here. Shows the
            # lambda's effect in isolation instead.
            st.caption(
                "⚠️ Couldn't resolve a raw source column for this field — "
                "showing the lambda's effect alone, without the code rule."
            )
            changed_count = sum(1 for p in preview if p.get("changed"))
            total_count   = len(preview)
            preview_color = "#065f46" if changed_count > 0 else "#92400e"

            st.markdown(
                f'<div style="font-size:.76rem;font-weight:600;color:{preview_color};'
                f'margin:.5rem 0 .25rem">'
                f'Preview: {changed_count} of {total_count} sample rows would change</div>',
                unsafe_allow_html=True)

            import pandas as _pd
            _prev_rows = []
            for p in preview:
                changed_marker = "✏️" if p["changed"] else "="
                err_str = f" ⚠ {p['error']}" if p.get("error") else ""
                _prev_rows.append({
                    "Before (original)": p["before"],
                    "After":             p["after"] + err_str,
                    "Status":            changed_marker,
                })
            prev_df = _pd.DataFrame(_prev_rows)

            def _style_status(v):
                if v == "✏️": return "color:#1565c0;font-weight:bold"
                if "⚠" in str(v): return "color:#ef4444"
                return "color:#9ca3af"

            st.dataframe(
                prev_df.style.map(_style_status, subset=["Status"]),
                use_container_width=True,
                height=min(len(_prev_rows) * 35 + 60, 360),
                hide_index=True,
            )

        # ── Accept / Decline ──────────────────────────────────────────────────
        if accept_key not in st.session_state and decline_key not in st.session_state:
            a1, a2 = st.columns(2)
            with a1:
                if st.button("✅  Accept & save rule",
                             key=f"cts_accept_{edit_field}", use_container_width=True):
                    rule_id = _rf.save_rule({
                        "output_col":  edit_field,
                        "source_col":  result.get("_src_col", ""),
                        "prompt":      result.get("_prompt", ""),
                        "lambda_src":  lambda_src,
                        "explanation": explanation,
                        "reason":      result.get("_reason", ""),
                        "reviewer":    result.get("_reviewer", reviewer),
                    })
                    st.session_state[accept_key] = rule_id
            with a2:
                if st.button("✗  Decline",
                             key=f"cts_decline_{edit_field}", use_container_width=True):
                    st.session_state[decline_key] = True

        if accept_key in st.session_state:
            st.success(
                f"✅ Rule saved (id: {st.session_state[accept_key]}) — "
                "it will apply automatically on the next upload. "
                "View all rules in the **Row Rules** tab.",
                icon="✅")

        if decline_key in st.session_state:
            st.info("Declined — nothing was saved.", icon="ℹ️")


def render_row_feedback_tab():
    """
    Tab — Saved Column Transformation Rules.
    Sections:
      A) Rule Chain Manager — view, reorder, delete per-column rules
      B) AI Rule Discovery — upload correct source→target examples, LLM infers lambdas
    """
    try:
        import sov_app.feedback.row_feedback as _rf
    except ImportError:
        st.error("`sov_row_feedback.py` not found.", icon="🚫")
        return

    rules = _rf.get_rules_summary()

    # ── Metrics ───────────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Rules",    len(rules))
    c2.metric("Fields Covered", len({r["output_col"] for r in rules}))
    c3.metric("Total Uses",     sum(r["uses"] for r in rules))

    # ── Section A: Rule Chain Manager ─────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        '<div style="font-family:var(--mono);font-size:.9rem;font-weight:700;'
        'color:#1565c0;margin-bottom:.4rem">⛓  Rule Chain Manager</div>'
        '<div style="font-size:.78rem;color:#6b7280;margin-bottom:.8rem">'
        'Rules for the same column run in order — the output of each rule feeds the next. '
        'Reorder rules by moving them up/down. All confirmed rules always apply together.</div>',
        unsafe_allow_html=True)

    if not rules:
        st.info(
            "No rules yet. Open the **Transform** tab, pick a column, "
            "and describe what you want to change.", icon="💡")
    else:
        # Filter controls
        rf1, rf2 = st.columns([2, 2])
        with rf1:
            rf_field = st.selectbox(
                "Filter by field",
                ["All fields"] + sorted({r["output_col"] for r in rules}),
                key="rf_field_filter")
        with rf2:
            rf_search = st.text_input(
                "Search prompts", placeholder="keyword…", key="rf_search")

        display = rules
        if rf_field != "All fields":
            display = [r for r in display if r["output_col"] == rf_field]
        if rf_search:
            kw = rf_search.lower()
            display = [r for r in display
                       if kw in r.get("prompt", "").lower()
                       or kw in r.get("explanation", "").lower()]

        st.markdown(
            f'<p style="font-size:.78rem;color:var(--muted)">'
            f'Showing {len(display)} of {len(rules)} rules</p>',
            unsafe_allow_html=True)

        # Group by output_col for chain display
        from collections import defaultdict as _dd
        by_col: dict = _dd(list)
        for r in display:
            by_col[r["output_col"]].append(r)

        for col_name, col_rules in by_col.items():
            chain_count = len(col_rules)
            with st.expander(
                f"**{col_name}** — {chain_count} rule{'s' if chain_count > 1 else ''} in chain",
                expanded=(chain_count > 1)
            ):
                if chain_count > 1:
                    st.markdown(
                        '<div style="font-size:.72rem;color:#92400e;background:rgba(234,179,8,.08);'
                        'border:1px solid rgba(234,179,8,.2);border-radius:4px;padding:.4rem .7rem;'
                        'margin-bottom:.6rem">⛓ These rules chain in order. Use ↑↓ to reorder.</div>',
                        unsafe_allow_html=True)

                for idx, r in enumerate(col_rules):
                    step_color = "#1565c0" if idx == 0 else "#0f766e" if idx == 1 else "#7c3aed"
                    col_a, col_b, col_c, col_d = st.columns([.3, 4, .6, .6])
                    with col_a:
                        st.markdown(
                            f'<div style="background:{step_color};color:white;border-radius:50%;'
                            f'width:22px;height:22px;display:flex;align-items:center;'
                            f'justify-content:center;font-size:.7rem;font-weight:700;margin-top:6px">'
                            f'{idx+1}</div>', unsafe_allow_html=True)
                    with col_b:
                        st.markdown(
                            f'<div style="font-size:.76rem;color:#111827;font-weight:600">'
                            f'{r["prompt"][:80]}{"…" if len(r["prompt"])>80 else ""}</div>'
                            f'<div style="font-size:.7rem;margin:.1rem 0">'
                            f'<code style="color:{step_color}">{r["lambda_src"][:80]}</code></div>'
                            f'<div style="font-size:.68rem;color:#9ca3af">'
                            f'{r["explanation"]} · {r["uses"]}× used · {r.get("reviewer","—")}</div>',
                            unsafe_allow_html=True)
                    with col_c:
                        # Move up
                        if idx > 0:
                            if st.button("↑", key=f"rf_up_{r['rule_id']}",
                                         help="Move earlier in chain"):
                                all_col_rules = _rf.load_rules(col_name).get(col_name, [])
                                ids = [x["rule_id"] for x in all_col_rules]
                                pos = ids.index(r["rule_id"])
                                if pos > 0:
                                    ids[pos], ids[pos-1] = ids[pos-1], ids[pos]
                                    _rf.reorder_rules(col_name, ids)
                                    st.rerun()
                    with col_d:
                        if st.button("🗑", key=f"rf_del_{r['rule_id']}",
                                     help="Delete this rule"):
                            if _rf.delete_rule(r["rule_id"]):
                                st.success(f"Rule {r['rule_id']} deleted.", icon="✅")
                                st.rerun()

                    if idx < chain_count - 1:
                        st.markdown(
                            '<div style="font-size:.65rem;color:#9ca3af;'
                            'padding:.1rem 0 .1rem 1.8rem">↓ feeds into</div>',
                            unsafe_allow_html=True)

    # ── Export / Clear ────────────────────────────────────────────────────────
    st.markdown("---")
    dl1, dl2 = st.columns(2)
    with dl1:
        import json as _json
        st.download_button(
            "↓  Export rules (.json)",
            data=_json.dumps(_rf.get_rules_summary(), indent=2, default=str),
            file_name="sov_row_feedback_rules.json",
            mime="application/json",
            use_container_width=True)
    with dl2:
        if st.button("🗑  Clear ALL rules", key="rf_clear_all",
                     use_container_width=True):
            st.warning("This will delete ALL rules permanently.")
            if st.button("Confirm — delete all", key="rf_clear_confirm"):
                n = _rf.clear_rules()
                st.success(f"Deleted {n} rules.", icon="✅")
                st.rerun()

    # ── Section B: AI Rule Discovery ─────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        '<div style="background:rgba(124,58,237,.06);border:1px solid rgba(124,58,237,.2);'
        'border-radius:8px;padding:1rem 1.2rem;margin-bottom:1rem">'
        '<div style="font-family:var(--mono);font-size:.9rem;font-weight:600;color:#7c3aed;'
        'margin-bottom:.3rem">🔬  AI Rule Discovery</div>'
        '<div style="font-size:.8rem;color:#6c757d">'
        'Have a correct reference file? Upload a CSV/Excel with <b>source</b> and <b>target</b> '
        'columns for a field, and the AI will analyse the patterns and propose reusable lambda '
        'rules you can accept with one click.'
        '</div></div>', unsafe_allow_html=True)

    # Column name + file upload
    disc1, disc2 = st.columns([2, 2])
    with disc1:
        disc_col = st.text_input(
            "Target column name (field this applies to)",
            placeholder="e.g. ConstructionCode",
            key="disc_col_name")
    with disc2:
        disc_file = st.file_uploader(
            "Upload reference file (CSV or Excel)",
            type=["csv", "xlsx", "xls"],
            key="disc_file_upload",
            help="Must have 'source' and 'target' columns (case-insensitive)")

    if disc_file and disc_col:
        import pandas as _pd3
        try:
            if disc_file.name.endswith(".csv"):
                ref_df = _pd3.read_csv(disc_file)
            else:
                ref_df = _pd3.read_excel(disc_file)
        except Exception as e:
            st.error(f"Could not read file: {e}")
            ref_df = None

        if ref_df is not None:
            # Normalise column names
            ref_df.columns = [c.lower().strip() for c in ref_df.columns]
            src_col_options = [c for c in ref_df.columns if "source" in c or "before" in c or "original" in c or "input" in c]
            tgt_col_options = [c for c in ref_df.columns if "target" in c or "after" in c or "output" in c or "expected" in c or "result" in c]

            dc1, dc2 = st.columns(2)
            with dc1:
                disc_src_col = st.selectbox(
                    "Source column in file",
                    ref_df.columns.tolist(),
                    index=ref_df.columns.tolist().index(src_col_options[0]) if src_col_options else 0,
                    key="disc_src_col")
            with dc2:
                disc_tgt_col = st.selectbox(
                    "Target column in file",
                    ref_df.columns.tolist(),
                    index=ref_df.columns.tolist().index(tgt_col_options[0]) if tgt_col_options else min(1, len(ref_df.columns)-1),
                    key="disc_tgt_col")

            # Show preview of examples
            examples_raw = []
            for _, row in ref_df.iterrows():
                src = str(row[disc_src_col]) if disc_src_col in row.index else ""
                tgt = str(row[disc_tgt_col]) if disc_tgt_col in row.index else ""
                if src not in ("", "nan", "None") and tgt not in ("", "nan", "None"):
                    examples_raw.append({"source": src, "target": tgt})

            st.markdown(
                f'<div style="font-size:.76rem;color:#6b7280;margin:.4rem 0">'
                f'📊 {len(examples_raw)} valid example pairs found '
                f'(up to 50 sent to AI, {min(8, len(examples_raw))} shown below)</div>',
                unsafe_allow_html=True)

            if examples_raw:
                prev_ex = examples_raw[:8]
                ex_df = _pd3.DataFrame(prev_ex)
                st.dataframe(ex_df, use_container_width=True,
                             height=min(len(prev_ex) * 35 + 60, 280), hide_index=True)

            disc_gen_key = f"disc_result_{disc_col}"
            if st.button("🔬  Discover Rules with AI", key="disc_generate_btn",
                         use_container_width=True, disabled=len(examples_raw) < 2):
                try:
                    import sov_header_mapping as _shm
                    cfg = _shm._get_azure_cfg_from_secrets()
                except Exception:
                    cfg = {}
                with st.spinner("AI is analysing transformation patterns…"):
                    disc_result = _rf.call_llm_for_rule_discovery(examples_raw, disc_col, cfg)
                    st.session_state[disc_gen_key] = disc_result

            disc_result = st.session_state.get(disc_gen_key)
            if disc_result:
                if disc_result.get("error"):
                    st.warning(f"⚠️ {disc_result['error']}", icon="⚠️")

                if disc_result.get("summary"):
                    st.markdown(
                        f'<div style="background:#f8fafc;border:1px solid #e2e8f0;'
                        f'border-radius:6px;padding:.7rem 1rem;margin:.6rem 0;'
                        f'font-size:.78rem;color:#374151">'
                        f'<b>🔍 AI Analysis:</b> {disc_result["summary"]}</div>',
                        unsafe_allow_html=True)

                discovered = disc_result.get("rules", [])
                if not discovered:
                    st.info("No rules discovered. Try with more diverse examples.", icon="ℹ️")
                else:
                    st.markdown(
                        f'<div style="font-size:.8rem;font-weight:600;color:#7c3aed;margin:.5rem 0">'
                        f'✨ {len(discovered)} rule(s) discovered — review and accept:</div>',
                        unsafe_allow_html=True)

                    reviewer = st.text_input("Your name", "analyst", key="disc_reviewer")

                    for di, dr in enumerate(discovered):
                        lambda_src  = dr.get("lambda_src", "lambda v: v")
                        explanation = dr.get("explanation", "")
                        confidence  = dr.get("confidence", 0)
                        accuracy    = dr.get("accuracy", 0)
                        prompt_text = dr.get("prompt", "")
                        preview_d   = dr.get("preview", [])
                        covers      = dr.get("covers_examples", [])

                        acc_color = "#065f46" if accuracy >= 80 else "#92400e" if accuracy >= 50 else "#991b1b"
                        conf_color = "#065f46" if confidence >= 70 else "#92400e" if confidence >= 40 else "#991b1b"

                        with st.expander(
                            f"Rule {di+1}: {prompt_text[:70]}{'…' if len(prompt_text)>70 else ''}  "
                            f"[{accuracy}% accuracy · {confidence}% confidence]",
                            expanded=(di == 0)
                        ):
                            # Lambda display
                            st.markdown(
                                f'<div style="background:#f8fafc;border:1px solid #e2e8f0;'
                                f'border-radius:6px;padding:.7rem 1rem;margin:.4rem 0">'
                                f'<div style="font-size:.68rem;font-weight:700;color:#6b7280;'
                                f'text-transform:uppercase;letter-spacing:.06em;margin-bottom:.3rem">'
                                f'Discovered rule</div>'
                                f'<code style="font-size:.8rem;color:#7c3aed;word-break:break-all">'
                                f'{lambda_src}</code>'
                                f'<div style="font-size:.76rem;color:#4b5563;margin-top:.4rem">'
                                f'{explanation}</div>'
                                f'<div style="font-size:.7rem;margin-top:.3rem">'
                                f'<span style="color:{acc_color};font-weight:600">'
                                f'✓ {accuracy}% of examples matched exactly</span>'
                                f'  <span style="color:{conf_color};margin-left.6rem">'
                                f'AI confidence: {confidence}%</span></div>'
                                f'</div>', unsafe_allow_html=True)

                            # Editable lambda
                            edited_lambda_d = st.text_input(
                                "✏️ Edit lambda (optional)",
                                value=lambda_src,
                                key=f"disc_lambda_edit_{disc_col}_{di}",
                            ).strip()
                            if edited_lambda_d != lambda_src:
                                preview_d = _rf._build_preview(edited_lambda_d, [e["source"] for e in examples_raw[:12]])
                                lambda_src = edited_lambda_d

                            # Preview
                            if preview_d:
                                changed_c = sum(1 for p in preview_d if p.get("changed"))
                                import pandas as _pd4
                                prev_rows_d = []
                                for p in preview_d:
                                    prev_rows_d.append({
                                        "Original": p["before"],
                                        "After rule": p["after"],
                                        "✓": "✏️" if p["changed"] else "=",
                                    })
                                st.dataframe(
                                    _pd4.DataFrame(prev_rows_d),
                                    use_container_width=True,
                                    height=min(len(prev_rows_d) * 35 + 60, 280),
                                    hide_index=True)

                            # Reason input
                            disc_reason = st.text_input(
                                "Reason / note (optional)",
                                placeholder="e.g. inferred from reference file Q2-2025",
                                key=f"disc_reason_{disc_col}_{di}").strip()

                            # Accept / Skip buttons
                            acc_key_d = f"disc_acc_{disc_col}_{di}"
                            sk_key_d  = f"disc_skip_{disc_col}_{di}"

                            if acc_key_d not in st.session_state and sk_key_d not in st.session_state:
                                ba1, ba2 = st.columns(2)
                                with ba1:
                                    if st.button(f"✅ Accept rule {di+1}",
                                                 key=f"disc_accept_{disc_col}_{di}",
                                                 use_container_width=True):
                                        rule_id_d = _rf.save_rule({
                                            "output_col":  disc_col,
                                            "source_col":  "",
                                            "prompt":      prompt_text,
                                            "lambda_src":  lambda_src,
                                            "explanation": explanation,
                                            "reason":      disc_reason or f"AI-discovered from {len(examples_raw)} examples",
                                            "reviewer":    reviewer,
                                        })
                                        st.session_state[acc_key_d] = rule_id_d
                                with ba2:
                                    if st.button(f"✗ Skip rule {di+1}",
                                                 key=f"disc_skip_btn_{disc_col}_{di}",
                                                 use_container_width=True):
                                        st.session_state[sk_key_d] = True

                            if acc_key_d in st.session_state:
                                st.success(
                                    f"✅ Rule saved (id: {st.session_state[acc_key_d]}) — "
                                    "will apply automatically on next upload.", icon="✅")
                            if sk_key_d in st.session_state:
                                st.info("Skipped.", icon="ℹ️")

