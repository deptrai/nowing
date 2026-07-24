"""ATDD acceptance tests for Story 6.5 — memory_change trigger + run linkage.

Red-phase: activated during ``dev-story`` (red -> green). Covers:

  AC-2  a ``memory_change`` trigger is selected for a matching ``memory.changed``
        event (workspace + type/tags filter) and starts a run via the existing
        ``launch_run`` dispatch path; it is NOT selected for a non-matching
        filter or an event in another workspace.
  AC-4  ``automation_runs.research_thread_id`` exists (nullable FK ->
        research_threads) and is populated when a run is tied to a thread.
  AC-5  an automation-origin ``memory.changed`` event does not re-fire a
        matching ``memory_change`` trigger (loop guard, mechanism 2).

Assumptions to reconcile during green (documented in the ATDD checklist):
  * ``TriggerType.MEMORY_CHANGE == "memory_change"`` exists.
  * The selector exposes an eligibility coroutine modeled on
    ``builtin/event/selector.py``: ``_eligible(session, *, event) ->
    list[AutomationTrigger]`` that scopes by the automation's workspace and the
    memory type/tags filter, and drops automation-origin events.
  * A run acquires ``research_thread_id`` from the trigger/inputs it fires with;
    this scaffold threads it via ``static_inputs``/``runtime_inputs``.
  * The test DB schema is built from the ORM models (``Base.metadata.create_all``
    in the integration harness), so the column assertion depends on the ORM
    model gaining the column; the Alembic migration (head 179 -> 180) is
    verified separately via ``alembic upgrade head``.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _make_automation_with_trigger(
    session,
    workspace,
    user,
    *,
    params,
    static_inputs=None,
    plan=None,
    status=None,
):
    """Create an automation with one enabled ``memory_change`` trigger.

    ``status`` defaults to ACTIVE; pass PAUSED/ARCHIVED to exercise the
    selector's status filter. ``plan`` overrides the default single
    ``agent_task`` step (e.g. to give the step params or use another action).
    """
    from app.automations.persistence.enums.automation_status import AutomationStatus
    from app.automations.persistence.enums.trigger_type import TriggerType
    from app.automations.persistence.models.automation import Automation
    from app.automations.persistence.models.trigger import AutomationTrigger
    from app.automations.schemas.definition.envelope import AutomationDefinition
    from app.automations.schemas.definition.plan_step import PlanStep

    definition = AutomationDefinition(
        name="memory-driven automation",
        plan=plan or [PlanStep(step_id="s1", action="agent_task")],
    )
    automation = Automation(
        workspace_id=workspace.id,
        created_by_user_id=user.id,
        name="memory-driven automation",
        status=status or AutomationStatus.ACTIVE,
        definition=definition.model_dump(mode="json", by_alias=True),
    )
    session.add(automation)
    await session.flush()

    trigger = AutomationTrigger(
        automation_id=automation.id,
        type=TriggerType.MEMORY_CHANGE,
        params=params,
        static_inputs=static_inputs or {},
        enabled=True,
    )
    session.add(trigger)
    await session.flush()
    return automation, trigger


def _memory_changed_event(workspace_id, *, memory_type="semantic", tags=None, **extra):
    from app.event_bus import Event

    payload = {
        "memory_id": 1,
        "workspace_id": workspace_id,
        "type": memory_type,
        "tags": tags if tags is not None else ["competitor"],
        "change": "created",
        "source_type": "manual",
        **extra,
    }
    return Event(
        event_type="memory.changed", payload=payload, workspace_id=workspace_id
    )


async def test_eligible_selects_matching_trigger(db_session, db_workspace, db_user):
    """AC-2: a matching enabled memory_change trigger is selected for the event."""
    from app.automations.triggers.builtin.memory_change.selector import _eligible

    _automation, trigger = await _make_automation_with_trigger(
        db_session,
        db_workspace,
        db_user,
        params={"memory_type": "semantic", "tags": ["competitor"]},
    )
    event = _memory_changed_event(
        db_workspace.id, memory_type="semantic", tags=["competitor", "pricing"]
    )

    eligible = await _eligible(db_session, event=event)

    assert [t.id for t in eligible] == [trigger.id]


async def test_eligible_ignores_nonmatching_filter(db_session, db_workspace, db_user):
    """AC-2 (negative): a trigger whose type filter differs is not selected."""
    from app.automations.triggers.builtin.memory_change.selector import _eligible

    await _make_automation_with_trigger(
        db_session,
        db_workspace,
        db_user,
        params={"memory_type": "episodic", "tags": []},
    )
    event = _memory_changed_event(db_workspace.id, memory_type="semantic", tags=[])

    eligible = await _eligible(db_session, event=event)

    assert eligible == []


async def test_eligible_ignores_other_workspace(db_session, db_workspace, db_user):
    """AC-2 (negative): a trigger whose automation is in another workspace is not
    selected for this workspace's event."""
    from app.automations.triggers.builtin.memory_change.selector import _eligible
    from app.db import Workspace
    from app.routes.workspaces_routes import create_default_roles_and_membership

    workspace_b = Workspace(name="Workspace B", user_id=db_user.id)
    db_session.add(workspace_b)
    await db_session.flush()
    await create_default_roles_and_membership(db_session, workspace_b.id, db_user.id)
    await db_session.flush()

    await _make_automation_with_trigger(
        db_session,
        workspace_b,
        db_user,
        params={"memory_type": "semantic", "tags": []},
    )
    # Event happens in workspace A; the trigger lives in workspace B.
    event = _memory_changed_event(db_workspace.id, memory_type="semantic", tags=[])

    eligible = await _eligible(db_session, event=event)

    assert eligible == []


