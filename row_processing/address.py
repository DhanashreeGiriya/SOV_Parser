"""
Auto-extracted module: row_processing/address.py
"""

from __future__ import annotations

import re

from row_processing.helpers import _clean_str, _clean_str_local

_STREET_TYPE_RE = re.compile(
    r"\b(st|ave|blvd|rd|dr|ln|ct|pl|way|pkwy|hwy|route|loop|cir|ter|"
    r"street|avenue|boulevard|road|drive|lane|court|place|highway|"
    r"pike|run|row|pass|path|walk|xing|crossing|trce|trace)\b",
    re.I,
)


_STOP_WORDS_RE = re.compile(
    r"\b(suite|ste|unit|apt|floor|fl|bldg|building|garage|lobby|dock|loading|parking|"
    r"po box|p\.o\.|city|state|zip|county|"
    r"[A-Z]{2}\s*\d{5})\b",
    re.I,
)


_MULTI_ADDR_AMP = re.compile(r"\s+&\s+(?=\d)", re.I)


def transform_street(row, sources):
    """
    Extract ONE clean street address: house/unit number + street name only.
    Output contains ONLY letters, digits and spaces (no hyphens, punctuation).

    Rules applied (in order):
    1.  Prefer a 'combined / full / address' source column when available.
    2a. Split on hard separators: newline, semicolon, |, /
    2b. Split on literal "(and)" between two addresses.
    2c. Split on " & NNN" (ampersand + digit = second address)
    3.  Comma split with multi-range detection.
    4.  Address range "400-440 Main St" -> "400 Main St"
    5.  Dual house number "1200 & 1206 E 52nd St" -> "1200 E 52nd St"
    6.  Remove unit/floor/suite/stories suffixes AND their values
        e.g. "123 Main St Units A&B Story 2" -> "123 Main St"
    7.  Strip everything except letters, digits, spaces; collapse whitespace.

    Returns (cleaned_street: str, flag: str)
    """
    # ── 1. Collect raw value ────────────────────────────────────────────────
    combined_kws = ("combined", "full", "address")
    raw = ""
    for col in sources:
        if any(k in col.lower() for k in combined_kws):
            v = _clean_str_local(row.get(col, ""))
            if v:
                raw = v
                break
    if not raw:
        parts = [_clean_str_local(row.get(col, "")) for col in sources]
        raw = " ".join(p for p in parts if p).strip()

    if not raw:
        return "", "missing_street"

    # ── 2a. Hard line-level separators ─────────────────────────────────────
    for sep in ("\n", "\r", ";", " | ", " / "):
        if sep in raw:
            raw = raw.split(sep)[0].strip()
            break

    # ── 2b. "(and)" word-separator ─────────────────────────────────────────
    paren_and_parts = re.split(r"\s*\(and\)\s*", raw, flags=re.I)
    if len(paren_and_parts) > 1:
        raw = paren_and_parts[0].strip()

    # ── 2c. " & NNN" multi-address splitter ────────────────────────────────
    amp_parts = _MULTI_ADDR_AMP.split(raw)
    if len(amp_parts) > 1 and re.search(r"[A-Za-z]", amp_parts[0]):
        raw = amp_parts[0].strip()

    # ── 2d. Non-English street prefix (e.g. Malay "No. 107, Jalan Permata 1") ──
    # Rewrites to "107 Jalan Permata 1" BEFORE comma-split so the street name is kept.
    _INTL_STREET_RE = re.compile(
        r"^No\.?\s*(\d[\w-]*)\s*,\s*"
        r"(Jalan|Jln|Lorong|Persiaran|Lebuh|Lebuhraya|Jl\.|Gang|Kampung|Blok|Block)\b",
        re.I,
    )
    _intl_m = _INTL_STREET_RE.match(raw)
    if _intl_m:
        _house  = _intl_m.group(1)
        _prefix = _intl_m.group(2)
        _rest   = raw[_intl_m.end():].strip()
        raw = f"{_house} {_prefix} {_rest}".strip()

    # ── 3. Comma split ──────────────────────────────────────────────────────
    if "," in raw:
        segments = [s.strip() for s in raw.split(",") if s.strip()]
        if (
            len(segments) >= 2
            and re.match(r"^\d+\s*(?:-|–|—|to)\s*\d+$", segments[0], flags=re.I)
            and re.match(r"^\d+\s+[A-Za-z]", segments[-1])
        ):
            first_num = re.match(r"^(\d+)", segments[0]).group(1)
            street_name = re.sub(r"^\d+\s+", "", segments[-1]).strip()
            raw = f"{first_num} {street_name}"
        else:
            chosen = segments[0]
            for seg in segments:
                if (re.match(r"^\d", seg) and re.search(r"[A-Za-z]", seg)) or _STREET_TYPE_RE.search(seg):
                    chosen = seg
                    break
            raw = chosen

    # ── 4. Address range "400-440 Main St" -> "400 Main St" ────────────────
    range_match = re.match(r"^(\d+)\s*(?:-|–|—|to)\s*\d+\s+(.+)$", raw.strip(), flags=re.I)
    if range_match:
        raw = f"{range_match.group(1)} {range_match.group(2).strip()}"

    # ── 5. Dual house number "1200 & 1206 E 52nd St" -> "1200 E 52nd St" ──
    amp_match = re.match(r"^(\d+)\s*&\s*\d+\s+(.+)$", raw.strip(), flags=re.I)
    if amp_match:
        raw = f"{amp_match.group(1)} {amp_match.group(2).strip()}"

    # ── 6. Remove unit/floor/suite/stories suffix AND its value(s) ─────────
    # Patterns like: "Units A&B", "Unit 5", "Suite 200", "Story 2", "Fl 3",
    #                "Apt 4B", "Bldg C", "#201", "No. 5", "- 2nd Floor"
    _SUFFIX_RE = re.compile(
        r"(?:^|\s|,|-)+"
        r"(?:"
        r"units?\s*[\w&,\s]+"
        r"|ste\.?\s*[\w-]+"
        r"|suite\s*[\w-]+"
        r"|apt\.?\s*[\w-]+"
        r"|apartment\s*[\w-]+"
        r"|floors?\s*[\w-]+"
        r"|fl\.?\s*[\w-]+"
        r"|stories?\s*[\w-]+"
        r"|stor(?:e|ey|eys|ies)?\s*[\w-]+"
        r"|bldg\.?\s*[\w-]+"
        r"|building\s*[\w-]+"
        r"|#\s*[\w-]+"
        r"|(?<=[\s,\-])no\.?\s+\d[\w-]*"
        r"|garage\s*[\w-]*"
        r"|dock\s*[\w-]*"
        r"|parking\s*[\w-]*"
        r"|lobby\s*[\w-]*"
        r")"
        r"(?=\s*(?:,|$|\(|\[))",
        re.I,
    )
    raw = _SUFFIX_RE.sub(" ", raw).strip()
    # Also strip trailing punctuation/noise left after suffix removal
    raw = re.sub(r"[,\-\s]+$", "", raw).strip()

    # ── 7. Keep ONLY letters, digits, spaces ────────────────────────────────
    cleaned = re.sub(r"[^A-Za-z0-9 ]", " ", raw)
    cleaned = re.sub(r" {2,}", " ", cleaned).strip()

    if not cleaned:
        return "", "street_cleaned_to_empty"
    return cleaned, ""


