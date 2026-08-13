"""Cron math wrapper for the alert engine.

Reuses the battle-tested schedule cron helper from Epic 6 automation triggers.
"""

from __future__ import annotations

from datetime import datetime

from app.automations.triggers.builtin.schedule.cron import (
    InvalidCronError,
    compute_next_fire_at as _compute_next_fire_at,
    validate_cron as _validate_cron,
)

__all__ = ["InvalidCronError", "compute_next_fire_at", "validate_cron"]


def validate_cron(cron: str, timezone: str) -> None:
    _validate_cron(cron, timezone)


def compute_next_fire_at(cron: str, timezone: str, *, after: datetime) -> datetime:
    return _compute_next_fire_at(cron, timezone, after=after)


# Human-friendly schedule -> cron mapping.
_SCHEDULE_CRON = {
    "none": None,
    "daily": "0 0 * * *",
    "weekly": "0 0 * * 1",
}


def cron_for_schedule(schedule: str) -> str | None:
    """Return the cron expression for a human schedule label."""
    return _SCHEDULE_CRON.get(schedule)


def derive_cron(schedule: str, timezone: str) -> str | None:
    """Return the cron string for a schedule, validating the timezone.

    Returns ``None`` for ``schedule='none'``.
    """
    cron = cron_for_schedule(schedule)
    if not cron:
        return None
    _validate_cron(cron, timezone)
    return cron
