"""
feedback.row_feedback
======================
Modular replacement for the old monolithic ``sov_row_feedback.py``, split into:

  store.py            - JSON persistence for confirmed transform rules
  transform_lambda.py - safe lambda execution / sanitising / preview
  llm_transform.py     - LLM-authored single-rule transform generation
  llm_discovery.py     - LLM-driven multi-rule discovery pass
  apply.py             - applying confirmed rules to a DataFrame

Everything that used to be a top-level name in ``sov_row_feedback`` is
re-exported here so existing call sites such as
``import sov_app.feedback.row_feedback as rf; rf.apply_rules(...)``
keep working unchanged.
"""

from sov_app.feedback.row_feedback.store import (
    RULES_FILE,
    PRE_CODE_RULE_COLUMNS,
    save_rule,
    load_rules,
    get_rules_summary,
    delete_rule,
    clear_rules,
    reorder_rules,
)
from sov_app.feedback.row_feedback.transform_lambda import (
    run_lambda_on_series,
)
from sov_app.feedback.row_feedback.llm_transform import (
    call_llm_for_transform,
)
from sov_app.feedback.row_feedback.llm_discovery import (
    call_llm_for_rule_discovery,
)
from sov_app.feedback.row_feedback.apply import (
    apply_rules,
    apply_rules_to_raw,
    build_full_preview,
)

__all__ = [
    "RULES_FILE",
    "PRE_CODE_RULE_COLUMNS",
    "save_rule",
    "load_rules",
    "get_rules_summary",
    "delete_rule",
    "clear_rules",
    "reorder_rules",
    "run_lambda_on_series",
    "call_llm_for_transform",
    "call_llm_for_rule_discovery",
    "apply_rules",
    "apply_rules_to_raw",
    "build_full_preview",
]
