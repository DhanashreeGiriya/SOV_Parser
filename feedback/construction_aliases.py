"""
Auto-extracted module: feedback/construction_aliases.py
"""

from __future__ import annotations

import re
import json
import string
from pathlib import Path

import os
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CONST_STORE_FILE = Path(os.environ.get("SOV_CONST_ALIAS_PATH", str(_DATA_DIR / "const_alias_store.json")))


def _norm(text: str) -> str:
    text = str(text).lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    return re.sub(r"\s+", " ", text).strip()


_CONSTRUCTION_VOCAB = re.compile(
    r"\b(wood|frame|timber|mason(ry)?|brick|veneer|steel|metal|concrete|"
    r"rc|reinforc\w*|fire.?resist\w*|non.?combust\w*|tilt.?up|precast|"
    r"pre.?fab\w*|manufactur\w*|mobile home|modular|class\s?[a-e]\b|"
    r"joisted|superior)\b",
    re.I,
)


def _looks_like_construction_text(text: str) -> bool:
    """Return True only if the text plausibly describes a building's
    construction type/material, not an unrelated underwriting note."""
    if not text or not text.strip():
        return False
    return bool(_CONSTRUCTION_VOCAB.search(text))


def load_const_rules() -> dict:
    if CONST_STORE_FILE.exists():
        try:
            return json.loads(CONST_STORE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_store(store: dict) -> None:
    CONST_STORE_FILE.write_text(
        json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")


def save_const_rule(raw_description: str, confirmed_code: int) -> None:
    if not _looks_like_construction_text(raw_description):
        # Refuse to cache — this text doesn't read like a construction
        # description (likely an underwriting note leaking in from the
        # wrong source column). Silently skip rather than poison the store.
        return
    store = load_const_rules()
    store[_norm(raw_description)] = {
        "code":        confirmed_code,
        "raw":         raw_description,
        "uses":        store.get(_norm(raw_description), {}).get("uses", 0) + 1,
    }
    _save_store(store)


def lookup_const_rule(raw_description: str) -> int | None:
    if not _looks_like_construction_text(raw_description):
        # Same guardrail on the read path, in case a bad entry already
        # exists in an older store file that hasn't been cleaned up.
        return None
    store = load_const_rules()
    return store.get(_norm(raw_description), {}).get("code")
