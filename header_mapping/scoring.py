"""
Auto-extracted module: header_mapping/scoring.py
"""

from __future__ import annotations

def apply_scoring(mappings: list) -> list:
    for m in mappings:
        m.confidence = max(0, min(100, int(m.confidence)))
    return mappings


def generate_mapping_flags(mappings, unmapped_raw):
    high, medium, low, missing, multi = [], [], [], [], []
    for m in mappings:
        if m.flag in ("missing",):
            missing.append(m.output_col)
        elif m.flag == "multi_source":
            multi.append(m.output_col)
        elif m.confidence >= 85:
            high.append(m.output_col)
        elif m.confidence >= 60:
            medium.append(m.output_col)
        elif m.confidence > 0:
            low.append(m.output_col)
    return {
        "high_confidence": high,
        "medium_confidence": medium,
        "low_confidence": low,
        "missing_source": missing,
        "multi_source": multi,
        "unmapped_raw_cols": unmapped_raw,
    }