async def test_memory_change_launches_run_for_matching_trigger(
    db_session, db_workspace, db_user, enqueue_spy
):
    """AC-2: a matching memory_change trigger starts a run via ``launch_run``."""
    from app.automations.dispatch import launch_run

    automation, trigger = await _make_automation_with_trigger(
        db_session,
        db_workspace,
        db_user,
        params={"memory_type": "semantic", "tags": ["competitor"]},
    )

    run = await launch_run(
        session=db_session,
        trigger=trigger,
        runtime_inputs={
            "memory_id": 1,
            "workspace_id": db_workspace.id,
            "type": "semantic",
            "tags": ["competitor"],
            "change": "created",
            "source_type": "manual",
            "event_type": "memory.changed",
        },
    )

    assert run.id is not None
    assert run.automation_id == automation.id
    assert run.trigger_id == trigger.id


async def test_automation_runs_has_research_thread_id_column(db_session):
    """AC-4: the ``automation_runs.research_thread_id`` column exists and is
    nullable (FK -> research_threads, ondelete SET NULL)."""
    from sqlalchemy import text

    result = await db_session.execute(
        text(
            "SELECT column_name, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_name = 'automation_runs' "
            "AND column_name = 'research_thread_id'"
        )
    )
    row = result.first()

    assert row is not None, "automation_runs.research_thread_id column is missing"
    assert row.is_nullable == "YES"


async def test_run_is_populated_with_research_thread_id(
    db_session, db_workspace, db_user, enqueue_spy
):
    """AC-4: when a run is driven by research continuity, the run row carries the
    ``research_thread_id`` of the thread it is tied to."""
    from app.automations.dispatch import launch_run
    from app.db import ResearchThread

    thread = ResearchThread(
        workspace_id=db_workspace.id, created_by_id=db_user.id, title="Q3 research"
    )
    db_session.add(thread)
    await db_session.flush()

    _automation, trigger = await _make_automation_with_trigger(
        db_session,
        db_workspace,
        db_user,
        params={"memory_type": "semantic", "tags": []},
        static_inputs={"research_thread_id": thread.id},
    )

    run = await launch_run(
        session=db_session,
        trigger=trigger,
        runtime_inputs={"research_thread_id": thread.id, "type": "semantic"},
    )

    assert run.research_thread_id == thread.id


