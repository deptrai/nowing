"""Celery tasks for Workspace Health & Adoption Daily Aggregation (Story 29.2, AD-52)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.celery_app import celery_app
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)


@celery_app.task(
    name="aggregate_workspace_health_daily",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def aggregate_workspace_health_daily(
    target_date_str: str | None = None,
) -> dict[str, int]:
    """Roll up workspace health and adoption metrics for yesterday (or specified target_date)."""
    return run_async_celery_task(_aggregate_health_daily, target_date_str)


async def _aggregate_health_daily(
    target_date_str: str | None = None,
) -> dict[str, int]:
    from app.services.workspace_health_service import WorkspaceHealthService

    if target_date_str:
        target_date = datetime.fromisoformat(target_date_str).date()
    else:
        # Default: yesterday UTC
        target_date = (datetime.now(UTC) - timedelta(days=1)).date()

    async with get_celery_session_maker()() as session:
        succeeded: list[int] = []
        failed: list[int] = []

        # Pre-fetch workspace ids outside the per-workspace transaction.
        ids_res = await session.execute(
            text("SELECT id FROM workspaces ORDER BY id")
        )
        workspace_ids = [r[0] for r in ids_res.all()]

        for wid in workspace_ids:
            # Each workspace is committed in its own savepoint so a single
            # failing workspace cannot roll back the whole nightly batch.
            try:
                async with session.begin_nested():
                    await WorkspaceHealthService._rollup_for_workspace_date(
                        session=session,
                        workspace_id=wid,
                        target_date=target_date,
                        persist=True,
                    )
                await session.commit()
                succeeded.append(wid)
            except Exception as exc:  # per-item failure; rollback and continue workspace batch
                logger.error(
                    "Workspace health rollup failed for workspace %s on %s: %s",
                    wid,
                    target_date,
                    exc,
                    exc_info=True,
                )
                await session.rollback()
                failed.append(wid)

        logger.info(
            "Aggregated workspace health metrics for %s workspaces on %s (%s succeeded, %s failed)",
            len(workspace_ids),
            target_date,
            len(succeeded),
            len(failed),
        )

        return {
            "workspaces_processed": len(succeeded),
            "workspaces_failed": len(failed),
        }
