"""Pure predicate: does a ``memory_change`` trigger fire for a given event?

A memory-typed specialization of ``builtin/event/match.py``: fires only for the
``memory.changed`` event and matches the event payload's ``type`` and ``tags``
against the trigger's optional filter. ``tags`` uses subset semantics — every
trigger tag must be present in the event payload's tags. An empty/omitted filter
matches any ``memory.changed`` event.
"""

from __future__ import annotations

from typing import Any

from app.event_bus import Event
from app.event_bus.events.memory_changed import EVENT_TYPE


def trigger_matches_event(params: dict[str, Any], event: Event) -> bool:
    """True when a ``memory_change`` trigger configured with ``params`` should
    fire for ``event``."""
    if event.event_type != EVENT_TYPE:
        return False

    memory_type = params.get("memory_type")
    if memory_type is not None and event.payload.get("type") != memory_type:
        return False

    required_tags = params.get("tags") or []
    event_tags = event.payload.get("tags") or []
    return set(required_tags).issubset(set(event_tags))
