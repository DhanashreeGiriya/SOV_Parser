"""
Auto-extracted module: row_processing/occupancy.py
"""

from __future__ import annotations
from sov_app.header_mapping.excel_io import _normalise

from fuzzywuzzy import fuzz  # type: ignore
import re
import json

from sov_app.header_mapping.ai_refine import _call_azure_openai
from sov_app.header_mapping.rms_crosswalk import AIR_TO_RMS_OCCUPANCY
from sov_app.row_processing.helpers import _clean_str

_OCCUPANCY_KEYWORDS: list = [
    # Residential
    (re.compile(r"\bsingle.?family\b|\bsfr\b|\bsingle family\b|\bindividual owned\b|\bTownhome\b|\btownhouse\b", re.I), 302, "Single Family Residential"),
    (re.compile(r"\bresidentialcondos\b|\bapartment\b|\bcondos\b|\bmulti.?family\b|\bResidential Condos\b|\bH.O.A\b|\bHoa\b", re.I), 306, "Apartment / Condo"),
    (re.compile(r"\bmobile home\b|\bmanufactured home\b|\bpre.?fab\b", re.I), 305, "Mobile Home"),
    # Generic "Residential" with no further qualifier — AIR 301 (General
    # Residential, the composite/catch-all code per the AIR reference guide).
    # Must come AFTER the single-family/apartment/mobile-home patterns above
    # so those more specific matches still win when present. Without this,
    # a bare "Residential" description fell through keyword matching
    # entirely and got a low-confidence, nonsensical semantic match
    # (e.g. to Church) instead of the obviously-correct residential bucket.
    (re.compile(r"\bresidential\b", re.I), 301, "General Residential"),
    # Hotels / Lodging — AIR 304 (Temporary Lodging), NOT 315
    (re.compile(r"\bhotel\b|\bmotel\b|\bhospitality\b|\binn\b|\blodging\b|\bbed.?and.?breakfast\b", re.I), 304, "Hotel / Motel / Temporary Lodging"),
    # Commercial
    (re.compile(r"\bwarehouse\b|\bwholesale\b|\bdistrib\b|\bCo-packer\b|\b3PL", re.I), 313, "Warehouse / Wholesale"),
    (re.compile(r"\bstorage\b(?!.*tank)", re.I), 313, "Storage / Warehouse"),
    # Office — AIR 315 (Professional/Technical/Business), NOT 314
    (re.compile(r"\boffice\b|\badmin\b|\bheadquarter\b|\bcorporate\b|\bbank\b|\bfinancial\b|\boffice condos\b", re.I), 315, "Office / Professional / Business"),
    (re.compile(r"\bretail\b|\bshop\b|\bstore\b|\bboutique\b|\bshopping\b", re.I), 312, "Retail"),
    (re.compile(r"\brestaurant\b|\bfood service\b|\bcafeteria\b|\bdining\b|\bbar\b|\bpub\b", re.I), 331, "Restaurant"),
    (re.compile(r"\bentertain\b|\bstadium\b|\barena\b|\brecreation\b|\btheater\b|\bcinema\b|\bgym\b|\bfitness\b", re.I), 317, "Entertainment / Recreation"),
    (re.compile(r"\bparking\b|\bdocks\b|\bgarage\b(?!.*[a-z]+ing)", re.I), 318, "Parking"),
    # Health care — AIR 316 (Health Care Services), NOT 403 (IFM Fabricated Metal!)
    (re.compile(r"\bhospital\b|\bmedical\b|\bclinic\b|\bhealthcare\b|\bhealth care\b|\bnursing\b|\bdental\b", re.I), 316, "Health Care Services"),
    # Education — AIR 345 (Universities) or 346 (Primary/Secondary Schools)
    (re.compile(r"\buniversity\b|\bcollege\b|\bacademy\b|\bhigher.?ed\b", re.I), 345, "University / College"),
    (re.compile(r"\bschool\b|\beducat\b|\bday.?care\b|\bnursery\b", re.I), 346, "School / Educational"),
    # Religion — AIR 342 (Church), NOT 404 (IFM Industrial/Commercial Machinery!)
    (re.compile(r"\bchurch\b|\btemple\b|\bmosque\b|\bsynagogue\b|\bworship\b|\breligious\b", re.I), 342, "Church / Religious"),
    (re.compile(r"\bnonprofit\b|\bnon.?profit\b|\bcharity\b|\bngo\b", re.I), 341, "Religion and Nonprofit"),
    # Government — AIR 343 (General Services), NOT 401 (IFM Heavy Fab!)
    (re.compile(r"\bgovernment\b|\bmunicipal\b|\bcity hall\b|\bfederal\b|\bstate agency\b|\bcourthouse\b", re.I), 343, "Government General Services"),
    (re.compile(r"\bpolice\b|\bfire station\b|\bemergency\b|\b911\b", re.I), 344, "Government Emergency Services"),
    # Industrial — keep after commercial/office keywords to avoid false positives
    (re.compile(r"\bheavy.?fabricat\b|\bsteel mill\b|\bshipbuild\b", re.I), 322, "Heavy Fabrication and Assembly"),
    (re.compile(r"\bmanufactur\b|\bassembly\b|\bproduction\b", re.I), 323, "Light Fabrication and Assembly"),
    (re.compile(r"\bfood.?process\b|\bpackaging\b|\bbeverage\b|\bbrewery\b|\bwinery\b", re.I), 324, "Food and Drug Processing"),
    (re.compile(r"\bchemical\b|\bpharmaceut\b|\brefiner\b|\bpetrochem\b", re.I), 325, "Chemical Processing"),
    (re.compile(r"\bplant\b|\bindustrial\b|\bfacility\b|\bmanufact.*plant\b", re.I), 321, "General Industrial"),
    # Agriculture / Construction
    (re.compile(r"\bagricultur\b|\bfarm\b|\bcrops\b|\borchard\b", re.I), 373, "Agriculture"),
    (re.compile(r"\bconstruction.?risk\b|\bunder.?construction\b|\berection.?risk\b", re.I), 381, "Construction / Erection Risk"),
]


