"""DSH worker CLI and runtime entrypoints."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import signal
from typing import Any

import httpx

from app.config import config
from app.redis_client import get_redis_client
from app.tasks.dsh_worker.worker import DshWorker

logger = logging.getLogger(__name__)


def _default_consumer_name() -> str:
    """Return a unique consumer name per process/host for load balancing."""
    import os
    import socket
    import uuid

    return f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"


def _validate_config() -> None:
    if not config.DSH_WORKER_PAT or not config.DSH_WORKER_SECRET:
        raise SystemExit(
            "DSH_WORKER_PAT and DSH_WORKER_SECRET must be set and non-empty"
        )
    if config.DSH_LOCK_TTL_SECONDS <= config.DSH_HEARTBEAT_INTERVAL_SECONDS:
        raise SystemExit(
            "DSH_LOCK_TTL_SECONDS must be greater than DSH_HEARTBEAT_INTERVAL_SECONDS"
        )
    if (
        config.DSH_XAUTOCLAIM_MIN_IDLE_MS
        <= config.DSH_HEARTBEAT_INTERVAL_SECONDS * 1000
    ):
        raise SystemExit(
            "DSH_XAUTOCLAIM_MIN_IDLE_MS must be greater than heartbeat interval in ms"
        )


async def healthcheck() -> int:
    """Liveness probe used by docker-compose."""
    try:
        redis_client = await get_redis_client()
        await redis_client.ping()
    except Exception as exc:
        logger.error("DSH healthcheck Redis ping failed: %s", exc)
        return 1

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{config.DSH_INTERNAL_BASE_URL.rstrip('/')}/health"
            )
            resp.raise_for_status()
    except Exception as exc:
        logger.error("DSH healthcheck API ping failed: %s", exc)
        return 1

    return 0


async def run_dsh_worker() -> None:
    """Entry point for the SERVICE_ROLE=dsh sidecar."""
    _validate_config()
    worker = DshWorker()
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError, ValueError):
            # Signals may not be supported on this platform (e.g. Windows).
            loop.add_signal_handler(sig, worker.stop)

    try:
        await worker.run()
    finally:
        worker.stop()
        await worker.aclose()


def main(argv: list[str] | None = None) -> int | Any:
    """CLI entrypoint for the DSH worker."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--healthcheck", action="store_true")
    args = parser.parse_args(argv)

    if args.healthcheck:
        return asyncio.run(healthcheck())

    try:
        asyncio.run(run_dsh_worker())
    except SystemExit as exc:
        if exc.code not in (0, None):
            return exc.code
    return 0
