"""
Auto-extracted module: row_processing/process_row.py
"""

from __future__ import annotations

import re
from typing import Any

from sov_app.header_mapping.ai_config import _get_azure_cfg_from_secrets
from sov_app.header_mapping.rms_crosswalk import AIR_TO_RMS_CONSTRUCTION
from sov_app.row_processing.address import _infer_country_from_address, resolve_country_iso, resolve_postal_code, transform_location_name, transform_street
from sov_app.row_processing.construction import resolve_construction_code, resolve_construction_semantic, resolve_construction_with_ai
from sov_app.row_processing.helpers import _clean_str, _pick_first_nonempty, _to_float, _to_int
from sov_app.row_processing.numeric_fields import resolve_building_value, resolve_gross_area, resolve_sprinkler, resolve_stories, resolve_time_element_value, resolve_year_built
from sov_app.row_processing.occupancy import resolve_occupancy_code, resolve_occupancy_semantic, resolve_occupancy_with_ai
from sov_app.row_processing.rms_output import apply_rms_crosswalk

def process_row(row_idx, row, schema, flag_log, target_system="AIR",
                days_covered=365, default_country="US", lob_col=""):
    out = {}
    rules_applied = {}
    sys_label = target_system.upper()

    def src(col):
        return schema.get_sources(col)

    def raw(col):
        return _pick_first_nonempty(row, src(col))

    def log(output_col, raw_val, rule, cleaned, flag_type, severity="warning"):
        if rule:
            rules_applied[output_col] = rule
        if flag_type:
            flag_log.add(row_idx, output_col, raw_val, rule, cleaned, flag_type, severity)

    out["LocationID"] = _clean_str(raw("LocationID")) or str(row_idx + 1)
    rules_applied["LocationID"] = "direct_or_sequential_id"

    raw_name = raw("LocationName")
    name, name_flag = transform_location_name(raw_name)
    out["LocationName"] = name
    log("LocationName", raw_name, "strip_special_chars", name, name_flag)

    street_sources = src("Street")
    street_val, street_flag = transform_street(row, street_sources)
    out["Street"] = street_val
    log("Street", "", "extract_street_number_name", street_val, street_flag)

    out["City"] = _clean_str(raw("City"))
    rules_applied["City"] = "direct_copy"

    # CountryISO: use mapped col if available, else infer from ZIP/state in address cols
    raw_country = raw("CountryISO")
    if not raw_country:
        # No country column mapped — try to infer from postal code and state columns
        raw_country = _infer_country_from_address(row, default_country)
    country_iso, country_flag = resolve_country_iso(raw_country or default_country, default=default_country)
    out["CountryISO"] = country_iso
    log("CountryISO", raw_country or "(inferred)", "normalise_iso2+address_infer", country_iso, country_flag)

    out["Area"] = _clean_str(raw("Area"))
    rules_applied["Area"] = "direct_copy"
    out["SubArea"] = _clean_str(raw("SubArea"))
    rules_applied["SubArea"] = "direct_copy"

    raw_zip = raw("PostalCode")
    postal, postal_flag = resolve_postal_code(raw_zip, country=country_iso)
    out["PostalCode"] = postal
    log("PostalCode", raw_zip, "zero_pad_5digit", postal, postal_flag)

    out["ContractID"]    = _clean_str(raw("ContractID")) or None
    rules_applied["ContractID"] = "direct_or_null"
    out["Cresta"]        = _clean_str(raw("Cresta")) or None
    rules_applied["Cresta"] = "direct_or_null"

    _lat = raw("Latitude")
    out["Latitude"] = _to_float(_lat) if _lat else None
    rules_applied["Latitude"] = "geocoded_or_source"

    _lon = raw("Longitude")
    out["Longitude"] = _to_float(_lon) if _lon else None
    rules_applied["Longitude"] = "geocoded_or_source"

    out["InceptionDate"]  = _clean_str(raw("InceptionDate")) or None
    rules_applied["InceptionDate"] = "direct_or_null"
    out["ExpirationDate"] = _clean_str(raw("ExpirationDate")) or None
    rules_applied["ExpirationDate"] = "direct_or_null"
    out["LocPerils"]      = _clean_str(raw("LocPerils")) or None
    rules_applied["LocPerils"] = "direct_or_null"
    out["SublimitArea"]   = _clean_str(raw("SublimitArea")) or None
    rules_applied["SublimitArea"] = "direct_or_null"

    out["Currency"] = _clean_str(raw("Currency")) or "USD"
    rules_applied["Currency"] = "source_or_hardcode_USD"

    _dc_raw = raw("DaysCovered")
    if _dc_raw:
        out["DaysCovered"] = _to_int(_dc_raw, default=days_covered)
        rules_applied["DaysCovered"] = "source_value"
    else:
        out["DaysCovered"] = days_covered if days_covered != 365 else None
        rules_applied["DaysCovered"] = "default_365"

    raw_rc = raw("RiskCount")
    if raw_rc and str(raw_rc).strip() not in ("", "nan", "None"):
        rc = _to_int(raw_rc)
        out["RiskCount"] = rc if rc and rc > 0 else None
    else:
        # Source column is empty — do NOT default to 1; leave null so it is
        # visible in QA. The reference rules say "number of buildings at the
        # location"; 1 is not always correct and masks missing data.
        out["RiskCount"] = None
    rules_applied["RiskCount"] = "to_int_or_null_no_default"

    out["NumUnits"] = _to_int(raw("NumUnits"))
    rules_applied["NumUnits"] = "to_int_or_null"

    raw_stor = raw("NumberOfStories")
    stories, stor_flag = resolve_stories(raw_stor)
    out["NumberOfStories"] = stories
    log("NumberOfStories", raw_stor, "resolve_stories", stories, stor_flag)

    year_src_cols = src("YearBuilt")
    year_vals = [_clean_str(row.get(c, "")) for c in year_src_cols]
    year, year_flag = resolve_year_built(year_vals)
    out["YearBuilt"] = year
    log("YearBuilt", str(year_vals), "oldest_valid_year", year, year_flag)

    iso_raw  = _pick_first_nonempty(row, src("ConstructionCode"))
    # ConstructionOther: prefer explicitly mapped ConstructionOther col,
    # then fall back to any column whose name contains "construct" (description),
    # then fall back to iso numeric code as last resort.
    # Guard against ConstructionOther having been mapped to a generic
    # free-text notes/remarks column (e.g. "NOTE"), which has previously
    # caused unrelated underwriting comments to be treated as construction
    # descriptions and poison the confirmed-rule cache. Any source column
    # whose *name* looks like a notes field is excluded here regardless of
    # what the header-mapping feedback store says.
    _NOTES_COL_PATTERN = re.compile(r"\b(note|notes|remark|remarks|comment|comments)\b", re.I)
    _co_src_cols = [c for c in src("ConstructionOther") if not _NOTES_COL_PATTERN.search(str(c))]
    other_raw = _pick_first_nonempty(row, _co_src_cols)
    desc_raw  = _pick_first_nonempty(row, [c for c in row.index if "construct" in c.lower() and c not in src("ConstructionOther")])
    # For resolve: description is primary signal (keywords), iso is numeric fallback
    desc_for_resolve = other_raw or desc_raw or ""
    air_const, const_flag = resolve_construction_code(iso_raw, desc_for_resolve, stories)

    _CONSTR_SEMANTIC_REVIEW_THRESHOLD = 90
    _CONSTR_AI_REVIEW_THRESHOLD       = 85
    constr_needs_review = False
    constr_method        = "keyword"
    constr_confidence    = 100
    constr_source_text   = desc_for_resolve or _clean_str(iso_raw)

    # Keyword/ISO pass didn't recognise the value (or found nothing at all) —
    # fall through to confirmed rule -> semantic -> AI, same ladder as occupancy.
    # Triggers on air_const is None (value present but unrecognised) as well
    # as the legacy "defaulted_100" flag from a fully-empty row, so long as
    # there's actual source text for the ladder to work with.
    if (air_const is None or "defaulted_100" in const_flag) and constr_source_text:
        stored_code = None
        try:
            from sov_app.feedback.construction_aliases import lookup_const_rule
            stored_code = lookup_const_rule(constr_source_text)
        except Exception:
            stored_code = None

        if stored_code is not None and stored_code in AIR_TO_RMS_CONSTRUCTION:
            air_const      = stored_code
            const_flag     = "construction_confirmed_rule_reuse"
            constr_method  = "confirmed_rule"
            constr_confidence = 100
        else:
            sem_code, sem_flag, sem_conf = resolve_construction_semantic(constr_source_text)
            if sem_code is not None:
                air_const, const_flag = sem_code, sem_flag
                constr_method, constr_confidence = "semantic", sem_conf
                if sem_conf <= _CONSTR_SEMANTIC_REVIEW_THRESHOLD:
                    constr_needs_review = True
            else:
                try:
                    _constr_cfg = _get_azure_cfg_from_secrets()
                    ai_code, ai_flag, ai_conf = resolve_construction_with_ai(constr_source_text, _constr_cfg)
                    if ai_code is not None:
                        air_const, const_flag = ai_code, ai_flag
                        constr_method, constr_confidence = "ai", ai_conf
                        if ai_conf <= _CONSTR_AI_REVIEW_THRESHOLD:
                            constr_needs_review = True
                except Exception as _constr_exc:
                    const_flag = f"construction_ai_error:{str(_constr_exc)[:40]}"
                    constr_needs_review = True

        # Ladder exhausted and still nothing — do NOT silently default to
        # 100. Leave the code blank, keep the original raw text (already
        # captured in constr_source_text / _constr_raw_description below),
        # and force it into review so it surfaces in the UI.
        if air_const is None:
            constr_method     = "unresolved"
            constr_confidence = 0
            constr_needs_review = True
            if "construction_ai_error" not in const_flag:
                const_flag = "construction_all_passes_failed_needs_review"

        # Re-apply the wood/stories downgrade rule since semantic/AI bypassed it
        if air_const in (101, 102, 103, 105, 106, 107, 108) and stories is not None and stories > 4:
            air_const = 100
            const_flag += " | wood_stories_rule_reapplied"

    out["ConstructionCode"]           = air_const
    out["_constr_needs_review"]       = constr_needs_review
    out["_constr_method"]             = constr_method
    out["_constr_confidence"]         = constr_confidence
    out["_constr_raw_description"]    = constr_source_text
    # ConstructionCodeType — always hardcoded, not mapped from source
    out["ConstructionCodeType"] = "AIR"
    rules_applied["ConstructionCodeType"] = "hardcoded_AIR"
    # ConstructionOther: prefer other_raw → then fall back to the
    # numeric AIR construction code (NOT the free-text description).
    # This avoids echoing verbose description text into ConstructionOther.
    # If air_const is None (unresolved — not silently defaulted), fall back
    # to the original raw source text instead of writing the string "None",
    # so the original entry is never lost even when we can't map it.
    if other_raw:
        out["ConstructionOther"] = other_raw
    elif air_const is not None:
        out["ConstructionOther"] = str(air_const)
    else:
        out["ConstructionOther"] = constr_source_text or ""
    rules_applied["ConstructionOther"] = "other_col_or_air_code"
    log("ConstructionCode", f"iso={iso_raw} other={other_raw} desc={desc_raw}", constr_method, air_const, const_flag)

    # Confidence thresholds
    _OCC_SEMANTIC_REVIEW_THRESHOLD = 90   # was 75 — too permissive, missed real errors
    _OCC_AI_REVIEW_THRESHOLD       = 85   # was 70

    occ_raw = _pick_first_nonempty(row, src("OccupancyCode"))
    lob_raw = _clean_str(row.get(lob_col, "")) if lob_col else ""
    occ_needs_review  = False
    occ_method        = "keyword"
    occ_confidence    = 100

    # Pass 1 — keyword rules (always trusted)
    air_occ, occ_flag = resolve_occupancy_code(occ_raw, lob_raw)

    # Only fall through to semantic/AI if the raw value is genuinely text,
    # not a number that simply failed to resolve via pass-through.
    _is_purely_numeric = occ_raw.strip().isdigit() if occ_raw else False

    # Pass 2 — semantic fuzzy
    if air_occ is None and occ_raw and occ_raw.strip() and not _is_purely_numeric:
        air_occ, occ_flag, occ_confidence = resolve_occupancy_semantic(occ_raw)
        occ_method = "semantic"
        if air_occ is not None and occ_confidence <= _OCC_SEMANTIC_REVIEW_THRESHOLD:
                occ_needs_review = True

    # Pass 3 — AI
    if air_occ is None and occ_raw and occ_raw.strip() and not _is_purely_numeric:
        try:
            _occ_cfg = _get_azure_cfg_from_secrets()
            air_occ, occ_flag, occ_confidence = resolve_occupancy_with_ai(occ_raw, _occ_cfg)
            occ_method = "ai"
            if air_occ is not None and occ_confidence <= _OCC_AI_REVIEW_THRESHOLD:
                 occ_needs_review = True
        except Exception as _occ_exc:
            occ_flag = f"occupancy_ai_error:{str(_occ_exc)[:40]}"
            occ_needs_review = True

    # Final default
    if air_occ is None:
        if not occ_raw and not lob_raw:
            air_occ = 300
            occ_flag = "occupancy_no_source_defaulted_300"
        else:
            # All passes failed but value was present — flag explicitly
            occ_needs_review = True
            occ_flag = "occupancy_all_passes_failed_needs_review"

    # Tag the row so the UI can surface it
    out["OccupancyCode"]           = air_occ
    out["_occ_needs_review"]       = occ_needs_review
    out["_occ_method"]             = occ_method
    out["_occ_confidence"]         = occ_confidence
    out["_occ_raw_description"]    = occ_raw
    out["OccupancyCodeType"]       = "AIR"
    rules_applied["OccupancyCodeType"] = "hardcoded_AIR"
    log(
        "OccupancyCode", occ_raw,
        f"keyword+semantic+ai_lookup method={occ_method} conf={occ_confidence}",
        air_occ,
        occ_flag,
        severity="warning" if occ_needs_review else "info",
    )

    bv_sources = src("BuildingValue")
    # Sum ALL mapped BuildingValue columns (handles multi-column TIV splits)
    bv_vals = []
    for c in bv_sources:
        if c in row.index:
            v = row[c]
            # Skip NaN / blank cells so they don't zero out real values
            if v is not None and str(v).strip() not in ("", "nan", "None"):
                bv_vals.append(_to_float(v))
    bv, bv_flag = resolve_building_value(bv_vals if bv_vals else [0.0])
    out["BuildingValue"] = bv
    log("BuildingValue", str(bv_vals), "sum+floor_negative", bv, bv_flag)

    ov_sources = src("OtherValue")
    ov_vals = []
    for c in ov_sources:
        if c in row.index:
            v = row[c]
            if v is not None and str(v).strip() not in ("", "nan", "None"):
                ov_vals.append(_to_float(v))
    ov_total = max(0.0, sum(ov_vals)) if ov_vals else 0.0
    ov_flag = "other_value_negative_floored" if any(x < 0 for x in ov_vals) else ""
    out["OtherValue"] = ov_total
    rules_applied["OtherValue"] = "sum+floor_negative"

    cv_sources = src("ContentsValue")
    cv_vals = []
    for c in cv_sources:
        if c in row.index:
            v = row[c]
            if v is not None and str(v).strip() not in ("", "nan", "None"):
                cv_vals.append(_to_float(v))
    cv_total = max(0.0, sum(cv_vals)) if cv_vals else 0.0
    cv_flag = "contents_value_negative_floored" if any(x < 0 for x in cv_vals) else ""
    out["ContentsValue"] = cv_total
    rules_applied["ContentsValue"] = "sum+floor_negative"

    te, te_flag = resolve_time_element_value(raw("TimeElementValue"), days_covered=days_covered)
    out["TimeElementValue"] = te
    rules_applied["TimeElementValue"] = "floor_negative+annualise"

    raw_area = raw("GrossArea")
    area_val, area_flag = resolve_gross_area(raw_area)
    out["GrossArea"] = area_val
    log("GrossArea", raw_area, "convert+validate", area_val, area_flag)

    raw_roof = raw("Roof Year Built")
    roof_year, roof_flag = resolve_year_built([raw_roof])
    out["Roof Year Built"] = roof_year
    rules_applied["Roof Year Built"] = "oldest_valid_year"

    raw_spr = raw("Sprinkler Availability")
    spr, spr_flag = resolve_sprinkler(raw_spr)
    out["Sprinkler Availability"] = spr
    rules_applied["Sprinkler Availability"] = "yes_no_partial_resolve"

    if sys_label == "RMS":
        out["RiskID"]   = _clean_str(raw("RiskID")) or None
        rules_applied["RiskID"] = "direct_or_null"
        out["AccGrpID"] = _clean_str(raw("AccGrpID")) or None
        rules_applied["AccGrpID"] = "direct_or_null"
        out["CRESTA"]   = _clean_str(raw("CRESTA")) or None
        rules_applied["CRESTA"] = "direct_or_null"
        out["PerilsCovered"] = _clean_str(raw("PerilsCovered")) or None
        rules_applied["PerilsCovered"] = "direct_or_null"
        _bp_raw = raw("BIPeriod")
        out["BIPeriod"] = _to_int(_bp_raw, default=12) if _bp_raw else 12
        rules_applied["BIPeriod"] = "source_or_default_12"
        out["ClassCodeScheme"] = _clean_str(raw("ClassCodeScheme")) or "RMS"
        rules_applied["ClassCodeScheme"] = "source_or_hardcode_RMS"
        out["OccupancyScheme"] = _clean_str(raw("OccupancyScheme")) or "RMS"
        rules_applied["OccupancyScheme"] = "source_or_hardcode_RMS"

        out["CountryISOA2"] = out.pop("CountryISO", default_country)
        rules_applied["CountryISOA2"] = rules_applied.pop("CountryISO", "normalise_iso2")
        out = apply_rms_crosswalk(out)

    return out, rules_applied

