"""Conflict resolution for CRM sync."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def resolve_conflict(
    nowing_value: Any,
    crm_value: Any,
    nowing_at: datetime | None,
    crm_at: datetime | None,
) -> tuple[Any, str]:
    """Last-write-wins conflict resolution.

    Returns (value, winner).
    """
    nowing_at = nowing_at or datetime.min.replace(tzinfo=UTC)
    crm_at = crm_at or datetime.min.replace(tzinfo=UTC)

    if crm_at > nowing_at:
        return crm_value, "crm"
    return nowing_value, "nowing"