_OCC_SEMANTIC_EXAMPLES: list[tuple[str, int]] = [
    # Production / Manufacturing
    ("production plant", 323),
    ("manufacturing plant", 323),
    ("fabrication facility", 322),
    ("assembly plant", 323),
    ("production facility", 323),
    ("manufacturing facility", 323),
    ("plant", 321),
    # Storage / Warehouse / Distribution
    ("warehouse", 313),
    ("storage building", 313),
    ("distribution center", 313),
    ("cold storage", 313),
    ("fulfillment center", 313),
    ("logistics center", 313),
    # Office / Admin
    ("office building", 315),
    ("conference center", 315),
    ("administrative building", 315),
    ("headquarters", 315),
    ("corporate office", 315),
    ("special projects", 315),
    ("leased office", 315),
    # Training / Education
    ("training center", 346),
    ("learning center", 346),
    ("education center", 346),
    ("training facility", 346),
    # Showroom / Retail / Display
    ("show site", 312),
    ("showroom", 312),
    ("display building", 312),
    ("retail store", 312),
    # Research / Lab
    ("research facility", 327),
    ("test facility", 327),
    ("laboratory", 327),
    ("r&d facility", 327),
    ("testing lab", 327),
    # Mixed use (default to dominant use)
    ("shop warehouse office", 313),
    ("shop and office", 315),
    ("office warehouse", 313),
    # Health
    ("clinic", 316),
    ("medical office", 316),
    ("health center", 316),
    # Hospitality
    ("hotel", 304),
    ("motel", 304),
    ("inn", 304),
    # Religion / Nonprofit
    ("church", 342),
    ("worship center", 342),
    # Government
    ("government building", 343),
    ("municipal building", 343),
    # Agriculture
    ("farm", 373),
    ("agricultural facility", 373),
    ("grain elevator", 373),
]


def resolve_occupancy_semantic(description: str, threshold: int = 55) -> tuple:
    if not description:
        return None, "occupancy_semantic_empty", 0

    desc_norm = _normalise(description)
    best_code, best_score, best_phrase = None, 0, ""

    for phrase, code in _OCC_SEMANTIC_EXAMPLES:
        score = max(
            fuzz.token_set_ratio(desc_norm, phrase),
            fuzz.partial_ratio(desc_norm, phrase),
        )
        if score > best_score:
            best_score = score
            best_code  = code
            best_phrase = phrase

    if best_score >= threshold:
        return best_code, f"occupancy_semantic_match:'{best_phrase}'_score:{best_score}", best_score

    return None, f"occupancy_semantic_no_match_best:{best_score}", 0


def looks_like_occupancy_text(text: str) -> bool:
    """
    Best-effort check for whether `text` actually describes a *use type*
    (office, warehouse, retail, hotel, residential, ...) rather than being
    a bare proper-noun building/location name (e.g. "South Building",
    "Busboom building") that happens to sit in the Occupancy column.

    Unlike construction descriptions, legitimate occupancy text can be
    almost anything a business calls its own buildings, so this is
    intentionally a *soft* signal (used to default a "remember this"
    checkbox, not to hard-block saving) rather than the hard guardrail
    used for ConstructionOther. A False result just means "this doesn't
    look like it names a use-type — pause before caching it globally."

    Deliberately keyword-only (no fuzzy/semantic scoring): partial-ratio
    style fuzzy matching against phrases like "office building" gives
    generic proper nouns containing the word "building" a false-positive
    match, which defeats the point of this check.
    """
    if not text or not text.strip():
        return False
    desc = _clean_str(text)
    return any(pattern.search(desc) for pattern, _code, _label in _OCCUPANCY_KEYWORDS)


