"""Confidence gate — advisory threshold helper, not middleware (AD-J4).

Callers decide what a passing answer triggers; the gate only answers
"is this answer confident enough to act on?" Below threshold the caller
keeps its existing behavior.

Direction is use-case-specific: ``passes`` answers "confidently YES?"
(confidence >= threshold); ``passes_negative`` answers "confidently
NO?" and exists only for ``noul`` answers — a noul value IS P(yes), so
"confidently false" means P(yes) is LOW (``1 - value >= threshold``).
Non-noul kinds have no meaningful negative direction and always return
False from ``passes_negative``.

Per-task defaults are env-tunable via ``DECISION_{TASK}_THRESHOLD``::

    gate = ConfidenceGate.for_task("routing")   # DECISION_ROUTING_THRESHOLD, default 0.6
    if gate.passes(result.answers["subagent"]):
        dispatch(...)
"""

from __future__ import annotations

import logging
import math
import os

from app.services.decision.types import Answer

logger = logging.getLogger(__name__)

# Per-task default thresholds (AD-J4). ``voice`` ships a conservative
# default alongside the four eval-backed tasks.
DEFAULT_THRESHOLDS: dict[str, float] = {
    "routing": 0.6,
    "filter": 0.5,
    "entity": 0.7,
    "intent": 0.5,
    "voice": 0.5,
}

_FALLBACK_THRESHOLD = 0.5


class ConfidenceGate:
    """Threshold check over an ``Answer``'s confidence."""

    def __init__(self, threshold: float = _FALLBACK_THRESHOLD) -> None:
        self.threshold = threshold

    @classmethod
    def for_task(cls, task: str) -> ConfidenceGate:
        """Build a gate for a named task with env-var override.

        Reads ``DECISION_{TASK}_THRESHOLD`` at construction time so tests
        and operators can tune without redeploying code; falls back to
        ``DEFAULT_THRESHOLDS`` (or 0.5 for unknown tasks).
        """
        key = task.strip().lower()
        default = DEFAULT_THRESHOLDS.get(key, _FALLBACK_THRESHOLD)
        raw = os.getenv(f"DECISION_{key.upper()}_THRESHOLD")
        if raw is None:
            return cls(default)
        try:
            value = float(raw)
        except (ValueError, OverflowError):
            value = float("nan")
        if not math.isfinite(value):
            logger.warning(
                "Invalid DECISION_%s_THRESHOLD=%r; using default %s",
                key.upper(),
                raw,
                default,
            )
            return cls(default)
        return cls(max(0.0, min(1.0, value)))

    def passes(self, answer: Answer | None) -> bool:
        """True when ``answer.confidence`` is finite and >= threshold."""
        if answer is None:
            return False
        confidence = answer.confidence
        if not isinstance(confidence, (int, float)) or not math.isfinite(
            float(confidence)
        ):
            return False
        return float(confidence) >= self.threshold

    def passes_negative(self, answer: Answer | None) -> bool:
        """True when a ``noul`` answer is confidently FALSE.

        A noul value IS P(yes) — "confidently no" therefore means
        P(yes) is low: ``1 - value >= threshold``. Non-noul kinds,
        missing answers, and non-finite values return False.
        """
        if answer is None or answer.kind != "noul":
            return False
        value = answer.value
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            return False
        return 1 - float(value) >= self.threshold


__all__ = ["DEFAULT_THRESHOLDS", "ConfidenceGate"]
