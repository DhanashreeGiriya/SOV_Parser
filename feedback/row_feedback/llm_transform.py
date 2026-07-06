"""
Auto-extracted module: feedback/row_feedback/llm_transform.py
"""

from __future__ import annotations

import re
import json
import urllib.request
import urllib.error

from sov_app.feedback.row_feedback.transform_lambda import _build_preview, _fallback_rule, _sanitise_lambda

_LLM_SYSTEM = """\
You are a data transformation expert for insurance SOV (Schedule of Values) processing.

The user will describe a column transformation in natural language.
You must respond with ONLY a valid JSON object (no markdown, no extra text):

{
  "lambda_src": "<single-line Python lambda: str -> str>",
  "explanation": "<one sentence explaining what the lambda does>",
  "confidence": <0-100 integer>
}

Rules for lambda_src:
- Must be a single Python expression starting with `lambda v:`
- Input v is always a string (never None); output must be a string
- You may import re inline: use re.sub(...), re.search(...) etc.
- Keep it simple and robust — prefer .strip(), .lower(), re.sub over complex logic
- If the intent is ambiguous, err toward a safe no-op
- Do NOT use eval, exec, open, import, or any IO

Examples:
  "strip currency symbols and commas" ->
    {"lambda_src": "lambda v: re.sub(r'[$,]', '', v).strip()", ...}

  "convert to UPPERCASE" ->
    {"lambda_src": "lambda v: v.upper()", ...}

  "remove everything after the word 'units'" ->
    {"lambda_src": "lambda v: re.sub(r'(?i)\\s*units.*$', '', v).strip()", ...}

  "extract first number only" ->
    {"lambda_src": "lambda v: (re.search(r'\\d+\\.?\\d*', v) or type('', (), {'group': lambda s, x: v})()).group(0)", ...}
"""


def call_llm_for_transform(
    prompt: str,
    column_name: str,
    sample_values: list,
    cfg: dict,
) -> dict:
    """
    Ask the LLM to generate a Python lambda that implements `prompt` on `column_name`.

    Parameters
    ----------
    prompt        : natural-language description of the desired transform
    column_name   : output column name (for context)
    sample_values : up to 10 raw string values from that column
    cfg           : Azure OpenAI config dict with keys:
                      endpoint, deployment, api_key, api_version

    Returns
    -------
    dict with keys:
      lambda_src   : str  — Python lambda source
      explanation  : str  — one-sentence description
      confidence   : int  — 0-100
      preview      : list[dict]  — [{before, after, changed}, ...]
      error        : str | None  — set if LLM call failed
    """
    import urllib.request
    import urllib.error

    endpoint    = (cfg.get("endpoint") or "").rstrip("/")
    deployment  = cfg.get("deployment") or ""
    api_key     = cfg.get("api_key") or ""
    api_version = cfg.get("api_version") or "2024-02-01"

    samples_str = "\n".join(f"  {i+1}. {repr(str(v))}" for i, v in enumerate(sample_values[:10]))
    user_msg = (
        f"Column: {column_name}\n"
        f"Sample values:\n{samples_str}\n\n"
        f"Transform instruction: {prompt}"
    )

    # ── Fallback if LLM not configured ────────────────────────────────────────
    if not endpoint or not api_key or not deployment:
        return _fallback_rule(prompt, sample_values,
                              note="LLM not configured — using rule-based fallback")

    url = (f"{endpoint}/openai/deployments/{deployment}"
           f"/chat/completions?api-version={api_version}")

    payload = json.dumps({
        "model": cfg.get("model", deployment),
        "max_tokens": 400,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": _LLM_SYSTEM},
            {"role": "user",   "content": user_msg},
        ],
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("api-key", api_key)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            text = data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        return _fallback_rule(prompt, sample_values, note=f"LLM error: {exc}")

    # ── Robust JSON extraction ─────────────────────────────────────────────
    # The model may wrap its JSON in markdown fences or add prose before/after.
    # Strategy 1: grab the first {...} block in the text.
    # Strategy 2: strip fences and try the whole text.
    parsed = None

    # Strategy 1 — extract first balanced { ... } block
    brace_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if brace_match:
        try:
            parsed = json.loads(brace_match.group(0))
        except Exception:
            parsed = None

    # Strategy 2 — strip markdown fences and parse whole text
    if parsed is None:
        clean = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
        try:
            parsed = json.loads(clean)
        except Exception:
            parsed = None

    if parsed is None:
        return _fallback_rule(prompt, sample_values, note="LLM returned invalid JSON")

    lambda_src  = _sanitise_lambda(parsed.get("lambda_src", "lambda v: v"))
    explanation = parsed.get("explanation", "")
    confidence  = int(parsed.get("confidence", 80))

    # Build preview
    preview = _build_preview(lambda_src, sample_values)

    return {
        "lambda_src":  lambda_src,
        "explanation": explanation,
        "confidence":  confidence,
        "preview":     preview,
        "error":       None,
    }

