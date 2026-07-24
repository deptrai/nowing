"""Memory-change selector (worker task): pick the triggers a ``memory.changed``
event fires, start each.

The source enqueues this with a serialized event. Here we load the enabled
``memory_change`` triggers whose automation lives in the event's workspace (AC-2
workspace scoping), keep the ones whose memory ``type``/``tags`` filter matches
the payload, and start a run for each. Per-trigger failures are isolated.

Loop guard (AC-5, mechanism 2): a ``memory.changed`` event stamped with an
``automation_run_id`` originated from an automation run and is dropped here, so
a memory-writing automation cannot re-fire a matching ``memory_change`` trigger
even if such an event ever reaches the bus.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.dispatch import launch_run
from app.automations.persistence.enums.automation_status import AutomationStatus
from app.automations.persistence.enums.trigger_type import TriggerType
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.trigger import AutomationTrigger
from app.automations.triggers.builtin.event.inputs import event_runtime_inputs
from app.celery_app import celery_app
from app.event_bus import Event
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

from .match import trigger_matches_event
from .source import TASK_NAME

logger = logging.getLogger(__name__)


@celery_app.task(name=TASK_NAME)
def automation_memory_change_select(event: dict[str, Any]) -> None:
    """Select and start the runs a ``memory.changed`` event fires."""
    return run_async_celery_task(lambda: _select_and_start(event))


async def _select_and_start(event_dict: dict[str, Any]) -> None:
    event = Event.model_validate(event_dict)
    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        for trigger in await _eligible(session, event=event):
            await _start_one(session, trigger=trigger, event=event)


async def _eligible(session: AsyncSession, *, event: Event) -> list[AutomationTrigger]:
    """Enabled ``memory_change`` triggers on an ACTIVE automation in the event's
    workspace whose filter matches.

    Automation-origin events (carrying an ``automation_run_id``) are dropped up
    front — the loop guard (mechanism 2) that prevents a memory-writing
    automation from re-triggering itself. Truthiness matches the repository's
    emit-skip (``0`` is not a valid run id).

    Only ACTIVE automations are considered: a paused/archived automation would
    otherwise be selected here and then rejected by ``launch_run``
    (``resolve_active_automation`` raises ``DispatchError``), logging an
    exception on every matching event.
    """
    if event.payload.get("automation_run_id"):
        return []

    stmt = (
        select(AutomationTrigger)
        .join(Automation, Automation.id == AutomationTrigger.automation_id)
        .where(
            AutomationTrigger.type == TriggerType.MEMORY_CHANGE,
            AutomationTrigger.enabled.is_(True),
            Automation.workspace_id == event.workspace_id,
            Automation.status == AutomationStatus.ACTIVE,
        )
    )
    triggers = (await session.execute(stmt)).scalars().all()
    return [t for t in triggers if trigger_matches_event(t.params, event)]


async def _start_one(
    session: AsyncSession, *, trigger: AutomationTrigger, event: Event
) -> None:
    try:
        run = await launch_run(
            session=session,
            trigger=trigger,
            runtime_inputs=event_runtime_inputs(event),
        )
        logger.info(
            "memory_change fire: trigger=%d automation=%d run=%d event=%s",
            trigger.id,
            trigger.automation_id,
            run.id,
            event.event_id,
        )
    except Exception:
        logger.exception("memory_change fire failed for trigger %d", trigger.id)
        await session.rollback()
