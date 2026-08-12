"""Metered deep-research endpoint for self-hosted Nowing instances.

Self-hosted instances do not call the ChainLens engine directly; they route
through Nowing Cloud with a self-host API key. Nowing keeps a single service
token, meters the call, and debits the key owner's credit wallet.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import time
from collections import defaultdict
from threading import Lock
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.chainlens.research.definition import build_research_executor
from app.capabilities.chainlens.research.schemas import ResearchInput, ResearchOutput
from app.capabilities.core import execute_with_context
from app.capabilities.core.types import CapabilityContext
from app.config import config
from app.db import PersonalAccessToken, User, Workspace, get_async_session
from app.services.chainlens.auth import ChainLensServiceAuth
from app.services.token_tracking_service import UsageType, record_token_usage
from app.services.wallet_credit import (
    InsufficientCreditsError,
    apply_debit,
    check_balance,
)
from app.utils.pat import maybe_touch_last_used, resolve_pat

logger = logging.getLogger(__name__)

router = APIRouter(tags=["self-host"])

_SELF_HOST_RATE_LIMIT_PER_MINUTE = 120
_SELF_HOST_WINDOW_SECONDS = 60
_SELF_HOST_RATE_LIMIT_PREFIX = "nowing:self_host_rate_limit"


class _SelfHostAuthError(HTTPException):
    """Raised when a self-host API key is missing or invalid."""


# ---------------------------------------------------------------------------
# Rate limiting (Redis + in-process fallback)
# ---------------------------------------------------------------------------

_redis = None
_memory: dict[str, list[float]] = defaultdict(list)
_memory_lock = Lock()


def _redis_client():
    global _redis
    if _redis is None:
        import redis

        _redis = redis.from_url(config.REDIS_APP_URL, decode_responses=True)
    return _redis


def _incr_memory(key: str, window_seconds: int) -> int:
    now = time.monotonic()
    with _memory_lock:
        hits = [t for t in _memory[key] if now - t < window_seconds]
        hits.append(now)
        _memory[key] = hits
        return len(hits)


def _incr(key: str, window_seconds: int) -> int:
    try:
        client = _redis_client()
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, window_seconds)
        return count
    except Exception:
        return _incr_memory(key, window_seconds)


async def _aincr(key: str, window_seconds: int) -> int:
    return await asyncio.to_thread(_incr, key, window_seconds)


def _rate_limit_key(token: str) -> str:
    # Hash the key so the Redis key does not leak the raw token.
    key_hash = hashlib.sha256(token.encode()).hexdigest()
    return f"{_SELF_HOST_RATE_LIMIT_PREFIX}:{key_hash}"


async def _enforce_self_host_rate_limit(token: str) -> None:
    """Cap self-host calls at 120 req/minute per API key."""
    count = await _aincr(_rate_limit_key(token), _SELF_HOST_WINDOW_SECONDS)
    if count > _SELF_HOST_RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for this self-host API key. Try again shortly.",
            headers={"Retry-After": str(_SELF_HOST_WINDOW_SECONDS)},
        )


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

_SELF_HOST_HELP = (
    "Create a self-host API key at /pats with token_kind='self_host' and "
    "pass it as Authorization: Bearer <key>. The deep-research engine is "
    "a hosted, metered cloud service; self-hosted instances must route "
    "through Nowing Cloud."
)


async def get_self_host_auth(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> tuple[User, PersonalAccessToken]:
    """Resolve a self-host API key to its owner user and PAT row."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        raise _SelfHostAuthError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing self-host API key. {_SELF_HOST_HELP}",
        )

    scheme, _, credential = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not credential:
        raise _SelfHostAuthError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Authorization header. {_SELF_HOST_HELP}",
        )

    pat = await resolve_pat(session, credential)
    if pat is None or pat.user is None or not pat.user.is_active:
        raise _SelfHostAuthError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired self-host API key. {_SELF_HOST_HELP}",
        )

    if pat.token_kind != "self_host":
        raise _SelfHostAuthError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "The supplied key is not a self-host API key. "
                "Create one with token_kind='self_host'."
            ),
        )

    maybe_touch_last_used(pat)
    return pat.user, pat


async def _resolve_workspace_id(session: AsyncSession, user: User, pat: PersonalAccessToken) -> int:
    """Return the workspace to attribute the call to.

    Uses the workspace_id stored on the PAT if present; otherwise falls back
    to the owner's first workspace so the call is still metered and recorded.
    """
    if pat.workspace_id is not None:
        return pat.workspace_id

    result = await session.execute(
        select(Workspace.id).where(Workspace.user_id == user.id).limit(1)
    )
    workspace_id = result.scalar_one_or_none()
    if workspace_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No workspace found for this self-host key owner.",
        )
    return workspace_id


# ---------------------------------------------------------------------------
# Cost helpers
# ---------------------------------------------------------------------------


def _self_host_multiplier() -> float:
    return float(getattr(config, "SELF_HOST_RESEARCH_COST_MULTIPLIER", 1.5))


def _billed_micros(cost_micros: int | None) -> int:
    """Apply the self-host cost multiplier and floor the result.

    Returns 0 when the engine cost is missing or non-positive so sponsored
    runway / benchmark keys do not consume credits.
    """
    if cost_micros is None or cost_micros <= 0:
        return 0
    return math.floor(cost_micros * _self_host_multiplier())


