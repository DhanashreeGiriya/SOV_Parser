"""
Auto-extracted module: ui/common.py
"""

from __future__ import annotations

import pandas as pd
import openpyxl
import string
import io

def safe_join(values, sep=", "):
    """
    Safely joins mixed-type iterables into a string.

    Handles:
    - int
    - float
    - None
    - NaN
    - strings
    """

    if not values:
        return ""

    cleaned = []

    for v in values:

        # Skip None
        if v is None:
            continue

        # Skip pandas NaN
        try:
            import pandas as pd
            if pd.isna(v):
                continue
        except Exception:
            pass

        # Convert everything else to string
        cleaned.append(str(v))

    return sep.join(cleaned)


def load_pipeline():
    try:
        import sov_app.pipeline as sov
        return sov, None
    except Exception as e:
        return None, str(e)


def _match_type_display(match_type: str) -> tuple[str, str, str]:
    """
    Returns (label, css_class, description) using only user-facing terminology.
    No internal names (fuzzy, LLM, hardcode, etc.) are exposed.
    """
    mt = match_type.lower()
    if mt in ("reference_exact", "alias_exact"):
        return "Reference Match", "m-ref", "Matched by known insurance industry name"
    if mt in ("reference_fuzzy", "alias_fuzzy", "semantic_match", "fuzzy"):
        return "Semantic Match", "m-sem", "Matched by column name similarity"
    if mt in ("ai_validated",):
        return "AI Validated", "m-ai", "Semantic match confirmed by AI using sample data"
    if mt in ("ai_refined", "llm_refined", "ai_inferred", "llm_inferred"):
        return "AI Refined", "m-ai", "AI identified best match using actual data values"
    if mt in ("template_auto",):
        return "Reference Match", "m-ref", "Applied from saved template"
    if mt in ("not_found", "not_in_source", "none", "template_unavailable", "not_in_source"):
        return "Not Found", "m-absent", "No matching column found in source file"
    if mt in ("human_override",):
        return "Manual Override", "m-human", "Manually assigned by reviewer"
    if mt in ("auto_populated",):
        return "Auto-Populated", "m-null", "Calculated automatically — not from source file"
    if mt in ("feedback_match", "feedback", "pass0", "alias_feedback", 
          "human_feedback", "feedback_exact"):
        return "Feedback Match", "m-fb", "Learned from a previous reviewer's override"
    return "Not Found", "m-absent", "No matching column found"


def _is_auto_populated(m) -> bool:
    return m.match_type == "auto_populated"


def _has_source(m) -> bool:
    """True if the mapping has real source columns from the uploaded file."""
    return bool(m.source_cols) and not _is_auto_populated(m)


def method_badge(match_type: str) -> str:
    label, cls, _ = _match_type_display(match_type)
    return f'<span class="method-badge {cls}">{label}</span>'


def conf_bar(score: int) -> str:
    colour = "#10b981" if score >= 85 else ("#f59e0b" if score >= 60 else ("#ef4444" if score > 0 else "#475569"))
    return (f'<span class="conf-bar-wrap">'
            f'<span class="conf-bar" style="width:{score}%;background:{colour}"></span>'
            f'</span>')


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False)
    return buf.getvalue()


def _human_basis(m) -> str:
    """Return a clean, user-facing explanation of why this mapping was chosen."""
    if _is_auto_populated(m):
        return "Calculated automatically during transformation — not sourced from your file"
    if m.final_decision_basis:
        b = m.final_decision_basis
        # Strip internal pass labels and technical jargon
        for token in ("Pass A:", "Pass B:", "Pass C:", "pending AI verification",
                      "fuzzy", "LLM", "llm", "hardcode", "alias_exact", "alias_fuzzy",
                      "Semantic match 'None'", "Semantic similarity match:"):
            b = b.replace(token, "")
        b = b.replace("  ", " ").strip(" ·|,")
        return b if b else "—"
    _, _, desc = _match_type_display(m.match_type)
    return desc


def render_sidebar():
    return "AIR", 90, None

