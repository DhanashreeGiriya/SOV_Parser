"""
header_mapping
========================
Column/header mapping pipeline (Pass 0 feedback, Pass A/B/C alias &
semantic matching, AI refinement, scoring, reporting, templates).

Submodules
----------
ai_config     - Azure OpenAI configuration helpers
schema        - target field schemas (AIR / RMS)
aliases       - reference alias dictionary
patterns      - regexes + value-pattern scoring helpers
rms_crosswalk - AIR <-> RMS code conversion tables/helpers
excel_io      - workbook loading / header-row detection
models        - ColumnMapping, MappingDecision, LockedSchema
matching      - map_headers() and its supporting matchers
ai_refine     - LLM-based mapping refinement
scoring       - confidence scoring + flag generation
reporting     - Excel mapping report export
templates     - save/load/apply mapping templates
pipeline      - run_header_mapping() orchestrator
"""