async def test_automation_origin_event_is_not_eligible(
    db_session, db_workspace, db_user
):
    """AC-5 (mechanism 2): a ``memory.changed`` event marked as automation-origin
    does not re-fire a matching memory_change trigger."""
    from app.automations.triggers.builtin.memory_change.selector import _eligible

    await _make_automation_with_trigger(
        db_session,
        db_workspace,
        db_user,
        params={"memory_type": "semantic", "tags": []},
    )
    # Same shape as a matching event, but stamped with an automation origin.
    origin_event = _memory_changed_event(
        db_workspace.id, memory_type="semantic", tags=[], automation_run_id=123
    )

    eligible = await _eligible(db_session, event=origin_event)

    assert eligible == []


@pytest.fixture
def memory_events():
    """Replace the bus subscribers with a spy that captures ``memory.changed``.

    Also prevents the real ``memory_change`` source subscriber from enqueueing a
    Celery task during the test.
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


@pytest.mark.parametrize("status", ["paused", "archived"])
async def test_eligible_excludes_non_active_automation(
    db_session, db_workspace, db_user, status
):
    """AC-2 / review: a matching trigger on a PAUSED/ARCHIVED automation is NOT
    selected — otherwise ``launch_run`` would raise ``DispatchError`` and log an
    exception on every matching event."""
    from app.automations.persistence.enums.automation_status import AutomationStatus
    from app.automations.triggers.builtin.memory_change.selector import _eligible

    await _make_automation_with_trigger(
        db_session,
        db_workspace,
        db_user,
        params={"memory_type": "semantic", "tags": []},
        status=AutomationStatus(status),
    )
    event = _memory_changed_event(db_workspace.id, memory_type="semantic", tags=[])

    eligible = await _eligible(db_session, event=event)

    assert eligible == []


async def test_run_populated_with_research_thread_id_from_event_payload(
    db_session, db_workspace, db_user, enqueue_spy
):
    """AC-4: a ``memory.changed`` payload carrying ``research_thread_id`` (now a
    payload field, flattened into run inputs) populates ``run.research_thread_id``."""
    from app.automations.dispatch import launch_run
    from app.db import ResearchThread

    thread = ResearchThread(
        workspace_id=db_workspace.id, created_by_id=db_user.id, title="Q3 research"
    )
    db_session.add(thread)
    await db_session.flush()

    _automation, trigger = await _make_automation_with_trigger(
        db_session,
        db_workspace,
        db_user,
        params={"memory_type": "semantic", "tags": []},
    )

    # Exactly what event_runtime_inputs produces from a thread-scoped memory.
    run = await launch_run(
        session=db_session,
        trigger=trigger,
        runtime_inputs={
            "memory_id": 1,
            "workspace_id": db_workspace.id,
            "type": "semantic",
            "tags": [],
            "change": "created",
            "source_type": "manual",
            "research_thread_id": thread.id,
            "event_type": "memory.changed",
        },
    )

    assert run.research_thread_id == thread.id


async def test_launch_drops_unknown_research_thread_id(
    db_session, db_workspace, db_user, enqueue_spy
):
    """Review: a non-existent ``research_thread_id`` in inputs is dropped (no FK
    IntegrityError), leaving the run unlinked."""
    from app.automations.dispatch import launch_run

    _automation, trigger = await _make_automation_with_trigger(
        db_session,
        db_workspace,
        db_user,
        params={"memory_type": "semantic", "tags": []},
    )

    run = await launch_run(
        session=db_session,
        trigger=trigger,
        runtime_inputs={"research_thread_id": 99_999_999, "type": "semantic"},
    )

    assert run.research_thread_id is None


async def test_launch_drops_cross_workspace_research_thread_id(
    db_session, db_workspace, db_user, enqueue_spy
):
    """Review: a ``research_thread_id`` from ANOTHER workspace is dropped (no
    cross-workspace link)."""
    from app.automations.dispatch import launch_run
    from app.db import ResearchThread, Workspace
    from app.routes.workspaces_routes import create_default_roles_and_membership

    workspace_b = Workspace(name="Workspace B", user_id=db_user.id)
    db_session.add(workspace_b)
    await db_session.flush()
    await create_default_roles_and_membership(db_session, workspace_b.id, db_user.id)
    await db_session.flush()

    other_thread = ResearchThread(
        workspace_id=workspace_b.id, created_by_id=db_user.id, title="B research"
    )
    db_session.add(other_thread)
    await db_session.flush()

    # The automation/trigger live in workspace A.
    _automation, trigger = await _make_automation_with_trigger(
        db_session,
        db_workspace,
        db_user,
        params={"memory_type": "semantic", "tags": []},
    )

    run = await launch_run(
        session=db_session,
        trigger=trigger,
        runtime_inputs={"research_thread_id": other_thread.id, "type": "semantic"},
    )

    assert run.research_thread_id is None


async def test_run_linked_from_continue_research_step_param(
    db_session, db_workspace, db_user, enqueue_spy
):
    """AC-4 (executor-side): a ``continue_research`` step's ``research_thread_id``
    param populates ``run.research_thread_id`` even when the trigger carries none."""
    from app.automations.dispatch import launch_run
    from app.automations.persistence.models.run import AutomationRun
    from app.automations.runtime import execute_run
    from app.automations.schemas.definition.plan_step import PlanStep
    from app.db import ResearchThread

    thread = ResearchThread(
        workspace_id=db_workspace.id, created_by_id=db_user.id, title="Q3 research"
    )
    db_session.add(thread)
    await db_session.flush()

    _automation, trigger = await _make_automation_with_trigger(
        db_session,
        db_workspace,
        db_user,
        params={"memory_type": "semantic", "tags": []},
        plan=[
            PlanStep(
                step_id="continue",
                action="continue_research",
                params={"research_thread_id": thread.id, "top_k": 5},
            )
        ],
    )

    run = await launch_run(
        session=db_session, trigger=trigger, runtime_inputs={"type": "semantic"}
    )
    # The trigger carries no thread; the run starts unlinked.
    assert run.research_thread_id is None

    await execute_run(db_session, run.id)

    linked = await db_session.get(AutomationRun, run.id)
    assert linked.research_thread_id == thread.id


async def test_memory_writing_automation_does_not_refire(
    db_session, db_workspace, db_user, enqueue_spy, memory_events, monkeypatch
):
    """AC-5 END-TO-END (hard guardrail): a ``memory_change`` automation whose
    ``agent_task`` step writes workspace memory must NOT emit ``memory.changed``
    for its own write, so it cannot re-fire its own trigger.

    Runs the REAL executor + REAL agent_task action + REAL repository; only the
    LLM agent (``run_agent_task``) is faked, writing a workspace memory the way
    the native memory tool / nowing_remember would. The executor stamps the
    automation-origin contextvar for the run, so the repository recognises the
    write as automation-origin and skips emission — without any hand-passed
    kwarg. (The contextvar is task-scoped, so it is seen regardless of which DB
    session the tool opens; the test writes via ctx.session to stay hermetic.)
    """
    from app.automations.dispatch import launch_run
    from app.automations.persistence.enums.run_status import RunStatus
    from app.automations.persistence.models.run import AutomationRun
    from app.automations.runtime import execute_run
    from app.automations.schemas.definition.plan_step import PlanStep
    from app.db import Memory, MemorySourceType, MemoryType
    from app.services.memory.repository import MemoryRepository

    written: list[int] = []

    async def fake_run_agent_task(*, ctx, query, auto_approve_all, **kwargs):
        # Write workspace memory the way an agent_task step would (agent →
        # nowing_remember / native update tool → MemoryRepository.create_memory).
        repo = MemoryRepository(ctx.session)
        mem = await repo.create_memory(
            workspace_id=ctx.workspace_id,
            content="Competitor Y cut prices (written by the automation step).",
            type=MemoryType.SEMANTIC,
            source_type=MemorySourceType.CHAT_MESSAGE,
            tags=["competitor"],
            created_by_id=ctx.creator_user_id,
            embedding=[0.1] * 384,
            commit=True,
        )
        written.append(mem.id)
        return {"agent_session_id": "fake", "final_message": "ok", "resumes": 0}

    monkeypatch.setattr(
        "app.automations.actions.builtin.agent_task.factory.run_agent_task",
        fake_run_agent_task,
    )

    _automation, trigger = await _make_automation_with_trigger(
        db_session,
        db_workspace,
        db_user,
        params={"memory_type": "semantic", "tags": ["competitor"]},
        plan=[
            PlanStep(
                step_id="s1",
                action="agent_task",
                params={"query": "Remember the competitor pricing update."},
            )
        ],
    )

    run = await launch_run(
        session=db_session,
        trigger=trigger,
        runtime_inputs={
            "memory_id": 1,
            "workspace_id": db_workspace.id,
            "type": "semantic",
            "tags": ["competitor"],
            "change": "created",
            "source_type": "manual",
            "event_type": "memory.changed",
        },
    )

    await execute_run(db_session, run.id)

    # The step ran and wrote a workspace memory.
    finished = await db_session.get(AutomationRun, run.id)
    assert finished.status == RunStatus.SUCCEEDED
    assert len(written) == 1
    persisted = await db_session.get(Memory, written[0])
    assert persisted is not None and persisted.workspace_id == db_workspace.id

    # LOOP GUARD: the automation's own write emitted NO ``memory.changed``, so
    # the memory_change selector is never re-invoked → no self-trigger.
    assert memory_events == []

    # Control: an identical-shaped write OUTSIDE the run (no origin) DOES emit —
    # proving the spy is wired and it was the origin guard that suppressed the
    # automation write, not a broken bus.
    control_repo = MemoryRepository(db_session)
    await control_repo.create_memory(
        workspace_id=db_workspace.id,
        content="Competitor Z merged (manual, not from an automation).",
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        tags=["competitor"],
        created_by_id=db_user.id,
        embedding=[0.2] * 384,
        commit=True,
    )
    assert len(memory_events) == 1
    assert memory_events[0].payload["change"] == "created"


async def test_eligible_excludes_disabled_trigger(db_session, db_workspace, db_user):
    """AC-2: a matching trigger that is DISABLED is not selected (the selector's
    ``enabled.is_(True)`` filter), so a paused trigger never starts runs."""
    from app.automations.triggers.builtin.memory_change.selector import _eligible

    _automation, trigger = await _make_automation_with_trigger(
        db_session,
        db_workspace,
        db_user,
        params={"memory_type": "semantic", "tags": []},
    )
    trigger.enabled = False
    await db_session.flush()

    event = _memory_changed_event(db_workspace.id, memory_type="semantic", tags=[])

    eligible = await _eligible(db_session, event=event)

    assert eligible == []


async def test_eligible_selects_all_matching_triggers(
    db_session, db_workspace, db_user
):
    """AC-2: every enabled matching trigger in the workspace is selected (a
    single event can fan out to multiple memory-driven automations)."""
    from app.automations.triggers.builtin.memory_change.selector import _eligible

    _a1, t1 = await _make_automation_with_trigger(
        db_session,
        db_workspace,
        db_user,
        params={"memory_type": "semantic", "tags": ["competitor"]},
    )
    _a2, t2 = await _make_automation_with_trigger(
        db_session,
        db_workspace,
        db_user,
        params={"memory_type": None, "tags": []},  # matches any memory.changed
    )

    event = _memory_changed_event(
        db_workspace.id, memory_type="semantic", tags=["competitor"]
    )

    eligible = await _eligible(db_session, event=event)

    assert {t.id for t in eligible} == {t1.id, t2.id}


async def test_start_one_isolates_a_launch_failure(db_session, monkeypatch):
    """Review (fault isolation): if ``launch_run`` raises for one trigger,
    ``_start_one`` swallows it (logs + rolls back) so a sibling trigger in the
    same event fan-out still gets its chance — a single bad trigger never aborts
    the whole selection."""
    from app.automations.persistence.enums.trigger_type import TriggerType
    from app.automations.persistence.models.trigger import AutomationTrigger
    from app.automations.triggers.builtin.memory_change import selector as sel

    async def _boom(**kwargs):
        raise RuntimeError("launch blew up")

    monkeypatch.setattr(sel, "launch_run", _boom)

    # Transient trigger: never added to the session; only its ids are read for
    # the failure log, and ``launch_run`` is patched to raise before any use.
    trigger = AutomationTrigger(
        id=123,
        automation_id=456,
        type=TriggerType.MEMORY_CHANGE,
        params={},
        enabled=True,
    )
    event = _memory_changed_event(7, memory_type="semantic", tags=[])

    # Must return normally (no exception propagates out of the per-trigger start).
    await sel._start_one(db_session, trigger=trigger, event=event)


async def test_deleting_linked_thread_nulls_run_and_preserves_it(
    db_session, db_workspace, db_user, enqueue_spy
):
    """AC-4 (FK ON DELETE SET NULL): deleting a research thread does NOT delete
    its historical runs — the run survives with ``research_thread_id`` set to
    NULL, so audit history is preserved."""
    from app.automations.dispatch import launch_run
    from app.automations.persistence.models.run import AutomationRun
    from app.db import ResearchThread

    thread = ResearchThread(
        workspace_id=db_workspace.id, created_by_id=db_user.id, title="Q3 research"
    )
    db_session.add(thread)
    await db_session.flush()

    _automation, trigger = await _make_automation_with_trigger(
        db_session,
        db_workspace,
        db_user,
        params={"memory_type": "semantic", "tags": []},
        static_inputs={"research_thread_id": thread.id},
    )

    run = await launch_run(
        session=db_session,
        trigger=trigger,
        runtime_inputs={"research_thread_id": thread.id, "type": "semantic"},
    )
    assert run.research_thread_id == thread.id
    run_id = run.id

    # Delete the thread via a Core statement so Postgres applies the ON DELETE
    # SET NULL FK action itself (an ORM ``session.delete`` would instead try to
    # lazily cascade relationships, which is unrelated to what we're asserting).
    from sqlalchemy import delete as sa_delete, func, select

    await db_session.execute(
        sa_delete(ResearchThread).where(ResearchThread.id == thread.id)
    )

    # Read the raw columns back (not the expired ORM object, which would trigger
    # a sync lazy-load): the run row survives with its thread link nulled.
    surviving_count = await db_session.scalar(
        select(func.count())
        .select_from(AutomationRun)
        .where(AutomationRun.id == run_id)
    )
    surviving_thread_id = await db_session.scalar(
        select(AutomationRun.research_thread_id).where(AutomationRun.id == run_id)
    )

    assert surviving_count == 1  # the historical run is preserved
    assert surviving_thread_id is None  # its thread link was nulled


async def test_launch_drops_bool_research_thread_id(
    db_session, db_workspace, db_user, enqueue_spy
):
    """Review: a JSON ``true`` in inputs (``bool``, an ``int`` subclass) must NOT
    be coerced to run #1 — it is dropped, leaving the run unlinked."""
    from app.automations.dispatch import launch_run

    _automation, trigger = await _make_automation_with_trigger(
        db_session,
        db_workspace,
        db_user,
        params={"memory_type": "semantic", "tags": []},
    )

    run = await launch_run(
        session=db_session,
        trigger=trigger,
        runtime_inputs={"research_thread_id": True, "type": "semantic"},
    )

    assert run.research_thread_id is None


async def test_launch_drops_float_research_thread_id(
    db_session, db_workspace, db_user, enqueue_spy
):
    """Review: a non-integer numeric id (``1.5``) is not a valid FK and is
    dropped, leaving the run unlinked (no coercion to 1)."""
    from app.automations.dispatch import launch_run

    _automation, trigger = await _make_automation_with_trigger(
        db_session,
        db_workspace,
        db_user,
        params={"memory_type": "semantic", "tags": []},
    )

    run = await launch_run(
        session=db_session,
        trigger=trigger,
        runtime_inputs={"research_thread_id": 1.5, "type": "semantic"},
    )

    assert run.research_thread_id is None
