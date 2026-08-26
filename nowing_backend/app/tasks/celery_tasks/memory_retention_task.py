"""Celery task to apply workspace memory retention policies (Story 28.5).

Archives (soft-deletes) or purges (hard-deletes) memory rows older than
the configured retention window per workspace.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update

from app.celery_app import celery_app
from app.db import (
    AuditEvent,
    DocumentRetentionAction,
    Memory,
    Workspace,
)
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)


@celery_app.task(name="apply_memory_retention_policies")
def apply_memory_retention_policies():
    return run_async_celery_task(apply_memory_retention_policies_async)


async def apply_memory_retention_policies_async() -> dict[str, int]:
    """Execute memory retention policy for all active workspaces."""
    session_maker = get_celery_session_maker()
    total_archived = 0
    total_deleted = 0

    async with session_maker() as session:
        result = await session.execute(
            select(Workspace).where(Workspace.memory_auto_archive_enabled.is_(True))
        )
        workspaces = list(result.scalars().all())
        now = datetime.now(UTC)

        for ws in workspaces:
            if not ws.memory_auto_archive_enabled or not ws.memory_retention_days:
                continue

            cutoff = now - timedelta(days=ws.memory_retention_days)
            action = ws.memory_retention_action or DocumentRetentionAction.ARCHIVE

            if action == DocumentRetentionAction.DELETE or action == "delete":
                # Hard delete memory rows older than cutoff (versions and relations cascade)
                del_stmt = delete(Memory).where(
                    Memory.workspace_id == ws.id,
                    Memory.created_at < cutoff,
                )
                del_res = await session.execute(del_stmt)
                raw_del = getattr(del_res, "rowcount", 0)
                deleted_count = int(raw_del) if isinstance(raw_del, int) else 0
                total_deleted += deleted_count

                if deleted_count > 0:
                    audit = AuditEvent(
                        action="retention_purge",
                        diff_payload={
                            "strategy": "delete",
                            "workspace_id": ws.id,
                            "affected_count": deleted_count,
                        },
                    )
                    session.add(audit)
                    logger.info(
                        "Purged %d expired memories for workspace %s (older than %s)",
                        deleted_count,
                        ws.id,
                        cutoff,
                    )
            else:
                # Soft delete (archive) memory rows older than cutoff
                upd_stmt = (
                    update(Memory)
                    .where(
                        Memory.workspace_id == ws.id,
                        Memory.created_at < cutoff,
                        Memory.archived_at.is_(None),
                    )
                    .values(archived_at=now)
                )
                upd_res = await session.execute(upd_stmt)
                raw_upd = getattr(upd_res, "rowcount", 0)
                archived_count = int(raw_upd) if isinstance(raw_upd, int) else 0
                total_archived += archived_count

                if archived_count > 0:
                    audit = AuditEvent(
                        action="retention_purge",
                        diff_payload={
                            "strategy": "archive",
                            "workspace_id": ws.id,
                            "affected_count": archived_count,
                        },
                    )
                    session.add(audit)
                    logger.info(
                        "Archived %d expired memories for workspace %s (older than %s)",
                        archived_count,
                        ws.id,
                        cutoff,
                    )

        await session.commit()

    return {"archived": total_archived, "deleted": total_deleted}
