from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AuditEvent, ScraperRule
from app.redis_client import get_redis_client
from app.schemas.admin_scraper_rules import RuleSchema
from app.services.scraper_rule_pubsub import publish_rule_update
from app.services.scraper_rule_validator import (
    validate_css_selectors,
    validate_regexes,
)

logger = logging.getLogger(__name__)


class RuleNotFoundError(ValueError):
    """Raised when a requested rule version does not exist."""


class CannotDeleteActiveRuleError(ValueError):
    """Raised when an active rule version is requested to be deleted."""


class PermissionDeniedError(ValueError):
    """Raised when an actor is not a superuser."""


CIRCUIT_BREAKER_KEY = "scraper_rule:{platform}:circuit_breaker"


def _now() -> float:
    from time import perf_counter

    return perf_counter()


def _as_rule_schema(value: Any) -> RuleSchema:
    if isinstance(value, RuleSchema):
        return value
    return RuleSchema.model_validate(value)


async def _max_version(session: AsyncSession, platform: str) -> int | None:
    result = await session.execute(
        select(func.max(ScraperRule.version)).where(ScraperRule.platform == platform)
    )
    return result.scalar()


def _audit(
    action: str,
    actor_id: UUID,
    diff_payload: dict[str, Any],
) -> AuditEvent:
    return AuditEvent(
        action=action,
        actor_id=actor_id,
        diff_payload=diff_payload,
    )


async def create_rule(
    session: AsyncSession,
    platform: str,
    rule_schema: dict[str, Any] | RuleSchema,
    auth: Any,
) -> ScraperRule:
    """Create a new rule version for a platform. First version becomes active."""
    user_id: UUID | None = getattr(auth.user, "id", None)

    schema = _as_rule_schema(rule_schema)
    validate_css_selectors(schema.selectors)
    validate_regexes(schema.regexes)

    existing_max = await _max_version(session, platform)
    new_version = (existing_max or 0) + 1
    # First rule for a platform auto-activates.
    should_activate = existing_max is None

    rule = ScraperRule(
        platform=platform,
        version=new_version,
        rule_schema=schema.model_dump(),
        is_active=should_activate,
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )
    session.add(rule)
    await session.flush()

    session.add(
        _audit(
            action="scraper_rule.create",
            actor_id=user_id,
            diff_payload={
                "platform": platform,
                "version": new_version,
                "schema": schema.model_dump(),
            },
        )
    )
    await session.flush()

    if should_activate:
        await publish_rule_update(
            redis=None,
            platform=platform,
            version=new_version,
            is_active=True,
            circuit_breaker_tripped=False,
        )

    return rule


async def activate_rule(
    session: AsyncSession,
    platform: str,
    version: int,
    auth: Any,
    redis: Any | None = None,
) -> ScraperRule:
    """Activate a specific rule version and deactivate all others."""
    if version < 1:
        raise ValueError(f"Rule version must be >= 1, got {version}")

    user_id: UUID | None = getattr(auth.user, "id", None)

    rule = await session.execute(
        select(ScraperRule).where(
            ScraperRule.platform == platform, ScraperRule.version == version
        )
    )
    rule = rule.scalar_one_or_none()
    if rule is None:
        raise RuleNotFoundError(f"Rule {platform}/{version} not found")

    # Deactivate all versions for this platform.
    await session.execute(
        update(ScraperRule)
        .where(ScraperRule.platform == platform, ScraperRule.is_active.is_(True))
        .values(is_active=False)
    )
    await session.flush()

    rule.is_active = True
    rule.updated_by_user_id = user_id
    await session.flush()

    if redis is None:
        redis = await get_redis_client()
    await publish_rule_update(
        redis=redis,
        platform=platform,
        version=version,
        is_active=True,
        circuit_breaker_tripped=rule.rule_schema.get("circuit_breaker", {}).get(
            "tripped", False
        ),
    )

    session.add(
        _audit(
            action="scraper_rule.activate",
            actor_id=user_id,
            diff_payload={
                "platform": platform,
                "version": version,
                "schema": rule.rule_schema,
            },
        )
    )
    await session.flush()

    return rule


