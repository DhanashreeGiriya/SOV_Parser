"""
Auto-extracted module: header_mapping/pipeline.py
"""

from __future__ import annotations

import pandas as pd
from pathlib import Path

from header_mapping.ai_refine import refine_mappings_with_ai
from header_mapping.excel_io import _normalise, auto_detect_best_sheet, load_sov
from header_mapping.matching import flag_unmapped_raw_columns, map_headers
from header_mapping.reporting import export_mapping_report
from header_mapping.schema import AI_REVIEW_THRESHOLD
from header_mapping.scoring import apply_scoring, generate_mapping_flags

def run_header_mapping(
    sov_file,
    sheet_name=None,
    output_dir=".",
    report_name="sov_header_mapping_report",
    max_scan_rows: int = 25,
    target_system: str = "AIR", # AIR harcoding in two places?
    header_row_override=None,
    progress_callback=None,
    template_name: str = "",          
) -> dict:
    sov_file = Path(sov_file)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sys_label = target_system.upper()

    def _progress(msg):
        if progress_callback:
            progress_callback(msg)

    _progress("Loading SOV and detecting header row...")

    if header_row_override is not None:
        resolved_sheet = sheet_name if sheet_name is not None else auto_detect_best_sheet(sov_file)
        header_row = header_row_override
        df = pd.read_excel(sov_file, sheet_name=resolved_sheet,
                           header=header_row - 1, dtype=str)
        df.dropna(how="all", inplace=True)
        df.reset_index(drop=True, inplace=True)
        raw_headers = list(df.columns)
    else:
        df, header_row, raw_headers = load_sov(sov_file, sheet_name=sheet_name,
                                               max_scan_rows=max_scan_rows)

    # ── Load human-feedback aliases (Pass 0) ─────────────────────────────────
    _progress("Pass 0: Loading human feedback rules...")
    try:
        from feedback.header_feedback import load_feedback_aliases
        feedback_aliases = load_feedback_aliases(template_name=template_name)
        n_fb = len(feedback_aliases)
        if n_fb:
            _progress(f"Pass 0: {n_fb} feedback rules loaded — these take priority over all other passes")
        else:
            _progress("Pass 0: No feedback rules yet — defaults to reference/semantic matching")
    except ImportError:
        feedback_aliases = {}
        _progress("Pass 0: sov_feedback module not found — skipping feedback pass")

    # ── DEBUG: show exactly what was loaded vs what headers exist ─────────────
    # Remove this block once your feedback rules are matching correctly.
    import os as _os
    if _os.environ.get("SOV_DEBUG_FEEDBACK", "0") == "1" and feedback_aliases:
        print("\n=== [DEBUG] FEEDBACK RULES LOADED ===")
        for norm_key, rule in feedback_aliases.items():
            stored_srcs = rule.get("source_cols", [rule.get("source_col", "?")])
            print(f"  Rule [{norm_key}]: {rule['output_col']} <- {stored_srcs}")
            for stored_src in stored_srcs:
                print(f"stored repr : {repr(stored_src)}")
                print(f"stored norm : {repr(_normalise(stored_src))}")
                found_exact  = [h for h in raw_headers if h == stored_src]
                found_normed = [h for h in raw_headers if _normalise(h) == _normalise(stored_src)]
                if found_exact:
                    print(f"EXACT match : {found_exact}")
                elif found_normed:
                    print(f"NORM  match : {found_normed}")
                else:
                    print(f"NO MATCH — closest raw headers:")
                    from fuzzywuzzy import fuzz as _fz
                    near = sorted(raw_headers,
                                  key=lambda h: _fz.token_set_ratio(_normalise(h), _normalise(stored_src)),
                                  reverse=True)[:3]
                    for h in near:
                        print(f"{repr(h)}  (score={_fz.token_set_ratio(_normalise(h), _normalise(stored_src))})")
        print("=== [DEBUG] RAW HEADERS ===")
        for h in raw_headers:
            print(f"  {repr(h)}")
        print("=== [DEBUG] END ===\n")
    # ── END DEBUG ─────────────────────────────────────────────────────────────

    _progress("Pass A: Reference dictionary matching...")
    _progress("Pass B: Semantic name similarity with value-pattern scoring...")
    mappings = map_headers(raw_headers, df=df, target_system=sys_label,
                           feedback_aliases=feedback_aliases)
    mappings = apply_scoring(mappings)

    # Feedback-matched columns skip AI; only borderline non-feedback columns go to AI
    need_ai = [m for m in mappings if m.confidence < AI_REVIEW_THRESHOLD and not m.feedback_matched]

    if need_ai:
        _progress(f"Pass C: Semantic AI validation — {len(need_ai)} borderline columns (confidence < {AI_REVIEW_THRESHOLD}%)...")
        mappings, ai_status = refine_mappings_with_ai(
            raw_headers, df, mappings,
            target_system=sys_label,
            progress_callback=_progress,
        )
        mappings = apply_scoring(mappings)
    else:
        ai_status = {
            "ran": False,
            "error": f"All {len(mappings)} columns above {AI_REVIEW_THRESHOLD}% threshold",
            "fields_reviewed": 0,
            "fields_confirmed": 0,
            "fields_corrected": 0,
            "raw_response_preview": "",
            "cfg_used": {},
            "threshold_used": AI_REVIEW_THRESHOLD,
        }

    _progress("Finalising flags and generating report...")
    unmapped_raw = flag_unmapped_raw_columns(raw_headers, mappings)
    flags = generate_mapping_flags(mappings, unmapped_raw)

    report_path = output_dir / f"{report_name}_{sys_label.lower()}.xlsx"
    export_mapping_report(
        mappings, unmapped_raw, flags,
        output_path=report_path,
        sov_file_name=sov_file.name,
        target_system=sys_label,
    )

    print(mappings)
    return {
        "header_row": header_row,
        "raw_headers": raw_headers,
        "data_frame": df,
        "mappings": mappings,
        "unmapped_raw": unmapped_raw,
        "flags": flags,
        "report_excel": str(report_path),
        "report_json": str(report_path.with_suffix(".json")),
        "ai_status": ai_status,
        "feedback_aliases_loaded": len(feedback_aliases),  # ← surfaced to UI
    }

