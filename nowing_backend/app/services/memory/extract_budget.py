"""Cost-control gate for memory auto-extraction (Story 8.7 / AR-6 / RS-1).

Guards ``MemoryExtractionService.extract_from_turn`` against unbounded spend
before it ever calls the extraction LLM. Four checks run in order, first
block wins, all evaluated BEFORE any LLM call:

    1. anonymous (no billable owner)     -> reason="anonymous_unbilled"
    2. wallet spendable < min reserve    -> reason="insufficient_wallet"
    3. period spend >= budget cap        -> reason="budget_exceeded"
    4. rate count >= rate max            -> reason="rate_limited"

**What the wallet pre-check is, and is not.** It is an *eligibility* gate: do
not perform optional background work for an attributed user who cannot pay for
their foreground work. It is **not** a spend meter for extraction, and it cannot
bound extraction spend. Per **AD-8** the wallet-debit surface is enumerated as
ETL pages / premium model calls / deep-research — memory extraction is
deliberately excluded, and ``record_token_usage(usage_type="memory_create")``
is Story 8.9's *observability* record (it writes a ``TokenUsage`` row; it does
not debit the wallet). Extraction spend against platform-key models is
therefore unmetered by design; the bounds that actually apply are the
``MEMORY_AUTO_EXTRACT_ENABLED`` / per-workspace kill-switch (Story 8.8) and the
opt-in budget cap below.

Config keys consumed (see ``app.config``):
    - ``MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS`` (always-on wallet floor)
    - ``MEMORY_AUTO_EXTRACT_BUDGET_MICROS`` (period spend ceiling; 0 = off)
    - ``MEMORY_AUTO_EXTRACT_BUDGET_WINDOW`` (``day``/``week``/``month``)
    - ``MEMORY_AUTO_EXTRACT_RATE_MAX`` (max extractions per window; 0 = off)
    - ``MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS`` (rolling window for the cap)

Stable skip reasons (AC-8 vocabulary, do not rename):
    - ``anonymous_unbilled``, ``insufficient_wallet``, ``budget_exceeded``,
      ``rate_limited`` (produced by this module)
    - ``disabled`` (produced by call sites when the kill-switch is off)
    - ``gate_error`` (produced on unexpected gate failures)

The budget and rate checks are opt-in (default ``0`` = disabled, matching the
repo's billing-flag convention: ``WEB_CRAWL_CREDIT_BILLING_ENABLED``,
``PLATFORM_SCRAPE_BILLING_ENABLED``).

Deliberately path-agnostic: this module knows nothing about chat threads or
messages. :func:`check_extract_allowed` takes a ``session``, a
``workspace``-like object (only ``.id`` is read) and an ``attributed_user_id``.
Story 3.13 will add a second (scraper-run) extraction path that must reuse this
same gate.

:func:`check_workspace_gates` is the cheap, principal-free variant used by the
enqueue-side fast-path in ``assistant_finalize``. It evaluates only the
workspace-scoped caps (budget, rate) and never fails closed, leaving the wallet
and anonymous determination to the authoritative service-side call. Keeping the
principal out of the enqueue side avoids verdict drift: the streaming caller
and the turn's message author are not guaranteed to be the same user (a
workspace member may resume a thread someone else wrote into), and it keeps an
always-on ``User`` lookup off the shielded SSE teardown path.

Collaborator seams (``_wallet_spendable_micros`` / ``_period_spend_micros`` /
``_rate_count``) are module-level functions rather than being inlined so
tests can monkeypatch them individually without a live DB/Redis.
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

from sqlalchemy import func, select

from app.config import config
from app.services.workspace_limits import WorkspaceLimitService

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
# callers/log consumers key off these strings. ``disabled`` is not produced by
# this module; it is the shared identifier the two call sites use when the
# kill-switch or the per-workspace flag short-circuits before the gate runs, so
# that every skip kind AC-8 enumerates shares one vocabulary.
REASON_ANONYMOUS_UNBILLED = "anonymous_unbilled"
REASON_INSUFFICIENT_WALLET = "insufficient_wallet"
REASON_BUDGET_EXCEEDED = "budget_exceeded"
REASON_RATE_LIMITED = "rate_limited"
REASON_DISABLED = "disabled"
REASON_GATE_ERROR = "gate_error"

_RATE_LIMIT_KEY_PREFIX = "nowing:memory_extract_rate"

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
    """Lazily build and cache the sync Redis client.

    Cached in a module global, mirroring
    ``app.capabilities.core.access.rate_limit`` and every other Redis site in
    the repo. Building a client per call would allocate a fresh
    ``ConnectionPool`` — and leak its socket until GC — on a per-chat-turn path.
    """
    global _redis
    if _redis is None:
        import redis

        _redis = redis.from_url(
            config.REDIS_APP_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
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
    """Return the attributed user's spendable balance (``balance - reserved``) in micros.

    Delegates to the canonical
    :func:`app.services.wallet_credit.spendable_micros` so this gate cannot
    drift from the reader the credit doors already trust. Two deliberate
    adaptations for gate use:

    * a ``user_id`` that no longer resolves to a row raises ``ValueError``
      there; here it counts as "nothing spendable" (fail-closed), because the
      wallet-*error* path is reserved for real query failures (DB down, etc.);
    * the canonical reader can return a negative difference; clamped to 0 so
      callers only ever compare non-negative amounts.
    """
    from app.services import wallet_credit

    try:
        spendable = await wallet_credit.spendable_micros(session, user_id)
    except ValueError:
        return 0
    return max(0, int(spendable))


def _period_window_start(now: datetime | None = None) -> datetime:
    """Rolling lookback start for the budget window.

    Rolling (``now - N``), not a calendar-day/-week/-month cliff, so a burst
    right after midnight rollover cannot slip through (Dev Notes R4). ``month``
    is a flat 30-day lookback, not a calendar month. The setting is validated at
    config load, so an unrecognised value has already been normalised to
    ``day`` before it reaches here.
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