def _fallback_micros() -> int:
    return int(getattr(config, "CHAINLENS_QUERY_MICROS_PER_CALL", 60000))


async def _charge_self_host_research(
    session: AsyncSession,
    user: User,
    workspace_id: int,
    output: ResearchOutput,
    run_id: str | None,
) -> int:
    """Debit the owner for a self-host research call and record TokenUsage.

    Returns the micros billed (0 for zero-cost or failed calls with no content).
    """
    status_name = output.status
    has_content = bool(output.answer or output.sources)
    if status_name == "engine_unavailable" and not has_content:
        return 0

    cost_micros: int | None = output.cost_micros
    cost_basis: str | None = output.cost_basis
    resolved_mode = output.resolved_mode
    mode_requested = output.mode_requested
    tokens_total = output.tokens_total
    e2e_ms = output.duration_ms
    ttfb_ms = output.first_token_time_ms

    if cost_micros is None:
        cost_micros = _fallback_micros()
        cost_basis = "fallback"
        logger.warning(
            "self-host research using fallback flat rate (%d micros) for user %s: "
            "no costDollars in SSE",
            cost_micros,
            user.id,
        )

    if cost_micros is None or cost_micros < 0:
        return 0

    billed_micros = _billed_micros(cost_micros)

    call_details: dict[str, Any] = {
        "resolved_mode": resolved_mode,
        "mode_requested": mode_requested,
        "cost_basis": cost_basis,
        "tokens_total": tokens_total,
        "e2e_ms": e2e_ms,
        "ttfb_ms": ttfb_ms,
        "cost_dollars": float(output.cost_dollars or 0),
        "cost_micros": cost_micros,
        "billed_micros": billed_micros,
        "multiplier": _self_host_multiplier(),
        "total_cost_micros": billed_micros,
        "degradation_reason": output.degradation_reason,
        "final_status": output.status,
    }
    if output.degraded:
        call_details["degraded"] = True

    # Record usage before debit so the audit row is staged even if debit fails.
    await record_token_usage(
        session,
        usage_type=UsageType.DEEP_RESEARCH,
        workspace_id=workspace_id,
        user_id=user.id,
        prompt_tokens=output.tokens_prompt or 0,
        completion_tokens=output.tokens_completion or 0,
        total_tokens=tokens_total or 0,
        cost_micros=billed_micros,
        call_details=call_details,
        resolved_mode=resolved_mode,
        mode_requested=mode_requested,
        e2e_ms=e2e_ms,
        ttfb_ms=ttfb_ms,
        run_id=run_id,
    )

    if billed_micros <= 0:
        return 0

    await check_balance(session, user.id, billed_micros)
    await apply_debit(session, user.id, billed_micros)
    return billed_micros


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post("/self-host/research")
async def self_host_research(
    request: Request,
    body: ResearchInput,
    session: AsyncSession = Depends(get_async_session),
    auth: tuple[User, PersonalAccessToken] = Depends(get_self_host_auth),
) -> ResearchOutput:
    """Run a metered deep-research call for a self-hosted Nowing instance."""
    user, pat = auth

    token = request.headers.get("Authorization", "").partition(" ")[2]
    await _enforce_self_host_rate_limit(token)

    workspace_id = await _resolve_workspace_id(session, user, pat)
    run_id = str(uuid4())

    # Pre-flight balance check using the worst-case fallback estimate so the
    # engine is not wasted when the wallet is empty.
    fallback_estimate = math.floor(_fallback_micros() * _self_host_multiplier())
    try:
        await check_balance(session, user.id, fallback_estimate)
    except InsufficientCreditsError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error_code": "insufficient_credits",
                "message": str(exc),
                "balance_micros": exc.balance_micros,
                "required_micros": exc.required_micros,
            },
        ) from exc

    auth_service = ChainLensServiceAuth(config_obj=config)
    if not auth_service.configured:
        logger.warning("ChainLens service token not configured; degrading self-host research.")
        return ResearchOutput(
            status="engine_unavailable",
            degradation_reason="not_configured",
            next_action=(
                "Deep research is not available. Set CHAINLENS_SERVICE_TOKEN or "
                "CHAINLENS_API_KEY on the Nowing Cloud instance to use the hosted engine."
            ),
        )

    payload = ResearchInput(
        query=body.query,
        mode=body.mode,
        sources=body.sources,
        system_instructions=body.system_instructions,
        history=body.history,
        chat_id=body.chat_id,
        tier=body.tier,
        workspace_id=workspace_id,
    )

    ctx = CapabilityContext(session=session, workspace_id=workspace_id, run_id=run_id)
    executor = build_research_executor()

    output = await execute_with_context(executor, payload=payload, ctx=ctx)

    try:
        await _charge_self_host_research(
            session, user, workspace_id, output, run_id=run_id
        )
    except InsufficientCreditsError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error_code": "insufficient_credits",
                "message": str(exc),
                "balance_micros": exc.balance_micros,
                "required_micros": exc.required_micros,
            },
        ) from exc

    return output
