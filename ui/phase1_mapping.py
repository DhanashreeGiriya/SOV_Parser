"""
Auto-extracted module: ui/phase1_mapping.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
import openpyxl
import os
import traceback
import tempfile
import io

from sov_app.header_mapping.ai_refine import refine_mappings_with_ai
from sov_app.header_mapping.pipeline import run_header_mapping
from sov_app.ui.common import _human_basis, _is_auto_populated, _match_type_display, conf_bar, method_badge, safe_join, to_excel_bytes

def build_mapped_excel(result) -> bytes:
    df_raw   = result["data_frame"]
    mappings = result["mappings"]
    out_rows = []
    for _, row in df_raw.iterrows():
        out_row = {}
        for m in mappings:
            if _is_auto_populated(m) or not m.source_cols:
                out_row[m.output_col] = ""
            else:
                val = ""
                for src in m.source_cols:
                    if src in row.index and str(row[src]).strip() not in ("", "nan", "None"):
                        val = row[src]; break
                out_row[m.output_col] = str(val) if val not in (None, "") else ""
        out_rows.append(out_row)
    return to_excel_bytes(pd.DataFrame(out_rows))


def _categorise_mappings(mappings):
    """
    Categorise all 34 schema columns into buckets for display.
    Auto-populated columns are treated as null/not from source.
    Returns dict of lists.
    """
    ref_match    = []  # reference/exact/template match
    sem_match    = []  # semantic/name-similarity match
    ai_validated = []  # AI confirmed
    ai_refined   = []  # AI corrected/inferred
    human        = []  # manual override
    missing_req  = []  # required, no source found
    null_cols    = []  # optional, no source found (incl. auto-populated)
    multi_src    = []  # multiple sources matched

    for m in mappings:
        # Multi-source check
        is_multi = (m.flag == "multi_source") or (len(m.source_cols) > 1)

        if _is_auto_populated(m):
            null_cols.append(m)
            continue

        if m.flag in ("missing_required", "missing_source", "missing"):
            missing_req.append(m)
            continue

        if not m.source_cols:
            if hasattr(m, 'required') and m.required:
                missing_req.append(m)
            else:
                null_cols.append(m)
            continue

        mt = m.match_type.lower()
        if mt in ("human_override",):
           human.append(m)
        elif mt in ("feedback_match", "feedback", "pass0", "feedback_exact"):
           ref_match.append(m)   # treat feedback like reference — highest priority
        elif mt in ("ai_validated", "ai_refined", "ai_inferred", "llm_refined", "llm_inferred"):
           if "refined" in mt or "inferred" in mt:
            ai_refined.append(m)
           else:
            ai_validated.append(m)
        elif mt in ("reference_exact", "alias_exact", "template_auto"):
            ref_match.append(m)
        else:
            sem_match.append(m)

    return {
        "reference": ref_match,
        "semantic": sem_match,
        "ai_validated": ai_validated,
        "ai_refined": ai_refined,
        "human": human,
        "missing_required": missing_req,
        "null": null_cols,
    }


def render_phase1(sov, system):
    st.markdown("Upload your SOV file.")

    uploaded = st.file_uploader("SOV Excel file", type=["xlsx", "xls"], label_visibility="collapsed")

    if not uploaded:
        st.markdown('<div style="background:var(--card);border:1px dashed var(--border);'
            'border-radius:6px;padding:2.5rem;text-align:center;color:#1a1a2e;'
            'font-size:.88rem">Drop your SOV Excel file here to begin</div>',
            unsafe_allow_html=True)
        return None

    if ("available_sheets" not in st.session_state or
            st.session_state.get("last_uploaded") != uploaded.name):
        try:
            import openpyxl as _oxl
            wb_check = _oxl.load_workbook(io.BytesIO(uploaded.getvalue()), read_only=True)
            visible_sheets = [ws.title for ws in wb_check.worksheets if ws.sheet_state == "visible"]
            wb_check.close()
            st.session_state["available_sheets"] = visible_sheets
            st.session_state["last_uploaded"] = uploaded.name
            st.rerun()
        except Exception:
            st.session_state["available_sheets"] = []

    sheet_name = None
    if "available_sheets" in st.session_state and len(st.session_state["available_sheets"]) > 1:
        ss_col, _ = st.columns([2, 3])
        with ss_col:
            sheet_name = st.selectbox(
                "Sheet to parse",
                options=st.session_state["available_sheets"],
                key="selected_sheet",
            )

    if st.button("▶  Detect, Map & Verify All Columns", use_container_width=True):
        ph = st.empty(); pb = st.progress(0)
        steps = ["loading", "reference", "semantic", "validation", "finalising"]
        step_pct = [10, 30, 55, 80, 100]; step_idx = [0]

        def _cb(msg):
            # Translate internal messages to user-facing language
            display_msg = msg
            replacements = [
                ("Pass A", "Step 1: Reference dictionary matching"),
                ("Pass B", "Step 2: Semantic name matching"),
                ("Pass C", "Step 3: AI validation of borderline columns"),
                ("alias", "reference"),
                ("fuzzy", "semantic"),
                ("LLM", "AI"),
                ("llm", "AI"),
            ]
            for old, new in replacements:
                display_msg = display_msg.replace(old, new)
            ph.markdown(f'<p style="color:var(--muted);font-size:.82rem;font-family:var(--mono)">⟳  {display_msg}</p>',
                        unsafe_allow_html=True)
            idx = step_idx[0]
            for i, s in enumerate(steps):
                if s in msg.lower(): idx = i; break
            pb.progress(step_pct[min(idx, len(step_pct)-1)]); step_idx[0] = idx

        try:
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                tmp.write(uploaded.getvalue()); tmp_path = tmp.name
            resolved = sheet_name or (
                st.session_state["available_sheets"][0]
                if st.session_state.get("available_sheets") else None)
            with tempfile.TemporaryDirectory() as tmpdir:
                result = sov.run_header_mapping(sov_file=tmp_path, sheet_name=resolved,
                                                output_dir=tmpdir, report_name="sov_mapping",
                                                target_system=system, progress_callback=_cb)
                with open(result["report_excel"], "rb") as f: result["_report_excel_bytes"] = f.read()
                with open(result["report_json"],  "r") as f: result["_report_json_str"]    = f.read()
            os.unlink(tmp_path); pb.progress(100)

            # ── Extra AI pass for multi-source columns ─────────────────────
            # Multi-source columns may have been auto-accepted at high
            # confidence. Force them through the AI so it can inspect actual
            # row values and select the single best source.
            multi_src_m = [m for m in result["mappings"] if len(m.source_cols) > 1]
            if multi_src_m:
                ph.markdown(
                    '<p style="color:var(--muted);font-size:.82rem;font-family:var(--mono)">'
                    '⟳  AI verifying multi-source columns to select best match…</p>',
                    unsafe_allow_html=True)
                # Save and zero confidences so review_candidates picks them up
                saved_conf = {m.output_col: m.confidence for m in multi_src_m}
                for m in multi_src_m:
                    m.confidence = 0
                try:
                    result["mappings"], _ = sov.refine_mappings_with_ai(
                        result["raw_headers"], result["data_frame"],
                        result["mappings"], target_system=system)
                except Exception:
                    # Restore original confidences on failure
                    for m in multi_src_m:
                        m.confidence = saved_conf[m.output_col]

            ph.empty()
            st.session_state["phase1_result"] = result
            st.session_state["uploaded_name"] = uploaded.name
        except Exception as e:
            st.error(f"Mapping failed: {e}")
            with st.expander("Traceback"): st.code(traceback.format_exc())
            return None

    if "phase1_result" not in st.session_state:
        return None
    result = st.session_state["phase1_result"]
    _render_p1_results(result)
    return result


def _render_p1_results(result):
    mappings = result["mappings"]
    flags    = result["flags"]
    df       = result["data_frame"]
    cats     = _categorise_mappings(mappings)

    total_schema   = len(mappings)
    total_sourced  = len(cats["reference"]) + len(cats["semantic"]) + len(cats["ai_validated"]) + len(cats["ai_refined"]) + len(cats["human"])
    total_missing  = len(cats["missing_required"])
    total_null     = len(cats["null"])
    total_ai       = len(cats["ai_validated"]) + len(cats["ai_refined"])
    multi_ct       = sum(1 for m in mappings if m.flag == "multi_source" or len(m.source_cols) > 1)

    st.markdown("---")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Schema Fields",      total_schema,  help="Total target schema columns (34)")
    c2.metric("Source Matched",     total_sourced, help="Fields mapped to a column in your file")
    c3.metric("AI Validated",       len(cats["ai_validated"]), help="Semantic match confirmed by AI using sample data")
    c4.metric("AI Refined",         len(cats["ai_refined"]),   help="AI corrected or inferred mapping from data values")
    c5.metric("Missing Required",   total_missing, help="Required fields with no matching source column")
    c6.metric("Unused Source Cols", len(flags["unmapped_raw_cols"]))
    
    fb_matched = sum(1 for m in mappings if getattr(m, "feedback_matched", False))
    if fb_matched:
        st.markdown(
            f'<div style="background:rgba(139,92,246,.08);border:1px solid rgba(139,92,246,.3);'
            f'border-radius:6px;padding:.5rem 1rem;display:inline-flex;align-items:center;'
            f'gap:.5rem;margin-top:.3rem">'
            f'<span style="font-size:.9rem">🧠</span>'
            f'<span style="font-family:var(--mono);font-size:.82rem;color:#6d28d9;font-weight:600">'
            f'{fb_matched} column(s) mapped using learned feedback rules</span>'
            f'</div>',
            unsafe_allow_html=True)

    # Schema coverage summary grid (all 34 columns) — collapsible
    st.markdown("---")
    with st.expander("📋  Schema Field Coverage — all target fields", expanded=True):

        def _cell_class(m):
            if m.flag in ("missing_required", "missing_source", "missing"):
                return "sc-miss"
            if not m.source_cols or _is_auto_populated(m):
                return "sc-null"
            mt = m.match_type.lower()
            if mt in ("human_override",):
                return "sc-human"
            if mt in ("ai_validated", "ai_refined", "ai_inferred", "llm_refined", "llm_inferred"):
                return "sc-ai"
            if mt in ("reference_exact", "alias_exact", "template_auto"):
                return "sc-ref"
            return "sc-sem"

        cells_html = ""
        for m in mappings:
            cls  = _cell_class(m)
            src = safe_join(str(x) for x in m.source_cols) if m.source_cols and not _is_auto_populated(m) else "—"
            conf = f"  {m.confidence}%" if m.confidence and not _is_auto_populated(m) else ""
            label, _, _ = _match_type_display(m.match_type)
            if m.flag in ("missing_required", "missing_source", "missing"):
                label = "Missing!"
            elif not m.source_cols or _is_auto_populated(m):
                label = "Not mapped"
            cells_html += (
                f'<div class="schema-cell {cls}">'
                f'<div style="font-weight:600;font-size:.76rem">{m.output_col}</div>'
                f'<div style="font-size:.67rem;color:#6c757d;margin-top:.15rem">{label}{conf}</div>'
                f'<div style="font-size:.65rem;color:#94a3b8;margin-top:.1rem;word-break:break-all">{src}</div>'
                f'</div>'
            )

        st.markdown(f"""
