"""
Auto-extracted module: header_mapping/ai_refine.py
"""

from __future__ import annotations

import pandas as pd
import re
import json
import urllib.request
import urllib.error

from header_mapping.ai_config import _get_azure_cfg_from_secrets
from header_mapping.patterns import _sample_values
from header_mapping.schema import AI_REVIEW_THRESHOLD, TARGET_SCHEMA_AIR, TARGET_SCHEMA_RMS

def _call_azure_openai(messages: list, cfg: dict, max_completion_tokens: int = 3000) -> tuple[str | None, str]:
    endpoint    = cfg.get("endpoint", "")
    deployment  = cfg.get("deployment", "")
    api_version = cfg.get("api_version", "2025-01-01-preview")
    api_key     = cfg.get("api_key", "")

    if not endpoint:
        return None, "ENDPOINT_MISSING: OPENAI_DEPLOYMENT_ENDPOINT not set"
    if not api_key:
        return None, "API_KEY_MISSING: OPENAI_API_KEY not set"
    if not deployment:
        return None, "DEPLOYMENT_MISSING: OPENAI_DEPLOYMENT_NAME not set"

    url = (
        f"{endpoint}/openai/deployments/{deployment}"
        f"/chat/completions?api-version={api_version}"
    )
    payload = json.dumps({
        "model": cfg.get("model", deployment),
        "max_completion_tokens": max_completion_tokens,
        "temperature": 0,
        "messages": messages,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("api-key", api_key)

    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read())
            content = data["choices"][0]["message"]["content"]
            return content, ""
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        return None, f"HTTP_{e.code}: {e.reason} — {body}"
    except urllib.error.URLError as e:
        return None, f"URL_ERROR: {e.reason}"
    except KeyError as e:
        return None, f"RESPONSE_PARSE_ERROR: {e}"
    except Exception as e:
        return None, f"UNEXPECTED_ERROR: {type(e).__name__}: {e}"


def _build_ai_messages(
    raw_headers: list,
    sample_rows: list,
    target_schema: list,
    review_items: list,
    target_system: str,
) -> list:
    col_samples: dict = {}
    for header in raw_headers:
        vals = []
        for row in sample_rows[:5]:
            v = str(row.get(header, "")).strip()
            if v and v.lower() not in ("nan", "none", ""):
                vals.append(v)
        col_samples[header] = vals[:5]

    col_catalogue = [
        {"column": h, "sample_values": col_samples.get(h, [])}
        for h in raw_headers
    ]

    schema_desc = [
        f"  {s['output_col']}"
        for s in target_schema
    ]

    system_content = (
        "You are a senior insurance data engineer specializing in SOV (Statement of Values) "
        "normalization for catastrophe modeling platforms (AIR Verisk, RMS RiskLink).\n\n"
        "Your task: for each target field, determine the BEST source column using BOTH "
        "column names AND actual sample row values. Sample values are PRIMARY evidence.\n\n"
        "FIELD IDENTIFICATION RULES:\n"
        "- Street: house number + street name (e.g. '123 Main St', '45 Oak Ave')\n"
        "- City: human city names only\n"
        "- State/Area: 2-letter US state codes or full state names\n"
        "- PostalCode: 5-digit ZIP or ZIP+4\n"
        "- SubArea: county names (often contain 'County')\n"
        "- BuildingValue/TIV: large currency-like replacement cost values (6+ digits)\n"
        "- ContentsValue: M&E, machinery, equipment, personal property dollar amounts, if something related to personal property is there in any source coloumn then map it to that also along with mse.\n"
        "- OtherValue: avg inventory, outdoor property, stock values\n"
        "- TimeElementValue/BIValue: business interruption or rental income amounts only if not such value then flag them missing dont give basements.\n"
        "- YearBuilt: 4-digit years 1700-present\n"
        "- NumberOfStories: small integers 1-120\n"
        "- GrossArea: area values (sq ft)\n"
        "- ConstructionCode: use the construction DESCRIPTION column (text like wood frame, masonry, steel, concrete, fire resistive) as PRIMARY source. Only fall back to iso const numeric code (1-9) if no description column is mapped or blank.\n"
        "- Occupancy: office, retail, warehouse, apartment etc.\n"
        "- Sprinkler: Yes/No, Y/N, Wet/Dry, Full/Partial, percentages\n\n"
        "DECISION RULES:\n"
        "1. Use sample values as primary evidence\n"
        "2. Never hallucinate non-existent column names\n"
        "3. Return null if field is genuinely absent\n"
        "4. Keep reasoning under 15 words\n"
        "5. Confidence between 0 and 1\n"
        "6. Return ONLY valid JSON, no markdown\n\n"
        "OUTPUT FORMAT:\n"
        "{ \"TargetField\": {\"source\": \"col_name_or_null\", "
        "\"reasoning\": \"brief\", \"confirmed\": true_or_false} }"
    )

    user_content = (
        f"TARGET SYSTEM: {target_system}\n\n"
        f"ALL RAW COLUMNS WITH SAMPLE VALUES:\n{json.dumps(col_catalogue, indent=2)}\n\n"
        f"FIELDS TO VALIDATE (borderline confidence only):\n{json.dumps(review_items, indent=2)}\n\n"
        f"FULL SCHEMA:\n" + "\n".join(schema_desc) + "\n\n"
        "Return JSON. For each field: "
        '{"source": "col_or_null", "reasoning": "max 15 words", "confirmed": bool}\n'
        "confirmed=true means current guess is correct per sample values.\n"
        "confirmed=false means you suggest a DIFFERENT column (or null)."
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user",   "content": user_content},
    ]


def refine_mappings_with_ai(
    raw_headers: list,
    df: pd.DataFrame,
    mappings: list,
    target_system: str = "AIR",
    progress_callback=None,
) -> tuple[list, dict]:
    schema = TARGET_SCHEMA_AIR if target_system.upper() == "AIR" else TARGET_SCHEMA_RMS

    ai_status = {
        "ran": False,
        "error": "",
        "fields_reviewed": 0,
        "fields_confirmed": 0,
        "fields_corrected": 0,
        "raw_response_preview": "",
        "cfg_used": {},
        "threshold_used": AI_REVIEW_THRESHOLD,
    }

    # Feedback-matched columns are already high-confidence — skip AI for them
    review_candidates = [
        m for m in mappings
        if m.confidence < AI_REVIEW_THRESHOLD and not m.feedback_matched
    ]

    if not review_candidates:
        ai_status["error"] = "All columns above confidence threshold — no AI review needed"
        return mappings, ai_status

    sample_rows = []
    for _, row in df.head(15).iterrows():
        row_dict = {
            k: v for k, v in row.items()
            if pd.notna(v) and str(v).strip() not in ("", "nan", "None")
        }
        if row_dict:
            sample_rows.append(row_dict)
        if len(sample_rows) >= 5:
            break

    col_samples = {}
    for header in raw_headers:
        col_samples[header] = _sample_values(df, header, n=5)

    review_items = []
    for m in review_candidates:
        current_guess = m.source_cols[0] if m.source_cols else None
        review_items.append({
            "target_field": m.output_col,
            "current_guess": current_guess,
            "match_type": m.match_type,
            "confidence": m.confidence,
            "sample_values_of_current_guess": col_samples.get(current_guess, []) if current_guess else [],
        })

    if progress_callback:
        progress_callback(
            f"Semantic AI validation — reviewing {len(review_items)} borderline columns "
            f"(confidence < {AI_REVIEW_THRESHOLD}%)..."
        )

    cfg = _get_azure_cfg_from_secrets()
    ai_status["cfg_used"] = {
        "endpoint": cfg.get("endpoint", ""),
        "deployment": cfg.get("deployment", ""),
        "api_version": cfg.get("api_version", ""),
        "has_key": bool(cfg.get("api_key", "")),
    }

    messages = _build_ai_messages(raw_headers, sample_rows, schema, review_items, target_system)
    response_text, error_msg = _call_azure_openai(messages, cfg, max_completion_tokens=3000)

    if not response_text:
        ai_status["error"] = error_msg
        for m in review_candidates:
            m.ai_suggestion = "unavailable"
            m.ai_agreement = False
            if m.source_cols:
                m.final_decision_basis += f" | Semantic validation unavailable: {error_msg[:60]}"
        return mappings, ai_status

    ai_status["ran"] = True
    ai_status["raw_response_preview"] = response_text[:500]

    ai_result: dict = {}
    try:
        clean = re.sub(r"^```(?:json)?\s*\n?", "", response_text.strip(), flags=re.MULTILINE)
        clean = re.sub(r"\n?```\s*$", "", clean, flags=re.MULTILINE).strip()
        ai_result = json.loads(clean)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', response_text, re.DOTALL)
        if m:
            try:
                ai_result = json.loads(m.group())
            except Exception as e:
                ai_status["error"] = f"JSON_PARSE_FAILED: {e}"
                return mappings, ai_status
        else:
            ai_status["error"] = f"NO_JSON_IN_RESPONSE: {response_text[:200]}"
            return mappings, ai_status

    if not isinstance(ai_result, dict):
        ai_status["error"] = f"UNEXPECTED_TYPE: {type(ai_result)}"
        return mappings, ai_status

    locked_cols: set = {
        m.source_cols[0]
        for m in mappings
        if m.match_type in ("reference_exact", "feedback_match") and m.source_cols
        and m.confidence >= AI_REVIEW_THRESHOLD
    }

    mapping_index = {m.output_col: m for m in mappings}
    ai_status["fields_reviewed"] = len(review_candidates)

    for out_col, ai_val in ai_result.items():
        m = mapping_index.get(out_col)
        if not m:
            continue

        if isinstance(ai_val, dict):
            source_col = ai_val.get("source")
            reasoning  = ai_val.get("reasoning", "")
            confirmed  = bool(ai_val.get("confirmed", False))
        elif isinstance(ai_val, str):
            source_col = ai_val if ai_val not in ("null", "NULL", "") else None
            reasoning  = ""
            confirmed  = False
        else:
            continue

        if source_col in (None, "null", "NULL", ""):
            source_col = None

        m.ai_suggestion = source_col if source_col else "null"
        m.ai_reasoning  = reasoning
        current_col = m.source_cols[0] if m.source_cols else None

        if current_col and (confirmed or (source_col and source_col == current_col)):
            m.ai_agreement = True
            ai_status["fields_confirmed"] += 1
            m.confidence = min(100, m.confidence + 8)
            m.match_type = "ai_validated"
            m.final_decision_basis = (
                f"'{current_col}' validated by AI using sample data: {reasoning}"
            )
            m.notes = f"AI validated: {reasoning}"
            continue

        if source_col is None:
            m.ai_agreement = (current_col is None)
            m.ai_suggestion = "null"
            if current_col:
                m.source_cols = []
                m.match_type  = "not_in_source"
                m.confidence  = 0
                m.flag = "missing"
                m.notes = f"AI rejected guess '{current_col}': {reasoning}"
                m.final_decision_basis = (
                    f"Semantic validator checked sample values of '{current_col}' "
                    f"and confirmed this field is absent from source: {reasoning}"
                )
            else:
                m.match_type = "not_in_source"
                m.flag = "missing"
                m.final_decision_basis = (
                    f"Field absent from source — confirmed by AI using sample data: {reasoning}"
                )
                m.notes = f"AI confirmed absent: {reasoning}"
            continue

        if source_col not in raw_headers:
            match_ci = next(
                (h for h in raw_headers if h.lower().strip() == source_col.lower().strip()), None
            )
            if match_ci:
                source_col = match_ci
            else:
                m.ai_suggestion = f"hallucinated:{source_col}"
                continue

        if source_col in locked_cols and source_col != current_col:
            m.final_decision_basis = (
                f"Semantic AI suggested '{source_col}' but it is committed to another field"
            )
            continue

        m.ai_agreement = False
        prior_col = current_col

        if m.match_type in ("not_found", "not_in_source") or not m.source_cols:
            m.match_type = "ai_inferred"
            m.confidence = 82
        else:
            m.match_type = "ai_refined"
            m.confidence = 85

        m.source_cols = [source_col]
        m.flag = ""
        m.notes = f"Semantic AI override: {reasoning}"
        m.final_decision_basis = (
            f"Prior guess '{prior_col or 'none'}' overridden — "
            f"semantic analysis of sample data maps to '{source_col}': {reasoning}"
        )
        ai_status["fields_corrected"] += 1

    return mappings, ai_status

