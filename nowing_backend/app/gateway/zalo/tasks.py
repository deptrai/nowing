"""Celery tasks for non-blocking Zalo OA Webhook event processing (Story 23.2 / INV-23.8)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from app.celery_app import celery_app
from app.db import ZaloConnection
from app.gateway.zalo.webhook import handle_zalo_webhook_event
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)


@celery_app.task(
    name="gateway.zalo.process_zalo_inbox_event",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def process_zalo_inbox_event(
    self: Any, workspace_id: int, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Process incoming Zalo webhook event asynchronously in Celery worker."""

    async def _process() -> dict[str, Any]:
        session_maker = get_celery_session_maker()
        async with session_maker() as session:
            try:
                # Resolve connection if available
                conn_stmt = select(ZaloConnection).where(
                    ZaloConnection.workspace_id == workspace_id,
                    ZaloConnection.is_active.is_(True),
                )
                res = await session.execute(conn_stmt)
                connection = res.scalar_one_or_none()

                return await handle_zalo_webhook_event(
                    session=session,
                    connection=connection,
                    event_data=event_dict,
                    workspace_id=workspace_id,
                )
            except Exception as exc:
                logger.error(
                    "[process_zalo_inbox_event] Error processing event for workspace %s: %s",
                    workspace_id,
                    exc,
                )
                await session.rollback()
                raise

    try:
        return run_async_celery_task(_process())
    except Exception as exc:
        logger.warning(
            "[process_zalo_inbox_event] Retrying event for workspace %s (attempt %s): %s",
            workspace_id,
            self.request.retries,
            exc,
        )
        raise self.retry(exc=exc) from exc
