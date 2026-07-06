"""
Auto-extracted module: feedback/row_feedback/store.py
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
RULES_FILE = Path(os.environ.get("SOV_ROW_FEEDBACK_PATH", str(_DATA_DIR / "sov_row_feedback_store.json")))


PRE_CODE_RULE_COLUMNS: set[str] = {"LocationName", "Street"}


def _load() -> dict:
    if RULES_FILE.exists():
        try:
            with open(RULES_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save(store: dict) -> None:
    try:
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2, ensure_ascii=False, default=str)
    except OSError as e:
        print(f"[sov_row_feedback] WARNING: could not write rules: {e}")


def save_rule(rule: dict) -> str:
    """
    Persist a single accepted rule. Returns the rule_id.

    rule must contain:
      output_col, source_col, prompt, lambda_src, explanation,
      reviewer (optional), reason (optional)
    """
    store   = _load()
    out_col = str(rule.get("output_col", "")).strip()
    if not out_col:
        raise ValueError("output_col is required")

    now     = datetime.now(timezone.utc).isoformat()
    rule_id = str(uuid.uuid4())[:8]

    bucket = store.setdefault(out_col, [])

    # Deduplicate by prompt + lambda_src
    for existing in bucket:
        if (existing.get("prompt") == rule.get("prompt") and
                existing.get("lambda_src") == rule.get("lambda_src")):
            existing["uses"]         = existing.get("uses", 0) + 1
            existing["last_applied"] = now
            existing["confirmed"]    = True
            _save(store)
            return existing["rule_id"]

    new_rule = {
        "rule_id":      rule_id,
        "output_col":   out_col,
        "source_col":   rule.get("source_col", ""),
        "prompt":       rule.get("prompt", ""),
        "lambda_src":   rule.get("lambda_src", "lambda v: v"),
        "explanation":  rule.get("explanation", ""),
        "reason":       rule.get("reason", ""),
        "reviewer":     rule.get("reviewer", ""),
        "uses":         1,
        "confirmed":    True,
        "created":      now,
        "last_applied": now,
    }
    bucket.append(new_rule)
    _save(store)
    return rule_id


def load_rules(output_col: Optional[str] = None) -> dict:
    store = _load()
    if output_col:
        return {output_col: store.get(output_col, [])}
    return store


def get_rules_summary() -> list[dict]:
    store  = _load()
    result = []
    for out_col, rules in store.items():
        for r in rules:
            result.append({
                "rule_id":      r.get("rule_id", ""),
                "output_col":   r.get("output_col", out_col),
                "source_col":   r.get("source_col", ""),
                "prompt":       r.get("prompt", ""),
                "lambda_src":   r.get("lambda_src", ""),
                "explanation":  r.get("explanation", ""),
                "reason":       r.get("reason", ""),
                "reviewer":     r.get("reviewer", ""),
                "uses":         r.get("uses", 0),
                "confirmed":    r.get("confirmed", True),
                "created":      r.get("created", "")[:10],
                "last_applied": r.get("last_applied", "")[:10],
            })
    return sorted(result, key=lambda x: (-x["uses"], x["output_col"]))


def delete_rule(rule_id: str) -> bool:
    store = _load()
    found = False
    for out_col, rules in store.items():
        before = len(rules)
        store[out_col] = [r for r in rules if r.get("rule_id") != rule_id]
        if len(store[out_col]) < before:
            found = True
    if found:
        _save(store)
    return found


def clear_rules(output_col: Optional[str] = None) -> int:
    store = _load()
    if output_col is None:
        total = sum(len(v) for v in store.values())
        _save({})
        return total
    count = len(store.get(output_col, []))
    store[output_col] = []
    _save(store)
    return count


def reorder_rules(output_col: str, ordered_rule_ids: list[str]) -> bool:
    """
    Reorder rules for a given output_col to match ordered_rule_ids.
    Rules not in ordered_rule_ids are appended at the end unchanged.
    Returns True if reorder was successful.
    """
    store = _load()
    bucket = store.get(output_col)
    if not bucket:
        return False

    id_to_rule = {r["rule_id"]: r for r in bucket}
    reordered  = [id_to_rule[rid] for rid in ordered_rule_ids if rid in id_to_rule]
    # Append any rules not in the ordered list (shouldn't normally happen)
    remaining  = [r for r in bucket if r["rule_id"] not in ordered_rule_ids]
    store[output_col] = reordered + remaining
    _save(store)
    return True

