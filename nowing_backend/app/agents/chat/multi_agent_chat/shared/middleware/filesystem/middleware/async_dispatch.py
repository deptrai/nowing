"""Sync/async dispatcher: drive an async tool body from a sync entry-point."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


def run_async_blocking(coro: Any) -> Any:
    """Run ``coro`` to completion, blocking the current thread.

    Returns an error string instead of raising if the current thread is
    already inside a running event loop — keeps sync tool entry-points
    safe to call from any context.
    """
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            return "Error: sync filesystem operation not supported inside an active event loop."
    except RuntimeError as exc:
        logger.debug("Suppressed %r", exc)
    return asyncio.run(coro)
