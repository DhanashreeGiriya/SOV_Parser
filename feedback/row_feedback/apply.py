"""
Auto-extracted module: feedback/row_feedback/apply.py
"""

from __future__ import annotations

import pandas as pd
from typing import Optional
from datetime import datetime, timezone

from feedback.row_feedback.store import PRE_CODE_RULE_COLUMNS, _load, _save
from feedback.row_feedback.transform_lambda import _safe_apply
from header_mapping.models import LockedSchema
from row_processing.export import run_value_transformation
from row_processing.flags import FlagLog
from row_processing.process_row import process_row

def apply_rules(
    cleaned_df: pd.DataFrame,
    locked_schema,
    raw_df: pd.DataFrame,
) -> tuple[pd.DataFrame, list]:
    """
    Apply every confirmed rule's lambda to its target column.

    Rules for the same output_col are applied in CHAIN order — rule N sees
    the output of rule N-1 (not the original raw value).  This lets users
    build up multi-step pipelines incrementally:

      Rule 1:  strip currency  →  "$1,200" → "1200"
      Rule 2:  divide by 1000 →  "1200"   → "1.2"

    The chain is seeded from the code rule's output for that column (i.e. the
    value already produced by process_row / the AIR-RMS crosswalk etc. in
    cleaned_df), so row-feedback rules apply on top of code rules rather than
    overwriting them. raw_df is retained for column-source lookups used in
    the change log only.

    Returns (df, log) where log is a list of change records.
    """
    store = _load()
    if not store:
        return cleaned_df, []

    df  = cleaned_df.copy()
    log: list = []
    now = datetime.now(timezone.utc).isoformat()

    # Build locked_schema lookup: output_col -> list of source col names
    col_to_sources: dict = {}
    if locked_schema is not None:
        for d in locked_schema.decisions:
            col_to_sources[d.output_col] = d.final_source or []

    for out_col, rules in store.items():
        if out_col not in df.columns:
            continue
        if out_col in PRE_CODE_RULE_COLUMNS:
            continue  # handled pre-code-rule by apply_rules_to_raw(), not here

        confirmed_rules = [r for r in rules if r.get("confirmed", True)]
        if not confirmed_rules:
            continue

        # Resolve the raw source column for this output column (used to seed chain)
        first_rule    = confirmed_rules[0]
        src_col_hint  = first_rule.get("source_col", "")
        if src_col_hint and src_col_hint in raw_df.columns:
            active_src = src_col_hint
        else:
            sources    = col_to_sources.get(out_col, [])
            active_src = next((s for s in sources if s in raw_df.columns), "")

        for row_idx in range(len(df)):
            # Seed value: start from the CODE RULE's output for this column
            # (cleaned_df), not the raw source value. This ensures row-feedback
            # rules apply on top of whatever the code rule already produced
            # (AIR/RMS crosswalk, ISO lookups, formatting, etc.) instead of
            # discarding that work and re-deriving from raw.
            seed = str(df.at[row_idx, out_col])

            current_val = seed  # ← chained value; updated after each rule

            for rule in confirmed_rules:
                lambda_src = rule.get("lambda_src", "lambda v: v")
                rule_id    = rule.get("rule_id", "")

                new_val, err = _safe_apply(lambda_src, current_val)
                if err:
                    continue  # skip this rule on error; keep current_val

                if str(new_val) != str(current_val):
                    old_val = current_val
                    current_val = str(new_val)
                    log.append({
                        "row_idx":    row_idx,
                        "output_col": out_col,
                        "rule_id":    rule_id,
                        "source_col": active_src or src_col_hint,
                        "raw_val":    seed,
                        "old_val":    old_val,
                        "new_val":    current_val,
                        "prompt":     rule.get("prompt", ""),
                        "chain_step": confirmed_rules.index(rule) + 1,
                    })

            # Write the final chained result back to the dataframe
            df.at[row_idx, out_col] = current_val

        for rule in confirmed_rules:
            rule["last_applied"] = now

    if log:
        _save(store)

    return df, log


