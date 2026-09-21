"""Config domain: decision service (Epic 39 — Jev typed decisions).

Flags are advisory/additive: when disabled or when the backend errors,
callers keep their existing behavior. The module constants below are
import-time snapshots (like every other config domain); the
``decision_enabled()`` / ``decision_task_enabled()`` helpers re-read the
environment at call time — they are the source of truth the service
gates on, so tests can ``monkeypatch.setenv`` without re-importing.
"""

from __future__ import annotations

import logging
import math
import os

from app.config._helpers import _env_choice, _env_float

logger = logging.getLogger(__name__)


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() == "true"


def _env_fallback_backend() -> str:
    """Read DECISION_FALLBACK_BACKEND, failing CLOSED on a bad value.

    Unlike ``_env_choice`` (which warns and returns the default), an
    unrecognized value here resolves to ``"none"`` — a typo must DISABLE
    the paid fallback leg, never silently enable it.
    """
    raw = os.getenv("DECISION_FALLBACK_BACKEND")
    if raw is None:
        return "llm_json"
    value = raw.strip().lower()
    if value in ("llm_json", "none"):
        return value
    logger.warning(
        "Invalid DECISION_FALLBACK_BACKEND=%r; expected llm_json/none; "
        "disabling the fallback chain",
        raw,
    )
    return "none"


# Master switch — default off: decision calls are opt-in until consumer
# stories (39.2+) land and each path is verified advisory.
DECISION_ENABLED = _env_flag("DECISION_ENABLED", False)

# Backend selection (AD-J2).
DECISION_BACKEND = _env_choice("DECISION_BACKEND", "jev", ("jev", "llm_json", "mock"))

# Fallback chain (story 39.1b): a primary-leg DecisionError with code in
# {timeout, backend_error, backend_unavailable, missing_api_key} retries
# once through this backend. "none" disables the chain. Fail-closed on
# typos — see _env_fallback_backend.
DECISION_FALLBACK_BACKEND = _env_fallback_backend()

# Pinned models, per backend — never "jev-latest" (AD-J3). The LLM pin
# defaults to the eval baseline model.
DECISION_JEV_MODEL = (
    os.getenv("DECISION_JEV_MODEL", "jev-1.13.0").strip() or "jev-1.13.0"
)
DECISION_LLM_MODEL = (
    os.getenv("DECISION_LLM_MODEL", "claude-haiku-4-5-20251001").strip()
    or "claude-haiku-4-5-20251001"
)

# Hard ceiling per decide() call; callers should never wait longer.
# ``float("inf")``/``nan`` parse fine via _env_float but would disable the
# ceiling — guard with isfinite.
_DECISION_TIMEOUT_RAW = _env_float("DECISION_TIMEOUT_SECONDS", 5.0)
DECISION_TIMEOUT_SECONDS = (
    max(0.1, _DECISION_TIMEOUT_RAW) if math.isfinite(_DECISION_TIMEOUT_RAW) else 5.0
)

# Per-task flags — default on so DECISION_ENABLED=true is the single
# opt-in; each flag selectively disables its task.
DECISION_ROUTING_ENABLED = _env_flag("DECISION_ROUTING_ENABLED", True)
DECISION_FILTER_ENABLED = _env_flag("DECISION_FILTER_ENABLED", True)
DECISION_ENTITY_ENABLED = _env_flag("DECISION_ENTITY_ENABLED", True)
DECISION_INTENT_ENABLED = _env_flag("DECISION_INTENT_ENABLED", True)
DECISION_VOICE_ENABLED = _env_flag("DECISION_VOICE_ENABLED", True)

_DECISION_TASK_DEFAULTS: dict[str, bool] = {
    "routing": True,
    "filter": True,
    "entity": True,
    "intent": True,
    "voice": True,
}


def decision_enabled() -> bool:
    """Master switch, read fresh at call time."""
    return _env_flag("DECISION_ENABLED", False)


def decision_task_enabled(task: str) -> bool:
    """Per-task flag ``DECISION_{TASK}_ENABLED``, read fresh.

    Unknown task names fail closed (return False) so a typo never
    silently enables a decision path.
    """
    if not isinstance(task, str):
        return False
    key = task.strip().lower()
    if key not in _DECISION_TASK_DEFAULTS:
        return False
    return _env_flag(f"DECISION_{key.upper()}_ENABLED", _DECISION_TASK_DEFAULTS[key])


__all__ = [
    "DECISION_BACKEND",
    "DECISION_ENABLED",
    "DECISION_ENTITY_ENABLED",
    "DECISION_FALLBACK_BACKEND",
    "DECISION_FILTER_ENABLED",
    "DECISION_INTENT_ENABLED",
    "DECISION_JEV_MODEL",
    "DECISION_LLM_MODEL",
    "DECISION_ROUTING_ENABLED",
    "DECISION_TIMEOUT_SECONDS",
    "DECISION_VOICE_ENABLED",
    "decision_enabled",
    "decision_task_enabled",
]