def transform_location_name(raw: str):
    if not raw:
        return "", "missing_location_name"
    # Remove parenthetical/bracket content, then keep only letters, digits and spaces
    cleaned = re.sub(r"\([^)]*\)", "", raw)
    cleaned = re.sub(r"\[[^\]]*\]", "", cleaned)
    cleaned = re.sub(r"[^A-Za-z0-9 ]", " ", cleaned)   # only alphanumeric + space
    cleaned = re.sub(r" {2,}", " ", cleaned).strip()
    if not cleaned:
        return "", "missing_location_name"
    return cleaned, ""


def resolve_postal_code(raw, country="US"):
    raw_str = _clean_str(raw)
    if not raw_str:
        return "", "postal_code_missing"
    if country.upper() == "US":
        digits = re.sub(r"\D", "", raw_str)[:5]
        if digits:
            return digits.zfill(5), ""
    return raw_str, ""


def resolve_country_iso(raw, default="US"):
    raw_str = _clean_str(raw).upper().strip()
    if not raw_str:
        return default, ""
    if len(raw_str) == 2 and raw_str.isalpha():
        return raw_str, ""
    iso3_map = {
        "USA": "US", "GBR": "GB", "DEU": "DE", "FRA": "FR", "JPN": "JP",
        "CHN": "CN", "AUS": "AU", "CAN": "CA", "IND": "IN", "BRA": "BR",
    }
    if raw_str in iso3_map:
        return iso3_map[raw_str], ""
    country_name_map = {
        "UNITED STATES": "US", "UNITED STATES OF AMERICA": "US", "U.S.A.": "US",
        "CANADA": "CA", "UNITED KINGDOM": "GB", "UK": "GB", "GERMANY": "DE",
        "FRANCE": "FR", "AUSTRALIA": "AU", "JAPAN": "JP", "INDIA": "IN",
        "BRAZIL": "BR", "MEXICO": "MX",
    }
    mapped = country_name_map.get(raw_str)
    if mapped:
        return mapped, ""
    return raw_str, f"country_unrecognised:{raw_str}"


def _infer_country_from_address(row, default="US") -> str:
    """
    Scan address-related columns for US ZIP codes or state codes.
    Returns "US" if found, otherwise returns default.
    """
    _ZIP_RE   = re.compile(r"\b\d{5}(?:-\d{4})?\b")
    _STATE_RE = re.compile(r"\b(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b")
    addr_kws  = ("address","street","city","state","zip","postal","location","addr")
    for col in row.index:
        col_lower = str(col).lower()
        if not any(k in col_lower for k in addr_kws):
            continue
        val = str(row.get(col, "") or "").strip()
        if not val or val.lower() in ("nan","none",""):
            continue
        if _ZIP_RE.search(val):
            return "US"
        if _STATE_RE.search(val.upper()):
            return "US"
    return default

