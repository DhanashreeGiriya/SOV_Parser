"""
Auto-extracted module: row_processing/construction.py
"""

from __future__ import annotations
from sov_app.header_mapping.excel_io import _normalise

from fuzzywuzzy import fuzz  # type: ignore
import re
import json

from sov_app.header_mapping.ai_refine import _call_azure_openai
from sov_app.header_mapping.rms_crosswalk import AIR_TO_RMS_CONSTRUCTION, ISO_TO_AIR_CONSTRUCTION
from sov_app.row_processing.helpers import _clean_str, _to_int

_CONSTRUCTION_KEYWORDS: list = [
    (re.compile(r"\bwood\b|\bframe\b|\btimber frame\b", re.I), 101),
    (re.compile(r"\bheavy timber\b", re.I), 104),
    (re.compile(r"\bjoisted masonry\b", re.I), 119),
    (re.compile(r"\bmasonry non.?combustible\b|\bmasonry nc\b", re.I), 111),
    (re.compile(r"\bbrick\b|\bblock\b|\bcmu\b|\brock veneer\b", re.I), 111),
    (re.compile(r"\bnon.?combustible\b|\bmetal\b|\bsteel frame\b", re.I), 152),
    (re.compile(r"\bmodified fire resistive\b|\bmod fire\b", re.I), 151),
    (re.compile(r"\bfire resistive\b|\bconcrete\b|\brc\b|\breinforced\b", re.I), 131),
    (re.compile(r"\bsuperior non.?combustible\b", re.I), 154),
    (re.compile(r"\bsuperior masonry\b", re.I), 132),
    (re.compile(r"\btilt.?up\b", re.I), 136),
    (re.compile(r"\bprecast\b", re.I), 137),
    (re.compile(r"\bmobile home\b|\bmanufactured\b|\bpre.?fab\b", re.I), 191),
]


_CONSTRUCTION_VULNERABILITY: list = [
    191, 101, 102, 103, 104, 105, 106, 107, 108,
    111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121,
    131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141,
    151, 152, 153, 154, 155, 156, 157, 158, 160, 100,
]


def _vulnerability_rank(code):
    try:
        return _CONSTRUCTION_VULNERABILITY.index(code)
    except ValueError:
        return len(_CONSTRUCTION_VULNERABILITY)


_CONSTRUCTION_SEMANTIC_EXAMPLES: list[tuple[str, int]] = [
    ("wood frame", 101), ("frame construction", 101), ("timber frame", 101),
    ("heavy timber", 104), ("mill construction", 104),
    ("joisted masonry", 119), ("brick veneer", 119), ("masonry bearing wall", 119),
    ("masonry non combustible", 111), ("reinforced masonry", 111),
    ("steel frame", 152), ("metal building", 152), ("pre engineered metal", 152),
    ("fire resistive", 131), ("concrete frame", 131), ("reinforced concrete", 131),
    ("tilt up concrete", 136), ("precast concrete", 137),
    ("modified fire resistive", 151),
    ("mobile home", 191), ("manufactured housing", 191), ("modular", 191),
]


def resolve_construction_semantic(description: str, threshold: int = 55) -> tuple:
    if not description:
        return None, "construction_semantic_empty", 0
    desc_norm = _normalise(description)
    best_code, best_score, best_phrase = None, 0, ""
    for phrase, code in _CONSTRUCTION_SEMANTIC_EXAMPLES:
        score = max(
            fuzz.token_set_ratio(desc_norm, phrase),
            fuzz.partial_ratio(desc_norm, phrase),
        )
        if score > best_score:
            best_score, best_code, best_phrase = score, code, phrase
    if best_score >= threshold:
        return best_code, f"construction_semantic_match:'{best_phrase}'_score:{best_score}", best_score
    return None, f"construction_semantic_no_match_best:{best_score}", 0


