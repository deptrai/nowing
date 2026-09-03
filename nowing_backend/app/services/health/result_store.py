"""Health Result Store for Redis caching, pub/sub broadcasting, and Postgres persistence."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_health import AdminHealthHistory, AdminHealthStatus
from app.redis_client import get_redis_client
from app.services.health.probe_base import HealthResult

logger = logging.getLogger(__name__)

HEALTH_PUB_SUB_CHANNEL = "nowing:health:updates"
HEALTH_SNAPSHOT_TTL_SECONDS = 300  # 5 minutes


class HealthResultStore:
    """Handles storage, caching, and pub/sub distribution of probe results."""

    @staticmethod
    async def save_result(session: AsyncSession, result: HealthResult) -> AdminHealthStatus:
        """Persist result to database (status + history) and publish to Redis."""
        now = datetime.now(UTC)

        # 1. Append to admin_health_history first so 15m calculation includes it
        history = AdminHealthHistory(
            service_id=result.service_id,
            probe_at=result.probed_at,
            status=result.status,
            latency_ms=result.latency_ms,
            error_message=result.last_error,
        )
        session.add(history)
        await session.flush()

        # 2. Compute rolling 15m rates from history
        cutoff = now - timedelta(minutes=15)
        tot_query = select(func.count()).select_from(AdminHealthHistory).where(
            AdminHealthHistory.service_id == result.service_id,
            AdminHealthHistory.probe_at >= cutoff,
        )
        err_query = select(func.count()).select_from(AdminHealthHistory).where(
            AdminHealthHistory.service_id == result.service_id,
            AdminHealthHistory.probe_at >= cutoff,
            AdminHealthHistory.status.in_(["unavailable"]),
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

        # 3. Upsert into admin_health_status
        stmt = select(AdminHealthStatus).where(AdminHealthStatus.service_id == result.service_id)
        res = await session.execute(stmt)
        record = res.scalar_one_or_none()

        if record is None:
            record = AdminHealthStatus(
                category=result.category,
                service_id=result.service_id,
                service_name=result.service_name,
                display_group=result.display_group,
                status=result.status,
                last_probe_at=result.probed_at,
                next_probe_at=now + timedelta(seconds=300),
                latency_ms=result.latency_ms,
                error_rate_15m=error_rate,
                success_rate_15m=success_rate,
                last_error=result.last_error,
                suggested_action=result.suggested_action,
                metadata_payload=result.metadata,
                updated_at=now,
            )
            session.add(record)
        else:
            record.status = result.status
            record.last_probe_at = result.probed_at
            record.next_probe_at = now + timedelta(seconds=300)
            record.latency_ms = result.latency_ms
            record.error_rate_15m = error_rate
            record.success_rate_15m = success_rate
            record.last_error = result.last_error
            record.suggested_action = result.suggested_action
            record.metadata_payload = result.metadata
            record.updated_at = now

        await session.commit()
        await session.refresh(record)

        # 4. Cache in Redis and publish update event (best-effort)
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
        )
        res = await session.execute(query)
        return list(res.scalars().all())
