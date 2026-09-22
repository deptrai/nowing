"""Voice semantic gate — one batched decide() per completed STT turn.

Story 39.6: the ``voice_turn`` question set scores each completed STT
transcript for ``should_respond`` (Noul), ``caller_frustration``
(Score 0-3), and ``transfer_to_human`` (Noul) in a single round-trip —
parallel server-side, timeout-clamped to ~0.45s.

Fail-open everywhere: disabled flags, short/noise transcripts, backend
errors, timeouts, and malformed answers all resolve to the default
assessment — respond normally — so the voice loop never dies on the
decision layer.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

import app.config.decision as decision_config
from app.services.decision.gate import ConfidenceGate
from app.services.decision.questions import get_question_registry
from app.services.decision.service import get_decision_service
from app.services.decision.types import Answer

logger = logging.getLogger(__name__)

# Suppression bar, pinned hard (spec 39.6): suppress only when Jev is
# confident the utterance needs NO reply — ``1 - P(respond) >= 0.7``.
# ``ConfidenceGate.passes_negative`` at the task's 0.5 default would
# silence the agent on any answer merely leaning "no" — far too
# trigger-happy for a live call.
VOICE_SUPPRESS_MIN_CONFIDENCE = 0.7

# Escalation bar: transfer only on a confident, explicit request.
VOICE_TRANSFER_MIN_CONFIDENCE = 0.7

# Per-turn decide() budget — keeps the added latency under the 500ms
# acceptance bound. The fallback leg is disabled for voice
# (``use_fallback=False``) because it would double the worst case to
# ~0.9s; a missed decision is preferable to a stalled turn.
VOICE_DECIDE_TIMEOUT_SECONDS = 0.45

# Below this stripped length a transcript is STT noise/debris — not
# worth a paid call, the turn responds per existing behavior. Note the
# check is ``len(transcript.strip())``: interior whitespace still counts.
_MIN_TRANSCRIPT_CHARS = 3

# Long turns are truncated before hitting the paid backend (same cap as
# intent_classification's _MAX_MESSAGE_CHARS).
_MAX_TRANSCRIPT_CHARS = 4000

# Pure Vietnamese backchannels/fillers — exact match after lowercasing
# and punctuation-stripping suppresses locally, no Jev call needed.
# Single-token "yes" words that can answer a real question ("vâng",
# "ok") are deliberately excluded.
LOCAL_BACKCHANNELS: frozenset[str] = frozenset(
    {
        "à",
        "ạ",
        "dạ",
        "ừ",
        "ừm",
        "ừ ừ",
        "ư",
        "ờ",
        "ờm",
        "uhm",
        "um",
        "à ừ",
        "vâng ạ",
    }
)

_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)


def _normalize_transcript(transcript: str) -> str:
    """Lowercase + strip punctuation + collapse whitespace for matching."""
    return " ".join(_PUNCT_RE.sub(" ", transcript.lower()).split())


@dataclass(frozen=True)
class VoiceTurnAssessment:
    """Outcome of the ``voice_turn`` set for one STT turn.

    ``transfer`` takes precedence over ``suppress_response`` — when both
    are set the caller escalates first and ignores suppression.
    """

    suppress_response: bool = False
    transfer: bool = False
    frustration_score: float | None = None


_FAIL_OPEN = VoiceTurnAssessment()


async def evaluate_voice_turn(
    transcript: str,
    *,
    workspace_id: int | None = None,
    user_id: UUID | None = None,
    client_id: str | None = None,
    timeout: float = VOICE_DECIDE_TIMEOUT_SECONDS,
) -> VoiceTurnAssessment:
    """Evaluate one completed STT turn via ``voice_turn@1.0.0``.

    Gated on ``DECISION_ENABLED`` + ``DECISION_VOICE_ENABLED``; when off
    this is a zero-overhead early return — no call, no transcript check.
    Pure backchannels (``LOCAL_BACKCHANNELS``) suppress locally without
    a paid call; other transcripts under ``_MIN_TRANSCRIPT_CHARS`` are
    skipped the same way. No ``session`` param by design —
    ``DecisionService`` opens its own ``AsyncSession`` for telemetry,
    and an ``AgentSession`` is not an ``AsyncSession``. Telemetry
    persists only when both ``workspace_id`` and ``user_id`` are
    present; otherwise the call is log-only. ``client_id`` carries the
    call session id so TokenUsage rows join back to the call. Never
    raises.
    """
    if not (
        decision_config.decision_enabled()
        and decision_config.decision_task_enabled("voice")
    ):
        return _FAIL_OPEN
    if not isinstance(transcript, str):
        return _FAIL_OPEN
    normalized = _normalize_transcript(transcript)
    if normalized in LOCAL_BACKCHANNELS:
        logger.info(
            "[voice_turn] local backchannel suppressed: %r", normalized
        )
        return VoiceTurnAssessment(suppress_response=True)
    if len(transcript.strip()) < _MIN_TRANSCRIPT_CHARS:
        return _FAIL_OPEN

    try:
        qs = get_question_registry().get_set("voice_turn")
        result = await get_decision_service().decide(
            {"transcript": transcript.strip()[:_MAX_TRANSCRIPT_CHARS]},
            # get_set() returns the registry's dict by reference — copy
            # so nothing downstream can corrupt the singleton.
            dict(qs.questions),
            task="voice",
            timeout=timeout,
            use_fallback=False,
            question_set=f"{qs.name}@{qs.version}",
            required_state_keys=qs.required_state_keys,
            workspace_id=workspace_id,
            user_id=user_id,
            client_id=client_id,
        )
    except Exception:
        logger.warning(
            "[voice_turn] decide failed — fail-open respond", exc_info=True
        )
        return _FAIL_OPEN

    try:
        gate = ConfidenceGate.for_task("voice")
        suppress = _confidently_no_respond(result.answers.get("should_respond"))
        transfer = _confident_transfer(
            result.answers.get("transfer_to_human"), gate
        )
        frustration = _score_value(result.answers.get("caller_frustration"))
    except Exception:
        logger.warning(
            "[voice_turn] answer handling failed — fail-open respond",
            exc_info=True,
        )
        return _FAIL_OPEN

    # Frustration is log-only this story — score 2-3 does not act on its
    # own; the structured line feeds future routing/dashboards.
    logger.info(
        "[voice_turn] frustration=%s suppress=%s transfer=%s latency_ms=%.0f",
        frustration,
        suppress,
        transfer,
        result.latency_ms,
    )
    return VoiceTurnAssessment(
        suppress_response=suppress,
        transfer=transfer,
        frustration_score=frustration,
    )


def _noul_value(answer: Answer | None) -> float | None:
    """Finite float value of a noul answer, else None.

    None covers missing answers, wrong kinds, and non-finite values —
    i.e. "uncertain", which must always resolve to respond-normally.
    """
    if answer is None or answer.kind != "noul":
        return None
    value = answer.value
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
    ):
        return None
    return float(value)


def _confidently_no_respond(answer: Answer | None) -> bool:
    """True only when ``should_respond`` is confidently NO at the pinned bar."""
    value = _noul_value(answer)
    return value is not None and 1 - value >= VOICE_SUPPRESS_MIN_CONFIDENCE


def _confident_transfer(answer: Answer | None, gate: ConfidenceGate) -> bool:
    """True only when ``transfer_to_human`` is >= 0.7 AND the task gate passes."""
    value = _noul_value(answer)
    return (
        value is not None
        and value >= VOICE_TRANSFER_MIN_CONFIDENCE
        and gate.passes(answer)
    )


def _score_value(answer: Answer | None) -> float | None:
    """Finite float value of a score answer, else None."""
    if answer is None or answer.kind != "score":
        return None
    value = answer.value
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
    ):
        return None
    return float(value)


__all__ = [
    "LOCAL_BACKCHANNELS",
    "VOICE_DECIDE_TIMEOUT_SECONDS",
    "VOICE_SUPPRESS_MIN_CONFIDENCE",
    "VOICE_TRANSFER_MIN_CONFIDENCE",
    "VoiceTurnAssessment",
    "evaluate_voice_turn",
]
