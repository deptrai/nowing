"""Shared SlowAPI limiter instance used by app.py and route modules."""

from __future__ import annotations

import time

from fastapi import HTTPException, Request, status
from limits import RateLimitItemPerMinute
from limits.storage import MemoryStorage
from slowapi import Limiter

from app.config import config


def get_real_client_ip(request: Request) -> str:
    """Extract the real client IP behind Cloudflare / reverse proxies.

    Priority: CF-Connecting-IP > X-Real-IP > X-Forwarded-For (first entry) > socket peer.
    """
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


limiter = Limiter(
    key_func=get_real_client_ip,
    storage_uri=config.REDIS_APP_URL,
    default_limits=["1024/minute"],
    in_memory_fallback_enabled=True,
    in_memory_fallback=[MemoryStorage()],
)

# Public agent-chat rate limits (Epic 18, AC-9 / AD-29).
AGENT_CHAT_CLIENT_LIMIT = RateLimitItemPerMinute(30)
AGENT_CHAT_WORKSPACE_LIMIT = RateLimitItemPerMinute(100)


def _agent_chat_limit_keys(client_id: str, workspace_id: int) -> tuple[str, str]:
    return (
        f"agent_chat:client:{client_id}",
        f"agent_chat:workspace:{workspace_id}",
    )


def _retry_after(item: RateLimitItemPerMinute, key: str) -> int:
    stats = limiter.limiter.get_window_stats(item, key)
    return max(1, int(stats.reset_time - time.time()))


def check_agent_chat_limits(client_id: str, workspace_id: int) -> None:
    """Enforce per-client and per-workspace public agent-chat rate limits.

    Raises HTTPException(429) with a Retry-After header when a limit is exceeded.
    """
    client_key, workspace_key = _agent_chat_limit_keys(client_id, workspace_id)

    if not limiter.limiter.test(AGENT_CHAT_CLIENT_LIMIT, client_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit exceeded for client",
            headers={
                "Retry-After": str(_retry_after(AGENT_CHAT_CLIENT_LIMIT, client_key))
            },
        )

    if not limiter.limiter.test(AGENT_CHAT_WORKSPACE_LIMIT, workspace_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit exceeded for workspace",
            headers={
                "Retry-After": str(
                    _retry_after(AGENT_CHAT_WORKSPACE_LIMIT, workspace_key)
                )
            },
        )


def hit_agent_chat_limits(client_id: str, workspace_id: int) -> None:
    """Record a successful public agent-chat call against both limit buckets."""
    client_key, workspace_key = _agent_chat_limit_keys(client_id, workspace_id)
    limiter.limiter.hit(AGENT_CHAT_CLIENT_LIMIT, client_key)
    limiter.limiter.hit(AGENT_CHAT_WORKSPACE_LIMIT, workspace_key)
