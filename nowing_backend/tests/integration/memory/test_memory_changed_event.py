"""ATDD acceptance tests for Story 6.5 — ``memory.changed`` emission (AC-1, AC-5).

Red-phase: activated during ``dev-story`` (red -> green). ``MemoryRepository``
already exists (Story 4.5), but it does not yet publish a ``memory.changed``
event. These assert the expected post-implementation behavior:

  AC-1  create_memory / update_memory publish ONE ``memory.changed`` event with
        payload {memory_id, workspace_id, type, tags, change, source_type} after
        the write commits; emission is best-effort (a bus failure must not fail
        the write).
  AC-5  a memory write ORIGINATING from an automation run is not emitted (loop
        guard, mechanism 1: skip emission for automation-origin writes).

Assumptions to reconcile during green (documented in the ATDD checklist):
  * The event is published on the process-wide ``app.event_bus.bus`` as
    ``memory.changed`` with ``workspace_id`` set and the payload above.
  * Automation-origin writes are marked by threading an origin flag into the
    repository write path; this scaffold uses ``automation_run_id=<id>`` as the
    assumed kwarg. If the dev names it differently, update these two tests.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.memory]

# A deterministic embedding so create/update never touch the real model.
_EMBEDDING = [0.1] * 384


@pytest.fixture
def memory_events():
    """Isolate the event bus and capture ``memory.changed`` events.

    Replaces the bus subscribers with a single spy for the test duration (so the
    real ``event`` trigger source does not enqueue a Celery task), then restores
    them. Yields the list of captured events.
    """
    from app.event_bus import bus

    captured = []

    async def _spy(event) -> None:
        if event.event_type == "memory.changed":
            captured.append(event)

    snapshot = bus.subscribers()
    bus._subscribers = [_spy]
    try:
        yield captured
    finally:
        bus._subscribers = snapshot


async def test_create_memory_publishes_memory_changed(
    db_session, db_workspace, db_user, memory_events
):
    """AC-1: creating a memory publishes one ``memory.changed`` (change=created)."""
    from app.db import MemorySourceType, MemoryType
    from app.services.memory.repository import MemoryRepository

    repo = MemoryRepository(db_session)
    created = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Competitor X raised prices by 10% in Q3.",
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        tags=["competitor"],
        created_by_id=db_user.id,
        embedding=_EMBEDDING,
        commit=True,
    )

    assert len(memory_events) == 1
    event = memory_events[0]
    assert event.event_type == "memory.changed"
    assert event.workspace_id == db_workspace.id
    payload = event.payload
    assert payload["memory_id"] == created.id
    assert payload["workspace_id"] == db_workspace.id
    assert payload["type"] == "semantic"
    assert payload["tags"] == ["competitor"]
    assert payload["change"] == "created"
    assert payload["source_type"] == "manual"
    assert payload["client_id"] is None
    assert payload["agent_id"] is None


async def test_update_memory_publishes_memory_changed_as_updated(
    db_session, db_workspace, db_user, memory_events
):
    """AC-1: updating a memory publishes one ``memory.changed`` (change=updated)."""
    from app.db import MemorySourceType, MemoryType
    from app.services.memory.repository import MemoryRepository

    repo = MemoryRepository(db_session)
    created = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Competitor X raised prices by 10% in Q3.",
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        tags=["competitor"],
        created_by_id=db_user.id,
        embedding=_EMBEDDING,
        commit=True,
    )
    memory_events.clear()  # drop the "created" event; assert only the update

    await repo.update_memory(
        created.id,
        corrected_content="Competitor X raised prices by 12% in Q3.",
        corrected_by_id=db_user.id,
        embedding=[0.2] * 384,
        commit=True,
    )

    assert len(memory_events) == 1
    event = memory_events[0]
    assert event.event_type == "memory.changed"
    assert event.payload["memory_id"] == created.id
    assert event.payload["change"] == "updated"


async def test_memory_write_succeeds_when_bus_publish_fails(
    db_session, db_workspace, db_user, monkeypatch
):
    """AC-1: a bus failure must NOT fail the memory write (best-effort emit)."""
    from app.db import Memory, MemorySourceType, MemoryType
    from app.event_bus import bus
    from app.services.memory.repository import MemoryRepository

    async def _boom(*args, **kwargs):
        raise RuntimeError("event bus is down")

    monkeypatch.setattr(bus, "publish", _boom)

    repo = MemoryRepository(db_session)
    created = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Best-effort emission must not break the write.",
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        tags=["competitor"],
        created_by_id=db_user.id,
        embedding=_EMBEDDING,
        commit=True,
    )

    assert created.id is not None
    # The row is durable despite the bus failure.
    persisted = await db_session.get(Memory, created.id)
    assert persisted is not None
    assert persisted.content == "Best-effort emission must not break the write."


async def test_automation_origin_write_does_not_publish(
    db_session, db_workspace, db_user, memory_events
):
    """AC-5 (mechanism 1): a memory write originating from an automation run must
    NOT emit ``memory.changed`` — so a memory-writing automation cannot re-fire
    its own ``memory_change`` trigger."""
    from app.db import MemorySourceType, MemoryType
    from app.services.memory.repository import MemoryRepository

    repo = MemoryRepository(db_session)
    await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Fact written by an automation step (agent_task -> nowing_remember).",
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.CHAT_MESSAGE,
        tags=["competitor"],
        created_by_id=db_user.id,
        embedding=_EMBEDDING,
        commit=True,
        automation_run_id=999,  # assumed origin marker (documented assumption)
    )

    assert memory_events == []


async def test_noop_update_does_not_publish(
    db_session, db_workspace, db_user, memory_events
):
    """Review: an update that does not change content must NOT emit
    ``change="updated"`` — a spurious event would re-fire memory_change triggers."""
    from app.db import MemorySourceType, MemoryType
    from app.services.memory.repository import MemoryRepository

    repo = MemoryRepository(db_session)
    created = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Competitor X raised prices by 10% in Q3.",
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        tags=["competitor"],
        created_by_id=db_user.id,
        embedding=_EMBEDDING,
        commit=True,
    )
    memory_events.clear()  # drop the "created" event

    # Same content → no-op; skip_version_if_unchanged mirrors the REST/dedup path.
    await repo.update_memory(
        created.id,
        corrected_content="Competitor X raised prices by 10% in Q3.",
        corrected_by_id=db_user.id,
        embedding=_EMBEDDING,
        skip_version_if_unchanged=True,
        commit=True,
    )

    assert memory_events == []


async def test_contextvar_origin_write_does_not_publish(
    db_session, db_workspace, db_user, memory_events
):
    """AC-5 (mechanism 1, contextvar): a write performed while the automation-run
    origin contextvar is set must NOT emit — WITHOUT a hand-passed
    ``automation_run_id`` kwarg (proves the in-process threading the executor
    relies on)."""
    from app.automations.runtime.origin import automation_run_origin
    from app.db import MemorySourceType, MemoryType
    from app.services.memory.repository import MemoryRepository

    repo = MemoryRepository(db_session)
    with automation_run_origin(4242):  # what the executor stamps for a run
        await repo.create_memory(
            workspace_id=db_workspace.id,
            content="Fact written inside an automation run (no kwarg).",
            type=MemoryType.SEMANTIC,
            source_type=MemorySourceType.CHAT_MESSAGE,
            tags=["competitor"],
            created_by_id=db_user.id,
            embedding=_EMBEDDING,
            commit=True,
        )

    assert memory_events == []

    # Once the run's context exits, writes emit normally again.
    await repo.create_memory(
        workspace_id=db_workspace.id,
        content="A different fact written outside any automation run.",
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        tags=["competitor"],
        created_by_id=db_user.id,
        embedding=[0.3] * 384,
        commit=True,
    )
    assert len(memory_events) == 1


async def test_created_event_carries_research_thread_id(
    db_session, db_workspace, db_user, memory_events
):
    """AC-4: a thread-scoped memory's ``memory.changed`` payload carries
    ``research_thread_id`` so a memory-driven run can link to the thread."""
    from app.db import MemorySourceType, MemoryType, ResearchThread
    from app.services.memory.repository import MemoryRepository

    thread = ResearchThread(
        workspace_id=db_workspace.id, created_by_id=db_user.id, title="Q3 research"
    )
    db_session.add(thread)
    await db_session.flush()

    repo = MemoryRepository(db_session)
    await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Thread-scoped competitor fact.",
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        tags=["competitor"],
        research_thread_id=thread.id,
        created_by_id=db_user.id,
        embedding=_EMBEDDING,
        commit=True,
    )

    assert len(memory_events) == 1
    assert memory_events[0].payload["research_thread_id"] == thread.id
    assert memory_events[0].payload["automation_run_id"] is None


async def test_commit_false_defers_emission_until_flush(
    db_session, db_workspace, db_user, memory_events
):
    """AC-1 (batch path): a ``commit=False`` write buffers its ``memory.changed``
    instead of emitting immediately; the caller announces it after its own commit
    via ``flush_pending_memory_changed`` — exactly once, with change=created."""
    from app.db import MemorySourceType, MemoryType
    from app.services.memory.repository import MemoryRepository

    repo = MemoryRepository(db_session)
    created = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Buffered fact from a batch write.",
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.CHAT_MESSAGE,
        tags=["competitor"],
        created_by_id=db_user.id,
        embedding=_EMBEDDING,
        commit=False,
    )

    # Nothing announced yet — the batch has not committed.
    assert memory_events == []

    await repo.flush_pending_memory_changed()

    assert len(memory_events) == 1
    assert memory_events[0].payload["memory_id"] == created.id
    assert memory_events[0].payload["change"] == "created"


async def test_flush_is_idempotent_and_drains_the_buffer(
    db_session, db_workspace, db_user, memory_events
):
    """AC-1: the buffer is drained on flush, so a retried flush (or a Celery
    redelivery calling flush again) cannot re-emit a duplicate event."""
    from app.db import MemorySourceType, MemoryType
    from app.services.memory.repository import MemoryRepository

    repo = MemoryRepository(db_session)
    await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Announced exactly once.",
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.CHAT_MESSAGE,
        tags=["competitor"],
        created_by_id=db_user.id,
        embedding=_EMBEDDING,
        commit=False,
    )

    await repo.flush_pending_memory_changed()
    assert len(memory_events) == 1

    # Second flush finds an empty buffer → no re-emit.
    await repo.flush_pending_memory_changed()
    assert len(memory_events) == 1


async def test_multiple_commit_false_writes_are_all_flushed(
    db_session, db_workspace, db_user, memory_events
):
    """AC-1: a batch of several deferred writes announces one event per durable
    memory when flushed (mirrors auto-extraction persisting N facts)."""
    from app.db import MemorySourceType, MemoryType
    from app.services.memory.repository import MemoryRepository

    repo = MemoryRepository(db_session)
    first = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="First batched fact.",
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.CHAT_MESSAGE,
        tags=["competitor"],
        created_by_id=db_user.id,
        embedding=_EMBEDDING,
        commit=False,
    )
    second = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Second batched fact, quite different.",
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.CHAT_MESSAGE,
        tags=["pricing"],
        created_by_id=db_user.id,
        embedding=[0.9] * 384,
        commit=False,
    )

    assert memory_events == []

    await repo.flush_pending_memory_changed()

    emitted_ids = {e.payload["memory_id"] for e in memory_events}
    assert emitted_ids == {first.id, second.id}


async def test_commit_false_automation_origin_is_not_buffered(
    db_session, db_workspace, db_user, memory_events
):
    """AC-5 x AC-1: an automation-origin write is skipped BEFORE buffering, so a
    later flush announces nothing for it — the loop guard holds on the batch path
    too."""
    from app.db import MemorySourceType, MemoryType
    from app.services.memory.repository import MemoryRepository

    repo = MemoryRepository(db_session)
    created = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Automation-origin batched write.",
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.CHAT_MESSAGE,
        tags=["competitor"],
        created_by_id=db_user.id,
        embedding=_EMBEDDING,
        commit=False,
        automation_run_id=999,
    )

    await repo.flush_pending_memory_changed()

    # The write persisted, but nothing was buffered or announced.
    assert created.id is not None
    assert memory_events == []


async def test_zero_run_id_is_treated_as_no_origin_and_emits(
    db_session, db_workspace, db_user, memory_events
):
    """AC-5 (truthiness contract): ``0`` is never a valid run id, so a write with
    ``automation_run_id=0`` is NOT an automation origin and DOES emit — matching
    the selector's truthy drop."""
    from app.db import MemorySourceType, MemoryType
    from app.services.memory.repository import MemoryRepository

    repo = MemoryRepository(db_session)
    created = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Written with a zero run id (no real origin).",
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        tags=["competitor"],
        created_by_id=db_user.id,
        embedding=_EMBEDDING,
        commit=True,
        automation_run_id=0,
    )

    assert len(memory_events) == 1
    assert memory_events[0].payload["memory_id"] == created.id


