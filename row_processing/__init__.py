"""
row_processing
========================
Row-level cleaning / transformation / resolution logic that turns a raw
SOV row into a cleaned AIR or RMS output row.

Submodules
----------
helpers        - small generic value helpers (_to_float, _to_int, ...)
address        - street / location-name / postal-code / country resolution
construction   - construction-code resolution (semantic + AI + cache)
occupancy      - occupancy-code resolution (semantic + AI + cache)
numeric_fields - year built, stories, areas, values, sprinkler resolution
flags          - CellFlag / FlagLog + cross-column validation
rms_output     - AIR -> RMS crosswalk application on an output row
process_row    - process_row() orchestrator for a single row
column_order   - final column ordering for AIR / RMS exports
eda            - exploratory data analysis over the raw sheet
export         - run_value_transformation() + Excel/QA export
"""
