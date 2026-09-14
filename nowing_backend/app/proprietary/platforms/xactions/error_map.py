"""Centralized XACT_* error to task-behavior mapping (AD-10 / Story 36.3).

Decouples XActions protocol-level error codes from task execution logic.
Pure logic module: NO Celery imports or framework retry execution allowed here.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class TaskBehavior(StrEnum):
    """Execution behavior requested by an error resolution."""

    RETRY = "retry"
    PAUSE = "pause"
    HALT = "halt"
    RAISE = "raise"


@dataclass(frozen=True)
class BehaviorDecision:
    """Resolved task behavior and associated scheduling metadata."""

    behavior: TaskBehavior
    countdown: int | None = None
    max_retries: int | None = None
    cooldown_seconds: int | None = None
    reason: str = ""
    suggested_action: str | None = None
    exhausted_behavior: TaskBehavior | None = None
    write_dlq: bool = False
    code: str = ""


def clamp_countdown(
    v: Any,
    default: int = 30,
    lo: int = 5,
    hi: int = 3600,
) -> int:
    """Coerce and clamp a countdown value safely within [lo, hi].

    Returns `default` (clamped to [lo, hi]) if `v` is None, bool, non-numeric,
    not finite, or <= 0.
    """
    if v is None or isinstance(v, bool):
        return max(lo, min(default, hi))
    try:
        val = float(v)
        if not math.isfinite(val) or val <= 0:
            return max(lo, min(default, hi))
        return max(lo, min(int(val), hi))
    except (TypeError, ValueError, OverflowError):
        return max(lo, min(default, hi))


def clamp_cooldown(
    v: Any,
    default: int = 600,
    lo: int = 60,
    hi: int = 86400,
) -> int:
    """Coerce and clamp a cooldown value safely within [lo, hi].

    Returns `default` (clamped to [lo, hi]) if `v` is None, bool, non-numeric,
    not finite, or <= 0.
    """
    if v is None or isinstance(v, bool):
        return max(lo, min(default, hi))
    try:
        val = float(v)
        if not math.isfinite(val) or val <= 0:
            return max(lo, min(default, hi))
        return max(lo, min(int(val), hi))
    except (TypeError, ValueError, OverflowError):
        return max(lo, min(default, hi))


def _extract_message(exc: Any) -> str:
    msg = getattr(exc, "message", None)
    if msg is not None and str(msg).strip():
        return str(msg)
    rendered = str(exc)
    if rendered.strip():
        return rendered
    raw_code = getattr(exc, "code", None)
    return f"{exc.__class__.__name__} (code={raw_code})"


XACT_ERROR_BEHAVIOR: dict[str, Callable[[Any], BehaviorDecision]] = {
    "XACT_4291": lambda e: BehaviorDecision(
        behavior=TaskBehavior.RETRY,
        countdown=clamp_countdown(getattr(e, "retry_after", None)),
        max_retries=5,
        exhausted_behavior=TaskBehavior.HALT,
        write_dlq=False,
        code="XACT_4291",
        reason=_extract_message(e),
        suggested_action=getattr(e, "suggested_action", None),
    ),
    "ACCOUNT_HIBERNATION": lambda e: BehaviorDecision(
        behavior=TaskBehavior.PAUSE,
        cooldown_seconds=clamp_cooldown(getattr(e, "retry_after", None)),
        code="ACCOUNT_HIBERNATION",
        reason=_extract_message(e),
        suggested_action=getattr(e, "suggested_action", None),
    ),
    "PROXY_EXHAUSTED": lambda e: BehaviorDecision(
        behavior=TaskBehavior.PAUSE,
        cooldown_seconds=clamp_cooldown(getattr(e, "retry_after", None)),
        code="PROXY_EXHAUSTED",
        reason=_extract_message(e),
        suggested_action=getattr(e, "suggested_action", None),
    ),
    "XACT_5030": lambda e: BehaviorDecision(
        behavior=TaskBehavior.PAUSE,
        cooldown_seconds=clamp_cooldown(getattr(e, "retry_after", None)),
        code="XACT_5030",
        reason=_extract_message(e),
        suggested_action=getattr(e, "suggested_action", None),
    ),
    "XACT_4010": lambda e: BehaviorDecision(
        behavior=TaskBehavior.HALT,
        code="XACT_4010",
        reason=_extract_message(e),
        suggested_action=getattr(e, "suggested_action", None),
    ),
    "XACT_5000": lambda e: BehaviorDecision(
        behavior=TaskBehavior.RETRY,
        countdown=60,
        max_retries=3,
        exhausted_behavior=TaskBehavior.HALT,
        write_dlq=True,
        code="XACT_5000",
        reason=_extract_message(e),
        suggested_action=getattr(e, "suggested_action", None),
    ),
    "XACT_4001": lambda e: BehaviorDecision(
        behavior=TaskBehavior.PAUSE,
        cooldown_seconds=clamp_cooldown(getattr(e, "retry_after", None)),
        code="XACT_4001",
        reason=_extract_message(e),
        suggested_action=getattr(e, "suggested_action", None),
    ),
}


def resolve_task_behavior(
    exc: Any,
    default: TaskBehavior = TaskBehavior.PAUSE,
) -> BehaviorDecision:
    """Resolve an exception into a BehaviorDecision via XACT_ERROR_BEHAVIOR map.

    Coerces exc.code with str().strip().upper(). Unmapped, None, or non-string
    codes return default behavior (PAUSE) with clamped cooldown and no KeyError.
    """
    raw_code = getattr(exc, "code", None)
    code = str(raw_code).strip().upper() if raw_code is not None else ""
    handler = XACT_ERROR_BEHAVIOR.get(code)
    if handler is not None:
        return handler(exc)

    msg = _extract_message(exc)
    cooldown = (
        clamp_cooldown(getattr(exc, "retry_after", None))
        if default is TaskBehavior.PAUSE
        else None
    )
    countdown = (
        clamp_countdown(getattr(exc, "retry_after", None))
        if default is TaskBehavior.RETRY
        else None
    )
    return BehaviorDecision(
        behavior=default,
        countdown=countdown,
        cooldown_seconds=cooldown,
        code=code,
        reason=f"unmapped code {raw_code}: {msg}",
        suggested_action=getattr(exc, "suggested_action", None),
    )


__all__ = [
    "XACT_ERROR_BEHAVIOR",
    "BehaviorDecision",
    "TaskBehavior",
    "clamp_cooldown",
    "clamp_countdown",
    "resolve_task_behavior",
]
