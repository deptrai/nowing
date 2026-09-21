"""decision config — env-var defaults for the 39.1b fallback chain vars."""

from __future__ import annotations

import importlib
import os

import pytest

import app.config.decision as decision_config

_KEYS = ("DECISION_FALLBACK_BACKEND", "DECISION_LLM_MODEL")


@pytest.mark.unit
def test_fallback_chain_env_defaults(monkeypatch):
    """With the env vars unset, the literal defaults hold.

    The constants are import-time snapshots, so the module must be
    reloaded under the patched environment; the finally-block restores
    ambient env and reloads again so later tests see their real values.
    """
    saved = {k: os.environ.get(k) for k in _KEYS}
    for k in _KEYS:
        monkeypatch.delenv(k, raising=False)
    try:
        importlib.reload(decision_config)
        assert decision_config.DECISION_FALLBACK_BACKEND == "llm_json"
        assert decision_config.DECISION_LLM_MODEL == "claude-haiku-4-5-20251001"
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
        importlib.reload(decision_config)


@pytest.mark.unit
def test_fallback_backend_env_choice_validation(monkeypatch):
    """A typo'd DECISION_FALLBACK_BACKEND warns and falls back to the
    default rather than silently disabling the chain."""
    saved = os.environ.get("DECISION_FALLBACK_BACKEND")
    monkeypatch.setenv("DECISION_FALLBACK_BACKEND", "gemini")
    try:
        importlib.reload(decision_config)
        assert decision_config.DECISION_FALLBACK_BACKEND == "llm_json"
    finally:
        if saved is None:
            os.environ.pop("DECISION_FALLBACK_BACKEND", None)
        else:
            os.environ["DECISION_FALLBACK_BACKEND"] = saved
        importlib.reload(decision_config)
