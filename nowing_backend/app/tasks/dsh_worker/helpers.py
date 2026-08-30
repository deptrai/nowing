"""Shared DSH helper utilities."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _checkpoint_update(**kwargs: Any) -> dict[str, Any]:
    """Build a JSON-serialisable checkpoint update with None values omitted.

    ``current_subtask_id`` is always preserved (including ``None``) because the
    sidecar must be able to clear it on terminal/success transitions.
    ``started_at`` and ``completed_at`` are normalised to ISO strings so the
    sidecar payload is JSON-serialisable even if a caller passes a ``datetime``.
    """
    result: dict[str, Any] = {}
    for k, v in kwargs.items():
        if v is None and k != "current_subtask_id":
            continue
        if k in ("started_at", "completed_at") and isinstance(v, datetime):
            v = v.isoformat()
        result[k] = v
    return result
