"""Celery task to apply workspace document retention policies.

Archives (soft-deletes) documents older than the configured retention window and,
when the workspace strategy is ``delete``, dispatches the existing per-document
``delete_document_task`` to perform the hard cleanup.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.future import select

from app.celery_app import celery_app
from app.db import Document, DocumentRetentionAction, Workspace
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task
from app.tasks.celery_tasks.document_tasks import delete_document_task

logger = logging.getLogger(__name__)


@celery_app.task(name="apply_document_retention_policies")
def apply_document_retention_policies():
    return run_async_celery_task(_apply_retention)


async def _apply_retention() -> None:
    async with get_celery_session_maker()() as session:
        workspaces = await session.execute(
            select(Workspace).filter(Workspace.auto_archive_enabled == True)  # noqa: E712
        )
        now = datetime.now(UTC)
        for ws in workspaces.scalars():
            if not ws.auto_archive_enabled or not ws.document_retention_days:
                continue
            cutoff = now - timedelta(days=ws.document_retention_days)
            result = await session.execute(
                select(Document).filter(
                    Document.workspace_id == ws.id,
                    Document.created_at < cutoff,
                    Document.archived_at.is_(None),
                    Document.status["state"].astext.notin_(
                        ["pending", "processing", "deleting"]
                    ),
                )
            )
            for doc in result.scalars():
                doc.archived_at = now
                if ws.document_retention_action == DocumentRetentionAction.DELETE:
                    doc.status = {"state": "deleting"}
                    try:
                        delete_document_task.delay(doc.id)
                    except Exception:
                        logger.exception(
                            "Failed to dispatch delete_document_task for doc %s; "
                            "reverting status to ready",
                            doc.id,
                        )
                        doc.status = {"state": "ready"}
        await session.commit()