def _rate_count_sync(workspace_id: int) -> int:
    key = _rate_key(workspace_id)
    window = config.MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS
    try:
        raw = _redis_client().get(key)
        return int(raw) if raw is not None else 0
    except Exception:
        logger.warning(
            "memory_extract_rate_count_redis_unavailable workspace_id=%s fallback=in_memory",
            workspace_id,
        )
        return _memory_count(key, window)


async def _rate_count(workspace_id: int) -> int:
    """Return the current window's extraction count for ``workspace_id``.

    Fixed-window counter over Redis, mirroring
    ``app.capabilities.core.access.rate_limit``. The underlying ``redis`` client
    is synchronous, so the call is off-loaded with :func:`asyncio.to_thread`:
    the gate is awaited from ``finalize_assistant_message``, which runs on the
    API event loop inside a shielded (non-cancellable) cleanup scope, where a
    blocking socket read would stall every other coroutine on that worker.

    Degrades to a per-worker in-memory window when Redis is unreachable — the
    same fallback ``rate_limit.py`` uses — rather than giving up entirely: the
    rate-limit is an abuse guard, not the cost-bleed guard, so an unreachable
    counter must neither block legitimate extraction nor silently stop counting.
    """
    return await asyncio.to_thread(_rate_count_sync, workspace_id)


def _record_extraction_sync(workspace_id: int) -> int:
    """Increment the extraction rate counter and return the new count.

    Runs the INCR+EXPIRE inside a single Lua script so the EXPIRE cannot be
    lost after the INCR. Falls back to the per-worker in-memory window when
    Redis is unreachable.
    """
    key = _rate_key(workspace_id)
    window = config.MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS
    try:
        client = _redis_client()
        return int(client.eval(_INCR_EXPIRE_LUA, 1, key, window))
    except Exception:
        logger.warning(
            "memory_extract_rate_increment_redis_unavailable workspace_id=%s fallback=in_memory",
            workspace_id,
        )
        return _memory_incr(key, window)


async def get_auto_extract_usage(
    session: AsyncSession, workspace_id: int
) -> dict[str, int]:
    """Return current window spend and count for memory auto-extraction.

    The window matches ``_period_window_start`` (rolling day/week/month) and
    the rate counter, so the dashboard can warn when usage approaches a cap.
    """
    spend = await _period_spend_micros(session, workspace_id)
    count = await _rate_count(workspace_id)
    window = config.MEMORY_AUTO_EXTRACT_BUDGET_WINDOW
    window_hours = {"day": 24, "week": 168, "month": 720}.get(window, 24)
    return {
        "period_spend_micros": spend,
        "period_count": count,
        "period_window_hours": window_hours,
    }


async def record_extraction(workspace_id: int) -> None:
    """Increment the rate-limit window counter for an extraction that ran.

    No-op when the rate limit is disabled (``MEMORY_AUTO_EXTRACT_RATE_MAX``
    unset/0, the default), so the shipped configuration adds no Redis traffic to
    the extraction path at all (AC-6: behaviour identical to baseline at
    defaults).

    The service calls this only *after* the extraction LLM call has actually
    succeeded — never before it, and never from the enqueue-side fast-path — so
    neither a Celery retry of a failed call nor the enqueue-side consult can
    inflate the counter.
    """
    if config.MEMORY_AUTO_EXTRACT_RATE_MAX <= 0:
        return
    await asyncio.to_thread(_record_extraction_sync, workspace_id)


