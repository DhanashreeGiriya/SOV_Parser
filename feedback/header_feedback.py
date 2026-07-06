"""
Auto-extracted module: feedback/header_feedback.py
"""

from __future__ import annotations

import re
import json
import os
import string
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

from header_mapping.matching import map_headers
from header_mapping.models import ColumnMapping
from header_mapping.schema import AI_REVIEW_THRESHOLD

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FEEDBACK_FILE = Path(os.environ.get("SOV_FEEDBACK_PATH", str(_DATA_DIR / "sov_feedback_store.json")))


_GLOBAL_KEY   = "_global"


def _normalise(text: str) -> str:
    """Identical normalisation used by sov_header_mapping.map_headers()."""
    text = str(text).lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    return re.sub(r"\s+", " ", text).strip()


def _load_store() -> dict:
    if FEEDBACK_FILE.exists():
        try:
            with open(FEEDBACK_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {_GLOBAL_KEY: {}}


def _save_store(store: dict) -> None:
    try:
        with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2, ensure_ascii=False)
    except OSError as e:
        print(f"[sov_feedback] WARNING: could not write feedback store: {e}")


def _bucket(store: dict, template_name: str) -> dict:
    """Return (and create if absent) the dict bucket for template_name."""
    key = template_name.strip() if template_name and template_name.strip() else _GLOBAL_KEY
    if key not in store:
        store[key] = {}
    return store[key]


def save_feedback(locked_schema, mappings) -> int:
    store         = _load_store()
    tname         = getattr(locked_schema, "template_name", "") or ""
    bucket        = _bucket(store, tname)
    global_bucket = _bucket(store, _GLOBAL_KEY)

    # Build lookup: output_col -> original ColumnMapping (to read match_type)
    mapping_index = {m.output_col: m for m in mappings}

    now     = datetime.now(timezone.utc).isoformat()
    written = 0

    for decision in locked_schema.decisions:
        if not decision.final_source:
            continue

        output_col = decision.output_col
        m          = mapping_index.get(output_col)
        match_type = getattr(m, "match_type", "") if m else ""

        # ── Decide whether to persist this decision ───────────────────────
        # 1. Human override  → always save
        # 2. AI refined/inferred/validated → save so Pass 0 replaces next AI call
        # 3. accepted auto   → skip (reference/semantic exact — already reliable)
        is_human_override = decision.decision == "override"
        is_ai_result      = match_type in (
            "ai_refined", "ai_inferred", "llm_refined", "llm_inferred", "ai_validated"
        )

        if not is_human_override and not is_ai_result:
            continue

        reason   = (decision.override_reason or "").strip()
        reviewer = (decision.reviewer or "").strip()

        # Auto-label AI results so the UI shows where the rule came from
        if is_ai_result and not reason:
            reason = f"Auto-learned from AI {match_type.replace('_', ' ')}"
        if is_ai_result and not reviewer:
            reviewer = "ai_autolearn"

        norm_key = _normalise(output_col)
        if not norm_key:
            continue

        existing  = bucket.get(norm_key, {})
        uses      = existing.get("uses", 0) + 1
        base_conf = existing.get("confidence", 88)

        # AI results start at a lower base confidence than human overrides
        # so they can still be bumped by human confirmation later
        if is_ai_result and not existing:
            base_conf = 90   # safely above AI_REVIEW_THRESHOLD (82) — won't re-trigger AI
        
        new_conf = min(99, base_conf + 2)

        rule = {
            "output_col":   output_col,
            "confidence":   new_conf,
            "reason":       reason or existing.get("reason", ""),
            "uses":         uses,
            "reviewer":     reviewer or existing.get("reviewer", ""),
            "last_seen":    now,
            "source_cols":  list(decision.final_source),
            "source_col":   decision.final_source[0] if decision.final_source else "",
            "origin":       "human" if is_human_override else "ai_autolearn",
        }
        bucket[norm_key]        = rule
        global_bucket[norm_key] = rule
        written += 1

    _save_store(store)
    return written


def load_feedback_aliases(template_name: str = "") -> dict:
    store  = _load_store()
    merged: dict = {}
    for norm_key, rule in store.get(_GLOBAL_KEY, {}).items():
        merged[norm_key] = rule
    tname = (template_name or "").strip()
    if tname and tname != _GLOBAL_KEY:
        for norm_key, rule in store.get(tname, {}).items():
            merged[norm_key] = rule
    # Ensure source_cols always a list
    for rule in merged.values():
        if "source_cols" not in rule and "source_col" in rule:
            rule["source_cols"] = [rule["source_col"]]
    return merged


def get_feedback_summary(template_name: str = "") -> list[dict]:
    store  = _load_store()
    result = []

    for scope, bucket in store.items():
        for norm_key, rule in bucket.items():
            # Support both old (source_col) and new (source_cols) format
            src_cols = rule.get("source_cols") or [rule.get("source_col", norm_key)]
            result.append({
                "norm_key":    norm_key,
                "source_col":  src_cols[0],               # first col for backwards compat
                "source_cols": src_cols,                   # ALL cols
                "output_col":  rule.get("output_col", ""),
                "confidence":  rule.get("confidence", 90),
                "reason":      rule.get("reason", ""),
                "uses":        rule.get("uses", 1),
                "reviewer":    rule.get("reviewer", ""),
                "last_seen":   rule.get("last_seen", ""),
                "origin":      rule.get("origin", "human"),
                "scope":       scope,
            })

    if template_name and template_name.strip() and template_name.strip() != _GLOBAL_KEY:
        result = [r for r in result
                  if r["scope"] in (_GLOBAL_KEY, template_name.strip())]

    seen: dict = {}
    for r in result:
        key = r["norm_key"]
        if key not in seen or r["scope"] != _GLOBAL_KEY:
            seen[key] = r
    return sorted(seen.values(), key=lambda x: (-x["uses"], x["output_col"]))


def delete_feedback_rule(norm_source_col: str, template_name: str = "") -> bool:
    """
    Delete a single feedback rule.

    Parameters
    ----------
    norm_source_col : str
        The normalised source column key to delete.
    template_name : str
        If given, delete from that template bucket; otherwise delete from global.

    Returns
    -------
    bool
        True if a rule was deleted, False if not found.
    """
    store  = _load_store()
    key    = (template_name or "").strip() or _GLOBAL_KEY
    bucket = store.get(key, {})
    if norm_source_col in bucket:
        del bucket[norm_source_col]
        _save_store(store)
        return True
    return False


def clear_feedback(template_name: Optional[str] = None) -> int:
    """
    Clear feedback rules.

    If template_name is None, wipes ALL rules (global + all templates).
    If template_name is given, wipes only that template's bucket.

    Returns number of rules deleted.
    """
    store = _load_store()
    if template_name is None:
        total = sum(len(v) for v in store.values())
        _save_store({_GLOBAL_KEY: {}})
        return total
    key = template_name.strip() or _GLOBAL_KEY
    count = len(store.get(key, {}))
    store[key] = {}
    _save_store(store)
    return count

