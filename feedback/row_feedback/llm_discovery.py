"""
Auto-extracted module: feedback/row_feedback/llm_discovery.py
"""

from __future__ import annotations

import re
import json
import urllib.request

from feedback.row_feedback.transform_lambda import _build_preview, _safe_apply

_DISCOVERY_SYSTEM = """\
You are a data transformation expert for insurance SOV (Schedule of Values) processing.

The user will provide a set of source→target transformation examples for a specific column.
Your task is to analyse the patterns and produce a list of GENERIC Python lambda rules
that would reproduce these transformations and handle similar future values.

Respond ONLY with a valid JSON object (no markdown, no extra text):

{
  "rules": [
    {
      "prompt": "<short plain-English description of what this rule does>",
      "lambda_src": "<single-line Python lambda: str -> str>",
      "explanation": "<one sentence explaining the pattern detected>",
      "confidence": <0-100>,
      "covers_examples": [<0-based indices of examples this rule covers>]
    }
  ],
  "summary": "<one paragraph describing the overall transformation pattern>"
}

Rules for lambda_src:
- Must be a single Python expression starting with `lambda v:`
- Input v is always a string; output must be a string
- You may use re inline: re.sub(...), re.search(...) etc.
- Prefer .strip(), .lower(), re.sub over complex logic
- Rules should be GENERIC — handle the pattern, not just hardcoded values
- Do NOT use eval, exec, open, import, or any IO
- Each rule should be independent (not dependent on another rule's output)
- Produce 1–5 rules ordered from most impactful to least

Examples of good generic rules:
  Strip currency symbols:  lambda v: re.sub(r'[$€£,]', '', v).strip()
  Title-case names:        lambda v: v.title()
  Remove trailing spaces:  lambda v: v.strip()
  Map Y/N to 1/0:          lambda v: '1' if v.strip().upper() in ('Y','YES') else ('0' if v.strip().upper() in ('N','NO') else v)
"""


def call_llm_for_rule_discovery(
    examples: list[dict],   # [{source: str, target: str}, ...]
    column_name: str,
    cfg: dict,
) -> dict:
    """
    Feed source→target examples to the LLM and ask it to infer generic
    lambda transformation rules.

    Parameters
    ----------
    examples     : list of {source, target} dicts (up to 50)
    column_name  : output column name for context
    cfg          : Azure OpenAI config dict

    Returns
    -------
    dict with keys:
      rules   : list of {prompt, lambda_src, explanation, confidence, covers_examples}
      summary : str — overall pattern description
      error   : str | None
    """
    import urllib.request

    endpoint    = (cfg.get("endpoint") or "").rstrip("/")
    deployment  = cfg.get("deployment") or ""
    api_key     = cfg.get("api_key") or ""
    api_version = cfg.get("api_version") or "2024-02-01"

    # Format examples as a numbered table
    ex_lines = [f"  {i+1}. source={repr(str(e.get('source','')))}  →  target={repr(str(e.get('target','')))}"
                for i, e in enumerate(examples[:50])]
    user_msg = (
        f"Column: {column_name}\n"
        f"Transformation examples ({len(ex_lines)} rows):\n"
        + "\n".join(ex_lines)
        + "\n\nInfer the generic transformation rules."
    )

    if not endpoint or not api_key or not deployment:
        return {
            "rules":   [],
            "summary": "LLM not configured — cannot discover rules automatically.",
            "error":   "LLM not configured",
        }

    url = (f"{endpoint}/openai/deployments/{deployment}"
           f"/chat/completions?api-version={api_version}")

    payload = json.dumps({
        "model":       cfg.get("model", deployment),
        "max_tokens":  1200,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": _DISCOVERY_SYSTEM},
            {"role": "user",   "content": user_msg},
        ],
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("api-key", api_key)

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read())
            text = data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        return {"rules": [], "summary": "", "error": f"LLM error: {exc}"}

    # Extract JSON
    parsed = None
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if m:
        try:
            parsed = json.loads(m.group(0))
        except Exception:
            pass
    if parsed is None:
        clean = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
        try:
            parsed = json.loads(clean)
        except Exception:
            return {"rules": [], "summary": text[:300], "error": "LLM returned invalid JSON"}

    # Build preview for each discovered rule against the example sources
    source_vals = [str(e.get("source", "")) for e in examples[:12]]
    for rule in parsed.get("rules", []):
        rule["preview"] = _build_preview(rule.get("lambda_src", "lambda v: v"), source_vals)
        # Also compute coverage accuracy against known targets
        correct = 0
        for ex in examples[:50]:
            out, err = _safe_apply(rule.get("lambda_src", "lambda v: v"), str(ex.get("source", "")))
            if not err and str(out) == str(ex.get("target", "")):
                correct += 1
        rule["accuracy"] = round(100 * correct / len(examples), 1) if examples else 0

    return {
        "rules":   parsed.get("rules", []),
        "summary": parsed.get("summary", ""),
        "error":   None,
    }