async def _check_budget(
    session: AsyncSession,
    workspace_id: int,
    *,
    stage: str,
    fail_closed: bool,
    limits=None,
) -> ExtractGateResult | None:
    """Budget cap check. Returns a blocking verdict, or ``None`` to continue.

    ``fail_closed`` controls what a failed aggregate query means. The
    authoritative service-side call blocks (bounded cost is the whole point of
    the cap); the enqueue-side fast-path continues, because blocking there
    would drop the turn before the authoritative gate ever runs.

    ``limits`` is an optional ``ResolvedWorkspaceLimits`` carrying per-workspace
    Story 8.14 caps; when absent, the global config defaults are used.
    """
    budget_cap = (
        limits.auto_extract_spend_cap_micros
        if limits is not None and limits.auto_extract_spend_cap_micros is not None
        else config.MEMORY_AUTO_EXTRACT_BUDGET_MICROS
    )
    if budget_cap is None or budget_cap <= 0:
        return None

    try:
        spent = await _period_spend_micros(session, workspace_id)
    except Exception:
        if fail_closed:
            logger.warning(
                "memory_extract_skip reason=%s workspace_id=%s stage=%s "
                "budget_check_failed=true",
                REASON_BUDGET_EXCEEDED,
                workspace_id,
                stage,
            )
            return ExtractGateResult(allowed=False, reason=REASON_BUDGET_EXCEEDED)
        logger.warning(
            "memory_extract_enqueue_gate_error reason=%s workspace_id=%s stage=%s "
            "budget_check_failed=true fall_through=true",
            REASON_BUDGET_EXCEEDED,
            workspace_id,
            stage,
        )
        return None

    # Story 8.14: surface a warning when 80% of the cap is reached.
    if spent >= int(budget_cap * 0.8):
        logger.warning(
            "memory_extract_budget_warning workspace_id=%s stage=%s "
            "spent=%s cap=%s threshold=80%%",
            workspace_id,
            stage,
            spent,
            budget_cap,
        )

    if spent >= budget_cap:
        logger.info(
            "memory_extract_skip reason=%s workspace_id=%s stage=%s spent=%s cap=%s",
            REASON_BUDGET_EXCEEDED,
            workspace_id,
            stage,
            spent,
            budget_cap,
        )
        return ExtractGateResult(allowed=False, reason=REASON_BUDGET_EXCEEDED)
    return None


async def _check_rate(
    workspace_id: int, *, stage: str, fail_closed: bool, limits=None
) -> ExtractGateResult | None:
    """Rate-limit / item-cap check. Returns a blocking verdict, or ``None``.

    ``_rate_count`` already contains its own Redis fallback and does not raise,
    so the ``except`` here is defense in depth for a substituted seam.

    ``limits`` is an optional ``ResolvedWorkspaceLimits`` carrying per-workspace
    Story 8.14 caps; when absent, the global config defaults are used.
    """
    rate_max = (
        limits.auto_extract_item_cap
        if limits is not None and limits.auto_extract_item_cap is not None
        else config.MEMORY_AUTO_EXTRACT_RATE_MAX
    )
    if rate_max is None or rate_max <= 0:
        return None

    try:
        rate = await _rate_count(workspace_id)
    except Exception:
        if fail_closed:
            logger.warning(
                "memory_extract_skip reason=%s workspace_id=%s stage=%s "
                "rate_check_failed=true",
                REASON_RATE_LIMITED,
                workspace_id,
                stage,
            )
            return ExtractGateResult(allowed=False, reason=REASON_RATE_LIMITED)
        logger.warning(
            "memory_extract_enqueue_gate_error reason=%s workspace_id=%s stage=%s "
            "rate_check_failed=true fall_through=true",
            REASON_RATE_LIMITED,
            workspace_id,
            stage,
        )
        return None

    # Story 8.14: surface a warning when 80% of the item cap is reached.
    if rate >= int(rate_max * 0.8):
        logger.warning(
            "memory_extract_item_cap_warning workspace_id=%s stage=%s "
            "rate=%s cap=%s threshold=80%%",
            workspace_id,
            stage,
            rate,
            rate_max,
        )

    if rate >= rate_max:
        logger.info(
            "memory_extract_skip reason=%s workspace_id=%s stage=%s rate=%s max=%s",
            REASON_RATE_LIMITED,
            workspace_id,
            stage,
            rate,
            rate_max,
        )
        return ExtractGateResult(allowed=False, reason=REASON_RATE_LIMITED)
    return None


