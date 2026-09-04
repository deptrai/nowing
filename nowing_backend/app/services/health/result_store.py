"""Health Result Store for Redis caching, pub/sub broadcasting, and Postgres persistence."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_health import AdminHealthHistory, AdminHealthStatus
from app.redis_client import get_redis_client
from app.services.health.probe_base import HealthResult

logger = logging.getLogger(__name__)

HEALTH_PUB_SUB_CHANNEL = "nowing:health:updates"
HEALTH_SNAPSHOT_TTL_SECONDS = 300  # 5 minutes

# Redact credentials in metadata and error text.
_SECRET_PATTERN = re.compile(r"(key|token|secret|password|bearer\s+|auth\s+)[=:\s]*([^\s,;&]+)", re.IGNORECASE)


def _sanitize_error(error_str: str | None) -> str | None:
    if not error_str:
        return error_str
    return _SECRET_PATTERN.sub(r"\1=***", error_str)


def _sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return {} if metadata is None else metadata
    redacted: dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, str):
            redacted[key] = _sanitize_error(value) or value
        else:
            redacted[key] = value
    return redacted


class HealthResultStore:
    """Handles storage, caching, and pub/sub distribution of probe results."""

    @staticmethod
    async def save_result(session: AsyncSession, result: HealthResult) -> AdminHealthStatus:
        """Persist result to database (status + history) and publish to Redis."""
        now = datetime.now(UTC)

        safe_error = _sanitize_error(result.last_error)
        safe_metadata = _sanitize_metadata(result.metadata)

        # 1. Append to admin_health_history first so 15m calculation includes it
        history = AdminHealthHistory(
            service_id=result.service_id,
            probe_at=result.probed_at,
            status=result.status,
            latency_ms=result.latency_ms,
            error_message=safe_error,
        )
        session.add(history)
        await session.flush()

        # 2. Compute rolling 15m rates from history (degraded also counts as error)
        cutoff = now - timedelta(minutes=15)
        tot_query = select(func.count()).select_from(AdminHealthHistory).where(
            AdminHealthHistory.service_id == result.service_id,
            AdminHealthHistory.probe_at >= cutoff,
        )
        err_query = select(func.count()).select_from(AdminHealthHistory).where(
            AdminHealthHistory.service_id == result.service_id,
            AdminHealthHistory.probe_at >= cutoff,
            AdminHealthHistory.status.in_(["unavailable", "degraded"]),
        )
        tot_res = await session.execute(tot_query)
        err_res = await session.execute(err_query)
        tot_count = tot_res.scalar() or 0
        err_count = err_res.scalar() or 0

        if tot_count > 0:
            error_rate = round((err_count / tot_count) * 100.0, 1)
            success_rate = round(100.0 - error_rate, 1)
        else:
            success_rate = result.success_rate_15m
            error_rate = result.error_rate_15m

        # Sync back to result
        result.success_rate_15m = success_rate
        result.error_rate_15m = error_rate

        # 3. Derive next_probe_at from probe-provided value or default interval
        if result.next_probe_at:
            next_probe_at = result.next_probe_at
        else:
            interval = max(1, result.interval_seconds or 300)
            next_probe_at = now + timedelta(seconds=interval)

        # 4. Atomic upsert into admin_health_status
        upsert_stmt = pg_insert(AdminHealthStatus).values(
            category=result.category,
            service_id=result.service_id,
            service_name=result.service_name,
            display_group=result.display_group,
            status=result.status,
            last_probe_at=result.probed_at,
            next_probe_at=next_probe_at,
            latency_ms=result.latency_ms,
            error_rate_15m=error_rate,
            success_rate_15m=success_rate,
            last_error=safe_error,
            suggested_action=result.suggested_action,
            metadata_payload=safe_metadata,
            updated_at=now,
        ).on_conflict_do_update(
            index_elements=["service_id"],
            set_={
                "category": result.category,
                "service_name": result.service_name,
                "display_group": result.display_group,
                "status": result.status,
                "last_probe_at": result.probed_at,
                "next_probe_at": next_probe_at,
                "latency_ms": result.latency_ms,
                "error_rate_15m": error_rate,
                "success_rate_15m": success_rate,
                "last_error": safe_error,
                "suggested_action": result.suggested_action,
                "metadata_payload": safe_metadata,
                "updated_at": now,
            },
        )
        await session.execute(upsert_stmt)

        record = (
            await session.execute(
                select(AdminHealthStatus).where(AdminHealthStatus.service_id == result.service_id)
            )
        ).scalar_one()

        await session.commit()
        await session.refresh(record)

        # 5. Cache in Redis and publish update event (best-effort)
        try:
            redis = await get_redis_client()
            payload = json.dumps(result.to_dict())
            snapshot_key = f"nowing:health:snapshot:{result.service_id}"
            await redis.set(snapshot_key, payload, ex=HEALTH_SNAPSHOT_TTL_SECONDS)
            await redis.publish(HEALTH_PUB_SUB_CHANNEL, payload)
        except Exception as exc:
            logger.warning("Failed to publish health result to Redis: %s", exc)

        return record

    @staticmethod
    async def get_latest_status(
        session: AsyncSession,
        category: str | None = None,
        service_id: str | None = None,
    ) -> list[AdminHealthStatus]:
        """Fetch current status snapshots from Postgres."""
        query = select(AdminHealthStatus)
        if category:
            query = query.where(AdminHealthStatus.category == category)
        if service_id:
            query = query.where(AdminHealthStatus.service_id == service_id)

        query = query.order_by(AdminHealthStatus.category, AdminHealthStatus.service_name)
        res = await session.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def get_history(
        session: AsyncSession,
        service_id: str,
        hours: int = 24,
        limit: int = 10000,
        offset: int = 0,
    ) -> list[AdminHealthHistory]:
        """Fetch probe history for a given service over the last N hours."""
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        query = (
            select(AdminHealthHistory)
            .where(
                AdminHealthHistory.service_id == service_id,
                AdminHealthHistory.probe_at >= cutoff,
            )
            .order_by(AdminHealthHistory.probe_at.asc())
            .offset(offset)
            .limit(limit)
        )
        res = await session.execute(query)
        return list(res.scalars().all())
