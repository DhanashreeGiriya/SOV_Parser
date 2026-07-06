"""
Auto-extracted module: header_mapping/templates.py
"""

from __future__ import annotations

import json
from pathlib import Path

from header_mapping.models import LockedSchema, MappingDecision

def save_mapping_template(schema, template_dir, template_name=None):
    template_dir = Path(template_dir)
    template_dir.mkdir(parents=True, exist_ok=True)
    name = (template_name or schema.template_name).replace(" ", "_")
    path = template_dir / f"{name}.json"
    payload = {
        "template_name": schema.template_name,
        "target_system": schema.target_system,
        "sov_file": schema.sov_file,
        "review_timestamp": schema.review_timestamp,
        "reviewer": schema.reviewer,
        "raw_headers": schema.raw_headers,
        "decisions": [d.to_dict() for d in schema.decisions],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path


def load_mapping_template(template_path):
    with open(template_path, encoding="utf-8") as f:
        payload = json.load(f)
    decisions = [MappingDecision(**d) for d in payload["decisions"]]
    return LockedSchema(
        target_system=payload["target_system"],
        sov_file=payload.get("sov_file", ""),
        template_name=payload["template_name"],
        review_timestamp=payload.get("review_timestamp", ""),
        reviewer=payload.get("reviewer", ""),
        decisions=decisions,
        raw_headers=payload.get("raw_headers", []),
    )


def apply_template_to_mappings(mappings, template, current_raw_headers):
    template_map = {d.output_col: d for d in template.decisions}
    current_set = set(current_raw_headers)
    exceptions = []
    for m in mappings:
        decision = template_map.get(m.output_col)
        if decision is None:
            continue
        if decision.decision == "unavailable":
            m.source_cols = []
            m.match_type = "template_unavailable"
            m.confidence = 100
            m.notes = f"Template: marked unavailable by {decision.reviewer}"
            continue
        missing = [s for s in decision.final_source if s not in current_set]
        if missing:
            exceptions.append(m.output_col)
            m.notes += f" | Template source missing: {missing}"
            continue
        m.source_cols = decision.final_source
        m.match_type = "template_auto"
        m.confidence = 100
        m.flag = ""
        m.notes = f"Template auto-applied: {template.template_name}"
    return mappings, exceptions

