"""
Auto-extracted module: row_processing/eda.py
"""

from __future__ import annotations

import pandas as pd

from sov_app.header_mapping.schema import TARGET_SCHEMA_AIR, TARGET_SCHEMA_RMS

def run_eda(df_raw: pd.DataFrame, locked_schema, target_system: str = "AIR") -> dict:
    schema     = TARGET_SCHEMA_AIR if target_system.upper() == "AIR" else TARGET_SCHEMA_RMS
    schema_map = {s["output_col"]: s for s in schema}

    NUMERIC_COLS  = {"BuildingValue","OtherValue","ContentsValue","TimeElementValue",
                     "BIValue","GrossArea","RiskCount","NumUnits","DaysCovered"}
    YEAR_COLS     = {"YearBuilt","Roof Year Built","RoofCoverYear"}
    STORY_COLS    = {"NumberOfStories","NumStories"}
    CURRENCY_COLS = {"BuildingValue","OtherValue","ContentsValue","TimeElementValue","BIValue"}

    results: dict = {}

    for decision in locked_schema.decisions:
        out_col = decision.output_col
        sources = decision.final_source or []
        if not sources or decision.decision == "unavailable":
            continue

        raw_series_parts = []
        for src in sources:
            if src in df_raw.columns:
                raw_series_parts.append(df_raw[src])
        if not raw_series_parts:
            continue

        total       = len(df_raw)
        primary_src = sources[0]
        primary_col = df_raw[primary_src] if primary_src in df_raw.columns else raw_series_parts[0]

        is_null = primary_col.isna() | primary_col.astype(str).str.strip().isin(
            ["", "nan", "None", "NaN", "N/A", "n/a", "-"])
        null_ct   = int(is_null.sum())
        non_null  = primary_col[~is_null].astype(str).str.strip()
        fill_rate = round(100 * (total - null_ct) / max(total, 1), 1)

        eda: dict = {
            "output_col":    out_col,
            "source_cols":   sources,
            "total_rows":    total,
            "null_count":    null_ct,
            "fill_rate":     fill_rate,
            "unique_count":  int(non_null.nunique()),
            "sample_values": non_null.head(6).tolist(),
            "issues":        [],
        }
        issues = eda["issues"]

        if fill_rate < 50:
            issues.append(("critical", f"{100 - fill_rate:.0f}% of rows are empty or null"))
        elif fill_rate < 80:
            issues.append(("warning", f"{100 - fill_rate:.0f}% of rows have no value"))

        cleaned_num = (non_null.str.replace(r"[\$,]", "", regex=True)
                                .str.replace(r"\s+", "", regex=True))
        numeric_parsed = pd.to_numeric(cleaned_num, errors="coerce")
        num_ratio = numeric_parsed.notna().mean() if len(numeric_parsed) > 0 else 0.0

        if out_col in YEAR_COLS:
            eda["inferred_type"] = "year"
            yvals = pd.to_numeric(non_null, errors="coerce").dropna()
            if len(yvals):
                import datetime
                cy = datetime.datetime.utcnow().year
                eda["min"] = int(yvals.min()); eda["max"] = int(yvals.max())
                future = int((yvals > cy).sum())
                old    = int((yvals < 1700).sum())
                if future: issues.append(("error",   f"{future} rows have year > {cy} (future date)"))
                if old:    issues.append(("warning", f"{old} rows have year before 1700"))
                if eda["max"] - eda["min"] > 200:
                    issues.append(("info", f"Year range is wide: {eda['min']}–{eda['max']}"))

        elif out_col in STORY_COLS:
            eda["inferred_type"] = "numeric"
            svals = pd.to_numeric(non_null, errors="coerce").dropna()
            if len(svals):
                eda["min"] = float(svals.min()); eda["max"] = float(svals.max())
                eda["mean"] = round(float(svals.mean()), 1)
                high = int((svals > 100).sum())
                if high: issues.append(("warning", f"{high} rows have stories > 100"))

        elif num_ratio > 0.7:
            eda["inferred_type"] = "currency" if out_col in CURRENCY_COLS else "numeric"
            nvals = numeric_parsed.dropna()
            if len(nvals):
                eda["min"]    = round(float(nvals.min()), 2)
                eda["max"]    = round(float(nvals.max()), 2)
                eda["mean"]   = round(float(nvals.mean()), 2)
                eda["median"] = round(float(nvals.median()), 2)
                zero_ct = int((nvals == 0).sum())
                neg_ct  = int((nvals < 0).sum())
                if zero_ct: issues.append(("info",    f"{zero_ct} rows have value = 0"))
                if neg_ct:  issues.append(("warning", f"{neg_ct} rows have negative values (will floor to 0)"))
                if len(nvals) >= 10:
                    Q1, Q3 = nvals.quantile(0.25), nvals.quantile(0.75)
                    IQR = Q3 - Q1
                    if IQR > 0:
                        lo, hi = Q1 - 3 * IQR, Q3 + 3 * IQR
                        outlier_mask = (nvals < lo) | (nvals > hi)
                        out_ct = int(outlier_mask.sum())
                        if out_ct:
                            eda["outlier_count"]  = out_ct
                            eda["outlier_values"] = [round(v, 0) for v in nvals[outlier_mask].head(5).tolist()]
                            issues.append(("warning",
                                f"{out_ct} extreme outliers detected (>{round(hi,0):,.0f})"))
                if out_col in CURRENCY_COLS:
                    if non_null.str.contains(r"\$").any() or non_null.str.contains(r",").any():
                        eda["has_currency_format"] = True
                        issues.append(("info", "Currency formatting detected ($, commas) — will be stripped"))
        else:
            eda["inferred_type"] = "text"
            top = non_null.value_counts().head(5)
            eda["top_values"] = {k: int(v) for k, v in top.items()}
            if out_col == "Street":
                multi = int(non_null.str.contains(r"[;\n]|/| & ").sum())
                if multi:
                    issues.append(("warning",
                        f"{multi} rows appear to contain multiple addresses — pipeline keeps first only"))
                ranges = int(non_null.str.contains(r"\d+-\d+").sum())
                if ranges:
                    issues.append(("info",
                        f"{ranges} rows contain address ranges like '400-440' — hyphens preserved"))

        results[out_col] = eda

    return results

