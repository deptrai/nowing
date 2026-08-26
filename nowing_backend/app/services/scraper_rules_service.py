from __future__ import annotations

import copy
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AuditEvent, ScraperRule
from app.lead_intelligence.services.circuit_breaker import PlatformCircuitBreaker
from app.redis_client import get_redis_client
from app.schemas.admin_scraper_rules import RuleSchema
from app.services import scraper_rule_cache as _rule_cache_module
from app.services.scraper_rule_pubsub import publish_rule_update
from app.services.scraper_rule_validator import (
    InvalidRegexError,
    validate_css_selectors,
    validate_regexes_async,
)

logger = logging.getLogger(__name__)


class RuleNotFoundError(ValueError):
    """Raised when a requested rule version does not exist."""


class CannotDeleteActiveRuleError(ValueError):
    """Raised when an active rule version is requested to be deleted."""


def _as_rule_schema(value: Any) -> RuleSchema:
    if isinstance(value, RuleSchema):
        return value
    return RuleSchema.model_validate(value)


async def _max_version(session: AsyncSession, platform: str) -> int | None:
    result = await session.execute(
        select(ScraperRule.version)
        .where(ScraperRule.platform == platform)
        .order_by(ScraperRule.version.desc())
        .limit(1)
        .with_for_update()
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


def _rule_schema_copy(rule: ScraperRule) -> dict[str, Any]:
    """Return a deep copy of the JSONB rule_schema for cache/response use."""
    return copy.deepcopy(rule.rule_schema)


def _update_circuit_breaker(
    rule_schema: dict[str, Any], tripped: bool
) -> dict[str, Any]:
    circuit_breaker = dict(rule_schema.get("circuit_breaker", {}))
    circuit_breaker["tripped"] = tripped
    return {**rule_schema, "circuit_breaker": circuit_breaker}


async def _after_rule_change(
    rule: ScraperRule,
    redis: Any,
    is_active: bool,
    circuit_breaker_tripped: bool,
) -> None:
    """Publish the change and warm the in-process cache when Redis is up."""
    if redis is None:
        return
    try:
        await publish_rule_update(
            redis=redis,
            platform=rule.platform,
            version=rule.version,
            is_active=is_active,
            circuit_breaker_tripped=circuit_breaker_tripped,
            updated_at=rule.updated_at.isoformat() if rule.updated_at else None,
        )
    except Exception:
        logger.exception("Failed to publish scraper rule update")
    try:
        _rule_cache_module.set(rule.platform, _rule_schema_copy(rule))
    except Exception:
        logger.exception("Failed to warm scraper rule cache")


async def _redis_client_silent() -> Any:
    """Return a Redis client, or None if Redis is not reachable."""
    try:
        return await get_redis_client()
    except Exception:
        logger.warning("Redis unavailable for scraper rule operation")
        return None


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
    try:
        await validate_regexes_async(schema.regexes)
    except InvalidRegexError:
        raise

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
                "rule_schema": schema.model_dump(),
            },
        )
    )
    await session.flush()
    await session.commit()

    redis = await _redis_client_silent()
    if should_activate:
        await _after_rule_change(
            rule, redis, is_active=True, circuit_breaker_tripped=False
        )

    return rule


async def activate_rule(
    session: AsyncSession,
    platform: str,
    version: int,
    is_active: bool = True,
    auth: Any = None,
    redis: Any | None = None,
) -> ScraperRule:
    """Activate or deactivate a specific rule version."""
    if version < 1:
        raise RuleNotFoundError(f"Rule {platform}/{version} not found")

    user_id: UUID | None = getattr(auth.user, "id", None)

    rule = await session.execute(
        select(ScraperRule)
        .where(ScraperRule.platform == platform, ScraperRule.version == version)
        .with_for_update()
    )
    rule = rule.scalar_one_or_none()
    if rule is None:
        raise RuleNotFoundError(f"Rule {platform}/{version} not found")

    if is_active:
        # Deactivate all versions for this platform before activating the chosen one.
        await session.execute(
            update(ScraperRule)
            .where(ScraperRule.platform == platform, ScraperRule.is_active.is_(True))
            .values(is_active=False)
        )
        await session.flush()

    rule.is_active = is_active
    rule.updated_by_user_id = user_id
    await session.flush()

    session.add(
        _audit(
            action="scraper_rule.activate",
            actor_id=user_id,
            diff_payload={
                "platform": platform,
                "version": version,
                "rule_schema": rule.rule_schema,
            },
        )
    )
    await session.flush()
    await session.commit()

    if redis is None:
        redis = await _redis_client_silent()

    if is_active:
        await _after_rule_change(
            rule,
            redis,
            is_active=True,
            circuit_breaker_tripped=rule.rule_schema.get("circuit_breaker", {}).get(
                "tripped", False
            ),
        )
    else:
        # Admin deactivated the active rule; invalidate the cache so the next
        # read falls back to the default (or a newly active rule).
        try:
            _rule_cache_module.invalidate(platform)
        except Exception:
            logger.exception("Failed to invalidate scraper rule cache")
        await _after_rule_change(
            rule,
            redis,
            is_active=False,
            circuit_breaker_tripped=rule.rule_schema.get("circuit_breaker", {}).get(
                "tripped", False
            ),
        )

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
        select(ScraperRule)
        .where(ScraperRule.platform == platform, ScraperRule.version == version)
        .with_for_update()
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
                "rule_schema": rule.rule_schema,
            },
        )
    )
    await session.flush()
    await session.commit()


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
    stmt = stmt.order_by(ScraperRule.updated_at.desc()).offset(offset).limit(limit)
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


async def get_active_rule_schema(
    session: AsyncSession,
    platform: str,
) -> dict[str, Any] | None:
    """Return the rule_schema of the active rule, or None."""
    rule = await get_active_rule(session, platform)
    if rule is None:
        return None
    return _rule_schema_copy(rule)


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
        raise RuleNotFoundError(f"No active rule for {platform}")

    rule.rule_schema = _update_circuit_breaker(rule.rule_schema, tripped=True)
    rule.updated_by_user_id = user_id
    await session.flush()

    session.add(
        _audit(
            action="scraper_rule.trip",
            actor_id=user_id,
            diff_payload={
                "platform": platform,
                "version": rule.version,
                "rule_schema": rule.rule_schema,
            },
        )
    )
    await session.flush()
    await session.commit()

    trip_duration = rule.rule_schema.get("circuit_breaker", {}).get(
        "trip_duration_seconds", 300
    )
    breaker = PlatformCircuitBreaker(redis_client=redis, cooldown_seconds=trip_duration)
    try:
        await breaker.trip(platform)
    except Exception:
        logger.exception("Failed to write OPEN state to Redis circuit breaker")

    await _after_rule_change(rule, redis, is_active=True, circuit_breaker_tripped=True)

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
        raise RuleNotFoundError(f"No active rule for {platform}")

    rule.rule_schema = _update_circuit_breaker(rule.rule_schema, tripped=False)
    rule.updated_by_user_id = user_id
    await session.flush()

    session.add(
        _audit(
            action="scraper_rule.reset",
            actor_id=user_id,
            diff_payload={
                "platform": platform,
                "version": rule.version,
                "rule_schema": rule.rule_schema,
            },
        )
    )
    await session.flush()
    await session.commit()

    breaker = PlatformCircuitBreaker(redis_client=redis)
    try:
        await breaker.reset(platform)
    except Exception:
        logger.exception("Failed to reset Redis circuit breaker")

    await _after_rule_change(rule, redis, is_active=True, circuit_breaker_tripped=False)

    return rule
