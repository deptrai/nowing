"""Cost-control gate for news entity extraction (Story 14.2a / AC-4).

Guards NewsEntityExtractor.extract against unbounded LLM spend before it ever
calls the extraction LLM. Four checks run in order, first block wins:

    1. disabled (global kill-switch)     -> reason="disabled"
    2. wallet spendable < min reserve    -> reason="insufficient_wallet"
    3. period spend >= budget cap        -> reason="budget_exceeded"
    4. rate count >= rate max            -> reason="rate_limited"

Reuses the proven pattern from ``app/services/memory/extract_budget.py``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import func, select

from app.config import config
from app.db import Workspace
from app.services.token_tracking_service import UsageType, record_token_usage
from app.services.workspace_limits import WorkspaceLimitService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtractGateResult:
    """Verdict from :func:`check_news_entity_extraction_allowed`."""

    allowed: bool
    reason: str | None = None


REASON_DISABLED = "disabled"
REASON_INSUFFICIENT_WALLET = "insufficient_wallet"
REASON_BUDGET_EXCEEDED = "budget_exceeded"
REASON_RATE_LIMITED = "rate_limited"
REASON_GATE_ERROR = "gate_error"
REASON_ANONYMOUS_UNBILLED = "anonymous_unbilled"

_RATE_LIMIT_KEY_PREFIX = "nowing:news_entity_extract_rate"

_INCR_EXPIRE_LUA = """
local key = KEYS[1]
local ttl = tonumber(ARGV[1])
local count = redis.call('INCR', key)
if count == 1 then
    redis.call('EXPIRE', key, ttl)
end
return count
"""

_redis = None
_memory_hits: dict[str, list[float]] = defaultdict(list)
_memory_lock = Lock()


def _redis_client():
    """Lazily build and cache the sync Redis client."""
    global _redis
    if _redis is None:
        import redis

        _redis = redis.from_url(
            config.REDIS_APP_URL,
            decode_responses=True,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
        )
    return _redis


def _rate_key(workspace_id: int) -> str:
    return f"{_RATE_LIMIT_KEY_PREFIX}:{workspace_id}"


def _memory_count(key: str, window_seconds: int) -> int:
    """Per-worker in-memory window count (Redis-unavailable fallback)."""
    now = time.monotonic()
    with _memory_lock:
        hits = [t for t in _memory_hits[key] if now - t < window_seconds]
        _memory_hits[key] = hits
        return len(hits)


def _memory_incr(key: str, window_seconds: int) -> int:
    """Per-worker in-memory window increment (Redis-unavailable fallback)."""
    now = time.monotonic()
    with _memory_lock:
        hits = [t for t in _memory_hits[key] if now - t < window_seconds]
        hits.append(now)
        _memory_hits[key] = hits
        return len(hits)


async def _wallet_spendable_micros(session: AsyncSession, user_id: Any) -> int:
    """Return the user's spendable balance in micros."""
    from app.services import wallet_credit

    try:
        spendable = await wallet_credit.spendable_micros(session, user_id)
    except ValueError:
        return 0
    except Exception:
        raise
    return max(0, int(spendable))


def _period_window_start(now: datetime | None = None) -> datetime:
    """Rolling lookback start for the budget window."""
    now = now or datetime.now(UTC)
    window = config.NEWS_ENTITY_EXTRACTION_BUDGET_WINDOW
    if window == "week":
        return now - timedelta(weeks=1)
    if window == "month":
        return now - timedelta(days=30)
    return now - timedelta(days=1)


async def _period_spend_micros(session: AsyncSession, workspace_id: int) -> int:
    """Sum ``entity_extraction`` ``TokenUsage.cost_micros`` for current window."""
    from app.db import TokenUsage

    window_start = _period_window_start()
    result = await session.execute(
        select(func.coalesce(func.sum(TokenUsage.cost_micros), 0)).where(
            TokenUsage.workspace_id == workspace_id,
            TokenUsage.usage_type == UsageType.ENTITY_EXTRACTION,
            TokenUsage.created_at >= window_start,
        )
    )
    return int(result.scalar_one())


def _rate_count_sync(workspace_id: int) -> int:
    key = _rate_key(workspace_id)
    window = config.NEWS_ENTITY_EXTRACTION_RATE_WINDOW_SECONDS
    try:
        raw = _redis_client().get(key)
        return int(raw) if raw is not None else 0
    except Exception:
        logger.warning(
            "news_entity_extract_rate_count_redis_unavailable workspace_id=%s fallback=in_memory",
            workspace_id,
        )
        return _memory_count(key, window)


