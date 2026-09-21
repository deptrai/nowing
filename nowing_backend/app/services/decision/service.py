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
import time
from collections.abc import Iterable
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
        required_state_keys: Iterable[str] | None = None,
        session: AsyncSession | None = None,
        workspace_id: int | None = None,
        user_id: UUID | None = None,
        client_id: str | None = None,
        thread_id: int | None = None,
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

        ``required_state_keys`` is an optional list of state keys the
        caller's questions need (registry sets expose them as
        ``QuestionSet.required_state_keys``). When provided, any missing
        key raises ``invalid_request`` BEFORE the backend is resolved —
        a malformed call never reaches a paid leg.

        ``session``/``workspace_id``/``user_id`` are optional; when all
        are provided the call's token usage is persisted to
        ``TokenUsage`` (fail-open). ``thread_id`` is forwarded to that
        row so decision spend can be joined back to the chat thread.

        ``model`` is validated against the ACTIVE backend's pin (AD-J3):
        for a Jev primary it must equal ``DECISION_JEV_MODEL`` — passing
        ``DECISION_LLM_MODEL`` raises ``invalid_model`` even though the
        fallback leg would accept it. The pin binds to the backend that
        takes the first call, not to whichever leg ends up answering.

        Fallback (story 39.1b): when the primary backend raises a
        ``DecisionError`` with code ``timeout``, ``backend_error``,
        ``backend_unavailable`` or ``missing_api_key``, the request is
        retried once through ``DECISION_FALLBACK_BACKEND`` (default
        ``llm_json``, ``"none"`` disables). ``InvalidDecisionAnswer``
        and caller errors never fall back — a malformed answer is not
        worth a second paid call. The fallback leg gets its own
        ``wait_for`` with the same clamped timeout, so worst-case
        latency is 2 x ``DECISION_TIMEOUT_SECONDS``; the result and
        telemetry always describe the leg that actually answered.
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
        if required_state_keys is not None:
            missing = sorted(set(required_state_keys) - state.keys())
            if missing:
                raise DecisionError(
                    f"decision state is missing required keys: {missing}",
                    code="invalid_request",
                )
        try:
            backend = self._get_backend()
        except DecisionError as exc:
            # A construction-time failure (e.g. an unrecognized
            # DECISION_BACKEND → backend_unavailable) uses the same
            # fallback trigger set as a failed primary call — the
            # fallback leg then becomes THE backend for this call.
            backend = None
            if exc.code in _FALLBACK_TRIGGER_CODES:
                logger.warning(
                    "Decision backend resolution failed (code=%s) — "
                    "trying the fallback backend",
                    exc.code,
                )
                backend = _try_build_fallback(decision_config.DECISION_BACKEND)
            if backend is None:
                raise
        # AD-J3: the model is pinned per backend — a caller may not
        # override it to "jev-latest" or any other value.
        pinned_model = _pinned_model(backend.name)
        if model is not None and model != pinned_model:
            raise DecisionError(
                f"model {model!r} is not allowed — backend {backend.name!r} "
                f"is pinned to {pinned_model!r}",
                code="invalid_model",
            )
        model = pinned_model
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

        # Per-leg telemetry: every attempted leg is recorded so a failed
        # primary leg stays visible when a fallback leg wins (or fails).
        legs: list[dict[str, Any]] = []
        leg_start = time.perf_counter()
        try:
            backend_result = await self._call_backend(
                backend, state, questions, model=model, timeout=timeout
            )
            legs.append(
                {
                    "backend": backend.name,
                    "model": backend_result.model,
                    "latency_ms": backend_result.latency_ms,
                    "outcome": "ok",
                }
            )
        except DecisionError as exc:
            legs.append(
                {
                    "backend": backend.name,
                    "model": model,
                    "latency_ms": (time.perf_counter() - leg_start) * 1000,
                    "outcome": exc.code,
                }
            )
            if exc.code not in _FALLBACK_TRIGGER_CODES:
                raise
            fallback = _try_build_fallback(backend.name)
            if fallback is None:
                raise
            # The fallback leg runs under its own wait_for with the same
            # clamped timeout — worst-case decide() latency is therefore
            # 2 x DECISION_TIMEOUT_SECONDS.
            logger.warning(
                "Decision backend %r failed (code=%s) — retrying once "
                "via fallback backend %r",
                backend.name,
                exc.code,
                fallback.name,
            )
            backend = fallback
            model = _pinned_model(backend.name)
            leg_start = time.perf_counter()
            try:
                backend_result = await self._call_backend(
                    backend,
                    state,
                    questions,
                    model=model,
                    timeout=timeout,
                )
                legs.append(
                    {
                        "backend": backend.name,
                        "model": backend_result.model,
                        "latency_ms": backend_result.latency_ms,
                        "outcome": "ok",
                    }
                )
            except DecisionError as fallback_exc:
                legs.append(
                    {
                        "backend": backend.name,
                        "model": model,
                        "latency_ms": (time.perf_counter() - leg_start) * 1000,
                        "outcome": fallback_exc.code,
                    }
                )
                # Surface the failed leg — its attempt is otherwise
                # invisible since telemetry only records the winning
                # leg. The synthetic BackendResult carries no token
                # counts (None → 0): the attempt becomes visible
                # without fabricating spend.
                logger.warning(
                    "Fallback decision backend %r also failed (code=%s): %s",
                    backend.name,
                    fallback_exc.code,
                    fallback_exc,
                )
                await self._record_usage(
                    BackendResult(
                        answers={}, model=model, latency_ms=legs[-1]["latency_ms"]
                    ),
                    backend_name=backend.name,
                    task=task or "generic",
                    question_set=question_set,
                    questions=questions,
                    session=session,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    client_id=client_id,
                    thread_id=thread_id,
                    extra_call_details={
                        "failed": True,
                        "error_code": fallback_exc.code,
                        "legs": legs,
                    },
                )
                raise

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
                backend_name=backend.name,
                task=task_label,
                question_set=question_set,
                questions=questions,
                session=session,
                workspace_id=workspace_id,
                user_id=user_id,
                client_id=client_id,
                thread_id=thread_id,
                # Only a multi-leg call (a fallback actually ran) exposes
                # the per-leg trace — a single-leg success stays terse.
                extra_call_details={"legs": legs} if len(legs) > 1 else None,
            )

        return DecisionResult(
            answers=answers,
            model=backend_result.model,
            backend=backend.name,
            latency_ms=backend_result.latency_ms,
            input_tokens=backend_result.input_tokens,
            output_tokens=backend_result.output_tokens,
        )

    async def _call_backend(
        self,
        backend: DecisionBackend,
        state: dict[str, Any],
        questions: dict[str, Question],
        *,
        model: str,
        timeout: float,
    ) -> BackendResult:
        """One backend leg: call + port-level ceiling + error taxonomy."""
        try:
            # Port-level hard ceiling — enforced here so it holds for
            # every backend, not just Jev's internal timeout handling.
            return await asyncio.wait_for(
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
        backend_name: str,
        task: str,
        question_set: str | None,
        questions: dict[str, Question],
        session: AsyncSession | None,
        workspace_id: int | None,
        user_id: UUID | None,
        client_id: str | None,
        thread_id: int | None = None,
        extra_call_details: dict[str, Any] | None = None,
    ) -> None:
        """Persist the call to ``TokenUsage``. Fail-open (AD-J7).

        ``extra_call_details`` is merged over the standard call_details
        keys — callers use it for per-leg traces and failure markers.
        """
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
                    "backend": backend_name,
                    "model": backend_result.model,
                    "latency_ms": backend_result.latency_ms,
                    "task": task,
                    "question_set": question_set,
                    # requested ids, not just answered ones
                    "questions": sorted(questions),
                    **(extra_call_details or {}),
                },
                client_id=client_id,
                thread_id=thread_id,
            )
        except Exception:  # best-effort telemetry; never abort a decision
            logger.warning(
                "Failed to record decision token usage; continuing",
                exc_info=True,
            )


