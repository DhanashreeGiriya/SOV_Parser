"""
Auto-extracted module: header_mapping/models.py
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict

@dataclass
class ColumnMapping:
    output_col: str
    method: str
    source_cols: list
    match_type: str
    confidence: int
    flag: str
    notes: str = ""
    default_value: object = None
    ai_reasoning: str = ""
    alias_suggestion: str = ""
    fuzzy_suggestion: str = ""
    fuzzy_confidence: int = 0
    ai_suggestion: str = ""
    ai_agreement: bool = False
    final_decision_basis: str = ""
    value_pattern_bonus: float = 0.0
    # ── embedding-match provenance (semantic similarity via local BGE model) ──
    embedding_score: float = 0.0
    # ── NEW: feedback provenance ──────────────────────────────────────────
    feedback_matched: bool = False
    feedback_reason: str = ""
    feedback_uses: int = 0


@dataclass
class MappingDecision:
    output_col: str
    original_source: list
    original_confidence: int
    original_match_type: str
    decision: str
    final_source: list
    override_reason: str = ""
    reviewer: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LockedSchema:
    target_system: str
    sov_file: str
    template_name: str
    review_timestamp: str
    reviewer: str
    decisions: list
    raw_headers: list
    col_to_sources: dict = field(default_factory=dict)
    locked: bool = True

    def __post_init__(self):
        self.col_to_sources = {d.output_col: d.final_source for d in self.decisions}

    def get_sources(self, output_col: str) -> list:
        return self.col_to_sources.get(output_col, [])

