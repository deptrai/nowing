"""``memory.changed``: a workspace memory fact was created or updated.

Emitted best-effort from ``MemoryRepository`` after a memory write commits, so a
``memory_change`` automation trigger (FR-35) can react to fresh facts. The
payload carries the fields a user can filter a trigger on (``type``, ``tags``)
plus the identifiers a downstream step needs.

Loop guard (Story 6.5, AC-5): writes that originate from an automation run are
NOT emitted. The origin is known either from a Python contextvar the run
executor stamps for its whole duration (in-process writes, e.g. the agent_task
tool → ``MemoryRepository.create_memory``) or from an explicit
``automation_run_id`` kwarg (e.g. the REST endpoint reading the
``X-Automation-Run-Id`` header for a cross-process write). The repository skips
emission for such writes (mechanism 1); the ``memory_change`` selector
additionally drops any event that still carries an ``automation_run_id``
(mechanism 2) so a memory-writing automation cannot re-fire its own trigger.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.event_bus.catalog import EventType, catalog

EVENT_TYPE = "memory.changed"


class MemoryChangedPayload(BaseModel):
    """Snapshot of a memory at the moment it was created or updated.

    ``change`` is ``"created"`` for a fresh row and ``"updated"`` when an
    existing row's content is corrected. ``type``/``source_type`` are the
    string values of the memory enums so subscribers can filter without
    importing the ORM enums.

    ``research_thread_id`` (AC-4) links the changed memory to its research
    thread when it has one, so a ``memory_change``-driven run can populate
    ``AutomationRun.research_thread_id`` from the event (via
    ``event_runtime_inputs`` → ``launch._research_thread_id_from_inputs``).

    ``automation_run_id`` (AC-5, mechanism 2) marks an event as originating from
    an automation run. The repository already skips emission for automation
    writes (mechanism 1), so repo-emitted events carry ``None`` here; the field
    exists so the ``memory_change`` selector's origin-drop is a live, reachable
    guard for any producer that does emit a stamped event (e.g. a cross-process
    write threaded via the ``X-Automation-Run-Id`` header).
    """

    model_config = ConfigDict(extra="forbid")

    memory_id: int
    workspace_id: int
    type: str
    tags: list[str] = Field(default_factory=list)
    change: str
    source_type: str
    research_thread_id: int | None = None
    client_id: str | None = None
    agent_id: str | None = None
    automation_run_id: int | None = None


catalog.register(
    EventType(
        type=EVENT_TYPE,
        description="A workspace memory fact was created or updated.",
        payload_model=MemoryChangedPayload,
    )
)
