"""Shared helpers for connector routes."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import redis
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.db import SearchSourceConnector, SearchSourceConnectorType

logger = logging.getLogger(__name__)

_heartbeat_redis_client: redis.Redis | None = None
HEARTBEAT_TTL_SECONDS = 120
HEARTBEAT_REFRESH_INTERVAL = 60


class GitHubPATRequest(BaseModel):
    github_pat: str = Field(..., description="GitHub Personal Access Token")


DRIVE_CONNECTOR_TYPES = {
    SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR,
    SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
}


def get_heartbeat_redis_client() -> redis.Redis:
    """Get or create Redis client for heartbeat tracking."""
    global _heartbeat_redis_client
    if _heartbeat_redis_client is None:
        _heartbeat_redis_client = redis.from_url(
            config.REDIS_APP_URL, decode_responses=True
        )
    return _heartbeat_redis_client


def _get_heartbeat_key(notification_id: int) -> str:
    """Generate Redis key for notification heartbeat."""
    return f"indexing:heartbeat:{notification_id}"


async def _run_indexing_heartbeat_loop(notification_id: int) -> None:
    """Background coroutine that refreshes the Redis heartbeat.

    Mirrors `_run_heartbeat_loop` in app/tasks/celery_tasks/document_tasks.py.
    Cancelled via heartbeat_task.cancel() when the indexing call returns.
    """
    from app.observability import metrics as ot_metrics

    key = _get_heartbeat_key(notification_id)
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_REFRESH_INTERVAL)
            try:
                get_heartbeat_redis_client().setex(key, HEARTBEAT_TTL_SECONDS, "alive")
                ot_metrics.record_celery_heartbeat_refresh(heartbeat_type="connector")
            except (redis.RedisError, OSError, TypeError, ValueError) as e:
                ot_metrics.record_celery_heartbeat_failure(heartbeat_type="connector")
                logger.warning(
                    f"Failed to refresh Redis heartbeat for notification "
                    f"{notification_id}: {e}"
                )
    except asyncio.CancelledError:
        pass


async def _update_connector_timestamp_by_id(
    session: AsyncSession, connector_id: int
) -> None:
    """Update the last_indexed_at timestamp for a connector."""
    result = await session.execute(
        select(SearchSourceConnector).filter(SearchSourceConnector.id == connector_id)
    )
    connector = result.scalars().first()
    if connector:
        connector.last_indexed_at = datetime.now(UTC)
        await session.commit()


def _is_auth_error(error_message: str) -> bool:
    """Check if an error message indicates an OAuth token expiry failure."""
    if not error_message:
        return False
    auth_error_patterns = (
        "failed to refresh linear oauth",
        "failed to refresh your notion connection",
        "failed to refresh notion token",
        "authentication failed",
        "auth_expired",
        "token has been expired or revoked",
        "invalid_grant",
    )
    lower = error_message.lower()
    return any(pattern in lower for pattern in auth_error_patterns)


async def _persist_auth_expired(session: AsyncSession, connector_id: int) -> None:
    """Flag a connector as auth_expired so the frontend shows a re-auth prompt."""
    from sqlalchemy.orm.attributes import flag_modified

    from app.observability import otel as ot

    ot.add_event(
        "connector.auth.expired",
        {
            "error.category": "auth_failed",
        },
    )
    try:
        result = await session.execute(
            select(SearchSourceConnector).where(SearchSourceConnector.id == connector_id)
        )
        connector = result.scalar_one_or_none()
        if connector and not connector.config.get("auth_expired"):
            connector.config = {**connector.config, "auth_expired": True}
            flag_modified(connector, "config")
            await session.commit()
            logger.info(f"Marked connector {connector_id} as auth_expired")
    except (SQLAlchemyError, OSError, TypeError, ValueError):
        logger.warning(
            f"Failed to persist auth_expired for connector {connector_id}",
            exc_info=True,
        )