# Primary-leg failure codes that may retry once via the fallback
# backend (story 39.1b). InvalidDecisionAnswer and caller errors
# (disabled / invalid_request / invalid_model) are deliberately absent —
# malformed answers and bad calls must not re-pay for a second leg.
_FALLBACK_TRIGGER_CODES = frozenset(
    {"timeout", "backend_error", "backend_unavailable", "missing_api_key"}
)


def _pinned_model(backend_name: str) -> str:
    """The model a backend is pinned to (AD-J3, backend-aware).

    Unknown names — e.g. injected test stubs — keep the historical Jev
    pin so pre-39.1b call sites behave exactly as before.
    """
    pinned = {
        "jev": decision_config.DECISION_JEV_MODEL,
        "llm_json": decision_config.DECISION_LLM_MODEL,
        "mock": decision_config.DECISION_JEV_MODEL,
    }
    return pinned.get(backend_name, decision_config.DECISION_JEV_MODEL)


def _build_backend() -> DecisionBackend:
    """Resolve the configured backend (AD-J2, factory-by-config)."""
    backend = decision_config.DECISION_BACKEND
    if backend == "jev":
        from app.services.decision.backends.jev import JevBackend

        return JevBackend()
    if backend == "llm_json":
        from app.services.decision.backends.llm_json import LLMJsonBackend

        return LLMJsonBackend()
    if backend == "mock":
        logger.warning(
            "Decision backend is 'mock' — deterministic answers, not real Jev decisions"
        )
        from app.services.decision.backends.mock import MockBackend

        return MockBackend()
    raise DecisionError(
        f"Decision backend {backend!r} is not available in this build",
        code="backend_unavailable",
    )


def _try_build_fallback(primary_name: str) -> DecisionBackend | None:
    """Build the fallback leg backend, tolerating construction failure.

    A raise inside the builder must never mask the primary's error —
    it logs a warning and returns ``None`` so the caller re-raises the
    original ``DecisionError``.
    """
    try:
        return _build_fallback_backend(primary_name)
    except Exception:
        logger.warning(
            "Failed to construct fallback decision backend (primary=%r)",
            primary_name,
            exc_info=True,
        )
        return None


def _build_fallback_backend(primary_name: str) -> DecisionBackend | None:
    """Resolve the fallback leg backend (story 39.1b chain).

    Returns ``None`` when ``DECISION_FALLBACK_BACKEND=none``, when the
    configured fallback is the backend that just failed (an llm_json →
    llm_json retry would double the cost for the same systemic failure —
    litellm already retries transient errors once via ``num_retries``),
    or when the primary is ``mock`` — a deterministic/offline backend
    must never trigger a paid LLM call.
    """
    choice = decision_config.DECISION_FALLBACK_BACKEND
    if choice == "none":
        return None
    if choice == "llm_json":
        if primary_name in ("llm_json", "mock"):
            return None
        from app.services.decision.backends.llm_json import LLMJsonBackend

        return LLMJsonBackend()
    logger.warning("Unrecognized DECISION_FALLBACK_BACKEND=%r — no fallback", choice)
    return None


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
