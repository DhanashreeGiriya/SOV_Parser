"""
Auto-extracted module: feedback/row_feedback/transform_lambda.py
"""

from __future__ import annotations

import pandas as pd
import json
import re
from typing import Any

def _safe_apply(lambda_src: str, value: Any) -> tuple[Any, str | None]:
    """
    Execute lambda_src(value) in a sandboxed namespace.
    Returns (result, error_str).  error_str is None on success.
    """
    try:
        fn = eval(lambda_src, {"re": re, "__builtins__": {}})  # noqa: S307
        result = fn(str(value) if value is not None else "")
        return result, None
    except Exception as exc:
        return value, str(exc)


def run_lambda_on_series(lambda_src: str, series: pd.Series) -> pd.Series:
    """Apply lambda_src row-by-row; silently fall back to original on error."""
    results = []
    for val in series:
        out, err = _safe_apply(lambda_src, val)
        results.append(val if err else out)
    return pd.Series(results, index=series.index)


def _sanitise_lambda(src: str) -> str:
    """
    The LLM returns lambda_src inside a JSON string, so json.loads() converts
    regex escape sequences like \\b, \\d, \\w into their ASCII control-character
    equivalents (backspace, etc.) before we ever see the value.  This function
    re-escapes those sequences so the lambda compiles and runs correctly.
    """
    # Map control characters that originate from regex escapes back to
    # their two-character backslash forms.
    replacements = [
        ("\x08", "\\b"),   # backspace  <- \b (word boundary)
        ("\x0c", "\\f"),   # form-feed  <- \f
        ("\x0b", "\\v"),   # vert-tab   <- \v (rarely used in regex)
    ]
    for bad, good in replacements:
        src = src.replace(bad, good)
    return src


def _fallback_rule(prompt: str, sample_values: list, note: str = "") -> dict:
    """Return a no-op lambda with an error note when LLM is unavailable."""
    lambda_src = "lambda v: v"
    return {
        "lambda_src":  lambda_src,
        "explanation": f"No-op (identity) — {note}",
        "confidence":  0,
        "preview":     _build_preview(lambda_src, sample_values),
        "error":       note,
    }


def _build_preview(lambda_src: str, sample_values: list) -> list[dict]:
    """Run lambda_src on each sample value; return [{before, after, changed, error}]."""
    rows = []
    for val in sample_values[:12]:
        before = str(val) if val is not None else ""
        after, err = _safe_apply(lambda_src, before)
        after = str(after) if after is not None else ""
        rows.append({
            "before":  before,
            "after":   after,
            "changed": before != after,
            "error":   err,
        })
    return rows

