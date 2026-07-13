"""
Auto-extracted module: header_mapping/matching.py
"""

from __future__ import annotations
from header_mapping.excel_io import _normalise

import pandas as pd
from fuzzywuzzy import fuzz  # type: ignore
import re

from header_mapping.ai_refine import refine_mappings_with_ai
from header_mapping.aliases import ALIAS_MAP
from header_mapping.embeddings import (
    EMBED_COUNTRY_MIN_COS,
    EMBED_MIN_COS,
    EMBED_OWNERSHIP_MARGIN,
    _compute_embedding_confidence,
    get_embedder,
)
from header_mapping.models import ColumnMapping
from header_mapping.patterns import _COUNTRY_NAMES, _RE_CITY, _RE_COORD, _RE_COUNTY, _RE_CURRENCY, _RE_ISO2, _RE_LARGE_NUM, _RE_STORIES, _RE_STREET_NUM, _RE_STREET_WORD, _RE_YEAR, _RE_ZIP5, _RE_ZIP_PARTIAL, _US_STATES, _sample_values, _value_pattern_score
from header_mapping.schema import TARGET_SCHEMA_AIR, TARGET_SCHEMA_RMS

def _compute_alias_confidence(norm_header: str, alias_norm: str, exact: bool) -> int:
    if exact:
        def trigrams(s):
            return set(s[i:i+3] for i in range(max(0, len(s)-2)))
        t1, t2 = trigrams(norm_header), trigrams(alias_norm)
        if not t1 or not t2:
            return 95
        j = len(t1 & t2) / len(t1 | t2)
        return min(100, int(85 + (j - 0.5) * 30))
    else:
        score = fuzz.token_set_ratio(norm_header, alias_norm)
        return min(94, int(70 + (score - 70) * 0.8))


def _compute_fuzzy_confidence(score: int) -> int:
    return min(74, int(50 + (score - 60) * 0.6))


def _best_fuzzy_match(target: str, candidates: list, threshold: int = 60):
    target_norm = _normalise(target)
    best, best_score = "", 0
    for cand in candidates:
        cand_norm = _normalise(cand)
        score = max(
            fuzz.token_set_ratio(target_norm, cand_norm),
            fuzz.partial_ratio(target_norm, cand_norm),
        )
        if score > best_score:
            best_score = score
            best = cand
    return (best, best_score) if best_score >= threshold else ("", 0)


def _value_pattern_best_match(
    target_field: str,
    candidates: list[str],
    df: pd.DataFrame,
    claimed: dict,
    threshold: float = 0.40,
) -> tuple[str, float]:
    best_col, best_score = "", 0.0
    for col in candidates:
        if col in claimed:
            continue
        vals = _sample_values(df, col, n=10)
        if not vals:
            continue
        hits = 0
        total = len(vals)

        if target_field == "Street":
            hits = sum(1 for v in vals if _RE_STREET_NUM.match(v) or _RE_STREET_WORD.search(v))
        elif target_field in ("PostalCode",):
            hits = sum(1 for v in vals if _RE_ZIP5.match(v.strip()) or _RE_ZIP_PARTIAL.search(v))
        elif target_field in ("Area", "StateCode"):
            hits = sum(1 for v in vals if v.upper() in _US_STATES or (len(v) == 2 and v.isalpha()))
        elif target_field in ("CountryISO", "CountryISOA2"):
            hits = sum(1 for v in vals if _RE_ISO2.match(v.upper()) or v.lower() in _COUNTRY_NAMES)
        elif target_field == "SubArea":
            hits = sum(1 for v in vals if _RE_COUNTY.search(v))
        elif target_field in ("YearBuilt", "Roof Year Built", "RoofCoverYear"):
            hits = sum(1 for v in vals if _RE_YEAR.match(v.strip()))
        elif target_field in ("NumberOfStories", "NumStories"):
            hits = sum(1 for v in vals if _RE_STORIES.match(v.strip()) and 1 <= int(v.strip()) <= 120)
        elif target_field in ("BuildingValue", "OtherValue", "ContentsValue",
                               "TimeElementValue", "BIValue"):
            hits = sum(1 for v in vals if _RE_LARGE_NUM.match(v.replace(",", "").replace("$", "")))
        elif target_field in ("GrossArea",):
            hits = sum(1 for v in vals if _RE_CURRENCY.match(v.replace(",", "")))
        elif target_field in ("Latitude",):
            try:
                hits = sum(1 for v in vals if _RE_COORD.match(v) and 24 <= abs(float(v)) <= 72)
            except Exception:
                pass
        elif target_field in ("Longitude",):
            try:
                hits = sum(1 for v in vals if _RE_COORD.match(v) and 66 <= abs(float(v)) <= 180)
            except Exception:
                pass
        elif target_field == "City":
            hits = sum(1 for v in vals if _RE_CITY.match(v) and not v.strip().isdigit())
        elif target_field in ("RiskCount",):
            hits = sum(1 for v in vals if v.strip().isdigit() and 1 <= int(v.strip()) <= 9999)
        elif target_field in ("ConstructionCode", "ClassCode"):
            kws = ("wood","frame","masonry","steel","concrete","brick","metal","fire","non-comb")
            hits = sum(1 for v in vals if any(k in v.lower() for k in kws) or v.strip().isdigit())
        elif target_field in ("OccupancyCode", "OccupancyType"):
            kws = ("office","retail","warehouse","hotel","motel","apartment","condo","residential",
                   "industrial","manufactur","school","church","hospital","government")
            hits = sum(1 for v in vals if any(k in v.lower() for k in kws))
        elif target_field in ("Sprinkler Availability", "SprinklerType"):
            kws = ("yes","no","y","n","wet","dry","full","partial","0","1","100")
            hits = sum(1 for v in vals if v.lower().strip() in kws or "%" in v)
        elif target_field == "LocationID":
            hits = sum(1 for v in vals if v.strip().isdigit() and int(v.strip()) < 100000)
        elif target_field in ("LocationName", "LocName"):
            hits = sum(1 for v in vals if re.match(r"^[A-Za-z\s\-\.\'&,]{3,80}$", v)
                       and not v.strip().isdigit())

        ratio = hits / total if total > 0 else 0.0
        if ratio > best_score:
            best_score = ratio
            best_col = col

    if best_score >= threshold:
        return best_col, best_score
    return "", 0.0


