"""Shared Async Redis client helper for Nowing Backend."""

from __future__ import annotations

import asyncio
from typing import Any

from redis import asyncio as aioredis

from app.config import config

_redis_clients_by_loop: dict[asyncio.AbstractEventLoop, Any] = {}


async def get_redis_client() -> Any:
    """Return an async redis client tied safely to the current running event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        client = _redis_clients_by_loop.get(loop)
        if client is not None:
            return client

    redis_url = getattr(
        config,
        "REDIS_APP_URL",
        getattr(config, "REDIS_URL", "redis://localhost:6379/0"),
    )
    client = aioredis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=5,
        # ponytail: 10s socket timeout so DSH XREADGROUP BLOCK (5s default)
        # plus network/parse margin does not trip redis-py TimeoutError.
        socket_timeout=10,
        health_check_interval=30,
    )
    if loop is not None:
        _redis_clients_by_loop[loop] = client
    return client
