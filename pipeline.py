"""
pipeline
=================
Backward-compatible facade for the old monolithic ``sov_header_mapping``
module. The UI layer (``ui.*``) was written against a single
``sov`` module object exposing everything it needed as attributes, e.g.
``sov.run_header_mapping(...)``, ``sov.LockedSchema``, ``sov.fuzz``.

Rather than rewriting every one of those call sites, this facade
re-exports the handful of names the UI actually touches via the ``sov.``
namespace, now sourced from their real modular homes in
``header_mapping/`` and ``row_processing/``. Everything else in the
pipeline should be imported directly from its owning module.
"""

from __future__ import annotations

from fuzzywuzzy import fuzz  # type: ignore  # re-exported as sov.fuzz

from header_mapping.rms_crosswalk import (
    AIR_TO_RMS_CONSTRUCTION,
    AIR_TO_RMS_OCCUPANCY,
)
from header_mapping.models import LockedSchema, MappingDecision
from header_mapping.ai_refine import refine_mappings_with_ai
from header_mapping.pipeline import run_header_mapping

from row_processing.construction import _save_construction_rule
from row_processing.occupancy import (
    _save_occupancy_rule,
    looks_like_occupancy_text,
)
from row_processing.eda import run_eda
from row_processing.export import run_value_transformation

__all__ = [
    "fuzz",
    "AIR_TO_RMS_CONSTRUCTION",
    "AIR_TO_RMS_OCCUPANCY",
    "LockedSchema",
    "MappingDecision",
    "refine_mappings_with_ai",
    "run_header_mapping",
    "_save_construction_rule",
    "_save_occupancy_rule",
    "looks_like_occupancy_text",
    "run_eda",
    "run_value_transformation",
]