def map_headers(
    raw_headers: list,
    df: pd.DataFrame = None,
    target_system: str = "AIR",
    feedback_aliases: dict = None,   # ← NEW: injected from sov_feedback
) -> list:
    """
    3-pass + feedback header mapping.

    Pass 0 (NEW): Human-feedback store   — exact normalised match against saved overrides
    Pass A:       Reference dictionary   — known insurance industry aliases
    Pass B:       Semantic similarity    — token-level fuzzy match on column names
    Pass C:       AI validation          — called separately via refine_mappings_with_ai()
    """
    schema = TARGET_SCHEMA_AIR if target_system.upper() == "AIR" else TARGET_SCHEMA_RMS
    norm_headers = {h: _normalise(h) for h in raw_headers}
    norm_alias = {_normalise(k): v for k, v in ALIAS_MAP.items()}

    # Normalise the feedback lookup once
    fb = feedback_aliases or {}  # norm_source_col -> {output_col, confidence, reason, uses}

    results: list = []
    claimed: dict = {}

    # ── PRE-PASS: claim ALL feedback matches first across ALL schema fields ──
    # This prevents Pass A from stealing columns that feedback rules need.
    # Two-sweep per stored source col: exact string first, normalised fallback.
    fb_results: dict = {}
    for schema_entry in schema:
        out_col: str = schema_entry["output_col"]
        method: str  = schema_entry["method"]
        default      = schema_entry.get("default")

        fb_entry = next((r for r in fb.values() if r.get("output_col") == out_col), None)
        if fb_entry is None:
            fb_results[out_col] = None
            continue

        stored_srcs = fb_entry.get("source_cols") or (
            [fb_entry["source_col"]] if fb_entry.get("source_col") else []
        )
        fb_match_cols = []
        for stored_src in stored_srcs:
            norm_stored = _normalise(stored_src)
            matched = None

            # Sweep 1 — exact string match (handles "Street Name*" vs "Street Name")
            for raw_h in norm_headers:
                if raw_h not in claimed and raw_h not in fb_match_cols:
                    if raw_h == stored_src:
                        matched = raw_h
                        break

            # Sweep 2 — normalised fallback (only if sweep 1 found nothing)
            if matched is None:
                for raw_h, norm_h in norm_headers.items():
                    if raw_h not in claimed and raw_h not in fb_match_cols:
                        if norm_h == norm_stored:
                            matched = raw_h
                            break

            if matched:
                fb_match_cols.append(matched)

        if fb_match_cols:
            conf   = min(99, fb_entry.get("confidence", 90))
            uses   = fb_entry.get("uses", 1)
            reason = fb_entry.get("reason", "")
            mapping = ColumnMapping(
                output_col=out_col, method=method,
                source_cols=fb_match_cols,
                match_type="feedback_match",
                confidence=conf,
                flag="multi_source" if len(fb_match_cols) > 1 else "",
                notes=f"Feedback match (confirmed {uses}x): {reason}",
                default_value=default,
                alias_suggestion=fb_match_cols[0],
                feedback_matched=True,
                feedback_reason=reason,
                feedback_uses=uses,
                final_decision_basis=(
                    f"Learned from a previous reviewer: "
                    f"{fb_match_cols} → {out_col} "
                    f"(confirmed {uses} time{'s' if uses != 1 else ''}"
                    + (f" · reason: {reason}" if reason else "") + ")"
                ),
            )
            fb_results[out_col] = mapping
            for c in fb_match_cols:
                claimed[c] = out_col   # claim NOW before Pass A starts
        else:
            fb_results[out_col] = None

    # ── MAIN LOOP: use pre-computed feedback result or fall through to A/B ──
    for schema_entry in schema:
        out_col: str = schema_entry["output_col"]
        method: str  = schema_entry["method"]
        default      = schema_entry.get("default")

        # Pass 0: use pre-computed feedback match if available
        if fb_results.get(out_col) is not None:
            results.append(fb_results[out_col])
            continue
        
        # ── Pass A (exact): Reference dictionary exact match ──────────────────
        matched_cols = []
        matched_alias_norms = []
        for raw_h, norm_h in norm_headers.items():
            if raw_h in claimed:
                continue
            for alias_norm, alias_target in norm_alias.items():
                if alias_target == out_col and norm_h == alias_norm:
                    matched_cols.append(raw_h)
                    matched_alias_norms.append(alias_norm)
                    break

        if matched_cols:
            raw_h          = matched_cols[0]
            alias_norm_used = matched_alias_norms[0]
            base_conf = _compute_alias_confidence(norm_headers[raw_h], alias_norm_used, exact=True)
            vp_bonus = 0.0
            if df is not None:
                vals = _sample_values(df, raw_h)
                vp_bonus = _value_pattern_score(out_col, vals)
            final_conf = min(100, int(base_conf + vp_bonus * 100))
            flag = "multi_source" if len(matched_cols) > 1 else ""
            results.append(ColumnMapping(
                output_col=out_col, method=method,
                source_cols=matched_cols,
                match_type="reference_exact",
                confidence=final_conf,
                flag=flag,
                notes="Reference dictionary exact match",
                default_value=default,
                alias_suggestion=raw_h,
                value_pattern_bonus=vp_bonus,
                final_decision_basis=(
                    f"Reference dictionary: '{raw_h}' is a known insurance alias for {out_col}"
                    + (f" · value pattern confirms (+{vp_bonus*100:.0f}%)" if vp_bonus > 0 else "")
                ),
            ))
            for c in matched_cols:
                claimed[c] = out_col
            continue
        # ── Pass A (embedding): Reference dictionary semantic match ──────────
        # Embeddings replace the lexical fuzzy score against the alias phrases.
        # An ownership guard stops an earlier schema field from greedily
        # claiming a header that clearly belongs to a later field. The old
        # fuzzywuzzy path is retained below as a fallback (embeddings off /
        # low similarity). Only this reference-dictionary "fuzzy" pass — the
        # one that can reach the 82 auto-accept threshold and land directly in
        # output without AI review — is affected; Pass B is left unchanged.
        _embedder = get_embedder()
        if _embedder is not None:
            best_raw, best_cos, best_alias = "", 0.0, ""
            for raw_h, norm_h in norm_headers.items():
                if raw_h in claimed:
                    continue
                cos, alias_phrase = _embedder.best_alias(norm_h, out_col)
                if cos < EMBED_MIN_COS:
                    continue
                # Ownership guard: skip headers that clearly belong elsewhere.
                own_t, own_c, _own_p = _embedder.best_target(norm_h)
                if own_t != out_col and (own_c - cos) > EMBED_OWNERSHIP_MARGIN:
                    continue
                if cos > best_cos:
                    best_cos, best_raw, best_alias = cos, raw_h, alias_phrase

            if out_col in ("CountryISO", "CountryISOA2") and best_cos < EMBED_COUNTRY_MIN_COS:
                best_cos, best_raw = 0.0, ""

            if best_raw and best_cos >= EMBED_MIN_COS:
                base_conf = _compute_embedding_confidence(best_cos)
                vp_bonus = 0.0
                if df is not None:
                    vals = _sample_values(df, best_raw)
                    vp_bonus = _value_pattern_score(out_col, vals)
                final_conf = min(100, int(base_conf + vp_bonus * 100))
                results.append(ColumnMapping(
                    output_col=out_col, method=method, source_cols=[best_raw],
                    match_type="embedding_match", confidence=final_conf, flag="",
                    notes=f"Semantic embedding similarity (cosine={best_cos:.3f})",
                    default_value=default,
                    fuzzy_suggestion=best_raw,
                    fuzzy_confidence=int(round(best_cos * 100)),
                    embedding_score=best_cos,
                    value_pattern_bonus=vp_bonus,
                    final_decision_basis=(
                        f"Semantic embedding match: '{best_raw}' means the same as "
                        f"'{best_alias}' (similarity {best_cos:.2f})"
                        + (f" · value pattern confirms (+{vp_bonus*100:.0f}%)" if vp_bonus > 0 else "")
                    ),
                ))
                claimed[best_raw] = out_col
                continue

        # ── Pass A (fuzzy fallback): Reference dictionary fuzzy match ────────
        best_raw, best_score, best_alias = "", 0, ""
        for raw_h, norm_h in norm_headers.items():
            if raw_h in claimed:
                continue
            # Reuse the ownership guard so the fuzzy fallback can't re-introduce
            # the greedy theft that embeddings just prevented.
            if _embedder is not None:
                cos, _ap = _embedder.best_alias(norm_h, out_col)
                own_t, own_c, _own_p = _embedder.best_target(norm_h)
                if own_t != out_col and (own_c - cos) > EMBED_OWNERSHIP_MARGIN:
                    continue
            for alias_norm, alias_target in norm_alias.items():
                if alias_target != out_col:
                    continue
                s = fuzz.token_set_ratio(norm_h, alias_norm)
                if s > best_score:
                    best_score = s
                    best_raw = raw_h
                    best_alias = alias_norm

        if out_col in ("CountryISO", "CountryISOA2") and best_score < 96:
            best_score = 0
            best_raw = ""

        if best_score >= 70:
            base_conf = _compute_alias_confidence(norm_headers[best_raw], best_alias, exact=False)
            vp_bonus = 0.0
            if df is not None:
                vals = _sample_values(df, best_raw)
                vp_bonus = _value_pattern_score(out_col, vals)
            final_conf = min(100, int(base_conf + vp_bonus * 100))
            results.append(ColumnMapping(
                output_col=out_col, method=method, source_cols=[best_raw],
                match_type="semantic_match", confidence=final_conf, flag="",
                notes=f"Semantic name similarity (raw score={best_score}/100)",
                default_value=default,
                fuzzy_suggestion=best_raw,
                fuzzy_confidence=best_score,
                value_pattern_bonus=vp_bonus,
                final_decision_basis=(
                    f"Semantic similarity match: '{best_raw}' resembles '{best_alias}' "
                    f"(score {best_score}/100)"
                    + (f" · value pattern confirms (+{vp_bonus*100:.0f}%)" if vp_bonus > 0 else "")
                ),
            ))
            claimed[best_raw] = out_col
            continue

        # ── Pass B: Direct name similarity ───────────────────────────────────
        unclaimed = [h for h in raw_headers if h not in claimed]
        best_raw2, best_score2 = _best_fuzzy_match(out_col, unclaimed, threshold=60)
        if best_raw2:
            base_conf = _compute_fuzzy_confidence(best_score2)
            vp_bonus = 0.0
            if df is not None:
                vals = _sample_values(df, best_raw2)
                vp_bonus = _value_pattern_score(out_col, vals)
            final_conf = min(100, int(base_conf + vp_bonus * 100))
            results.append(ColumnMapping(
                output_col=out_col, method=method, source_cols=[best_raw2],
                match_type="semantic_match", confidence=final_conf, flag="",
                notes=f"Direct name similarity (score={best_score2}/100)",
                default_value=default,
                fuzzy_suggestion=best_raw2,
                fuzzy_confidence=best_score2,
                value_pattern_bonus=vp_bonus,
                final_decision_basis=(
                    f"Column name similarity: '{best_raw2}' resembles output field '{out_col}' "
                    f"(score {best_score2}/100)"
                    + (f" · value pattern confirms (+{vp_bonus*100:.0f}%)" if vp_bonus > 0 else "")
                ),
            ))
            claimed[best_raw2] = out_col
            continue

        # ── No match ──────────────────────────────────────────────────────────
        results.append(ColumnMapping(
            output_col=out_col, method=method, source_cols=[],
            match_type="not_found", confidence=0, flag="missing",
            notes="No matching source column found",
            default_value=default,
            final_decision_basis="No column name or value pattern match found — field will be null",
        ))

    return results


def flag_unmapped_raw_columns(raw_headers, mappings):
    claimed = {col for m in mappings for col in m.source_cols}
    return [h for h in raw_headers if h not in claimed]