async def delete_rule(
    session: AsyncSession,
    platform: str,
    version: int,
    auth: Any,
) -> None:
    """Delete a rule version. Active versions cannot be deleted."""
    user_id: UUID | None = getattr(auth.user, "id", None)

    rule = await session.execute(
        select(ScraperRule).where(
            ScraperRule.platform == platform, ScraperRule.version == version
        )
    )
    rule = rule.scalar_one_or_none()
    if rule is None:
        raise RuleNotFoundError(f"Rule {platform}/{version} not found")
    if rule.is_active:
        raise CannotDeleteActiveRuleError(
            f"Cannot delete active rule {platform}/{version}"
        )

    await session.delete(rule)

    session.add(
        _audit(
            action="scraper_rule.delete",
            actor_id=user_id,
            diff_payload={
                "platform": platform,
                "version": version,
            },
        )
    )
    await session.flush()


async def get_rules(
    session: AsyncSession,
    limit: int,
    offset: int,
    platform: str | None = None,
) -> list[ScraperRule]:
    """List rule versions, optionally filtered by platform."""
    stmt = select(ScraperRule)
    if platform:
        stmt = stmt.where(ScraperRule.platform == platform)
    stmt = (
        stmt.order_by(ScraperRule.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_active_rule(
    session: AsyncSession,
    platform: str,
) -> ScraperRule | None:
    """Return the currently active rule for a platform, if any."""
    result = await session.execute(
        select(ScraperRule).where(
            ScraperRule.platform == platform, ScraperRule.is_active.is_(True)
        )
    )
    return result.scalar_one_or_none()


async def trip_circuit_breaker(
    session: AsyncSession,
    platform: str,
    auth: Any,
    redis: Any,
) -> ScraperRule:
    """Trip the circuit breaker for the active rule and persist it."""
    user_id: UUID | None = getattr(auth.user, "id", None)

    rule = await get_active_rule(session, platform)
    if rule is None:
        raise RuleNotFoundError(f"No active rule for platform {platform}")

    rule.rule_schema.setdefault("circuit_breaker", {})
    rule.rule_schema["circuit_breaker"]["tripped"] = True
    rule.updated_by_user_id = user_id
    await session.flush()

    await redis.set(
        CIRCUIT_BREAKER_KEY.format(platform=platform),
        json.dumps({"tripped": True, "tripped_at": _now()}),
        ex=rule.rule_schema["circuit_breaker"].get("trip_duration_seconds", 300),
    )

    await publish_rule_update(
        redis=redis,
        platform=platform,
        version=rule.version,
        is_active=True,
        circuit_breaker_tripped=True,
    )

    session.add(
        _audit(
            action="scraper_rule.circuit_breaker.trip",
            actor_id=user_id,
            diff_payload={
                "platform": platform,
                "version": rule.version,
            },
        )
    )
    await session.flush()

    return rule


async def reset_circuit_breaker(
    session: AsyncSession,
    platform: str,
    auth: Any,
    redis: Any,
) -> ScraperRule:
    """Reset the circuit breaker for the active rule."""
    user_id: UUID | None = getattr(auth.user, "id", None)

    rule = await get_active_rule(session, platform)
    if rule is None:
        raise RuleNotFoundError(f"No active rule for platform {platform}")

    rule.rule_schema.setdefault("circuit_breaker", {})
    rule.rule_schema["circuit_breaker"]["tripped"] = False
    rule.updated_by_user_id = user_id
    await session.flush()

    await redis.delete(CIRCUIT_BREAKER_KEY.format(platform=platform))

    await publish_rule_update(
        redis=redis,
        platform=platform,
        version=rule.version,
        is_active=True,
        circuit_breaker_tripped=False,
    )

    session.add(
        _audit(
            action="scraper_rule.circuit_breaker.reset",
            actor_id=user_id,
            diff_payload={
                "platform": platform,
                "version": rule.version,
            },
        )
    )
    await session.flush()

    return rule
