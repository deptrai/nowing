"""Run-derived memory extraction metric instruments."""

from __future__ import annotations

import contextlib
import logging
from functools import lru_cache

from app.observability.metrics.base import _add, _get_meter

_memory_injection_failure_logger = logging.getLogger("memory_injection.failure")
_memory_injection_truncated_logger = logging.getLogger("memory_injection.truncated")


@lru_cache(maxsize=1)
def _run_memory_enqueued():
    return _get_meter().create_counter(
        "run_memory_enqueued_total",
        description="Count of successful capability runs enqueued for memory extraction.",
    )


@lru_cache(maxsize=1)
def _run_memory_created():
    return _get_meter().create_counter(
        "run_memory_created_total",
        description="Count of durable memories created from capability runs.",
    )


@lru_cache(maxsize=1)
def _run_memory_zero_fact():
    return _get_meter().create_counter(
        "run_memory_zero_fact_total",
        description="Count of run extractions that succeeded but yielded no qualifying fact.",
    )


@lru_cache(maxsize=1)
def _run_memory_skipped():
    return _get_meter().create_counter(
        "run_memory_skipped_total",
        description="Count of run extractions skipped by a gate or policy decision.",
    )


@lru_cache(maxsize=1)
def _run_memory_failed():
    return _get_meter().create_counter(
        "run_memory_failed_total",
        description="Count of run extractions that exhausted their retry budget or failed terminally.",
    )


@lru_cache(maxsize=1)
def _run_memory_retried():
    return _get_meter().create_counter(
        "run_memory_retried_total",
        description="Count of run extraction attempts re-scheduled after a transient failure.",
    )


@lru_cache(maxsize=1)
def _memory_injection_failures():
    return _get_meter().create_counter(
        "nowing.memory.injection.failures",
        description="Count of memory injection failures by scope/stage/reason.",
    )


@lru_cache(maxsize=1)
def _memory_injection_truncated():
    return _get_meter().create_counter(
        "nowing.memory.injection.truncated",
        description="Count of memory injection truncations by scope.",
    )


def record_run_memory_enqueued() -> None:
    """One successful run handed to the extraction queue (AC-9)."""
    _add(_run_memory_enqueued(), 1, {})


def record_run_memory_created(count: int = 1) -> None:
    """``count`` durable memories were committed from one run extraction."""
    if count <= 0:
        return
    _add(_run_memory_created(), count, {})


def record_run_memory_zero_fact() -> None:
    """A run extraction ran the LLM successfully and found nothing worth keeping."""
    _add(_run_memory_zero_fact(), 1, {})


def record_run_memory_skipped(*, reason: str) -> None:
    """A run extraction was skipped before the LLM call."""
    _add(_run_memory_skipped(), 1, {"reason": reason})


def record_run_memory_failed() -> None:
    _add(_run_memory_failed(), 1, {})


def record_run_memory_retried() -> None:
    _add(_run_memory_retried(), 1, {})


def record_memory_injection_failure(*, scope: str, stage: str, reason: str) -> None:
    """Log + count exactly one ordinary memory injection failure attempt (D8)."""
    attrs = {"scope": scope, "stage": stage, "reason": reason}
    with contextlib.suppress(Exception):
        _memory_injection_failure_logger.warning(
            "memory_injection.failure scope=%s stage=%s reason=%s",
            scope,
            stage,
            reason,
            extra=attrs,
        )
    with contextlib.suppress(Exception):
        _add(_memory_injection_failures(), 1, attrs)


def record_memory_injection_truncated(*, scope: str) -> None:
    """Log + count one memory injection truncated to fit the char budget."""
    attrs = {"scope": scope}
    with contextlib.suppress(Exception):
        _memory_injection_truncated_logger.warning(
            "memory_injection.truncated scope=%s", scope, extra=attrs
        )
    with contextlib.suppress(Exception):
        _add(_memory_injection_truncated(), 1, attrs)
