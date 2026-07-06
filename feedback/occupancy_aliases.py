"""
Auto-extracted module: feedback/occupancy_aliases.py
"""

from __future__ import annotations

import re
import json
import string
from pathlib import Path

import os
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OCC_STORE_FILE = Path(os.environ.get("SOV_OCC_ALIAS_PATH", str(_DATA_DIR / "occ_alias_store.json")))


def _norm(text: str) -> str:
    text = str(text).lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    return re.sub(r"\s+", " ", text).strip()


def load_occ_rules() -> dict:
    if OCC_STORE_FILE.exists():
        try:
            return json.loads(OCC_STORE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_store(store: dict) -> None:
    OCC_STORE_FILE.write_text(
        json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")


def save_occ_rule(raw_description: str, confirmed_code: int) -> None:
    store = load_occ_rules()
    store[_norm(raw_description)] = {
        "code":        confirmed_code,
        "raw":         raw_description,
        "uses":        store.get(_norm(raw_description), {}).get("uses", 0) + 1,
    }
    _save_store(store)


def lookup_occ_rule(raw_description: str) -> int | None:
    store = load_occ_rules()
    return store.get(_norm(raw_description), {}).get("code")
