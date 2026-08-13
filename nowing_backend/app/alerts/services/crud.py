"""CRUD service for alert rules and subscriptions."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.engine.cron import cron_for_schedule, derive_cron, validate_cron
from app.alerts.persistence.models.alert_rule import AlertRule
from app.alerts.persistence.models.alert_snapshot import AlertSnapshot
from app.alerts.persistence.models.alert_subscription import AlertSubscription
from app.alerts.schemas import (
    AlertRuleCreate,
    AlertRuleUpdate,
    AlertSubscriptionCreate,
)
from app.capabilities.core.store import CapabilityRegistry


class AlertRuleError(Exception):
    """Domain error for alert rule operations."""


JOB_ALERT_CAPABILITY_ID = "vn_jobs.aggregate"


def default_job_alert_query(
    *,
    keyword: str,
    location: str | None = None,
    salary_min: int | None = None,
    salary_max: int | None = None,
) -> dict:
    """Build the default query schema for a job market alert (AC-1).

    Maps onto ``VnJobAggregateInput`` so the same query feeds the shared
    aggregator capability. Raises ``ValueError`` if the salary range is
    inverted (a programmer error that's cheaper to catch here than deep in
    the capability executor).
    """
    if salary_min is not None and salary_max is not None and salary_min > salary_max:
        raise ValueError(f"salary_min ({salary_min}) must not exceed salary_max ({salary_max})")
    query: dict = {"keyword": keyword}
    if location:
        query["location"] = location
    if salary_min is not None:
        query["salary_min"] = salary_min
    if salary_max is not None:
        query["salary_max"] = salary_max
    return query


async def list_alert_rules(
    *,
    session: AsyncSession,
    workspace_id: int,
) -> list[AlertRule]:
    stmt = select(AlertRule).where(AlertRule.workspace_id == workspace_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_alert_rule(
    *,
    session: AsyncSession,
    alert_rule_id: UUID,
    workspace_id: int,
) -> AlertRule | None:
    stmt = select(AlertRule).where(
        AlertRule.id == alert_rule_id,
        AlertRule.workspace_id == workspace_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_alert_rule(
    *,
    session: AsyncSession,
    workspace_id: int,
    client_id: str | None,
    user_id: UUID,
    data: AlertRuleCreate,
) -> AlertRule:
    # AD-33: capability_id must be registered in the in-process CapabilityRegistry.
    try:
        CapabilityRegistry.get(data.capability_id)
    except KeyError as exc:
        raise AlertRuleError(
            f"capability {data.capability_id!r} is not registered"
        ) from exc

    # Validate timezone even when schedule is "none" so an invalid IANA string
    # is rejected at creation time, not later when the user enables scheduling.
    if data.timezone:
        cron_for_validation = cron_for_schedule("daily")
        if cron_for_validation:
            validate_cron(cron_for_validation, data.timezone)

    cron = (
        derive_cron(data.schedule, data.timezone) if data.schedule != "none" else None
    )

    rule = AlertRule(
        workspace_id=workspace_id,
        client_id=client_id,
        name=data.name,
        capability_id=data.capability_id,
        query=data.query,
        schedule=data.schedule,
        timezone=data.timezone,
        cron=cron,
        diff_strategy=data.diff_strategy,
        threshold=data.threshold,
        notification_channels=data.notification_channels,
        enabled=data.enabled,
    )
    if cron:
        rule.next_fire_at = rule.compute_next_fire_at()

    session.add(rule)
    await session.commit()
    await session.refresh(rule)

    # Creator is auto-subscribed to default channels.
    await create_alert_subscription(
        session=session,
        workspace_id=workspace_id,
        alert_rule_id=rule.id,
        data=AlertSubscriptionCreate(
            user_id=user_id,
            channels=data.notification_channels or ["in_app"],
            enabled=True,
        ),
    )

    return rule


async def update_alert_rule(
    *,
    session: AsyncSession,
    rule: AlertRule,
    data: AlertRuleUpdate,
) -> AlertRule:
    for field in (
        "name",
        "capability_id",
        "query",
        "schedule",
        "timezone",
        "diff_strategy",
        "threshold",
        "target_sequence_id",
        "target_step_id",
        "notification_channels",
        "enabled",
    ):
        value = getattr(data, field, None)
        if value is not None:
            setattr(rule, field, value)

    # AD-33: re-validate capability_id if it changed.
    if data.capability_id is not None:
        try:
            CapabilityRegistry.get(data.capability_id)
        except KeyError as exc:
            raise AlertRuleError(
                f"capability {data.capability_id!r} is not registered"
            ) from exc

    # Recompute cron and next fire if schedule/timezone changed.
    # Use the incoming values when present; otherwise fall back to existing rule values.
    if data.schedule is not None or data.timezone is not None:
        schedule = data.schedule if data.schedule is not None else rule.schedule
        timezone = data.timezone if data.timezone is not None else rule.timezone
        rule.cron = derive_cron(schedule, timezone) if schedule != "none" else None
        rule.next_fire_at = (
            rule.compute_next_fire_at() if rule.cron and rule.enabled else None
        )

    # If disabled, clear next fire; if enabled without cron, clear too.
    if data.enabled is not None:
        if not rule.enabled or not rule.cron:
            rule.next_fire_at = None
        elif rule.next_fire_at is None:
            rule.next_fire_at = rule.compute_next_fire_at()

    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule


async def delete_alert_rule(
    *,
    session: AsyncSession,
    rule: AlertRule,
) -> None:
    await session.delete(rule)
    await session.commit()


async def create_alert_subscription(
    *,
    session: AsyncSession,
    workspace_id: int,
    alert_rule_id: UUID,
    data: AlertSubscriptionCreate,
) -> AlertSubscription:
    sub = AlertSubscription(
        workspace_id=workspace_id,
        user_id=data.user_id,
        alert_rule_id=alert_rule_id,
        channels=data.channels,
        enabled=data.enabled,
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    return sub


async def list_snapshots(
    *,
    session: AsyncSession,
    workspace_id: int,
    alert_rule_id: UUID,
    limit: int = 20,
) -> list[AlertSnapshot]:
    stmt = (
        select(AlertSnapshot)
        .join(AlertRule)
        .where(
            AlertSnapshot.alert_rule_id == alert_rule_id,
            AlertRule.workspace_id == workspace_id,
        )
        .order_by(AlertSnapshot.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