async def _rate_count(workspace_id: int) -> int:
    """Return the current window's extraction count for ``workspace_id``."""
    return await asyncio.to_thread(_rate_count_sync, workspace_id)


def _record_extraction_sync(workspace_id: int) -> int:
    """Increment the extraction rate counter and return the new count."""
    key = _rate_key(workspace_id)
    window = config.NEWS_ENTITY_EXTRACTION_RATE_WINDOW_SECONDS
    try:
        client = _redis_client()
        return int(client.eval(_INCR_EXPIRE_LUA, 1, key, window))
    except Exception:
        logger.warning(
            "news_entity_extract_rate_increment_redis_unavailable workspace_id=%s fallback=in_memory",
            workspace_id,
        )
        return _memory_incr(key, window)


async def check_news_entity_extraction_allowed(
    session: AsyncSession,
    *,
    workspace_id: int | None = None,
    workspace: Workspace | None = None,
    attributed_user_id: Any | None = None,
    user_id: Any | None = None,
) -> ExtractGateResult:
    """Decide whether news entity extraction LLM call may proceed.

    Evaluated BEFORE any LLM call. Never raises: gracefully degrades on error.
    """
    try:
        resolved_workspace_id = (
            workspace_id
            if workspace_id is not None
            else (workspace.id if workspace else None)
        )
        if resolved_workspace_id is None:
            return ExtractGateResult(allowed=False, reason=REASON_GATE_ERROR)

        effective_user_id = user_id if user_id is not None else attributed_user_id
        if effective_user_id is None:
            ws = await session.get(Workspace, resolved_workspace_id)
            if ws and ws.user_id:
                effective_user_id = ws.user_id

        # 1. Global kill-switch check
        if not config.NEWS_ENTITY_EXTRACTION_ENABLED:
            logger.info(
                "news_entity_extraction_disabled workspace_id=%s reason=%s",
                resolved_workspace_id,
                REASON_DISABLED,
            )
            return ExtractGateResult(allowed=False, reason=REASON_DISABLED)

        limits = await WorkspaceLimitService.get_effective_limits(
            session, resolved_workspace_id
        )

        # 2. Wallet eligibility pre-check
        wallet_pre_check = limits.news_entity_extraction_wallet_pre_check is not False
        min_reserve = config.NEWS_ENTITY_EXTRACTION_MIN_RESERVE_MICROS
        if wallet_pre_check and min_reserve > 0 and effective_user_id is not None:
            try:
                spendable = await _wallet_spendable_micros(session, effective_user_id)
            except Exception:
                logger.warning(
                    "news_entity_extraction_insufficient_wallet workspace_id=%s wallet_lookup_failed=true",
                    resolved_workspace_id,
                )
                return ExtractGateResult(
                    allowed=False, reason=REASON_INSUFFICIENT_WALLET
                )

            if spendable < min_reserve:
                logger.info(
                    "news_entity_extraction_insufficient_wallet workspace_id=%s spendable=%s min_reserve=%s",
                    resolved_workspace_id,
                    spendable,
                    min_reserve,
                )
                return ExtractGateResult(
                    allowed=False, reason=REASON_INSUFFICIENT_WALLET
                )

        # 3. Budget cap check
        if (
            limits.news_entity_extraction_spend_cap_micros is not None
            and limits.news_entity_extraction_spend_cap_micros <= 0
        ):
            return ExtractGateResult(allowed=False, reason=REASON_BUDGET_EXCEEDED)

        budget_cap = (
            limits.news_entity_extraction_spend_cap_micros
            if limits.news_entity_extraction_spend_cap_micros is not None
            else config.NEWS_ENTITY_EXTRACTION_BUDGET_MICROS
        )
        if budget_cap is not None and budget_cap > 0:
            try:
                spent = await _period_spend_micros(session, resolved_workspace_id)
            except Exception:
                logger.warning(
                    "news_entity_extraction_budget_exceeded workspace_id=%s budget_query_failed=true",
                    resolved_workspace_id,
                )
                return ExtractGateResult(allowed=False, reason=REASON_BUDGET_EXCEEDED)

            if spent >= budget_cap:
                logger.info(
                    "news_entity_extraction_budget_exceeded workspace_id=%s spent=%s cap=%s",
                    resolved_workspace_id,
                    spent,
                    budget_cap,
                )
                return ExtractGateResult(allowed=False, reason=REASON_BUDGET_EXCEEDED)

        # 4. Rate-limit / item cap check
        if (
            limits.news_entity_extraction_item_cap is not None
            and limits.news_entity_extraction_item_cap <= 0
        ):
            return ExtractGateResult(allowed=False, reason=REASON_RATE_LIMITED)

        rate_max = (
            limits.news_entity_extraction_item_cap
            if limits.news_entity_extraction_item_cap is not None
            else config.NEWS_ENTITY_EXTRACTION_RATE_MAX
        )
        if rate_max is not None and rate_max > 0:
            try:
                rate = await _rate_count(resolved_workspace_id)
            except Exception:
                logger.warning(
                    "news_entity_extraction_rate_limited workspace_id=%s rate_lookup_failed=true",
                    resolved_workspace_id,
                )
                return ExtractGateResult(allowed=False, reason=REASON_RATE_LIMITED)

            if rate >= rate_max:
                logger.info(
                    "news_entity_extraction_rate_limited workspace_id=%s rate=%s max=%s",
                    resolved_workspace_id,
                    rate,
                    rate_max,
                )
                return ExtractGateResult(allowed=False, reason=REASON_RATE_LIMITED)

        return ExtractGateResult(allowed=True, reason=None)

    except Exception:
        logger.warning(
            "news_entity_extraction_gate_error workspace_id=%s",
            workspace_id,
            exc_info=True,
        )
        return ExtractGateResult(allowed=False, reason=REASON_GATE_ERROR)