def apply_rules_to_raw(
    raw_df: pd.DataFrame,
    locked_schema,
    output_cols: Optional[set] = None,
) -> tuple[pd.DataFrame, list]:
    """
    Apply saved row-feedback rules to the RAW source column(s), BEFORE the
    code rule (process_row / transform_* / resolve_* functions) ever sees
    the data — the opposite order from apply_rules().

    Use this only for output columns whose code-rule logic reads a single
    pre-existing raw source column and cleans/parses it (e.g. LocationName,
    Street). It is not meaningful for columns whose code rule derives the
    value from multiple independent raw inputs combined together (e.g.
    ConstructionCode from iso_code + description + num_stories) — for those,
    keep using the default apply_rules() (rules run after the code rule).

    Parameters
    ----------
    raw_df       : the original uploaded dataframe (df_raw)
    locked_schema: used to resolve output_col -> source_col(s) when a rule
                   doesn't have an explicit source_col saved
    output_cols  : which output columns to pre-apply for. Defaults to
                   PRE_CODE_RULE_COLUMNS.

    Returns (raw_df_adjusted, log) — raw_df_adjusted is a COPY of raw_df with
    the targeted source column(s) rewritten in place; the original raw_df
    (and therefore raw_val shown elsewhere, e.g. Before/After tabs) is
    untouched. log entries mirror apply_rules()'s shape, with chain_step,
    rule_id, etc., plus a "pre_code_rule": True marker.
    """
    if output_cols is None:
        output_cols = PRE_CODE_RULE_COLUMNS

    store = _load()
    if not store:
        return raw_df, []

    df  = raw_df.copy()
    log: list = []
    now = datetime.now(timezone.utc).isoformat()

    col_to_sources: dict = {}
    if locked_schema is not None:
        for d in locked_schema.decisions:
            col_to_sources[d.output_col] = d.final_source or []

    for out_col in output_cols:
        rules = store.get(out_col, [])
        confirmed_rules = [r for r in rules if r.get("confirmed", True)]
        if not confirmed_rules:
            continue

        # Resolve which raw column this chain targets
        first_rule   = confirmed_rules[0]
        src_col_hint = first_rule.get("source_col", "")
        if src_col_hint and src_col_hint in df.columns:
            active_src = src_col_hint
        else:
            sources    = col_to_sources.get(out_col, [])
            active_src = next((s for s in sources if s in df.columns), "")

        if not active_src:
            continue  # no resolvable raw source column — nothing to pre-apply to

        for row_idx in range(len(df)):
            seed = str(df.at[row_idx, active_src])
            current_val = seed

            for rule in confirmed_rules:
                lambda_src = rule.get("lambda_src", "lambda v: v")
                rule_id    = rule.get("rule_id", "")

                new_val, err = _safe_apply(lambda_src, current_val)
                if err:
                    continue

                if str(new_val) != str(current_val):
                    old_val = current_val
                    current_val = str(new_val)
                    log.append({
                        "row_idx":        row_idx,
                        "output_col":     out_col,
                        "rule_id":        rule_id,
                        "source_col":     active_src,
                        "raw_val":        seed,
                        "old_val":        old_val,
                        "new_val":        current_val,
                        "prompt":         rule.get("prompt", ""),
                        "chain_step":     confirmed_rules.index(rule) + 1,
                        "pre_code_rule":  True,
                    })

            df.at[row_idx, active_src] = current_val

        for rule in confirmed_rules:
            rule["last_applied"] = now

    if log:
        _save(store)

    return df, log


