"""
Auto-extracted module: row_processing/numeric_fields.py
"""

from __future__ import annotations

import re
from typing import Any

from row_processing.helpers import _clean_str, _to_float

_YEAR_PATTERN = re.compile(r"\b(1[89]\d{2}|20[0-2]\d)\b")


def resolve_year_built(year_values, renovation_values=None):
    """
    Extract year from values.  Rules:
    - "2000s" / "early 2000s" / "late 1990s" -> strip 's' suffix -> 2000 / 1990
    - Multiple years in one cell -> take the FIRST one found left-to-right
    - Multiple source columns -> take the oldest valid year across all columns
    - Returns None when nothing valid is found
    """
    _DECADE_RE = re.compile(r"\b(1[89]\d{2}|20[0-2]\d)s\b", re.I)
    years = []
    for val in year_values:
        raw = _clean_str(val)
        if not raw:
            continue
        # Normalise decade shorthand: "2000s" -> "2000"
        raw = _DECADE_RE.sub(lambda m: m.group(1), raw)
        # Take FIRST year found in the string
        found = _YEAR_PATTERN.findall(raw)
        if found:
            y = int(found[0])   # first occurrence only
            if y > 1800:
                years.append(y)
    if not years:
        return None, "year_built_missing"
    oldest = min(years)
    if oldest <= 1800:
        return None, "year_built_rejected_le_1800"
    return int(oldest), ""


_STORIES_RANGE  = re.compile(r"(\d+(?:\.\d+)?)\s*(?:to|--|and)\s*(\d+(?:\.\d+)?)", re.I)


_STORIES_SINGLE = re.compile(r"(\d+(?:\.\d+)?)")


_STORIES_EXCLUDE = re.compile(r"\bmezzanine\b|\bbasement\b|\b\d+(?:st|nd|rd|th)\s+floor\b", re.I)


def resolve_stories(raw):
    raw_str = _clean_str(raw)
    if not raw_str:
        return None, "stories_missing"
    clean = _STORIES_EXCLUDE.sub("", raw_str).strip()
    if not clean:
        return None, "stories_only_exclusion_terms"
    range_match = _STORIES_RANGE.search(clean)
    if range_match:
        lo, hi = float(range_match.group(1)), float(range_match.group(2))
        chosen = max(lo, hi)
        return int(chosen + 0.5), f"stories_range_resolved_to_{int(chosen+0.5)}"
    # Find ALL integers in the string and take the highest
    all_matches = _STORIES_SINGLE.findall(clean)
    if all_matches:
        vals = [float(v) for v in all_matches]
        highest = max(vals)
        flag = "stories_max_of_multiple" if len(vals) > 1 else ""
        return int(highest + 0.5), flag
    return None, "stories_unresolvable"


_AREA_SQFT_RANGE = (0, 15_000_000)


_UNIT_PATTERNS = {
    "sqm":  re.compile(r"\bsq\.?\s*m(?:etres?|eters?)?\b|\bm[2]\b", re.I),
    "sqyd": re.compile(r"\bsq\.?\s*y(?:ard)?s?\b|\byd[2]\b", re.I),
    "acre": re.compile(r"\bacres?\b", re.I),
}


_SHORTHAND_RE = re.compile(
    r"^\s*\$?(?P<num>[\d,]+(?:\.\d+)?)\s*(?P<sfx>[KkMmBb])?\s*"
    r"(?:sq\.?\s*ft\.?|sqft|sf|square\s+feet|square\s+foot)?\s*$",
    re.I,
)


def _expand_area_shorthand(raw_str: str) -> float | None:
    """
    Convert shorthand area strings to a float number of square feet.
    Examples: "3k" → 3000, "1.5M" → 1_500_000, "2,500 SF" → 2500.
    Returns None if the string cannot be parsed as an area shorthand.
    """
    m = _SHORTHAND_RE.match(raw_str.strip())
    if not m:
        return None
    num_part = m.group("num").replace(",", "")
    try:
        val = float(num_part)
    except ValueError:
        return None
    sfx = (m.group("sfx") or "").upper()
    if sfx == "K":
        val *= 1_000
    elif sfx == "M":
        val *= 1_000_000
    elif sfx == "B":
        val *= 1_000_000_000
    return val


def resolve_gross_area(raw, unit_hint=""):
    raw_str = _clean_str(raw)
    if not raw_str:
        return None, "gross_area_missing"
    unit = "sqft"
    for u, pat in _UNIT_PATTERNS.items():
        if pat.search(raw_str) or pat.search(unit_hint):
            unit = u
            break
    # Try shorthand expansion first (e.g. "3k", "1.5M sf")
    expanded = _expand_area_shorthand(raw_str)
    if expanded is not None:
        val = expanded
    else:
        val = _to_float(raw_str)
    if unit == "sqm":
        val = val * 10.7639
    elif unit == "sqyd":
        val = val * 9.0
    elif unit == "acre":
        val = val * 43560.0
    lo, hi = _AREA_SQFT_RANGE
    if not (lo <= val <= hi):
        return val, f"gross_area_out_of_range:{val:.0f}"
    return val, ""


def resolve_building_value(sources):
    total = max(0.0, sum(s for s in sources))
    flag = "building_value_negative_floored" if any(s < 0 for s in sources) else ""
    return total, flag


def resolve_other_value(raw):
    v = _to_float(raw)
    return (0.0, "other_value_negative_floored") if v < 0 else (v, "")


def resolve_contents_value(raw):
    v = _to_float(raw)
    return (0.0, "contents_value_negative_floored") if v < 0 else (v, "")


def resolve_time_element_value(raw, days_covered=365):
    v = _to_float(raw)
    if v < 0:
        return 0.0, "bi_value_negative_floored"
    if days_covered != 365 and days_covered > 0:
        return v * (365.0 / days_covered), f"bi_annualised_from_{days_covered}d"
    return v, ""


def resolve_sprinkler(raw):
    """
    Returns 0 (not sprinklered / unknown) or 1 (sprinklered).
    Any non-zero numeric value (including decimals like 0.5, 75.0) maps to 1.
    Only explicit "no / 0 / none / n" values map to 0.
    """
    raw_str = _clean_str(raw).lower().strip()
    if not raw_str or raw_str in ("0", "no", "none", "nan", "n", "no sprinklers", "0%", "0.0"):
        return 0, ""
    if raw_str in ("1", "yes", "y", "100", "100%", "full", "fully", "wet", "dry",
                   "wet pipe", "dry pipe", "full coverage"):
        return 1, ""
    if raw_str in ("partial", "partially"):
        return 1, "sprinkler_partial_mapped_to_1"
    # Extract LEADING numeric / percentage (handles "100% Currently being updated...")
    import re as _re
    leading = _re.match(r"^([\d,]+(?:\.\d+)?)\s*%?", raw_str)
    if leading:
        try:
            val = float(leading.group(1).replace(",", ""))
            if val == 0:
                return 0, ""
            return 1, f"sprinkler_nonzero_{val}_mapped_to_1"
        except ValueError:
            pass
    # Fallback: unrecognised text -> 0
    return 0, f"sprinkler_unrecognised_{raw_str}_defaulted_0"

