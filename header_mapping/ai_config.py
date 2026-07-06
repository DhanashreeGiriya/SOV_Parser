"""
Auto-extracted module: header_mapping/ai_config.py
"""

from __future__ import annotations

import streamlit as st
import os

def _get_azure_cfg() -> dict:
    return {
        "endpoint":    os.environ.get("OPENAI_DEPLOYMENT_ENDPOINT", "").rstrip("/"),
        "deployment":  os.environ.get("OPENAI_DEPLOYMENT_NAME", "gpt-4.1"),
        "model":       os.environ.get("OPENAI_MODEL_NAME", "gpt-4.1"),
        "api_key":     os.environ.get("OPENAI_API_KEY", ""),
        "api_version": os.environ.get("OPENAI_API_VERSION", "2025-01-01-preview"),
    }


def _get_azure_cfg_from_secrets() -> dict:
    try:
        import streamlit as st
        sec = st.secrets.get("azure_openai", {})
        return {
            "endpoint":    sec.get("endpoint",    os.environ.get("OPENAI_DEPLOYMENT_ENDPOINT", "")).rstrip("/"),
            "deployment":  sec.get("deployment",  os.environ.get("OPENAI_DEPLOYMENT_NAME", "gpt-4.1")),
            "model":       sec.get("model",       os.environ.get("OPENAI_MODEL_NAME", "gpt-4.1")),
            "api_key":     sec.get("api_key",     os.environ.get("OPENAI_API_KEY", "")),
            "api_version": sec.get("api_version", os.environ.get("OPENAI_API_VERSION", "2025-01-01-preview")),
        }
    except Exception:
        return _get_azure_cfg()