<div style="margin:.5rem 0 .3rem">
  <span class="method-badge m-ref" style="margin-right:.3rem">Reference Match</span>
  <span class="method-badge m-sem" style="margin-right:.3rem">Semantic Match</span>
  <span class="method-badge m-ai" style="margin-right:.3rem">AI Validated / Refined</span>
  <span class="method-badge m-human" style="margin-right:.3rem">Manual Override</span>
  <span class="method-badge m-absent" style="margin-right:.3rem">Not Mapped</span>
  <span class="method-badge m-miss">Missing</span>
</div>
<div class="schema-grid">{cells_html}</div>
""", unsafe_allow_html=True)

    # Column count breakdown
    bc1, bc2, bc3, bc4, bc5 = st.columns(5)
    bc1.metric("Reference Matched",  len(cats["reference"]),    help="Matched by known insurance industry names")
    bc2.metric("Semantic Matched",   len(cats["semantic"]),     help="Matched by column name similarity")
    bc3.metric("AI Validated",       len(cats["ai_validated"]), help="Semantic match confirmed by AI")
    bc4.metric("AI Refined",         len(cats["ai_refined"]),   help="AI corrected or identified from data")
    bc5.metric("Not Mapped / Null",  total_null + total_missing)

    tabs = st.tabs(["Column Mapping", "Mapping Journey", "Data Preview", "Flag Log"])

    # ── Column Mapping ────────────────────────────────────────────────────────
    with tabs[0]:
        st.markdown(
            '<p style="font-size:.82rem;color:var(--muted);margin-bottom:.8rem">'
            f'All {total_schema} schema fields — columns without a source match are shown as null/missing.'
            '</p>', unsafe_allow_html=True)

        rows_html = []
        for m in mappings:
            # Badge
            if m.flag in ("missing_required", "missing_source", "missing"):
                badge = '<span class="method-badge m-miss">Missing</span>'
            else:
                badge = method_badge(m.match_type)

            # Source column(s) — show ALL if multi-source
            if _is_auto_populated(m):
                src_html = '<span style="color:var(--muted);font-size:.78rem;font-style:italic">null</span>'
            elif m.source_cols:
                src_parts = [f'<code style="font-size:.78rem">{s}</code>' for s in m.source_cols]
                src_html = safe_join(src_parts)
                if len(m.source_cols) > 1:
                    src_html += ' <span style="font-size:.65rem;color:#f59e0b;font-weight:600">MULTI</span>'
            else:
                src_html = '<span style="color:var(--muted);font-size:.78rem;font-style:italic">null</span>'

            # Confidence
            if _is_auto_populated(m) or m.confidence == 0:
                conf_html = '<span style="color:var(--muted);font-size:.78rem">—</span>'
            else:
                conf_html = (
                    f'<span style="font-family:var(--mono);font-size:.82rem">{m.confidence}%</span>'
                    f'{conf_bar(m.confidence)}'
                )

            basis = _human_basis(m)
            basis_short = (basis[:90] + "…") if len(basis) > 90 else basis

            rows_html.append(f"""
