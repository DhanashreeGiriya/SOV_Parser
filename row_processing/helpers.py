"""
Auto-extracted module: row_processing/helpers.py
"""

from __future__ import annotations

import pandas as pd

def _to_float(val, default: float = 0.0) -> float:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    try:
        return float(str(val).replace(",", "").replace("$", "").strip())
    except (ValueError, TypeError):
        return default


def _to_int(val, default=None):
    f = _to_float(val, default=float("nan"))
    if pd.isna(f):
        return default
    return int(round(f))


def _clean_str(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).strip()


def _pick_first_nonempty(row, cols):
    for col in cols:
        if col in row.index:
            v = _clean_str(row[col])
            if v:
                return v
    return ""


def _clean_str_local(val) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    return "" if s.lower() in ("nan", "none") else s

