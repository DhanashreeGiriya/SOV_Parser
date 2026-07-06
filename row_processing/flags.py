"""
Auto-extracted module: row_processing/flags.py
"""

from __future__ import annotations

import pandas as pd
import re
from dataclasses import dataclass, field, asdict

from sov_app.row_processing.helpers import _to_float

@dataclass
class CellFlag:
    row_idx: int
    output_col: str
    raw_value: str
    rule_applied: str
    cleaned_value: str
    flag_type: str
    severity: str


class FlagLog:
    def __init__(self):
        self._flags: list = []

    def add(self, row_idx, output_col, raw_value, rule_applied,
            cleaned_value, flag_type, severity="warning"):
        self._flags.append(CellFlag(
            row_idx=row_idx, output_col=output_col,
            raw_value=str(raw_value) if raw_value is not None else "",
            rule_applied=rule_applied,
            cleaned_value=str(cleaned_value) if cleaned_value is not None else "",
            flag_type=flag_type, severity=severity,
        ))

    def for_row(self, row_idx):
        return [f for f in self._flags if f.row_idx == row_idx]

    def to_dataframe(self):
        return pd.DataFrame([asdict(f) for f in self._flags])

    def summary(self):
        from collections import Counter
        return dict(Counter(f.flag_type for f in self._flags))


_US_ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")


def validate_cross_column_flags(cleaned_df, flag_log):
    import datetime
    current_year = datetime.datetime.utcnow().year
    for row_idx, row in cleaned_df.iterrows():
        country = str(row.get("CountryISO", "") or row.get("CountryISOA2", "")).upper()
        postal = str(row.get("PostalCode", "") or "").strip()
        if postal and country == "US" and not _US_ZIP_RE.match(postal):
            flag_log.add(row_idx, "PostalCode", postal, "zip_country_cross_check",
                         postal, "zip_country_mismatch", "warning")
        lat_raw = row.get("Latitude")
        lon_raw = row.get("Longitude")
        lat_present = lat_raw is not None and str(lat_raw).strip() not in ("", "None", "nan")
        lon_present = lon_raw is not None and str(lon_raw).strip() not in ("", "None", "nan")
        if lat_present != lon_present:
            flag_log.add(row_idx, "Latitude", f"lat={lat_raw} lon={lon_raw}",
                         "lat_lon_pair_check", "", "lat_lon_incomplete", "warning")
        yr = row.get("YearBuilt")
        if yr is not None and str(yr).strip() not in ("", "None", "nan"):
            try:
                if int(float(str(yr))) > current_year:
                    flag_log.add(row_idx, "YearBuilt", yr, "year_built_range_check",
                                 yr, "year_built_in_future", "error")
            except (ValueError, TypeError):
                pass
        bv  = _to_float(row.get("BuildingValue", 0))
        ov  = _to_float(row.get("OtherValue", 0))
        cv  = _to_float(row.get("ContentsValue", 0))
        tev = _to_float(row.get("TimeElementValue", 0)) or _to_float(row.get("BIValue", 0))
        if bv == 0 and ov == 0 and cv == 0 and tev == 0:
            flag_log.add(row_idx, "BuildingValue", "0", "tiv_cross_check",
                         "0", "no_insurable_value", "warning")