<div style="display:grid;grid-template-columns:180px 130px 260px 140px 1fr;
            border-bottom:1px solid var(--border);align-items:center">
  <div style="padding:.5rem .8rem;font-family:var(--mono);font-size:.82rem;color:var(--text)">{m.output_col}</div>
  <div style="padding:.5rem .8rem">{badge}</div>
  <div style="padding:.5rem .8rem">{src_html}</div>
  <div style="padding:.5rem .8rem">{conf_html}</div>
  <div style="padding:.5rem .8rem;font-size:.75rem;color:#94a3b8;line-height:1.4">{basis_short}</div>
</div>""")

        table = f"""
<div style="border:1px solid var(--border);border-radius:6px;overflow:hidden">
  <div style="display:grid;grid-template-columns:180px 130px 260px 140px 1fr;
              background:#f8f9fa;border-bottom:1px solid #dee2e6">
    <div style="padding:.55rem .8rem;font-size:.7rem;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.06em">Target Field</div>
    <div style="padding:.55rem .8rem;font-size:.7rem;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.06em">Match Type</div>
    <div style="padding:.55rem .8rem;font-size:.7rem;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.06em">Source Column(s)</div>
    <div style="padding:.55rem .8rem;font-size:.7rem;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.06em">Confidence</div>
    <div style="padding:.55rem .8rem;font-size:.7rem;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.06em">Why This Match</div>
  </div>
  {"".join(rows_html)}
