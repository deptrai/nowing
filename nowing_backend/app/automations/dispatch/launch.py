"""Launch a run for a trigger that fired: resolve, validate, persist, enqueue.

The trigger-facing entry every selector calls. A selector builds the runtime
inputs and hands one trigger row here; this resolves and guards its automation,
snapshots the definition onto a PENDING run, and enqueues execution. The
snapshot makes the run immune to later edits of the automation.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.persistence.enums.run_status import RunStatus
from app.automations.persistence.models.run import AutomationRun
from app.automations.persistence.models.trigger import AutomationTrigger
from app.automations.schemas.definition.envelope import AutomationDefinition
from app.automations.tasks.execute_run import automation_run_execute

from .errors import DispatchError
from .inputs import prepare_inputs
from .resolve import resolve_active_automation


async def launch_run(
    *,
    session: AsyncSession,
    trigger: AutomationTrigger,
    runtime_inputs: dict[str, Any] | None = None,
) -> AutomationRun:
    """Resolve ``trigger``'s active automation and enqueue a PENDING run for it."""
    automation = await resolve_active_automation(session, trigger)

    try:
        definition = AutomationDefinition.model_validate(automation.definition)
    except Exception as exc:
        raise DispatchError(f"invalid automation definition: {exc}") from exc

    inputs = prepare_inputs(definition, trigger, runtime_inputs)
    snapshot = definition.model_dump(mode="json", by_alias=True)

    research_thread_id = await resolve_research_thread_id(
        session,
        workspace_id=automation.workspace_id,
        raw=inputs.get("research_thread_id"),
    )

    run = AutomationRun(
        automation_id=automation.id,
        trigger_id=trigger.id,
        research_thread_id=research_thread_id,
        status=RunStatus.PENDING,
        definition_snapshot=snapshot,
        inputs=inputs,
        step_results=[],
        artifacts=[],
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    automation_run_execute.apply_async(
        args=[run.id],
        time_limit=definition.execution.timeout_seconds,
    )
    return run


def _coerce_research_thread_id(raw: Any) -> int | None:
    """Coerce a JSON-sourced research-thread id to an int, else ``None``.

    ``bool`` is rejected (it is an ``int`` subclass but never a valid FK).
    """
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None


async def resolve_research_thread_id(
    session: AsyncSession, *, workspace_id: int | None, raw: Any
) -> int | None:
    """Return a valid research-thread id to link onto a run, else ``None``.

    A ``continue_research`` step or a research-driven ``memory_change`` trigger
    threads ``research_thread_id`` through the trigger's ``static_inputs`` / the
    producer's runtime inputs (or the ``memory.changed`` payload's
    ``research_thread_id``); surface it onto the run so the run row links to its
    thread (AC-4).

    The id is validated to EXIST and belong to ``workspace_id`` before it is
    accepted, so a bad or cross-workspace id is dropped silently instead of
    raising an FK ``IntegrityError`` or linking a run to another workspace's
    thread.
    """
    thread_id = _coerce_research_thread_id(raw)
    if thread_id is None or workspace_id is None:
        return None

    from app.db import ResearchThread

    exists = await session.scalar(
        select(ResearchThread.id).where(
            ResearchThread.id == thread_id,
            ResearchThread.workspace_id == workspace_id,
        )
    )
    return thread_id if exists is not None else None
