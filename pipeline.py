"""
sov_app.pipeline
=================
Backward-compatible facade for the old monolithic ``sov_header_mapping``
module. The UI layer (``sov_app.ui.*``) was written against a single
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

from sov_app.header_mapping.rms_crosswalk import (
    AIR_TO_RMS_CONSTRUCTION,
    AIR_TO_RMS_OCCUPANCY,
)
from sov_app.header_mapping.models import LockedSchema, MappingDecision
from sov_app.header_mapping.ai_refine import refine_mappings_with_ai
from sov_app.header_mapping.pipeline import run_header_mapping

from sov_app.row_processing.construction import _save_construction_rule
from sov_app.row_processing.occupancy import (
    _save_occupancy_rule,
    looks_like_occupancy_text,
)
from sov_app.row_processing.eda import run_eda
from sov_app.row_processing.export import run_value_transformation

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