</div>"""
        st.markdown(table, unsafe_allow_html=True)

    # ── Mapping Journey ───────────────────────────────────────────────────────
    with tabs[1]:
        st.markdown(
            '<p style="font-size:.85rem;color:#1a1a2e;margin-bottom:1rem">'
            'Full decision trail for every schema field — what each matching step found and why the final column was chosen.'
            '</p>', unsafe_allow_html=True)

        fc1, fc2 = st.columns([3, 1])
        with fc1:
            jf = st.selectbox("Filter by outcome", [
                "All mapped columns",
                "AI confirmed semantic match",
                "AI corrected the mapping",
                "AI found field absent",
                "Reference match (no AI needed)",
                "Not mapped / null",
                "Multi-source columns",
            ], key="journey_filter")
        with fc2:
            show_null = st.checkbox("Show null / auto-populated", False, key="journey_null")

        for m in mappings:
            if not show_null and (_is_auto_populated(m) or not m.source_cols):
                if jf not in ("Not mapped / null", "All mapped columns"):
                    continue
            mt = m.match_type.lower()
            if jf == "AI confirmed semantic match" and not (
                mt == "ai_validated" or (hasattr(m, "ai_agreement") and m.ai_agreement and m.fuzzy_suggestion)
            ): continue
            if jf == "AI corrected the mapping" and mt not in ("ai_refined", "ai_inferred", "llm_refined", "llm_inferred"): continue
            if jf == "AI found field absent" and getattr(m, "ai_suggestion", "") != "null": continue
            if jf == "Reference match (no AI needed)" and mt not in ("reference_exact", "alias_exact", "template_auto"): continue
            if jf == "Not mapped / null" and m.source_cols and not _is_auto_populated(m): continue
            if jf == "Multi-source columns" and not (m.flag == "multi_source" or len(m.source_cols) > 1): continue
            _render_journey_card(m)

    # ── Data Preview ──────────────────────────────────────────────────────────
    with tabs[2]:
        mapped_only = [m for m in mappings if m.source_cols and not _is_auto_populated(m)]
        if mapped_only:
            st.markdown('<p style="font-size:.82rem;color:var(--muted)">Sample values from your file for each mapped field. Multi-source fields show all contributing columns.</p>', unsafe_allow_html=True)
            preview = []
            for m in mapped_only:
                label, _, _ = _match_type_display(m.match_type)
                # Show all source columns and their samples
                for sc in m.source_cols:
                    samples = df[sc].dropna().astype(str).head(8).tolist() if sc in df.columns else []
                    multi_note = f" (multi-source {m.source_cols.index(sc)+1}/{len(m.source_cols)})" if len(m.source_cols) > 1 else ""
                    preview.append({
                        "Target Field": m.output_col + multi_note,
                        "Source Column": sc,
                        "How Matched": label,
                        "Confidence %": m.confidence,
                        "Sample Values": safe_join(samples) if samples else "—"
                    })
            pf = pd.DataFrame(preview)
            def sty_c(v):
                if v >= 85: return "color:#10b981"
                if v >= 60: return "color:#f59e0b"
                return "color:#ef4444"
            st.dataframe(pf.style.map(sty_c, subset=["Confidence %"]), use_container_width=True, height=480)

        st.markdown("---")
        st.markdown(f'<p style="font-size:.82rem;color:var(--muted)">Raw file — {len(df)} rows × {len(df.columns)} columns · header at row {result["header_row"]}</p>', unsafe_allow_html=True)
        st.dataframe(df.head(20), use_container_width=True, height=280)

        # Null / not-mapped fields summary
        null_fields = [m for m in mappings if not m.source_cols or _is_auto_populated(m)]
        if null_fields:
            st.markdown("---")
            st.markdown(f"**{len(null_fields)} fields with no source column** (will be null or default in output)")
            null_rows = []
            for m in null_fields:
                null_rows.append({
                    "Field": m.output_col,
                    "Status": "Missing" if m.flag in ("missing_required","missing_source","missing") else "Not mapped",
                    "Reason": "Field not found in source file" if m.flag in ("missing_required","missing_source","missing") else "No matching column or auto-derived",
                })
            st.dataframe(pd.DataFrame(null_rows), use_container_width=True, height=min(len(null_fields)*40+60,380))

    # ── Flag Log ──────────────────────────────────────────────────────────────
    with tabs[3]:
        ca, cb = st.columns(2)
        with ca:
            missing = [m for m in mappings if m.flag in ("missing_required", "missing_source", "missing")]
            if missing:
                st.markdown(f"**🔴 Fields not found in source ({len(missing)})**")
                for m in missing: st.markdown(f"- `{m.output_col}` — {m.notes or 'No matching source column found'}")
            else:
                st.success("All fields are mapped", icon="✅")
            multi = [m for m in mappings if m.flag == "multi_source" or len(m.source_cols) > 1]
            if multi:
                st.markdown(f"**🟡 Fields with multiple source columns ({len(multi)})**")
                for m in multi: st.markdown(f"- `{m.output_col}` → {safe_join(m.source_cols)}")
        with cb:
            unmapped = flags["unmapped_raw_cols"]
            if unmapped:
                st.markdown(f"**🔵 Source columns not used in mapping ({len(unmapped)})**")
                for col in unmapped: st.markdown(f"- `{col}`")
            else:
                st.success("All source columns are used", icon="✅")

    st.markdown("---")
    d1, d2, d3 = st.columns(3)
    with d1:
        st.download_button("↓  Mapped SOV (.xlsx)", data=build_mapped_excel(result),
                            file_name="sov_mapped_air.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True)
    with d2:
        st.download_button("↓  Mapping Report (.xlsx)", data=result["_report_excel_bytes"],
                            file_name="sov_mapping_report.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True)
    with d3:
        st.download_button("↓  Mapping Report (.json)", data=result["_report_json_str"],
                            file_name="sov_mapping_report.json", mime="application/json",
                            use_container_width=True)


def _render_journey_card(m):
    mt = m.match_type.lower()

    # Determine outcome label and card class
    if _is_auto_populated(m):
        ocls, olbl = "", "Not from source"
    elif not m.source_cols:
        ocls, olbl = "j-removed", "Not mapped"
    elif mt in ("ai_refined", "ai_inferred", "llm_refined", "llm_inferred"):
        ocls, olbl = "j-override", "AI refined"
    elif mt == "ai_validated" or (getattr(m, "ai_agreement", False) and getattr(m, "fuzzy_suggestion", "")):
        ocls, olbl = "j-agreed", "AI validated"
    elif getattr(m, "ai_suggestion", "") == "null" and getattr(m, "fuzzy_suggestion", ""):
        ocls, olbl = "j-removed", "AI found absent"
    elif mt in ("reference_exact", "alias_exact", "template_auto"):
        ocls, olbl = "j-agreed", "Reference match"
    else:
        label, _, _ = _match_type_display(m.match_type)
        ocls, olbl = "", label

    # Build steps
    steps = []

    # Step 1: Reference dictionary
    alias_sug = getattr(m, "alias_suggestion", "")
    if alias_sug:
        steps.append(("1. Reference Dict", alias_sug, "Known insurance industry name recognised"))
    elif mt in ("reference_exact", "alias_exact", "template_auto"):
        steps.append(("1. Reference Dict", m.source_cols[0] if m.source_cols else "—", "Exact match found"))
    else:
        steps.append(("1. Reference Dict", "no match", "No known alias found"))

    # Step 2: Semantic similarity
    fuzzy_sug = getattr(m, "fuzzy_suggestion", "")
    fuzzy_conf = getattr(m, "fuzzy_confidence", 0)
    if fuzzy_sug:
        note = f"name similarity: {fuzzy_conf}/100" if fuzzy_conf else ""
        steps.append(("2. Semantic Match", fuzzy_sug, note))
    elif mt in ("semantic_match", "fuzzy"):
        steps.append(("2. Semantic Match", m.source_cols[0] if m.source_cols else "—", "Column name similarity"))
    elif mt in ("reference_exact", "alias_exact", "template_auto"):
        steps.append(("2. Semantic Match", "—", "Not needed — reference match found"))
    else:
        steps.append(("2. Semantic Match", "no match", "Column name not similar enough"))

    # Step 3: AI validation
    ai_sug = getattr(m, "ai_suggestion", "")
    ai_reasoning = getattr(m, "ai_reasoning", "")
    if _is_auto_populated(m):
        steps.append(("3. AI Validation", "skipped", "Not sourced from file"))
    elif not ai_sug or ai_sug == "unavailable":
        steps.append(("3. AI Validation", "not run", "Above confidence threshold — not needed"))
    elif ai_sug == "null":
        steps.append(("3. AI Validation", "absent in data", ai_reasoning or "Field not found in sample values"))
    else:
        steps.append(("3. AI Validation", ai_sug, ai_reasoning or "Confirmed from sample data"))

    # Step 4 (Final): show ALL source columns for multi-source
    if m.source_cols and not _is_auto_populated(m):
        final_val = safe_join(m.source_cols)
        final_note = f"confidence {m.confidence}%" + (" · multi-source" if len(m.source_cols) > 1 else "")
    else:
        final_val = "null / not mapped"
        final_note = ""

    steps.append(("4. Final Decision", final_val, final_note))

    # Render steps
    steps_html = '<div class="j-steps-row">'
    for i, (lbl, val, note) in enumerate(steps):
        is_final = i == len(steps) - 1
        scls = "j-final" if is_final else ""
        vc = "#1565c0" if (is_final and m.source_cols and not _is_auto_populated(m)) else (
            "#adb5bd" if val in ("no match", "absent in data", "not needed — reference match found",
                                  "—", "not run", "skipped", "null / not mapped") else "#1a1a2e"
        )
        note_html = f'<div class="j-step-note">{note}</div>' if note else ""
        steps_html += f'<div class="j-step {scls}"><div class="j-step-lbl">{lbl}</div><div class="j-step-val" style="color:{vc}">{val}</div>{note_html}</div>'
        if i < len(steps) - 1:
            steps_html += '<div class="j-arrow">→</div>'
    steps_html += '</div>'

    # Flag pills
    flag_html = ""
    if m.flag in ("missing_required", "missing_source", "missing"):
        flag_html = '<span style="background:rgba(239,68,68,.15);color:#dc2626;font-family:var(--mono);font-size:.68rem;padding:.15rem .5rem;border-radius:3px;margin-left:.5rem">missing</span>'
    elif m.flag == "multi_source" or len(m.source_cols) > 1:
        flag_html = f'<span style="background:rgba(245,158,11,.15);color:#b45309;font-family:var(--mono);font-size:.68rem;padding:.15rem .5rem;border-radius:3px;margin-left:.5rem">{len(m.source_cols)} source columns</span>'

    oc_col = {"j-agreed": "#10b981", "j-override": "#8b5cf6", "j-removed": "#ef4444"}.get(ocls, "#6c757d")
    out_badge = (f'<span style="background:rgba(0,0,0,.06);color:{oc_col};font-family:var(--mono);'
                 f'font-size:.68rem;padding:.15rem .5rem;border-radius:3px;margin-left:.5rem;'
                 f'border:1px solid {oc_col}60">{olbl}</span>')

    basis = _human_basis(m)
    basis_html = f'<div class="j-basis">📌 {basis}</div>' if basis else ""

    # For multi-source, show value pattern info per column
    multi_info = ""
    if len(m.source_cols) > 1:
        multi_info = (
            f'<div style="font-size:.72rem;color:#6c757d;margin-top:.4rem;padding:.3rem .6rem;'
            f'background:#fffbf0;border:1px solid #f59e0b30;border-radius:4px">'
            f'<strong>All contributing source columns:</strong> '
            + safe_join(f"<code>{s}</code>" for s in m.source_cols)
            + f'</div>'
        )

    st.markdown(f"""<div class="j-card {ocls}">
  <div class="j-title">{m.output_col}{out_badge}{flag_html}</div>
  {steps_html}
  {multi_info}
  {basis_html}
</div>""", unsafe_allow_html=True)

