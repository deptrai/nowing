"""Map LiteLLM completion exceptions to domain errors."""

from __future__ import annotations

import time
from typing import Any

from langchain_core.exceptions import ContextOverflowError
from litellm.exceptions import (
    BadRequestError as LiteLLMBadRequestError,
    ContextWindowExceededError,
)

from app.services.llm_router.constants import _is_context_overflow_error


def _log_context_overflow(
    perf: Any,
    stage: str,
    msg_count: int,
    elapsed: float,
) -> None:
    """Emit a consistent context-overflow perf log."""
    perf.warning(
        "[llm_router] %s CONTEXT_OVERFLOW msgs=%d in %.3fs",
        stage,
        msg_count,
        elapsed,
    )


def _raise_if_context_overflow(exc: Exception) -> None:
    """Raise ``ContextOverflowError`` if *exc* signals a context window
    overflow; otherwise return without raising."""
    if isinstance(exc, ContextWindowExceededError):
        raise ContextOverflowError(str(exc)) from exc
    if isinstance(exc, LiteLLMBadRequestError) and _is_context_overflow_error(exc):
        raise ContextOverflowError(str(exc)) from exc


def handle_completion_error(
    exc: Exception,
    *,
    perf: Any,
    stage: str,
    msg_count: int,
    t0: float | None = None,
) -> None:
    """Raise the correct domain exception for a LiteLLM router error.

    Logs and re-raises ``ContextOverflowError`` for context-window failures;
    otherwise lets the original exception propagate.
    """
    elapsed = time.perf_counter() - t0 if t0 is not None else 0.0
    try:
        _raise_if_context_overflow(exc)
    except ContextOverflowError:
        _log_context_overflow(perf, stage, msg_count, elapsed)
        raise
    raise exc


def handle_streaming_error(
    exc: Exception,
) -> None:
    """Raise the correct domain exception for a LiteLLM streaming error."""
    _raise_if_context_overflow(exc)
    raise exc


__all__ = [
    "handle_completion_error",
    "handle_streaming_error",
]
