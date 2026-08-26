"""Admin routes for managing dynamic scraper rule versions."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import ScraperRule, get_async_session
from app.redis_client import get_redis_client
from app.schemas.admin_scraper_rules import (
    ScraperRuleCreate,
    ScraperRuleListItem,
    ScraperRuleListResponse,
    ScraperRuleRead,
    ScraperRuleUpdate,
)
from app.services.scraper_rule_validator import (
    InvalidRegexError,
    InvalidSelectorError,
    ReDoSTimeoutError,
)
from app.services.scraper_rules_service import (
    CannotDeleteActiveRuleError,
    RuleNotFoundError,
    activate_rule,
    create_rule,
    delete_rule,
    get_active_rule,
    get_rules,
    reset_circuit_breaker,
    trip_circuit_breaker,
)
from app.users import require_superuser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/scraper-rules", tags=["admin"])


def _handle_validation_error(exc: Exception) -> HTTPException:
    """Map sandbox validation errors to 422 with the expected code shape."""
    if isinstance(exc, InvalidSelectorError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid CSS selector: {exc}",
        )
    if isinstance(exc, (ReDoSTimeoutError, InvalidRegexError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "REDOS_TIMEOUT", "message": str(exc)},
        )
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"Validation error: {exc}",
    )


def _rule_to_read(rule: ScraperRule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "platform": rule.platform,
        "version": rule.version,
        "rule_schema": rule.rule_schema,
        "is_active": rule.is_active,
        "created_by_user_id": rule.created_by_user_id,
        "updated_by_user_id": rule.updated_by_user_id,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


@router.get("", response_model=ScraperRuleListResponse)
async def list_scraper_rules(
    limit: int = 20,
    offset: int = 0,
    platform: str | None = None,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
) -> ScraperRuleListResponse:
    """List scraper rule versions, optionally filtered by platform."""
    rules = await get_rules(
        session=session,
        limit=max(1, min(limit, 100)),
        offset=max(0, offset),
        platform=platform,
    )
    items = [
        ScraperRuleListItem(
            platform=rule.platform,
            version=rule.version,
            is_active=rule.is_active,
            updated_at=rule.updated_at,
            updated_by=rule.updated_by_user_id,
        )
        for rule in rules
    ]
    return ScraperRuleListResponse(
        items=items,
        total=await _count_rules(session, platform),
    )


async def _count_rules(session: AsyncSession, platform: str | None) -> int:
    from sqlalchemy import func, select

    stmt = select(func.count()).select_from(ScraperRule)
    if platform:
        stmt = stmt.where(ScraperRule.platform == platform)
    result = await session.execute(stmt)
    return result.scalar() or 0


@router.post(
    "/{platform}",
    response_model=ScraperRuleRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_scraper_rule(
    platform: str,
    payload: ScraperRuleCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
) -> ScraperRule:
    """Create a new rule version for the given platform."""
    try:
        rule = await create_rule(
            session=session,
            platform=platform,
            rule_schema=payload.rule_schema,
            auth=auth,
        )
    except (InvalidSelectorError, ReDoSTimeoutError, InvalidRegexError) as exc:
        raise _handle_validation_error(exc) from None
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.errors(),
        ) from exc
    return rule


@router.patch(
    "/{platform}/{version}",
    response_model=ScraperRuleRead,
)
async def activate_scraper_rule(
    platform: str,
    version: int,
    payload: ScraperRuleUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
    redis: Any = Depends(get_redis_client),
) -> ScraperRule:
    """Activate a specific rule version."""
    if not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Use DELETE to deactivate; PATCH only supports activation",
        )
    try:
        rule = await activate_rule(
            session=session,
            platform=platform,
            version=version,
            auth=auth,
            redis=redis,
        )
    except RuleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return rule


@router.delete("/{platform}/{version}")
async def delete_scraper_rule(
    platform: str,
    version: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
) -> dict[str, Any]:
    """Delete an inactive rule version."""
    try:
        await delete_rule(
            session=session,
            platform=platform,
            version=version,
            auth=auth,
        )
    except RuleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except CannotDeleteActiveRuleError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return {"deleted": True, "platform": platform, "version": version}


@router.get("/{platform}", response_model=ScraperRuleRead)
async def get_active_scraper_rule(
    platform: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
) -> ScraperRule:
    """Get the currently active rule for a platform."""
    rule = await get_active_rule(session=session, platform=platform)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active rule for platform {platform}",
        )
    return rule


@router.post("/{platform}/circuit-breaker/trip", response_model=ScraperRuleRead)
async def trip_scraper_circuit_breaker(
    platform: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
    redis: Any = Depends(get_redis_client),
) -> ScraperRule:
    """Trip the circuit breaker for the active rule."""
    try:
        rule = await trip_circuit_breaker(
            session=session,
            platform=platform,
            auth=auth,
            redis=redis,
        )
    except RuleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return rule


@router.post("/{platform}/circuit-breaker/reset", response_model=ScraperRuleRead)
async def reset_scraper_circuit_breaker(
    platform: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
    redis: Any = Depends(get_redis_client),
) -> ScraperRule:
    """Reset the circuit breaker for the active rule."""
    try:
        rule = await reset_circuit_breaker(
            session=session,
            platform=platform,
            auth=auth,
            redis=redis,
        )
    except RuleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return rule


@router.post("/{platform}/refresh")
async def refresh_scraper_rule(
    platform: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
    redis: Any = Depends(get_redis_client),
) -> dict[str, Any]:
    """Re-publish the active rule to refresh subscribers."""
    rule = await get_active_rule(session=session, platform=platform)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active rule for platform {platform}",
        )
    from app.services.scraper_rule_pubsub import publish_rule_update

    await publish_rule_update(
        redis=redis,
        platform=platform,
        version=rule.version,
        is_active=True,
        circuit_breaker_tripped=rule.rule_schema.get("circuit_breaker", {}).get(
            "tripped", False
        ),
    )
    return {"refreshed": True, "platform": platform, "version": rule.version}
