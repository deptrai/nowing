"""DecisionService — the single port for typed decisions (AD-J1).

Callers use only ``DecisionService.decide(state, questions)``. The
service owns flag gating, backend selection, strict answer validation,
and TokenUsage telemetry; backends and the question registry are
implementation details behind it.

Error contract (both mean "caller falls back to existing behavior"):

- ``DecisionError`` — disabled flag, missing API key, Jev 5xx/529/
  timeout/transport failure.
- ``InvalidDecisionAnswer`` — backend answered but the answer failed
  strict structural validation; never becomes an action.
"""

from __future__ import annotations

import asyncio
import logging
import math
from typing import TYPE_CHECKING, Any

import app.config.decision as decision_config
from app.services.decision.backends.base import DecisionBackend
from app.services.decision.errors import DecisionError, InvalidDecisionAnswer
from app.services.decision.types import (
    Answer,
    BackendResult,
    DecisionResult,
    Question,
)
from app.services.decision.validation import validate_answer

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class DecisionService:
    """Facade: flag gate → backend → strict validation → telemetry."""

    def __init__(self, backend: DecisionBackend | None = None) -> None:
        # Lazy: the configured backend is resolved inside decide() AFTER
        # the flag checks, so an unavailable DECISION_BACKEND cannot
        # break get_decision_service() while the feature is disabled.
        # An injected backend always takes precedence.
        self._backend = backend

    def _get_backend(self) -> DecisionBackend:
        if self._backend is None:
            self._backend = _build_backend()
        return self._backend

    async def decide(
        self,
        state: dict[str, Any],
        questions: dict[str, Question],
        *,
        task: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        question_set: str | None = None,
        session: AsyncSession | None = None,
        workspace_id: int | None = None,
        user_id: UUID | None = None,
        client_id: str | None = None,
    ) -> DecisionResult:
        """Evaluate ``questions`` against ``state``.

        ``task`` is the caller's task name ("routing", "filter",
        "entity", "intent", "voice") — it gates the call on
        ``DECISION_{TASK}_ENABLED`` and is recorded for telemetry.
        Task-less calls (``task=None``) are gated only by the master
        flag and recorded as ``"generic"``.

        ``question_set`` is an optional registry label recorded in
        telemetry for drift tracking — e.g. ``"subagent_routing@1.0.0"``
        built from ``registry.get_set(name)``.

        ``session``/``workspace_id``/``user_id`` are optional; when all
        are provided the call's token usage is persisted to
        ``TokenUsage`` (fail-open).
        """
        if not decision_config.decision_enabled():
            raise DecisionError(
                "Decision service is disabled (DECISION_ENABLED=false)",
                code="disabled",
            )
        if task is not None and not decision_config.decision_task_enabled(task):
            raise DecisionError(
                f"Decision task {task!r} is disabled "
                f"(DECISION_{task.upper()}_ENABLED=false)",
                code="disabled",
            )
        if not questions:
            raise DecisionError(
                "questions must be a non-empty dict",
                code="invalid_request",
            )
        # AD-J3: the model is pinned — a caller may not override it to
        # "jev-latest" or any other value.
        if model is not None and model != decision_config.DECISION_JEV_MODEL:
            raise DecisionError(
                f"model {model!r} is not allowed — the Jev model is pinned "
                f"to {decision_config.DECISION_JEV_MODEL!r}",
                code="invalid_model",
            )
        model = decision_config.DECISION_JEV_MODEL
        if timeout is None:
            timeout = decision_config.DECISION_TIMEOUT_SECONDS
        else:
            # Clamp into [0.1, DECISION_TIMEOUT_SECONDS] — callers can
            # tighten but never exceed the configured ceiling.
            timeout = min(
                max(float(timeout), 0.1), decision_config.DECISION_TIMEOUT_SECONDS
            )
        if not math.isfinite(timeout):
            # nan slips through min/max (all comparisons False) — fall
            # back to the ceiling rather than hand wait_for a NaN delay.
            timeout = decision_config.DECISION_TIMEOUT_SECONDS

        backend = self._get_backend()
        try:
            # Port-level hard ceiling — enforced here so it holds for
            # every backend, not just Jev's internal timeout handling.
            backend_result = await asyncio.wait_for(
                backend.decide(state, questions, model=model, timeout=timeout),
                timeout=timeout,
            )
        except TimeoutError as exc:
            # asyncio.TimeoutError is an alias of builtin TimeoutError.
            raise DecisionError(
                f"decision timed out after {timeout}s",
                code="timeout",
            ) from exc
        except DecisionError:
            raise
        except Exception as exc:
            # Backends must raise DecisionError; wrap stragglers so
            # callers only ever see the documented taxonomy. The full
            # exception may embed request data — log it, don't
            # interpolate it into the error message.
            logger.exception("Decision backend %r failed", backend.name)
            raise DecisionError(
                f"Decision backend {backend.name!r} failed: {type(exc).__name__}",
                code="backend_error",
            ) from exc

        task_label = task or "generic"
        try:
            if not isinstance(backend_result.answers, dict):
                raise InvalidDecisionAnswer("backend returned non-dict answers")
            answers = {
                qid: validate_answer(
                    self._require_answer(backend_result, qid), question
                )
                for qid, question in questions.items()
            }
        finally:
            # Tokens were consumed even when validation rejects the
            # answers — always log + persist (fail-open) per AD-J7.
            logger.info(
                "[decision] backend=%s model=%s task=%s question_set=%s "
                "latency_ms=%.0f input_tokens=%s output_tokens=%s",
                backend.name,
                backend_result.model,
                task_label,
                question_set,
                backend_result.latency_ms,
                backend_result.input_tokens,
                backend_result.output_tokens,
            )
            await self._record_usage(
                backend_result,
                task=task_label,
                question_set=question_set,
                questions=questions,
                session=session,
                workspace_id=workspace_id,
                user_id=user_id,
                client_id=client_id,
            )

        return DecisionResult(
            answers=answers,
            model=backend_result.model,
            backend=backend.name,
            latency_ms=backend_result.latency_ms,
            input_tokens=backend_result.input_tokens,
            output_tokens=backend_result.output_tokens,
        )

    @staticmethod
    def _require_answer(backend_result: BackendResult, qid: str) -> Any:
        answer = backend_result.answers.get(qid)
        if answer is None:
            raise InvalidDecisionAnswer(
                f"backend returned no answer for question {qid!r}"
            )
        return answer

    async def _record_usage(
        self,
        backend_result: BackendResult,
        *,
        task: str,
        question_set: str | None,
        questions: dict[str, Question],
        session: AsyncSession | None,
        workspace_id: int | None,
        user_id: UUID | None,
        client_id: str | None,
    ) -> None:
        """Persist the call to ``TokenUsage``. Fail-open (AD-J7)."""
        if session is None or workspace_id is None or user_id is None:
            logger.debug(
                "Decision usage not persisted — missing session/workspace_id/user_id"
            )
            return
        try:
            from app.services.token_tracking_service import (
                UsageType,
                record_token_usage,
            )

            input_tokens = backend_result.input_tokens or 0
            output_tokens = backend_result.output_tokens or 0
            await record_token_usage(
                session,
                usage_type=UsageType.DECISION,
                workspace_id=workspace_id,
                user_id=user_id,
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                e2e_ms=round(backend_result.latency_ms),
                call_details={
                    "backend": self._get_backend().name,
                    "model": backend_result.model,
                    "latency_ms": backend_result.latency_ms,
                    "task": task,
                    "question_set": question_set,
                    # requested ids, not just answered ones
                    "questions": sorted(questions),
                },
                client_id=client_id,
            )
        except Exception:  # best-effort telemetry; never abort a decision
            logger.warning(
                "Failed to record decision token usage; continuing",
                exc_info=True,
            )


def _build_backend() -> DecisionBackend:
    """Resolve the configured backend (AD-J2, factory-by-config)."""
    backend = decision_config.DECISION_BACKEND
    if backend == "jev":
        from app.services.decision.backends.jev import JevBackend

        return JevBackend()
    if backend == "mock":
        logger.warning(
            "Decision backend is 'mock' — deterministic answers, not real Jev decisions"
        )
        from app.services.decision.backends.mock import MockBackend

        return MockBackend()
    # "llm_json" is reserved — LLM fallback chain is a deferred story.
    raise DecisionError(
        f"Decision backend {backend!r} is not available in this build",
        code="backend_unavailable",
    )


_decision_service: DecisionService | None = None


def get_decision_service() -> DecisionService:
    """Get or create the process-wide ``DecisionService`` singleton."""
    global _decision_service
    if _decision_service is None:
        _decision_service = DecisionService()
    return _decision_service


__all__ = [
    "Answer",
    "DecisionResult",
    "DecisionService",
    "get_decision_service",
]
