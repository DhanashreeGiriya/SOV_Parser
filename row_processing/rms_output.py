"""
Auto-extracted module: row_processing/rms_output.py
"""

from __future__ import annotations

from header_mapping.rms_crosswalk import convert_air_to_rms_construction, convert_air_to_rms_occupancy, get_rms_ind

def apply_rms_crosswalk(row_out):
    air_const = row_out.get("ConstructionCode")
    if air_const is not None:
        rms_const = convert_air_to_rms_construction(int(air_const))
        row_out["ClassCode"] = rms_const["rms_code"]
        row_out.setdefault("ClassCodeScheme", "RMS")
        row_out.pop("ConstructionCode", None)
        row_out.pop("ConstructionCodeType", None)
    air_occ = row_out.get("OccupancyCode")
    if air_occ is not None:
        rms_occ = convert_air_to_rms_occupancy(int(air_occ))
        row_out["OccupancyType"] = rms_occ["rms_code"]
        row_out.setdefault("OccupancyScheme", "RMS")
        row_out.pop("OccupancyCode", None)
        row_out.pop("OccupancyCodeType", None)
    country = row_out.get("CountryISOA2") or row_out.get("CountryISO", "US")
    row_out["IND"] = get_rms_ind(country, use_4digit=(country == "US"))
    renames = {
        "LocationID": "LocNumber", "LocationName": "LocName",
        "Street": "StreetAddress", "Area": "StateCode",
        "NumberOfStories": "NumStories", "TimeElementValue": "BIValue",
        "Roof Year Built": "RoofCoverYear", "Sprinkler Availability": "SprinklerType",
    }
    for air_col, rms_col in renames.items():
        if air_col in row_out:
            row_out[rms_col] = row_out.pop(air_col)
    return row_out