def build_full_preview(
    raw_df,
    locked_schema,
    output_col: str,
    candidate_lambda_src: str,
    sample_row_indices: list,
    existing_rules: Optional[list] = None,
    target_system: str = "AIR",
    days_covered: int = 365,
    default_country: str = "US",
    lob_col: str = "",
    primary_source_col: str = "",
) -> list[dict]:
    """
    Preview what output_col will ACTUALLY contain once `candidate_lambda_src`
    is accepted — running it together with the column's code rule
    (process_row / transform_*) and any already-confirmed row rules, in the
    same order the real pipeline (run_value_transformation) uses:

      • output_col in PRE_CODE_RULE_COLUMNS (e.g. Street, LocationName):
          raw source value -> existing row rules -> code rule
      • all other output_cols:
          raw row -> code rule -> existing row rules -> candidate rule

    This replaces a lambda-only preview (which never touches the code rule)
    with one that mirrors clicking "Run Transformation".

    Parameters
    ----------
    raw_df               : the original uploaded dataframe (positional access
                            via .iloc — sample_row_indices are POSITIONS, not
                            pandas index labels, matching process_row's idx)
    locked_schema        : LockedSchema used to resolve output_col -> source col(s)
    output_col           : the field being edited (e.g. "Street")
    candidate_lambda_src : the new rule's lambda, not yet saved
    sample_row_indices   : positional row indices into raw_df to preview
    existing_rules       : already-confirmed row-feedback rules for output_col
                            (chain runs before the candidate rule)
    target_system, days_covered, default_country, lob_col
                          : passed straight through to process_row — keep these
                            in sync with the values run_value_transformation()
                            actually uses, or the preview won't match reality
    primary_source_col   : raw column to show in the "raw" field for context
                            (falls back to the first mapped source column)

    Returns
    -------
    list[dict], one per sampled row:
      {"raw": str, "current_output": str, "new_output": str,
       "changed": bool, "error": str | None}
    """
    import sov_header_mapping as _shm  # lazy import — avoids any load-order issues

    existing_rules = [r for r in (existing_rules or []) if r.get("confirmed", True)]
    flag_log     = _shm.FlagLog()
    is_pre_code  = output_col in PRE_CODE_RULE_COLUMNS

    sources = locked_schema.get_sources(output_col) if locked_schema is not None else []
    display_src = primary_source_col or (sources[0] if sources else "")

    # Resolve which raw column the row-rule chain rewrites (pre-code columns only)
    active_src = ""
    if is_pre_code:
        hint = (existing_rules[0].get("source_col", "") if existing_rules else "")
        if hint and hint in raw_df.columns:
            active_src = hint
        else:
            active_src = next((s for s in sources if s in raw_df.columns), "")

    def _run_process_row(pos, row):
        out, _ = _shm.process_row(
            row_idx=pos, row=row, schema=locked_schema, flag_log=flag_log,
            target_system=target_system, days_covered=days_covered,
            default_country=default_country, lob_col=lob_col,
        )
        return out

    rows_out = []
    n = len(raw_df)
    for pos in sample_row_indices:
        if pos < 0 or pos >= n:
            continue
        base_row = raw_df.iloc[pos]
        raw_display = str(base_row.get(display_src, "")) if display_src else ""
        cand_err = None

        if is_pre_code and active_src:
            # 1. raw source value -> chain of existing rules
            seed = str(base_row.get(active_src, ""))
            prior_val = seed
            for r in existing_rules:
                out_v, err = _safe_apply(r.get("lambda_src", "lambda v: v"), prior_val)
                if not err:
                    prior_val = str(out_v)

            new_val, cand_err = _safe_apply(candidate_lambda_src, prior_val)
            new_val = str(new_val) if not cand_err else prior_val

            # 2. feed each variant into the code rule
            row_current = base_row.copy()
            row_current[active_src] = prior_val
            row_new = base_row.copy()
            row_new[active_src] = new_val

            current_out = _run_process_row(pos, row_current)
            new_out     = _run_process_row(pos, row_new)
            current_val = str(current_out.get(output_col, ""))
            new_col_val = str(new_out.get(output_col, ""))
            if not raw_display:
                raw_display = seed
        else:
            # 1. code rule runs on the untouched raw row (unaffected by row
            #    rules for non-pre-code columns)
            code_out = _run_process_row(pos, base_row)
            code_val = str(code_out.get(output_col, ""))
            if not raw_display:
                raw_display = code_val

            # 2. existing row rules, then the candidate rule, chained on
            #    the code rule's output
            prior_val = code_val
            for r in existing_rules:
                out_v, err = _safe_apply(r.get("lambda_src", "lambda v: v"), prior_val)
                if not err:
                    prior_val = str(out_v)

            new_v, cand_err = _safe_apply(candidate_lambda_src, prior_val)
            new_col_val = str(new_v) if not cand_err else prior_val
            current_val = prior_val

        rows_out.append({
            "raw":            raw_display,
            "current_output": current_val,
            "new_output":     new_col_val,
            "changed":        current_val != new_col_val,
            "error":          cand_err,
        })

    return rows_out

