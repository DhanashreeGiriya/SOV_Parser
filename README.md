# sov_app — Modularized Intelligent SOV Parser

This is the modularized rewrite of the original flat files
(`sov_header_mapping_5.py`, `app_1.py`, `sov_row_feedback.py`,
`sov_feedback.py`, `occ_alias_store.py`, `const_alias_store.py`).

**Nothing about the app's behaviour changed.** Every function, class,
constant, docstring, and comment from the original files was preserved
byte-for-byte — they were only relocated into topic-based files and
re-wired with imports. All 46 modules were verified to import cleanly
and the header-mapping pipeline was smoke-tested end-to-end after the
split.

## How to run it

```bash
pip install -r requirements.txt   # streamlit, pandas, openpyxl, fuzzywuzzy, python-Levenshtein
streamlit run sov_app/app.py
```

`app.py` bootstraps `sys.path` on startup, so it works whether you
launch it from inside or outside the `sov_app/` folder.

## Structure

```
sov_app/
├── app.py                         # Streamlit entry point (was: main() in app_1.py)
├── pipeline.py                    # facade re-exporting the handful of names the
│                                   #   UI still accesses as sov.<name> (was the
│                                   #   giant sov_header_mapping module object)
├── data/                          # JSON persistence — was scattered at repo root
│   ├── sov_feedback_store.json
│   ├── sov_row_feedback_store.json
│   ├── occ_alias_store.json
│   └── const_alias_store.json
│
├── header_mapping/                # Column/header mapping pipeline
│   ├── ai_config.py                 - Azure OpenAI config helpers
│   ├── schema.py                    - TARGET_SCHEMA_AIR / RMS, auto-populated cols
│   ├── aliases.py                   - ALIAS_MAP reference dictionary
│   ├── patterns.py                  - regexes + value-pattern scoring
│   ├── rms_crosswalk.py              - AIR <-> RMS code tables/conversion
│   ├── excel_io.py                   - workbook load, header-row detection, _normalise
│   ├── models.py                      - ColumnMapping / MappingDecision / LockedSchema
│   ├── matching.py                     - map_headers() + fuzzy/alias/value matchers
│   ├── ai_refine.py                     - LLM-based mapping refinement
│   ├── scoring.py                        - confidence scoring + flags
│   ├── reporting.py                       - Excel mapping report export
│   ├── templates.py                        - save/load/apply mapping templates
│   └── pipeline.py                          - run_header_mapping() orchestrator
│
├── row_processing/                # Row-level cleaning / transformation
│   ├── helpers.py                   - _to_float/_to_int/_clean_str/...
│   ├── address.py                    - street/location-name/postal/country
│   ├── construction.py                - construction-code resolution
│   ├── occupancy.py                    - occupancy-code resolution
│   ├── numeric_fields.py                - year built, stories, areas, values
│   ├── flags.py                          - CellFlag / FlagLog / validation
│   ├── rms_output.py                      - apply_rms_crosswalk()
│   ├── process_row.py                      - process_row() orchestrator
│   ├── column_order.py                      - AIR_COLUMN_ORDER / RMS_COLUMN_ORDER
│   ├── eda.py                                - run_eda()
│   └── export.py                              - run_value_transformation() + exports
│
├── feedback/                      # Reviewer feedback persistence
│   ├── header_feedback.py           - column-mapping overrides (was sov_feedback.py)
│   ├── occupancy_aliases.py          - confirmed occupancy description -> code
│   ├── construction_aliases.py        - confirmed construction description -> code
│   └── row_feedback/                   - value-transform rules (was sov_row_feedback.py)
│       ├── store.py                      - JSON persistence for rules
│       ├── transform_lambda.py            - safe lambda exec / sanitising / preview
│       ├── llm_transform.py                - LLM single-rule generation
│       ├── llm_discovery.py                 - LLM multi-rule discovery pass
│       └── apply.py                          - applying confirmed rules to a DataFrame
│
└── ui/                             # Streamlit rendering layer, one file per tab
    ├── common.py                     - badges, formatters, sidebar, pipeline loader
    ├── phase1_mapping.py              - "Map & Analyse" tab
    ├── phase2_review.py                - "Review" tab
    ├── phase3_transform.py              - "Transform" tab + EDA/code-review panels
    ├── accuracy_tab.py                   - "Accuracy QA" tab
    ├── feedback_tab.py                    - "Column Rules" tab
    └── row_feedback_tab.py                 - "Row Rules" tab
```

## Design notes / why it still works

1. **Every top-level function/class/constant kept its exact original
   body.** They were extracted with Python's `ast` module by precise
   line ranges, not retyped, so there is no risk of a typo changing
   behaviour.

2. **Cross-module calls were rewired automatically** based on which
   module now owns each name, then verified with `pyflakes` (zero
   "undefined name" warnings) and a full recursive import walk (all 46
   submodules import cleanly, no circular imports).

3. **The old `sov.<name>` access pattern in the UI layer is preserved**
   via `sov_app/pipeline.py`, a small facade that re-exports the dozen
   names (`run_header_mapping`, `LockedSchema`, `run_eda`, `fuzz`, ...)
   that `ui/*.py` still reaches through a `sov` module object, exactly
   as the original `app_1.py` did with the monolithic
   `sov_header_mapping` module.

4. **The existing lazy/optional cross-file imports were kept lazy.**
   The original code already guarded things like
   `from sov_row_feedback import apply_rules` inside `try/except`
   blocks so the app degrades gracefully if that file was missing —
   those blocks are untouched, just repointed at the new module paths
   (`sov_app.feedback.row_feedback`).

5. **Data files moved into `sov_app/data/`.** Each store's path is
   still overridable via the same environment variables as before
   (`SOV_FEEDBACK_PATH`, `SOV_ROW_FEEDBACK_PATH`), plus two new ones
   for consistency (`SOV_OCC_ALIAS_PATH`, `SOV_CONST_ALIAS_PATH`).

## Verification performed

- `python -m py_compile` on all 46 files — clean.
- `pyflakes` on the whole package — zero undefined-name errors (a few
  pre-existing, harmless warnings like unused locals/re-imports inside
  functions carried over unchanged from the original files).
- Recursive `pkgutil.walk_packages` + `importlib.import_module` over
  every submodule — 0 failures, no circular imports.
- Functional smoke test: `map_headers()` run end-to-end against a
  sample header list produced correct alias/semantic matches with the
  right confidence scores; `ColumnMapping`/`FlagLog` dataclasses
  instantiate correctly; alias-store lookups (`lookup_const_rule`,
  `lookup_occ_rule`) return the same codes as the original JSON data.
