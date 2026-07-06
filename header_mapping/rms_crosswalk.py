"""
Auto-extracted module: header_mapping/rms_crosswalk.py
"""

from __future__ import annotations

ISO_TO_AIR_CONSTRUCTION: dict[int, int] = {
    1: 101, 2: 119, 3: 152, 4: 111, 5: 151, 6: 131, 7: 104, 8: 154, 9: 132,
}


AIR_TO_RMS_CONSTRUCTION: dict[int, dict] = {
    100: {"rms_code": 1000, "rms_label": "Unknown"},
    101: {"rms_code": 1100, "rms_label": "Wood Frame"},
    102: {"rms_code": 1100, "rms_label": "Wood Frame"},
    103: {"rms_code": 1100, "rms_label": "Wood Frame"},
    104: {"rms_code": 1150, "rms_label": "Heavy Timber"},
    105: {"rms_code": 1100, "rms_label": "Wood Frame"},
    106: {"rms_code": 1100, "rms_label": "Wood Frame"},
    107: {"rms_code": 1100, "rms_label": "Wood Frame"},
    108: {"rms_code": 1100, "rms_label": "Wood Frame"},
    111: {"rms_code": 1300, "rms_label": "Masonry"},
    112: {"rms_code": 1300, "rms_label": "Masonry"},
    113: {"rms_code": 1300, "rms_label": "Masonry"},
    114: {"rms_code": 1300, "rms_label": "Masonry"},
    115: {"rms_code": 1300, "rms_label": "Masonry"},
    116: {"rms_code": 1350, "rms_label": "Masonry Non-Combustible"},
    117: {"rms_code": 1350, "rms_label": "Masonry Non-Combustible"},
    118: {"rms_code": 1350, "rms_label": "Masonry Non-Combustible"},
    119: {"rms_code": 1300, "rms_label": "Masonry"},
    120: {"rms_code": 1350, "rms_label": "Masonry Non-Combustible"},
    121: {"rms_code": 1350, "rms_label": "Masonry Non-Combustible"},
    131: {"rms_code": 1400, "rms_label": "Concrete"},
    132: {"rms_code": 1500, "rms_label": "Superior Masonry NC"},
    133: {"rms_code": 1400, "rms_label": "Concrete"},
    134: {"rms_code": 1400, "rms_label": "Concrete"},
    135: {"rms_code": 1400, "rms_label": "Concrete"},
    136: {"rms_code": 1400, "rms_label": "Concrete"},
    137: {"rms_code": 1400, "rms_label": "Concrete"},
    138: {"rms_code": 1400, "rms_label": "Concrete"},
    139: {"rms_code": 1400, "rms_label": "Concrete"},
    140: {"rms_code": 1400, "rms_label": "Concrete"},
    141: {"rms_code": 1400, "rms_label": "Concrete"},
    151: {"rms_code": 1200, "rms_label": "Steel Frame"},
    152: {"rms_code": 1200, "rms_label": "Steel Frame"},
    153: {"rms_code": 1200, "rms_label": "Steel Frame"},
    154: {"rms_code": 1250, "rms_label": "Superior Non-Combustible"},
    155: {"rms_code": 1200, "rms_label": "Steel Frame"},
    156: {"rms_code": 1200, "rms_label": "Steel Frame"},
    157: {"rms_code": 1200, "rms_label": "Steel Frame"},
    158: {"rms_code": 1250, "rms_label": "Superior Non-Combustible"},
    160: {"rms_code": 1450, "rms_label": "Modified Fire Resistive"},
    191: {"rms_code": 1600, "rms_label": "Mobile Home / Pre-Fabricated"},
}