async def test_dedup_rewrite_with_unchanged_content_does_not_emit(
    db_session, db_workspace, db_user, memory_events
):
    """content_changed gate: re-creating a content-identical duplicate (dedup,
    ``update_on_duplicate=False``) may refresh tags/type but must NOT announce
    ``change="updated"`` — the content did not change, so a memory_change trigger
    must not re-fire."""
    from app.db import Memory, MemorySourceType, MemoryType
    from app.services.memory.repository import MemoryRepository

    repo = MemoryRepository(db_session)
    created = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Competitor X raised prices by 10% in Q3.",
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        tags=["competitor"],
        created_by_id=db_user.id,
        embedding=_EMBEDDING,
        commit=True,
    )
    memory_events.clear()  # drop the "created" event

    # Same content + same embedding → hits the dedup branch; only tags differ.
    deduped = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Competitor X raised prices by 10% in Q3.",
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        tags=["competitor", "pricing"],
        created_by_id=db_user.id,
        embedding=_EMBEDDING,
        commit=True,
    )

    # It updated the existing row (no new row, refreshed tags) but stayed silent.
    assert deduped.id == created.id
    assert memory_events == []
    persisted = await db_session.get(Memory, created.id)
    assert set(persisted.tags) == {"competitor", "pricing"}


async def test_string_type_and_source_type_are_serialized_as_enum_values(
    db_session, db_workspace, db_user, memory_events
):
    """AC-1: passing ``type``/``source_type`` as raw strings still yields a
    payload whose ``type``/``source_type`` are the enum string values (never a
    repr), so subscribers filter without importing the ORM enums."""
    from app.services.memory.repository import MemoryRepository

    repo = MemoryRepository(db_session)
    await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Fact created via string enum inputs.",
        type="episodic",
        source_type="chat_message",
        tags=["competitor"],
        created_by_id=db_user.id,
        embedding=_EMBEDDING,
        commit=True,
    )

    assert len(memory_events) == 1
    payload = memory_events[0].payload
    assert payload["type"] == "episodic"
    assert payload["source_type"] == "chat_message"
