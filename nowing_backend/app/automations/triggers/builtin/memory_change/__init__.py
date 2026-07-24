"""``memory_change`` trigger: fire an automation when a workspace memory changes.

A memory-typed specialization of the generic ``event`` trigger (FR-35).
Subscribes to the event bus and matches ``memory.changed`` events against an
optional memory ``type``/``tags`` filter (see :mod:`.match`).
"""

from __future__ import annotations

from app.event_bus import bus

from .match import trigger_matches_event
from .params import MemoryChangeTriggerParams
from .source import on_event

__all__ = [
    "MemoryChangeTriggerParams",
    "trigger_matches_event",
]

# Side-effect: register on the triggers store.
from . import definition  # noqa: F401

# Side-effect: react to published ``memory.changed`` events.
bus.subscribe(on_event)