async def check_extract_allowed(
    session: AsyncSession,
    *,
    workspace: Workspace,
    attributed_user_id: Any | None,
) -> ExtractGateResult:
    """Decide whether a memory-extraction LLM call may proceed.

    The authoritative gate. Runs BEFORE any LLM call. First block wins; each
    check is evaluated only if the prior ones passed, so a single call resolves
    at most one reason. Never raises: every branch, including reading
    ``workspace.id``, is contained so a gate failure can never break the chat
    turn that already succeeded.
    """
    try:
        workspace_id = workspace.id
    except Exception:
        # A detached/expired ORM instance (Story 3.13 will reuse this gate from
        # a different path) must not raise into the caller.
        logger.warning(
            "memory_extract_skip reason=%s stage=service workspace_unreadable=true",
            REASON_GATE_ERROR,
            exc_info=True,
        )
        return ExtractGateResult(allowed=False, reason=REASON_GATE_ERROR)

    try:
        limits = await WorkspaceLimitService.get_effective_limits(session, workspace_id)

        # 1. Anonymous / no billable owner.
        if attributed_user_id is None:
            logger.info(
                "memory_extract_skip reason=%s workspace_id=%s stage=service",
                REASON_ANONYMOUS_UNBILLED,
                workspace_id,
            )
            return ExtractGateResult(allowed=False, reason=REASON_ANONYMOUS_UNBILLED)

        # 2. Wallet eligibility pre-check (Story 8.14: can be disabled per workspace).
        # Default to enabled (``None`` or ``True`` both run the pre-check).
        wallet_pre_check = limits.auto_extract_wallet_pre_check is not False
        if wallet_pre_check:
            try:
                spendable = await _wallet_spendable_micros(session, attributed_user_id)
            except Exception:
                logger.warning(
                    "memory_extract_skip reason=%s workspace_id=%s stage=service "
                    "wallet_check_failed=true",
                    REASON_INSUFFICIENT_WALLET,
                    workspace_id,
                )
                return ExtractGateResult(
                    allowed=False, reason=REASON_INSUFFICIENT_WALLET
                )

            if spendable < config.MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS:
                logger.info(
                    "memory_extract_skip reason=%s workspace_id=%s stage=service "
                    "spendable=%s min_reserve=%s",
                    REASON_INSUFFICIENT_WALLET,
                    workspace_id,
                    spendable,
                    config.MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS,
                )
                return ExtractGateResult(
                    allowed=False, reason=REASON_INSUFFICIENT_WALLET
                )

        # 3. Per-workspace spend/budget cap over the rolling period.
        blocked = await _check_budget(
            session,
            workspace_id,
            stage="service",
            fail_closed=True,
            limits=limits,
        )
        if blocked is not None:
            return blocked

        # 4. Time-based rate-limit / item cap.
        blocked = await _check_rate(
            workspace_id, stage="service", fail_closed=True, limits=limits
        )
        if blocked is not None:
            return blocked
    except Exception:
        logger.warning(
            "memory_extract_skip reason=%s workspace_id=%s stage=service",
            REASON_GATE_ERROR,
            workspace_id,
            exc_info=True,
        )
        return ExtractGateResult(allowed=False, reason=REASON_GATE_ERROR)

    return ExtractGateResult(allowed=True, reason=None)


async def check_workspace_gates(
    session: AsyncSession, *, workspace: Workspace
) -> ExtractGateResult:
    """Workspace-scoped caps only (budget, rate) — no principal required.

    The enqueue-side fast-path (AC-7). Deliberately omits the wallet and
    anonymous checks: both need a principal, and the enqueue site's principal
    (the streaming caller) is not guaranteed to be the turn's message author,
    so consulting them here could drop a turn the authoritative gate would
    allow. Omitting them also keeps a per-turn ``User`` lookup off the shielded
    SSE teardown path.

    Never fails closed and never raises — any uncertainty resolves to
    "enqueue and let :func:`check_extract_allowed` decide".
    """
    try:
        workspace_id = workspace.id
        limits = await WorkspaceLimitService.get_effective_limits(session, workspace_id)
        blocked = await _check_budget(
            session,
            workspace_id,
            stage="enqueue",
            fail_closed=False,
            limits=limits,
        )
        if blocked is not None:
            return blocked
        blocked = await _check_rate(
            workspace_id, stage="enqueue", fail_closed=False, limits=limits
        )
        if blocked is not None:
            return blocked
    except Exception:
        logger.warning(
            "memory_extract_enqueue_gate_error falling_through=true", exc_info=True
        )
    return ExtractGateResult(allowed=True, reason=None)


__all__ = [
    "REASON_ANONYMOUS_UNBILLED",
    "REASON_BUDGET_EXCEEDED",
    "REASON_DISABLED",
    "REASON_GATE_ERROR",
    "REASON_INSUFFICIENT_WALLET",
    "REASON_RATE_LIMITED",
    "ExtractGateResult",
    "check_extract_allowed",
    "check_workspace_gates",
    "record_extraction",
]
