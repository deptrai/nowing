"""Celery background tasks for in-app broadcast announcements lifecycle (Story 25.6)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select, update

from app.celery_app import celery_app
from app.db import AuditEvent, BroadcastAnnouncement
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)


async def _expire_stale_broadcasts() -> int:
    """Deactivate broadcast announcements whose expiry timestamp has passed."""
    now = datetime.now(UTC)
    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        # Capture the IDs that are about to expire for the audit trail
        select_stmt = select(BroadcastAnnouncement.id).where(
            BroadcastAnnouncement.is_active.is_(True),
            BroadcastAnnouncement.expires_at.is_not(None),
            BroadcastAnnouncement.expires_at <= now,
        )
        select_res = await session.execute(select_stmt)
        expired_ids = [row[0] for row in select_res.all()]

        if not expired_ids:
            return 0

        update_stmt = (
            update(BroadcastAnnouncement)
            .where(BroadcastAnnouncement.id.in_(expired_ids))
            .values(is_active=False, updated_at=now, updated_by_user_id=None)
            .execution_options(synchronize_session=False)
        )
        res = await session.execute(update_stmt)

        # Immutable audit trail for the system-initiated state change (INV-25.2)
        audit = AuditEvent(
            action="broadcast.expire",
            actor_id=None,
            subject_id=None,
            ip_address=None,
            user_agent="system/expire_broadcast_announcements",
            diff_payload={
                "expired_count": res.rowcount or 0,
                "expired_ids": [str(iid) for iid in expired_ids],
                "expires_at_threshold": now.isoformat(),
            },
        )
        session.add(audit)
        await session.commit()

        if res.rowcount:
            logger.info("[BroadcastTasks] Expired %d announcements", res.rowcount)
        return res.rowcount or 0


@celery_app.task(name="expire_broadcast_announcements", bind=True)
def expire_broadcast_announcements_task(self) -> int:
    """Periodic task running every minute to auto-expire past broadcast announcements."""
    return run_async_celery_task(_expire_stale_broadcasts)
