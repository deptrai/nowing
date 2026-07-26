"""Cost-control gate for memory auto-extraction (Story 8.7 / AR-6 / RS-1).

Guards ``MemoryExtractionService.extract_from_turn`` against unbounded spend
before it ever calls the extraction LLM. Four checks run in order, first
block wins, all evaluated BEFORE any LLM call:

    1. anonymous (no billable owner)     -> reason="anonymous_unbilled"
    2. wallet spendable < min reserve    -> reason="insufficient_wallet"
    3. period spend >= budget cap        -> reason="budget_exceeded"
    4. rate count >= rate max            -> reason="rate_limited"

The budget and rate checks are opt-in (default ``0`` = disabled, matching the
repo's billing-flag convention: ``WEB_CRAWL_CREDIT_BILLING_ENABLED``,
``PLATFORM_SCRAPE_BILLING_ENABLED``). The wallet pre-check is always on — it
is the P0 guard against cost bleed from AR-6.

Deliberately path-agnostic: this module knows nothing about chat threads or
messages. It only takes a ``session``, a ``workspace``-like object (needs
``.id``, ``.user_id``), and an ``attributed_user_id``. Story 3.13 will add a
second (scraper-run) extraction path that must reuse this same gate.

Collaborator seams (``_wallet_spendable_micros`` / ``_period_spend_micros`` /
``_rate_count``) are module-level functions rather than being inlined so
tests can monkeypatch them individually without a live DB/Redis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.config import config

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db import Workspace

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtractGateResult:
    """Verdict from :func:`check_extract_allowed`.

    ``reason`` is one of the stable, machine-parseable identifiers below when
    ``allowed`` is ``False``; ``None`` when allowed.
    """

    allowed: bool
    reason: str | None = None


# Stable reason vocabulary (AC-8). Keep values snake_case and unchanging —
# callers/log consumers key off these strings.
REASON_ANONYMOUS_UNBILLED = "anonymous_unbilled"
REASON_INSUFFICIENT_WALLET = "insufficient_wallet"
REASON_BUDGET_EXCEEDED = "budget_exceeded"
REASON_RATE_LIMITED = "rate_limited"

_RATE_LIMIT_KEY_PREFIX = "nowing:memory_extract_rate"


async def _wallet_spendable_micros(session: AsyncSession, user_id: Any) -> int:
    """Return the owner's spendable balance (``balance - reserved``) in micros.

    A user_id that no longer resolves to a row is treated as having nothing
    spendable (fail-closed), not as an error — the wallet-error path is
    reserved for actual query failures (DB down, etc.).
    """
    from app.db import User

    result = await session.execute(
        select(User.credit_micros_balance, User.credit_micros_reserved).where(
            User.id == user_id
        )
    )
    row = result.first()
    if row is None:
        return 0
    balance, reserved = row
    return max(0, int(balance) - int(reserved))


def _period_window_start(now: datetime | None = None) -> datetime:
    """Rolling lookback start for the budget window.

    Rolling (``now - N``), not a calendar-day/-week/-month cliff, so a burst
    right after midnight rollover cannot slip through (Dev Notes R4).
    """
    now = now or datetime.now(UTC)
    window = config.MEMORY_AUTO_EXTRACT_BUDGET_WINDOW
    if window == "week":
        return now - timedelta(weeks=1)
    if window == "month":
        return now - timedelta(days=30)
    return now - timedelta(days=1)


async def _period_spend_micros(session: AsyncSession, workspace_id: int) -> int:
    """Sum ``memory_create`` ``TokenUsage.cost_micros`` for the current window."""
    from app.db import TokenUsage

    window_start = _period_window_start()
    result = await session.execute(
        select(func.coalesce(func.sum(TokenUsage.cost_micros), 0)).where(
            TokenUsage.workspace_id == workspace_id,
            TokenUsage.usage_type == "memory_create",
            TokenUsage.created_at >= window_start,
        )
    )
    return int(result.scalar_one())


async def _rate_count(workspace_id: int) -> int:
    """Return the current window's extraction count for ``workspace_id``.

    Fixed-window counter over Redis, mirroring
    ``app.capabilities.core.access.rate_limit`` (sync ``redis`` client,
    read-only here — increment happens in ``record_extraction`` after the
    gate passes and the LLM is actually invoked). Internally falls back to
    ``0`` when Redis itself is unreachable: the rate-limit is an abuse guard,
    not the AR-6 cost-bleed guard (that is the wallet pre-check, which does
    not depend on Redis), so an unreachable counter should not block
    extraction. ``check_extract_allowed`` still wraps this call in its own
    try/except for defense in depth in case this internal handling is ever
    bypassed (e.g. a test substituting this seam directly).
    """
    try:
        import redis

        client = redis.from_url(config.REDIS_APP_URL, decode_responses=True)
        raw = client.get(f"{_RATE_LIMIT_KEY_PREFIX}:{workspace_id}")
        return int(raw) if raw is not None else 0
    except Exception:
        logger.warning(
            "memory_extract_rate_count_unavailable workspace_id=%s", workspace_id
        )
        return 0


async def record_extraction(workspace_id: int) -> None:
    """Increment the rate-limit window counter after an allowed extraction.

    Called by the service only once the gate has passed AND the LLM call is
    actually about to happen — never on the enqueue-side best-effort check —
    so the enqueue-side consult (AC-7) cannot double-count.
    """
    try:
        import redis

        client = redis.from_url(config.REDIS_APP_URL, decode_responses=True)
        key = f"{_RATE_LIMIT_KEY_PREFIX}:{workspace_id}"
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, config.MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS)
    except Exception:
        logger.warning(
            "memory_extract_rate_increment_failed workspace_id=%s", workspace_id
        )


async def check_extract_allowed(
    session: AsyncSession,
    *,
    workspace: Workspace,
    attributed_user_id: Any | None,
) -> ExtractGateResult:
    """Decide whether a memory-extraction LLM call may proceed.

    Runs BEFORE any LLM call. First block wins; each gate is evaluated only
    if the prior ones passed, so a single call resolves at most one reason.
    """
    workspace_id = workspace.id

    # 1. Anonymous / no billable owner.
    if attributed_user_id is None:
        logger.info(
            "memory_extract_skip reason=%s workspace_id=%s",
            REASON_ANONYMOUS_UNBILLED,
            workspace_id,
        )
        return ExtractGateResult(allowed=False, reason=REASON_ANONYMOUS_UNBILLED)

    # 2. Wallet pre-check (always-on; the core AR-6 cost-bleed guard).
    # Fail-closed: any error resolving the wallet blocks extraction rather
    # than letting an outage turn into unbounded spend.
    try:
        spendable = await _wallet_spendable_micros(session, attributed_user_id)
    except Exception:
        logger.warning(
            "memory_extract_skip reason=%s workspace_id=%s wallet_check_failed=true",
            REASON_INSUFFICIENT_WALLET,
            workspace_id,
        )
        return ExtractGateResult(allowed=False, reason=REASON_INSUFFICIENT_WALLET)

    if spendable < config.MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS:
        logger.info(
            "memory_extract_skip reason=%s workspace_id=%s spendable=%s min_reserve=%s",
            REASON_INSUFFICIENT_WALLET,
            workspace_id,
            spendable,
            config.MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS,
        )
        return ExtractGateResult(allowed=False, reason=REASON_INSUFFICIENT_WALLET)

    # 3. Per-workspace spend/budget cap over the rolling period. Disabled
    # (no gating) when the cap is unset/0 — back-compat default.
    budget_cap = config.MEMORY_AUTO_EXTRACT_BUDGET_MICROS
    if budget_cap > 0:
        try:
            spent = await _period_spend_micros(session, workspace_id)
        except Exception:
            logger.warning(
                "memory_extract_skip reason=%s workspace_id=%s budget_check_failed=true",
                REASON_BUDGET_EXCEEDED,
                workspace_id,
            )
            return ExtractGateResult(allowed=False, reason=REASON_BUDGET_EXCEEDED)

        if spent >= budget_cap:
            logger.info(
                "memory_extract_skip reason=%s workspace_id=%s spent=%s cap=%s",
                REASON_BUDGET_EXCEEDED,
                workspace_id,
                spent,
                budget_cap,
            )
            return ExtractGateResult(allowed=False, reason=REASON_BUDGET_EXCEEDED)

    # 4. Time-based rate-limit. Disabled (no throttling) when unset/0.
    rate_max = config.MEMORY_AUTO_EXTRACT_RATE_MAX
    if rate_max > 0:
        try:
            rate = await _rate_count(workspace_id)
        except Exception:
            logger.warning(
                "memory_extract_skip reason=%s workspace_id=%s rate_check_failed=true",
                REASON_RATE_LIMITED,
                workspace_id,
            )
            return ExtractGateResult(allowed=False, reason=REASON_RATE_LIMITED)

        if rate >= rate_max:
            logger.info(
                "memory_extract_skip reason=%s workspace_id=%s rate=%s max=%s",
                REASON_RATE_LIMITED,
                workspace_id,
                rate,
                rate_max,
            )
            return ExtractGateResult(allowed=False, reason=REASON_RATE_LIMITED)

    return ExtractGateResult(allowed=True, reason=None)


__all__ = [
    "REASON_ANONYMOUS_UNBILLED",
    "REASON_BUDGET_EXCEEDED",
    "REASON_INSUFFICIENT_WALLET",
    "REASON_RATE_LIMITED",
    "ExtractGateResult",
    "check_extract_allowed",
    "record_extraction",
]
