"""
Auto-extracted module: header_mapping/schema.py
"""

from __future__ import annotations

AI_REVIEW_THRESHOLD = 82


TARGET_SCHEMA_AIR: list[dict] = [
    {"output_col": "ContractID",            "method": "System",         "default": None },
    {"output_col": "LocationID",            "method": "Direct",         "default": None },
    {"output_col": "LocationName",          "method": "Transform",      "default": None },
    {"output_col": "Street",                "method": "Transform",      "default": None },
    {"output_col": "City",                  "method": "Direct",         "default": None },
    {"output_col": "Cresta",                "method": "Derived/NULL",   "default": None },
    {"output_col": "CountryISO",            "method": "Hardcode",       "default": "US" },
    {"output_col": "Area",                  "method": "Direct",         "default": None },
    {"output_col": "SubArea",               "method": "Direct",         "default": None },
    {"output_col": "PostalCode",            "method": "Direct/Format",  "default": None },
    {"output_col": "Latitude",              "method": "Geocoded/NULL",  "default": None },
    {"output_col": "Longitude",             "method": "Geocoded/NULL",  "default": None },
    {"output_col": "InceptionDate",         "method": "System/NULL",    "default": None },
    {"output_col": "ExpirationDate",        "method": "System/NULL",    "default": None },
    {"output_col": "Currency",              "method": "Hardcode/NULL",  "default": "USD"},
    {"output_col": "RiskCount",             "method": "Direct",         "default": None },
    {"output_col": "NumUnits",              "method": "Direct/Note",    "default": None },
    {"output_col": "BuildingValue",         "method": "Transform/Rules","default": 0    },
    {"output_col": "OtherValue",            "method": "Direct/Rules",   "default": 0    },
    {"output_col": "ContentsValue",         "method": "Direct/Rules",   "default": 0    },
    {"output_col": "TimeElementValue",      "method": "Direct/Rules",   "default": 0    },
    {"output_col": "DaysCovered",           "method": "Default/NULL",   "default": 365  },
    {"output_col": "ConstructionCode",      "method": "Lookup/Rules",   "default": 100  },
    {"output_col": "ConstructionOther",     "method": "Direct/Note",    "default": None },
    {"output_col": "OccupancyCode",         "method": "Rules/Lookup",   "default": None },
    {"output_col": "YearBuilt",             "method": "Direct/Rules",   "default": None },
    {"output_col": "NumberOfStories",       "method": "Direct/Rules",   "default": None },
    {"output_col": "LocPerils",             "method": "System/Policy",  "default": None },
    {"output_col": "SublimitArea",          "method": "System/NULL",    "default": None },
    {"output_col": "GrossArea",             "method": "Direct/Rules",   "default": None },
    {"output_col": "Roof Year Built",       "method": "Direct",         "default": None },
    {"output_col": "Sprinkler Availability","method": "Transform",      "default": 0    },
]


TARGET_SCHEMA = TARGET_SCHEMA_AIR


TARGET_SCHEMA_RMS: list[dict] = [
    {"output_col": "LocNumber",          "method": "Direct",         "default": None },
    {"output_col": "RiskID",             "method": "System",         "default": None },
    {"output_col": "AccGrpID",           "method": "System",         "default": None },
    {"output_col": "LocName",            "method": "Transform",      "default": None },
    {"output_col": "StreetAddress",      "method": "Transform",      "default": None },
    {"output_col": "City",               "method": "Direct",         "default": None },
    {"output_col": "StateCode",          "method": "Direct",         "default": None },
    {"output_col": "PostalCode",         "method": "Direct/Format",  "default": None },
    {"output_col": "CountryISOA2",       "method": "Hardcode",       "default": "US" },
    {"output_col": "IND",                "method": "Lookup/Rules",   "default": None },
    {"output_col": "Latitude",           "method": "Geocoded/NULL",  "default": None },
    {"output_col": "Longitude",          "method": "Geocoded/NULL",  "default": None },
    {"output_col": "Currency",           "method": "Hardcode/NULL",  "default": "USD"},
    {"output_col": "BuildingValue",      "method": "Transform/Rules","default": 0    },
    {"output_col": "OtherValue",         "method": "Direct/Rules",   "default": 0    },
    {"output_col": "ContentsValue",      "method": "Direct/Rules",   "default": 0    },
    {"output_col": "BIValue",            "method": "Direct/Rules",   "default": 0    },
    {"output_col": "BIPeriod",           "method": "Default/NULL",   "default": 12   },
    {"output_col": "RiskCount",          "method": "Direct",         "default": None },
    {"output_col": "NumUnits",           "method": "Direct/Note",    "default": None },
    {"output_col": "ClassCode",          "method": "Lookup/Rules",   "default": 1000 },
    {"output_col": "ClassCodeScheme",    "method": "Hardcode",       "default": "RMS"},
    {"output_col": "OccupancyType",      "method": "Lookup/Rules",   "default": None },
    {"output_col": "OccupancyScheme",    "method": "Hardcode",       "default": "RMS"},
    {"output_col": "YearBuilt",          "method": "Direct/Rules",   "default": None },
    {"output_col": "NumStories",         "method": "Direct/Rules",   "default": None },
    {"output_col": "GrossArea",          "method": "Direct/Rules",   "default": None },
    {"output_col": "RoofCoverYear",      "method": "Direct",         "default": None },
    {"output_col": "SprinklerType",      "method": "Transform",      "default": 1    },
    {"output_col": "ConstructionOther",  "method": "Direct/Note",    "default": None },
    {"output_col": "InceptionDate",      "method": "System/NULL",    "default": None },
    {"output_col": "ExpirationDate",     "method": "System/NULL",    "default": None },
    {"output_col": "PerilsCovered",      "method": "System/Policy",  "default": None },
    {"output_col": "SubArea",            "method": "Direct",         "default": None },
    {"output_col": "CRESTA",             "method": "Derived/NULL",   "default": None },
]


AUTO_POPULATED_COLS_AIR: set[str] = set()


AUTO_POPULATED_COLS_RMS: set[str] = set()


AUTO_POPULATED_COLS = AUTO_POPULATED_COLS_AIR

