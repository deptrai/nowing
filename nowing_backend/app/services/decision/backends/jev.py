"""Jev backend — TypeSafe System One via ``typesafe-sdk`` (AD-J3).

This is the ONLY module in the codebase allowed to import
``typesafe_sdk`` (AD-J1); the import is lazy so the rest of the app runs
without the SDK installed.

Failures (5xx, 529 Overloaded, timeout, connection, missing
``TYPESAFE_API_KEY``, missing SDK) all surface as ``DecisionError`` —
the LLM fallback chain is a deferred story, so callers fall back to
their existing behavior.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from app.services.decision.errors import DecisionError, InvalidDecisionAnswer
from app.services.decision.types import (
    Answer,
    BackendResult,
    ChoiceQuestion,
    NoulQuestion,
    Question,
    ScoreQuestion,
)

logger = logging.getLogger(__name__)


def _to_sdk_question(question: Question) -> Any:
    """Map our backend-agnostic question onto a typesafe_sdk question."""
    from typesafe_sdk import Choice, Noul, Score

    if isinstance(question, ChoiceQuestion):
        return Choice(
            instructions=question.instructions,
            criteria=dict(question.criteria),
        )
    if isinstance(question, ScoreQuestion):
        return Score(
            instructions=question.instructions,
            criteria=list(question.criteria),
        )
    if isinstance(question, NoulQuestion):
        return Noul(
            instructions=question.instructions,
            criteria=question.criteria,
        )
    raise DecisionError(
        f"Unsupported question type {type(question).__name__!r} for Jev backend",
        code="backend_error",
    )


def _get(obj: Any, attr: str) -> Any:
    """Attr-or-key access — the SDK returns pydantic models, but stay
    defensive in case a test double or future SDK hands us dicts."""
    value = getattr(obj, attr, None)
    if value is None and isinstance(obj, dict):
        value = obj.get(attr)
    return value


def _require_field(raw: Any, attr: str, kind: str) -> Any:
    value = _get(raw, attr)
    if value is None:
        raise InvalidDecisionAnswer(f"{kind} answer is missing {attr!r}")
    return value


def _from_sdk_answer(raw: Any) -> Answer:
    """Normalize a typesafe_sdk answer object into our ``Answer`` shape.

    Missing/unrecognized fields raise ``InvalidDecisionAnswer`` — the
    answer is malformed, not a transport failure, so it must not be
    retried as a backend error.
    """
    kind = _get(raw, "type")
    if kind == "choice":
        probs = _get(raw, "probabilities") or {}
        return Answer(
            kind="choice",
            value=str(_require_field(raw, "choice", "choice")),
            confidence=float(_get(raw, "confidence") or 0.0),
            probabilities={str(k): float(v) for k, v in probs.items()},
        )
    if kind == "score":
        probs = _get(raw, "probabilities") or {}
        return Answer(
            kind="score",
            value=float(_require_field(raw, "score", "score")),
            confidence=float(_get(raw, "confidence") or 0.0),
            # SDK keys probabilities by int level index; normalize to str.
            probabilities={str(k): float(v) for k, v in probs.items()},
        )
    if kind == "noul":
        noul = float(_require_field(raw, "noul", "noul"))
        # A noul IS a probability — it doubles as its own confidence so
        # ConfidenceGate can treat every answer kind uniformly.
        return Answer(kind="noul", value=noul, confidence=noul, probabilities=None)
    raise InvalidDecisionAnswer(f"Jev returned an unrecognized answer type {kind!r}")


class JevBackend:
    """``AsyncTypeSafeClient`` adapter implementing ``DecisionBackend``."""

    name = "jev"

    def __init__(self, *, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("TYPESAFE_API_KEY")
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise DecisionError(
                "TYPESAFE_API_KEY is not set — Jev backend unavailable",
                code="missing_api_key",
            )
        try:
            from typesafe_sdk import AsyncTypeSafeClient
        except ImportError as exc:
            raise DecisionError(
                "typesafe-sdk is not installed — Jev backend unavailable",
                code="backend_unavailable",
            ) from exc
        self._client = AsyncTypeSafeClient(api_key=self._api_key)
        return self._client

    async def decide(
        self,
        state: dict[str, Any],
        questions: dict[str, Question],
        *,
        model: str | None = None,
        timeout: float | None = None,
    ) -> BackendResult:
        client = self._ensure_client()
        q_objects = {qid: _to_sdk_question(q) for qid, q in questions.items()}

        start = time.perf_counter()
        try:
            # The SDK accepts its own timeout; asyncio.wait_for is the
            # hard ceiling (DECISION_TIMEOUT_SECONDS) in case the SDK's
            # handling misbehaves.
            response = await asyncio.wait_for(
                client.system_one(
                    state=state,
                    questions=q_objects,
                    model=model,
                    timeout=timeout,
                ),
                timeout=timeout,
            )
        except DecisionError:
            raise
        except TimeoutError as exc:
            # asyncio.TimeoutError is an alias of builtin TimeoutError.
            raise DecisionError("Jev request timed out", code="timeout") from exc
        except Exception as exc:
            # SDK raises TypeSafeAPIError subclasses for 5xx/529/4xx and
            # TypeSafeAPITimeoutError/TypeSafeAPIConnectionError for
            # transport issues — all mean "caller falls back". The full
            # exception may embed request data — log it, don't
            # interpolate it into the error message.
            logger.exception("Jev request failed")
            raise DecisionError(
                f"Jev request failed: {type(exc).__name__}",
                code="backend_error",
            ) from exc
        latency_ms = (time.perf_counter() - start) * 1000

        raw_answers = _get(response, "answers") or {}
        try:
            answers = {qid: _from_sdk_answer(a) for qid, a in raw_answers.items()}
        except InvalidDecisionAnswer:
            raise
        except Exception as exc:
            # Any normalization failure (missing/oddly-typed fields) is a
            # malformed answer, not a transport error.
            logger.exception("Failed to normalize Jev answers")
            raise InvalidDecisionAnswer(
                f"failed to normalize Jev answers: {type(exc).__name__}"
            ) from exc
        usage = _get(response, "usage")
        return BackendResult(
            answers=answers,
            model=_get(response, "model") or model or "jev-unknown",
            latency_ms=latency_ms,
            input_tokens=_get(usage, "input_tokens") if usage else None,
            output_tokens=_get(usage, "output_tokens") if usage else None,
        )
