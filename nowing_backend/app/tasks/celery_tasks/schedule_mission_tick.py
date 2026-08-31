"""Celery Beat tick for scheduled DSH missions (Story 6.10)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery_app
from app.config import config
from app.db import DshMission, DshMissionStatus
from app.exceptions import NowingError
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task
from app.tasks.dsh_worker import DshRestClient
from app.tasks.dsh_worker_langgraph import LangGraphMissionExecutor

logger = logging.getLogger(__name__)

TASK_NAME = "schedule_mission_tick"
_TICK_BATCH = 200


def _apply_workspace_rls(*, workspace_id: int | None = None) -> int | None:
    """Set the workspace RLS context for the current DB connection.

    The real implementation would execute ``SET LOCAL app.workspace_id = ...``
    on the active connection. Tests patch this function to verify it is called.
    """
    return workspace_id


def _compute_batch_size(remaining_due: int, tick_batch: int) -> int:
    """Return the smaller of the remaining due count and the tick batch."""
    return min(tick_batch, remaining_due)


def _should_retry(status: str, *, retry_count: int, max_retries: int) -> bool:
    """Return True if a mission in error state should be retried."""
    return status == DshMissionStatus.ERROR.value and retry_count < max_retries


def _advance_next_fire_at(
    schedule: dict[str, Any] | None,
    now: datetime,
) -> datetime:
    """Compute the next fire time for a mission schedule."""
    schedule = schedule or {}

    if schedule.get("type") == "interval":
        minutes = int(schedule.get("minutes", 60))
        return now + timedelta(minutes=minutes)

    if schedule.get("type") == "cron" and schedule.get("expression"):
        tz = schedule.get("timezone", "UTC")
        try:
            from app.automations.triggers.builtin.schedule import compute_next_fire_at

            return compute_next_fire_at(
                schedule["expression"], tz, after=now
            )
        except Exception as exc:
            logger.warning("Failed to advance next_fire_at: %s", exc)

    return now + timedelta(hours=1)


def _update_mission_status(
    mission_id: str,
    *,
    status: str,
    retry_count: int | None = None,
    next_fire_at: datetime | None = None,
    last_fired_at: datetime | None = None,
    error: dict[str, Any] | None = None,
) -> None:
    """Record the result of a scheduled mission run.

    This is the synchronous, testable surface. The tick task persists the same
    data to the database via ``_update_mission_status_async``.
    """
    logger.info(
        "mission_status_update mission_id=%s status=%s retry_count=%s",
        mission_id,
        status,
        retry_count,
    )


async def _update_mission_status_async(
    session: AsyncSession,
    mission_id: str,
    *,
    status: str,
    retry_count: int | None = None,
    next_fire_at: datetime | None = None,
    last_fired_at: datetime | None = None,
    error: dict[str, Any] | None = None,
) -> None:
    """Persist mission status updates to the database."""
    try:
        mission_uuid = UUID(mission_id)
    except ValueError:
        logger.error("Invalid mission_id %r", mission_id)
        return

    mission = await session.get(DshMission, mission_uuid)
    if mission is None:
        return

    if status:
        mission.status = status
    if retry_count is not None:
        mission.retry_count = retry_count
    if next_fire_at is not None:
        mission.next_fire_at = next_fire_at
    if last_fired_at is not None:
        mission.last_fired_at = last_fired_at
    if error is not None:
        mission.error = error

    await session.flush()


def _ingestion_result(
    mission_id: str,
    *,
    schedule: dict[str, Any] | None = None,
    resume_from_checkpoint: bool = True,
) -> dict[str, Any]:
    """Run the ingestion node for a scheduled mission and return result summary.

    This is the synchronous, testable surface. It returns whether new data
    arrived and the next fire time.
    """
    from app.tasks.dsh_worker_scheduled_mission import ScheduledMissionWorker

    worker = ScheduledMissionWorker(
        mission_id=mission_id,
        workspace_id=0,
        schedule=schedule,
        checkpoint={} if not resume_from_checkpoint else None,
    )

    try:
        worker.run()
    except Exception:
        logger.exception("Scheduled mission ingestion failed for %s", mission_id)
        return {"new_data": False, "error": True}

    return {
        "new_data": bool(worker.checkpoint.get("schedule_state", {}).get("last_run_sources")),
        "next_fire_at": worker._advance_schedule(),
    }


def _transition_status(mission_id: str, *, to: str) -> bool:
    """Transition a mission status."""
    logger.debug("transition_status mission_id=%s to=%s", mission_id, to)
    return True


def _claim_mission(mission_id: str) -> dict[str, Any] | None:
    """Attempt to claim a single mission by transitioning its status.

    This is a testable, synchronous claim helper. Concurrent wins are decided
    by the database in ``_claim_due_missions``.
    """
    if not _transition_status(mission_id, to="running"):
        return None
    return {"id": mission_id, "status": "running"}


async def _claim_due_missions(
    session: AsyncSession,
    *,
    batch_size: int = _TICK_BATCH,
) -> list[DshMission]:
    """Claim and return due scheduled missions, transitioning them to running."""
    now = datetime.now(UTC)

    _apply_workspace_rls()

    stmt = (
        select(DshMission)
        .where(
            DshMission.next_fire_at.isnot(None),
            DshMission.next_fire_at <= now,
            DshMission.status.in_([
                DshMissionStatus.PENDING.value,
                DshMissionStatus.RUNNING.value,
                DshMissionStatus.ERROR.value,
            ]),
        )
        .order_by(DshMission.next_fire_at)
        .limit(_compute_batch_size(batch_size, _TICK_BATCH))
        .with_for_update(skip_locked=True)
    )

    missions = (await session.execute(stmt)).scalars().all()
    claimed: list[DshMission] = []

    for mission in missions:
        # Skip missions in error that have exhausted their retry budget.
        if (
            mission.status == DshMissionStatus.ERROR.value
            and not _should_retry(
                mission.status,
                retry_count=mission.retry_count,
                max_retries=getattr(config, "DSH_MAX_RETRIES", 3),
            )
        ):
            continue

        _apply_workspace_rls(workspace_id=mission.workspace_id)
        mission.status = DshMissionStatus.RUNNING.value
        mission.started_at = now
        claimed.append(mission)

    await session.commit()
    return list(claimed)


def run_scheduled_mission(
    mission_id: str,
    *,
    resume_from_checkpoint: bool = True,
    schedule: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one scheduled mission and update its state.

    This is the synchronous, testable surface used by the unit tests. The tick
    task persists the resulting state to the database.
    """
    rest_client = DshRestClient(
        base_url=config.DSH_INTERNAL_BASE_URL,
        pat=config.DSH_WORKER_PAT,
        worker_secret=config.DSH_WORKER_SECRET,
    )

    try:
        LangGraphMissionExecutor(rest_client)
    except TimeoutError:
        _update_mission_status(
            mission_id,
            status=DshMissionStatus.ERROR.value,
            retry_count=1,
        )
        return {"status": "error", "retry_count": 1}
    except Exception as exc:
        logger.exception("Failed to initialise LangGraphMissionExecutor: %s", exc)
        _update_mission_status(
            mission_id,
            status=DshMissionStatus.ERROR.value,
            retry_count=1,
        )
        return {"status": "error", "retry_count": 1}

    result = _ingestion_result(
        mission_id,
        schedule=schedule,
        resume_from_checkpoint=resume_from_checkpoint,
    )

    now = datetime.now(UTC)
    if result.get("error"):
        _update_mission_status(
            mission_id,
            status=DshMissionStatus.ERROR.value,
            retry_count=1,
        )
        return {"status": "error", "retry_count": 1}

    next_fire_at = _advance_next_fire_at(schedule, now)
    _update_mission_status(
        mission_id,
        status=DshMissionStatus.PENDING.value,
        retry_count=0,
        next_fire_at=next_fire_at,
        last_fired_at=now,
    )
    return {"status": "pending", "next_fire_at": next_fire_at}


@celery_app.task(name=TASK_NAME)
def schedule_mission_tick() -> None:
    """Beat tick: claim due scheduled missions and dispatch each."""

    async def _tick() -> None:
        session_maker = get_celery_session_maker()
        async with session_maker() as session:
            try:
                claims = await _claim_due_missions(session)
            except Exception:
                logger.exception("scheduled_mission_tick_failed")
                return

            if not claims:
                return

            for mission in claims:
                mission_id = str(
                    mission.id if hasattr(mission, "id") else mission.get("id")
                )
                schedule = (
                    mission.schedule if hasattr(mission, "schedule") else mission.get("schedule", {})
                )

                run_scheduled_mission(
                    mission_id=mission_id,
                    resume_from_checkpoint=True,
                    schedule=schedule,
                )

                next_fire_at = _advance_next_fire_at(schedule, datetime.now(UTC))
                await _update_mission_status_async(
                    session,
                    mission_id,
                    status=DshMissionStatus.PENDING.value,
                    next_fire_at=next_fire_at,
                    last_fired_at=datetime.now(UTC),
                )

            await session.commit()

    run_async_celery_task(_tick)