def resolve_construction_with_ai(description: str, cfg: dict) -> tuple:
    if not description or not description.strip():
        return None, "construction_ai_skipped_empty", 0
    catalogue = "\n".join(
        f"  {code}: {info['rms_label']}"
        for code, info in sorted(AIR_TO_RMS_CONSTRUCTION.items())
    )
    messages = [
        {"role": "system", "content": (
            "Map the construction description to the best AIR construction code.\n"
            "AIR Construction Codes:\n" + catalogue + "\n\n"
            'Return ONLY JSON: {"code": <int>, "reasoning": "<max 12 words>", "confidence": <0-100>}\n'
            "Never return null — always pick the closest fit."
        )},
        {"role": "user", "content": f'Construction description: "{description}"'},
    ]
    response, error = _call_azure_openai(messages, cfg, max_completion_tokens=100)
    if not response:
        return None, f"construction_ai_failed:{error[:50]}", 0
    try:
        clean = re.sub(r"```json|```", "", response).strip()
        result = json.loads(clean)
        code = int(result["code"])
        conf = int(result.get("confidence", 50))
        if code in AIR_TO_RMS_CONSTRUCTION:
            return code, f"construction_ai:'{result.get('reasoning','')}'", conf
        return None, f"construction_ai_invalid_code:{code}", 0
    except Exception as exc:
        return None, f"construction_ai_parse_error:{exc}", 0


def resolve_construction_code(iso_code_raw, description_raw, num_stories):
    candidates = []
    flags = []

    # Pass -1 — pass-through: if iso_code_raw is ALREADY a valid AIR
    # construction code, don't run it through the ISO 1-9 lookup at all.
    raw_stripped = _clean_str(iso_code_raw).strip()
    if raw_stripped.isdigit():
        code_int = int(raw_stripped)
        if code_int in AIR_TO_RMS_CONSTRUCTION:
            chosen = code_int
            # still apply the wood/stories downgrade rule below
            if chosen in (101, 102, 103, 105, 106, 107, 108):
                if num_stories is not None and num_stories > 4:
                    flags.append(f"wood_stories_rule: {num_stories} stories => AIR 100")
                    chosen = 100
            return chosen, ("construction_passthrough_already_air_coded"
                             + (" | " + " | ".join(flags) if flags else ""))

    # Pass 0 — ISO 1-9 fire code lookup (only fires for genuinely 1-digit ISO codes)
    iso_int = _to_int(iso_code_raw)
    if iso_int is not None and 1 <= iso_int <= 9:
        air = ISO_TO_AIR_CONSTRUCTION.get(iso_int)
        if air:
            candidates.append(air)

    desc = _clean_str(description_raw)
    if desc:
        matched = []
        for pattern, air_code in _CONSTRUCTION_KEYWORDS:
            if pattern.search(desc):
                matched.append(air_code)
        if matched:
            matched.sort(key=_vulnerability_rank)
            candidates.append(matched[0])

    if not candidates:
        if iso_code_raw or description_raw:
            # A value WAS present but nothing matched — don't guess a code.
            # Return None so process_row's fallback ladder (confirmed rule ->
            # semantic -> AI) gets a real shot at it, and so it stays flagged
            # for human review instead of silently landing on AIR 100.
            return None, "construction_value_present_but_unrecognised_needs_review"
        # Truly nothing supplied anywhere for this row — 100 is a harmless,
        # non-committal default since there's no original entry to preserve.
        return 100, "construction_source_empty_defaulted_100"

    candidates.sort(key=_vulnerability_rank)
    chosen = candidates[0]
    if chosen in (101, 102, 103, 105, 106, 107, 108):
        if num_stories is not None and num_stories > 4:
            flags.append(f"wood_stories_rule: {num_stories} stories => AIR 100")
            chosen = 100
    return chosen, " | ".join(flags)


def _save_construction_rule(raw_description: str, confirmed_code: int) -> None:
    try:
        from sov_app.feedback.construction_aliases import save_const_rule
        save_const_rule(raw_description, confirmed_code)
    except Exception:
        pass

