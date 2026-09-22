"""Intent classification — one ``decide()`` runs the ``intent_classify``
Choice set over a user chat message and returns a ``{"label",
"confidence", "model", "backend"}`` payload the caller stores on the
user row's ``platform_metadata["intent"]`` (Story 39.5).

Fail-open everywhere: empty messages, disabled flags, backend errors,
timeouts, and malformed answers all resolve to ``None`` (logged, never
raised) so a dead backend silently disables labeling instead of breaking
chat persistence. The label is advisory storage only — nothing blocks,
reroutes, or answers based on it. Telemetry is log-only
(``[intent_classify]``): the persist context carries no request
``session``/``workspace_id``, so no TokenUsage row is written.
"""

from __future__ import annotations

import logging
from typing import Any

import app.config.decision as decision_config
from app.services.decision.gate import ConfidenceGate
from app.services.decision.questions import get_question_registry
from app.services.decision.service import get_decision_service

logger = logging.getLogger(__name__)

# Long messages are truncated before hitting the paid backend (same cap
# as content_guardrails' _MAX_PASSAGE_CHARS).
_MAX_MESSAGE_CHARS = 4000


async def classify_intent(user_message: str) -> dict[str, Any] | None:
    """Classify ``user_message`` via the ``intent_classify@1.0.0`` set.

    Returns ``{"label", "confidence", "model", "backend"}`` when the
    choice answer passes ``ConfidenceGate.for_task("intent")``
    (``DECISION_INTENT_THRESHOLD``, default 0.5); ``None`` otherwise —
    below threshold, flag off, empty input, or any backend/validation
    failure. Never raises.

    Below-gate labels are deliberately NOT returned: downstream
    automation triggers read ``label`` naively, so storing a
    low-confidence guess would poison them. The info log keeps them
    observable for threshold tuning.
    """
    # isinstance guard: a truthy non-str input has no .strip() — the
    # "never raises" contract must hold even for malformed caller input.
    if not isinstance(user_message, str) or not user_message.strip():
        return None
    if not (
        decision_config.decision_enabled()
        and decision_config.decision_task_enabled("intent")
    ):
        return None

    try:
        qs = get_question_registry().get_set("intent_classify")
        result = await get_decision_service().decide(
            {"user_message": user_message[:_MAX_MESSAGE_CHARS]},
            # get_set() returns the registry's dict by reference — copy
            # so nothing downstream can corrupt the singleton.
            dict(qs.questions),
            task="intent",
            question_set=f"{qs.name}@{qs.version}",
            required_state_keys=qs.required_state_keys,
        )
        answer = result.answers.get("intent")
        gate = ConfidenceGate.for_task("intent")
        if not gate.passes(answer):
            logger.info(
                "[intent_classify] below gate: label=%s confidence=%s "
                "threshold=%.2f — not stored",
                getattr(answer, "value", None),
                getattr(answer, "confidence", None),
                gate.threshold,
            )
            return None
        payload: dict[str, Any] = {
            "label": answer.value,
            "confidence": answer.confidence,
            "model": result.model,
            "backend": result.backend,
        }
    except Exception:
        logger.warning(
            "[intent_classify] classify failed — fail-open None",
            exc_info=True,
        )
        return None

    logger.info(
        "[intent_classify] label=%s confidence=%s model=%s backend=%s latency_ms=%.0f",
        payload["label"],
        payload["confidence"],
        payload["model"],
        payload["backend"],
        result.latency_ms,
    )
    return payload


__all__ = ["classify_intent"]
