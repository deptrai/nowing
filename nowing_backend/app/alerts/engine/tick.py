"""Celery tick task for the Generic Alert Engine.

Beat ticks this every minute. It claims due alert rules, executes each,
computes diffs, and writes snapshots.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.persistence.models.alert_rule import AlertRule
from app.celery_app import celery_app
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

from .cron import compute_next_fire_at
from .execute import execute_alert_rule

logger = logging.getLogger(__name__)

TASK_NAME = "alert_engine_tick"
_TICK_BATCH = 200


@celery_app.task(name=TASK_NAME)
def alert_engine_tick() -> None:
    """Tick once: claim due alert rules and execute each."""
    return run_async_celery_task(_tick)


async def _tick() -> None:
    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        now = datetime.now(UTC)

        await _self_heal_null_next_fire(session, now=now)

        claims = await _claim_due_rules(session, now=now)
        if not claims:
            return

        for rule in claims:
            try:
                await execute_alert_rule(session=session, alert_rule=rule, fired_at=now)
            except Exception:
                logger.exception("alert rule %s execution failed", rule.id)
                await session.rollback()


async def _self_heal_null_next_fire(session: AsyncSession, *, now: datetime) -> None:
    """Backfill next_fire_at for enabled rules that lack it."""
    from .cron import InvalidCronError, compute_next_fire_at

    stmt = (
        select(AlertRule)
        .where(
            AlertRule.enabled.is_(True),
            AlertRule.next_fire_at.is_(None),
            AlertRule.cron.isnot(None),
        )
        .limit(_TICK_BATCH)
    )
    rules = (await session.execute(stmt)).scalars().all()
    if not rules:
        return

    for rule in rules:
        try:
            rule.next_fire_at = compute_next_fire_at(
                rule.cron, rule.timezone, after=now
            )
        except (InvalidCronError, KeyError, TypeError) as exc:
            logger.warning(
                "alert rule %s has invalid cron/timezone, disabling: %s",
                rule.id,
                exc,
            )
            rule.enabled = False

    await session.commit()


async def _claim_due_rules(session: AsyncSession, *, now: datetime) -> list[AlertRule]:
    """Return and advance enabled rules whose next_fire_at is due."""
    stmt = (
        select(AlertRule)
        .where(
            AlertRule.enabled.is_(True),
            AlertRule.next_fire_at.isnot(None),
            AlertRule.next_fire_at <= now,
        )
        .order_by(AlertRule.next_fire_at)
        .limit(_TICK_BATCH)
        .with_for_update(skip_locked=True)
    )
    rules = (await session.execute(stmt)).scalars().all()

    for rule in rules:
        rule.last_fired_at = now
        if rule.cron:
            rule.next_fire_at = compute_next_fire_at(
                rule.cron, rule.timezone, after=now
            )

    await session.commit()
    return list(rules)