async def record_news_entity_extraction(
    session: AsyncSession,
    *,
    workspace_id: int | None = None,
    workspace: Workspace | None = None,
    attributed_user_id: Any | None = None,
    user_id: Any | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    cost_micros: int = 0,
    model: str | None = None,
    model_breakdown: dict[str, Any] | None = None,
    call_details: dict[str, Any] | None = None,
    record_usage: bool = True,
) -> None:
    """Increment rate limit counter and optionally record TokenUsage for news entity extraction."""
    resolved_workspace_id = (
        workspace_id
        if workspace_id is not None
        else (workspace.id if workspace else None)
    )
    if resolved_workspace_id is None:
        return

    effective_user_id = user_id if user_id is not None else attributed_user_id
    if effective_user_id is None:
        ws = await session.get(Workspace, resolved_workspace_id)
        if ws and ws.user_id:
            effective_user_id = ws.user_id

    # Coerce effective_user_id to UUID for TokenUsage.user_id (UUID column).
    if isinstance(effective_user_id, str):
        try:
            effective_user_id = UUID(effective_user_id)
        except (ValueError, AttributeError):
            try:
                ws = await session.get(Workspace, resolved_workspace_id)
                if ws and ws.user_id:
                    effective_user_id = ws.user_id
            except AttributeError:
                pass

    if record_usage:
        # 1. Record TokenUsage row first. If it fails, do not inflate the
        # rate counter without any cost being tracked (AC-4 / AD cost control).
        if model_breakdown is None and model:
            model_breakdown = {
                model: {
                    "model": model,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cost_micros": cost_micros,
                }
            }
        if call_details is None and model:
            call_details = {"model": model}

        try:
            await record_token_usage(
                session,
                usage_type=UsageType.ENTITY_EXTRACTION,
                workspace_id=resolved_workspace_id,
                user_id=effective_user_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_micros=cost_micros,
                model_breakdown=model_breakdown,
                call_details=call_details,
            )
        except Exception:
            logger.warning(
                "failed_to_record_news_entity_token_usage workspace_id=%s",
                resolved_workspace_id,
                exc_info=True,
            )
            return

    # 2. Increment rate counter in Redis / memory only after token recording.
    await asyncio.to_thread(_record_extraction_sync, resolved_workspace_id)


__all__ = [
    "REASON_ANONYMOUS_UNBILLED",
    "REASON_BUDGET_EXCEEDED",
    "REASON_DISABLED",
    "REASON_GATE_ERROR",
    "REASON_INSUFFICIENT_WALLET",
    "REASON_RATE_LIMITED",
    "ExtractGateResult",
    "check_news_entity_extraction_allowed",
    "record_news_entity_extraction",
]
