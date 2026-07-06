"""
Auto-extracted module: header_mapping/patterns.py
"""

from __future__ import annotations

import pandas as pd
import re

_RE_STREET_NUM  = re.compile(r"^\d{1,6}\s+\w")


_RE_STREET_WORD = re.compile(r"\b(st|ave|blvd|rd|dr|ln|ct|pl|way|pkwy|hwy|route|loop|cir|ter)\b", re.I)


_RE_ZIP5        = re.compile(r"^\d{5}(-\d{4})?$")


_RE_ZIP_PARTIAL = re.compile(r"\b\d{5}\b")


_RE_YEAR        = re.compile(r"^(1[89]\d{2}|20[0-2]\d)$")


_RE_STATE_CODE  = re.compile(r"^[A-Z]{2}$")


_US_STATES      = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC","PR","VI","GU","AS","MP",
}


_RE_ISO2        = re.compile(r"^[A-Z]{2}$")


_COUNTRY_NAMES  = {"united states","usa","us","canada","united kingdom","germany","france","australia"}


_RE_STORIES     = re.compile(r"^\d{1,3}$")


_RE_CURRENCY    = re.compile(r"^[\$]?[\d,]+(\.\d{0,2})?$")


_RE_LARGE_NUM   = re.compile(r"^\$?[\d,]{6,}(\.\d{0,2})?$")


_RE_COORD       = re.compile(r"^-?\d{1,3}\.\d{4,}$")


_RE_COUNTY      = re.compile(r"county|parish|borough", re.I)


_RE_CITY        = re.compile(r"^[A-Za-z\s\-\.\']{3,40}$")


def _sample_values(df: pd.DataFrame, col: str, n: int = 10) -> list[str]:
    return (
        df[col].dropna().astype(str)
        .str.strip()
        .replace({"nan": None, "None": None, "": None})
        .dropna()
        .head(n)
        .tolist()
    )


_RE_NUMERIC_CELL = re.compile(r"^\$?[\d,]+(\.\d{0,2})?$")


NUMERIC_REQUIRED_FIELDS = {
    "BuildingValue", "OtherValue", "ContentsValue",
    "TimeElementValue", "BIValue", "GrossArea",
    "RiskCount", "NumUnits",
}


def _is_numeric_column(values: list[str], threshold: float = 0.50) -> bool:
    if not values:
        return False
    hits = sum(
        1 for v in values
        if _RE_NUMERIC_CELL.match(v.replace(",", "").replace("$", "").strip())
    )
    return (hits / len(values)) >= threshold


def _value_pattern_score(target_field: str, values: list[str]) -> float:
    if not values:
        return 0.0

    hits = 0
    total = len(values)

    if target_field == "Street":
        hits = sum(1 for v in values if _RE_STREET_NUM.match(v) or _RE_STREET_WORD.search(v))
    elif target_field in ("PostalCode",):
        hits = sum(1 for v in values if _RE_ZIP5.match(v.strip()) or _RE_ZIP_PARTIAL.search(v))
    elif target_field in ("Area", "StateCode"):
        hits = sum(1 for v in values if v.upper() in _US_STATES or (len(v) == 2 and v.isalpha()))
    elif target_field in ("CountryISO", "CountryISOA2"):
        hits = sum(1 for v in values if _RE_ISO2.match(v.upper()) or v.lower() in _COUNTRY_NAMES)
    elif target_field == "SubArea":
        hits = sum(1 for v in values if _RE_COUNTY.search(v))
    elif target_field in ("YearBuilt", "Roof Year Built", "RoofCoverYear"):
        hits = sum(1 for v in values if _RE_YEAR.match(v.strip()))
    elif target_field in ("NumberOfStories", "NumStories"):
        hits = sum(1 for v in values
                   if _RE_STORIES.match(v.strip()) and 1 <= int(v.strip()) <= 120)
    elif target_field in ("BuildingValue", "OtherValue", "ContentsValue",
                           "TimeElementValue", "BIValue"):
        hits = sum(1 for v in values if _RE_LARGE_NUM.match(v.replace(",", "").replace("$", "")))
    elif target_field in ("GrossArea",):
        hits = sum(1 for v in values if _RE_CURRENCY.match(v.replace(",", "")))
    elif target_field in ("Latitude",):
        hits = sum(1 for v in values if _RE_COORD.match(v) and 24 <= abs(float(v)) <= 72)
    elif target_field in ("Longitude",):
        hits = sum(1 for v in values if _RE_COORD.match(v) and 66 <= abs(float(v)) <= 180)
    elif target_field == "City":
        hits = sum(1 for v in values if _RE_CITY.match(v) and not v.strip().isdigit())
    elif target_field in ("RiskCount",):
        hits = sum(1 for v in values
                   if v.strip().isdigit() and 1 <= int(v.strip()) <= 9999)
    elif target_field in ("ConstructionCode", "ClassCode"):
        kws = ("wood","frame","masonry","steel","concrete","brick","metal","fire","non-comb")
        hits = sum(1 for v in values if any(k in v.lower() for k in kws) or v.strip().isdigit())
    elif target_field in ("OccupancyCode", "OccupancyType"):
        kws = ("office","retail","warehouse","hotel","motel","apartment","condo","residential",
               "industrial","manufactur","school","church","hospital","government")
        hits = sum(1 for v in values if any(k in v.lower() for k in kws))
    elif target_field in ("Sprinkler Availability", "SprinklerType"):
        kws = ("yes","no","y","n","wet","dry","full","partial","0","1","100")
        hits = sum(1 for v in values if v.lower().strip() in kws or "%" in v)

    if total == 0:
        return 0.0
    ratio = hits / total
    return min(0.15, ratio * 0.15)

