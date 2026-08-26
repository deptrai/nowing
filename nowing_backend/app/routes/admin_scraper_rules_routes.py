"""Admin routes for managing dynamic scraper rule versions."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import ScraperRule, get_async_session
from app.redis_client import get_redis_client
from app.schemas.admin_scraper_rules import (
    ScraperRuleCreate,
    ScraperRuleListItem,
    ScraperRuleListResponse,
    ScraperRuleMetricsResponse,
    ScraperRuleRead,
    ScraperRuleUpdate,
)
from app.services import scraper_rule_cache
from app.services.scraper_rule_metrics import get_error_rate
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
    """Map sandbox validation errors to a single 422 envelope."""
    if isinstance(exc, InvalidSelectorError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "INVALID_CSS_SELECTOR", "detail": str(exc)},
        )
    if isinstance(exc, (ReDoSTimeoutError, InvalidRegexError)):
        code = (
            "REDOS_TIMEOUT" if isinstance(exc, ReDoSTimeoutError) else "INVALID_REGEX"
        )
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": code, "detail": str(exc)},
        )
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "VALIDATION_ERROR", "detail": exc.errors()},
        )
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={"code": "VALIDATION_ERROR", "detail": str(exc)},
    )


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
    platform: Annotated[str, Path(min_length=1, max_length=64)],
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
        raise _handle_validation_error(exc) from exc
    return rule


@router.patch(
    "/{platform}/{version}",
    response_model=ScraperRuleRead,
)
async def activate_scraper_rule(
    platform: Annotated[str, Path(min_length=1, max_length=64)],
    version: Annotated[int, Path(ge=1)],
    payload: ScraperRuleUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
    redis: Any = Depends(get_redis_client),
) -> ScraperRule:
    """Activate or deactivate a specific rule version."""
    try:
        rule = await activate_rule(
            session=session,
            platform=platform,
            version=version,
            is_active=payload.is_active,
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
    platform: Annotated[str, Path(min_length=1, max_length=64)],
    version: Annotated[int, Path(ge=1)],
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
    platform: Annotated[str, Path(min_length=1, max_length=64)],
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
    platform: Annotated[str, Path(min_length=1, max_length=64)],
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
    platform: Annotated[str, Path(min_length=1, max_length=64)],
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
    platform: Annotated[str, Path(min_length=1, max_length=64)],
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

    scraper_rule_cache.invalidate(platform)
    await publish_rule_update(
        redis=redis,
        platform=platform,
        version=rule.version,
        is_active=True,
        updated_at=rule.updated_at.isoformat() if rule.updated_at else None,
        circuit_breaker_tripped=rule.rule_schema.get("circuit_breaker", {}).get(
            "tripped", False
        ),
    )
    return {"refreshed": True, "platform": platform, "version": rule.version}


@router.get("/{platform}/metrics", response_model=ScraperRuleMetricsResponse)
async def get_scraper_rule_metrics(
    platform: Annotated[str, Path(min_length=1, max_length=64)],
    auth: AuthContext = Depends(require_superuser),
) -> ScraperRuleMetricsResponse:
    """Return recent success/error metrics for a platform."""
    return ScraperRuleMetricsResponse.model_validate(await get_error_rate(platform))