def resolve_occupancy_with_ai(description: str, cfg: dict) -> tuple:
    if not description or not description.strip():
        return None, "occupancy_ai_skipped_empty", 0

    occ_catalogue = "\n".join(
        f"  {code}: {info['rms_label']}"
        for code, info in sorted(AIR_TO_RMS_OCCUPANCY.items())
        if code < 400
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are an insurance data expert specialising in property risk classification.\n"
                "Map the building description to the single most appropriate AIR Worldwide "
                "occupancy code from the list below.\n\n"
                "AIR Occupancy Codes:\n" + occ_catalogue + "\n\n"
                "Rules:\n"
                "- Return ONLY valid JSON: "
                '{"code": <integer>, "reasoning": "<max 12 words>", '
                '"confidence": <integer 0-100>}\n'
                "- confidence reflects how certain you are (0=guessing, 100=certain).\n"
                "- Never return null — always pick the best fit.\n"
                "- No markdown, no explanation outside the JSON."
            ),
        },
        {
            "role": "user",
            "content": f'Building description: "{description}"',
        },
    ]

    response, error = _call_azure_openai(messages, cfg, max_completion_tokens=100)
    if not response:
        return None, f"occupancy_ai_failed:{error[:50]}", 0

    try:
        clean  = re.sub(r"```json|```", "", response).strip()
        result = json.loads(clean)
        code   = int(result["code"])
        conf   = int(result.get("confidence", 50))
        if code in AIR_TO_RMS_OCCUPANCY:
            reasoning = result.get("reasoning", "")
            return code, f"occupancy_ai:'{reasoning}'", conf
        return None, f"occupancy_ai_invalid_code:{code}", 0
    except Exception as exc:
        return None, f"occupancy_ai_parse_error:{exc}", 0  


_LOB_TO_OCCUPANCY = {
    "residential":  306,   # Apartment / Condo
    "commercial":   315,   # Professional/Technical/Business (Office) — NOT 314 Personal Services
    "industrial":   321,   # General Industrial
    "warehouse":    313,
    "Co-Packer":313,
    "3PL":313,  # Wholesale Trade / Warehouse
    "manufacturing":323,   # Light Fabrication and Assembly
    "retail":       312,   # Retail Trade
    "hospitality":  304,   # Temporary Lodging (Hotels/Motels) — NOT 315
    "office":       315,   # Professional/Technical/Business — NOT 314 Personal Services
    "health":       316,   # Health Care Services
    "medical":      316,   # Health Care Services
    "education":    345,   # Universities / Colleges
    "government":   343,   # Government General Services
    "religious":    342,   # Church
    "restaurant":   331,   # Restaurants
    "food service": 331,   # Restaurants
}


def resolve_occupancy_code(description_raw, lob_raw=""):
    # Pass -1 — pass-through detection: if the raw value IS ALREADY a valid
    # AIR occupancy code, don't re-derive it from text — just use it directly.
    raw_stripped = _clean_str(description_raw).strip()
    if raw_stripped.isdigit():
        code_int = int(raw_stripped)
        if code_int in AIR_TO_RMS_OCCUPANCY:
            return code_int, "occupancy_passthrough_already_coded"
        # numeric but not a recognised AIR code — don't feed it to text matchers either
        return None, f"occupancy_numeric_but_unrecognised:{raw_stripped}"

    # Pass 0 — human-confirmed alias store (always wins)
    try:
        from sov_app.feedback.occupancy_aliases import lookup_occ_rule
        stored = lookup_occ_rule(description_raw)
        if stored is not None:
            return stored, "occupancy_confirmed_alias"
    except ImportError:
        pass

    desc = _clean_str(description_raw)
    if desc:
        for pattern, code, label in _OCCUPANCY_KEYWORDS:
            if pattern.search(desc):
                return code, ""
    lob = _clean_str(lob_raw).lower()
    for lob_key, code in _LOB_TO_OCCUPANCY.items():
        if lob_key in lob:
            return code, "occupancy_from_lob_fallback"
    # No match found — return None so the field is flagged missing,
    # not silently filled with a wrong default (AIR 300 = Residential).
    # The caller (process_row) will write None; the flag will surface in QA.
    return None, "occupancy_not_identified_flagged"


def _save_occupancy_rule(raw_description: str, confirmed_code: int) -> None:
    try:
        from sov_app.feedback.occupancy_aliases import save_occ_rule
        save_occ_rule(raw_description, confirmed_code)
    except Exception:
        pass

