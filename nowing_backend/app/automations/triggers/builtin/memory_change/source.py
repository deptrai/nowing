"""``memory_change`` trigger source: the bus subscriber that enqueues the selector.

Runs in whatever process published the ``memory.changed`` event, so it stays
thin — it only hands the event to a worker (the selector does the DB matching).
Mirrors ``builtin/event/source.py`` but is scoped to ``memory.changed`` so
unrelated events do not enqueue a memory-change selection task.
"""

from __future__ import annotations

from app.event_bus import Event
from app.event_bus.events.memory_changed import EVENT_TYPE

TASK_NAME = "automation_memory_change_select"


async def on_event(event: Event) -> None:
    """Enqueue the memory-change selector for a ``memory.changed`` ``event``."""
    if event.event_type != EVENT_TYPE:
        return
    # Lazy import: keeps app.celery_app out of the triggers-package import graph.
    from app.celery_app import celery_app

    celery_app.send_task(TASK_NAME, kwargs={"event": event.model_dump(mode="json")})