AIR_TO_RMS_OCCUPANCY: dict[int, dict] = {
    # ── Residential ──────────────────────────────────────────────────────────
    300: {"rms_code": "RES",  "rms_label": "Residential"},           # General Residential
    301: {"rms_code": "RES",  "rms_label": "Residential"},           # General Residential (composite)
    302: {"rms_code": "SFR",  "rms_label": "Single Family Residential"},  # Permanent dwelling single-family
    303: {"rms_code": "MFR",  "rms_label": "Multi Family Residential"},   # Permanent dwelling multi-family
    304: {"rms_code": "HOT",  "rms_label": "Hotel / Temporary Lodging"},  # Temporary lodging (hotels/motels)
    305: {"rms_code": "INST", "rms_label": "Institutional / Group Housing"}, # Group institutional (dorms, nursing)
    306: {"rms_code": "APT",  "rms_label": "Apartment / Condo"},          # Apartments / Condominiums
    307: {"rms_code": "MFR",  "rms_label": "Multi Family Residential"},   # Terraced / Attached housing
    308: {"rms_code": "MFR",  "rms_label": "Multi Family Residential"},
    309: {"rms_code": "MFR",  "rms_label": "Multi Family Residential"},
    310: {"rms_code": "MFR",  "rms_label": "Multi Family Residential"},
    # ── Commercial ───────────────────────────────────────────────────────────
    311: {"rms_code": "COM",  "rms_label": "General Commercial"},
    312: {"rms_code": "RET",  "rms_label": "Retail Trade"},
    313: {"rms_code": "WH",   "rms_label": "Wholesale Trade / Warehouse"},
    314: {"rms_code": "SVC",  "rms_label": "Personal and Repair Services"},
    315: {"rms_code": "OFF",  "rms_label": "Professional / Technical / Business (Office)"},
    316: {"rms_code": "MED",  "rms_label": "Health Care Services"},
    317: {"rms_code": "ENT",  "rms_label": "Entertainment and Recreation"},
    318: {"rms_code": "PKG",  "rms_label": "Parking"},
    319: {"rms_code": "COM",  "rms_label": "Commercial (Golf Courses)"},
    320: {"rms_code": "COM",  "rms_label": "Commercial"},
    # ── Industrial ───────────────────────────────────────────────────────────
    321: {"rms_code": "IND",  "rms_label": "General Industrial"},
    322: {"rms_code": "HVY",  "rms_label": "Heavy Fabrication and Assembly"},
    323: {"rms_code": "LGT",  "rms_label": "Light Fabrication and Assembly"},
    324: {"rms_code": "FDP",  "rms_label": "Food and Drug Processing"},
    325: {"rms_code": "CHM",  "rms_label": "Chemical Processing"},
    326: {"rms_code": "MET",  "rms_label": "Metal and Minerals Processing"},
    327: {"rms_code": "HIT",  "rms_label": "High Technology"},
    328: {"rms_code": "CON",  "rms_label": "Construction"},
    329: {"rms_code": "PET",  "rms_label": "Petroleum"},
    330: {"rms_code": "MIN",  "rms_label": "Mining"},
    # ── Restaurants / Mercantile ─────────────────────────────────────────────
    331: {"rms_code": "REST", "rms_label": "Restaurant"},
    335: {"rms_code": "GAS",  "rms_label": "Gasoline Service Station"},
    336: {"rms_code": "SVC",  "rms_label": "Automotive Repair / Carwash"},
    # ── Religion / Government / Education ────────────────────────────────────
    341: {"rms_code": "REL",  "rms_label": "Religion and Nonprofit"},
    342: {"rms_code": "REL",  "rms_label": "Church"},
    343: {"rms_code": "GOV",  "rms_label": "Government General Services"},
    344: {"rms_code": "GOV",  "rms_label": "Government Emergency Services"},
    345: {"rms_code": "EDU",  "rms_label": "Education – Universities / Colleges"},
    346: {"rms_code": "EDU",  "rms_label": "Education – Primary / Secondary Schools"},
    # ── Transportation ───────────────────────────────────────────────────────
    351: {"rms_code": "TRN",  "rms_label": "Transportation – Highway"},
    352: {"rms_code": "TRN",  "rms_label": "Transportation – Railroad"},
    353: {"rms_code": "TRN",  "rms_label": "Transportation – Air"},
    354: {"rms_code": "TRN",  "rms_label": "Transportation – Sea / Inland Waterway"},
    # ── Utilities ────────────────────────────────────────────────────────────
    361: {"rms_code": "UTL",  "rms_label": "Utilities – Electrical"},
    362: {"rms_code": "UTL",  "rms_label": "Utilities – Water"},
    363: {"rms_code": "UTL",  "rms_label": "Utilities – Sanitary Sewer"},
    364: {"rms_code": "UTL",  "rms_label": "Utilities – Natural Gas"},
    365: {"rms_code": "UTL",  "rms_label": "Utilities – Telephone / Telegraph"},
    # ── Miscellaneous ────────────────────────────────────────────────────────
    371: {"rms_code": "MISC", "rms_label": "Communication"},
    373: {"rms_code": "AGR",  "rms_label": "Agriculture"},
    381: {"rms_code": "CNST", "rms_label": "Construction / Erection Risk"},
    # ── IFM – Industrial Facilities Model (400-series) ───────────────────────
    # These are NOT general occupancy categories — they are the AIR Industrial
    # Facilities Model codes. Map to the closest RMS industrial category.
    400: {"rms_code": "IFM",  "rms_label": "IFM – Unknown Industrial Facility"},
    401: {"rms_code": "IFM",  "rms_label": "IFM – Heavy Fabrication and Assembly"},
    402: {"rms_code": "IFM",  "rms_label": "IFM – Automotive Manufacturing"},
    403: {"rms_code": "IFM",  "rms_label": "IFM – Fabricated Metal Products"},
    404: {"rms_code": "IFM",  "rms_label": "IFM – Industrial and Commercial Machinery"},
    405: {"rms_code": "IFM",  "rms_label": "IFM – Transportation Equipment Assembly"},
    429: {"rms_code": "IFM",  "rms_label": "IFM – Food and Drug Processing"},
    438: {"rms_code": "IFM",  "rms_label": "IFM – Chemical Processing"},
    449: {"rms_code": "IFM",  "rms_label": "IFM – Metal and Minerals Processing"},
    455: {"rms_code": "IFM",  "rms_label": "IFM – High Technology"},
    475: {"rms_code": "IFM",  "rms_label": "IFM – Oil Refinery"},
    476: {"rms_code": "IFM",  "rms_label": "IFM – Hydro-Electric Power"},
    477: {"rms_code": "IFM",  "rms_label": "IFM – Thermo-Electric Power"},
    500: {"rms_code": "MISC", "rms_label": "Miscellaneous"},
}


RMS_COUNTRY_IND: dict[str, dict] = {
    "US": {"4digit": 1000, "2digit": 10, "label": "United States",  "notes": "US counties use 4-digit IND"},
    "CA": {"4digit": 1100, "2digit": 11, "label": "Canada",         "notes": "Province-level 4-digit IND"},
    "DE": {"4digit": 2100, "2digit": 21, "label": "Germany",        "notes": "Bundesland-level 4-digit IND"},
    "GB": {"4digit": 2200, "2digit": 22, "label": "United Kingdom", "notes": "Region-level 4-digit IND"},
    "FR": {"4digit": 2300, "2digit": 23, "label": "France",         "notes": "Departement-level IND"},
    "JP": {"4digit": 3100, "2digit": 31, "label": "Japan",          "notes": "Prefecture-level 4-digit IND"},
    "CN": {"4digit": 3200, "2digit": 32, "label": "China",          "notes": "Province-level 4-digit IND"},
    "AU": {"4digit": 4100, "2digit": 41, "label": "Australia",      "notes": "State-level 4-digit IND"},
    "MY": {"4digit": 3500, "2digit": 35, "label": "Malaysia",       "notes": "State-level 4-digit IND"},
    "SG": {"4digit": 3600, "2digit": 36, "label": "Singapore",      "notes": "Single region"},
    "IN": {"4digit": 3400, "2digit": 34, "label": "India",          "notes": "State-level 4-digit IND"},
    "BR": {"4digit": 5100, "2digit": 51, "label": "Brazil",         "notes": "State-level 4-digit IND"},
    "MX": {"4digit": 5200, "2digit": 52, "label": "Mexico",         "notes": "State-level 4-digit IND"},
    "NZ": {"4digit": 4200, "2digit": 42, "label": "New Zealand",    "notes": "Region-level 4-digit IND"},
    "ZA": {"4digit": 6100, "2digit": 61, "label": "South Africa",   "notes": "Province-level 4-digit IND"},
}


def get_rms_ind(country_iso: str, use_4digit: bool = True):
    entry = RMS_COUNTRY_IND.get(country_iso.upper())
    if not entry:
        return None
    return entry["4digit"] if use_4digit else entry["2digit"]


def convert_air_to_rms_construction(air_code: int) -> dict:
    return AIR_TO_RMS_CONSTRUCTION.get(air_code, {"rms_code": 1000, "rms_label": "Unknown"})


def convert_air_to_rms_occupancy(air_code: int) -> dict:
    return AIR_TO_RMS_OCCUPANCY.get(air_code, {"rms_code": "MISC", "rms_label": "Miscellaneous"})


def convert_iso_to_air_construction(iso_code: int) -> int:
    return ISO_TO_AIR_CONSTRUCTION.get(iso_code, 100)

