"""Document delete Celery tasks."""

import logging

from app.celery_app import celery_app
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)

# ===== Redis heartbeat for document processing tasks =====
# Same mechanism as connector indexing heartbeats (app/routes/connectors/_shared.py).
# A background coroutine refreshes a Redis key every 60s with a 2-min TTL.
# If the Celery worker crashes, the coroutine dies, the key expires, and the
# stale_notification_cleanup_task detects the missing key and marks the
# notification + document as failed.
_doc_heartbeat_redis = None
HEARTBEAT_TTL_SECONDS = 120  # 2 minutes — same as connector indexing
HEARTBEAT_REFRESH_INTERVAL = 60  # Refresh every 60 seconds


@celery_app.task(
    name="delete_document_background",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=5,
)
def delete_document_task(self, document_id: int):
    """Celery task to delete a document and its chunks in batches."""
    return run_async_celery_task(lambda: _delete_document_background(document_id))
async def _delete_document_background(document_id: int) -> None:
    """Delete chunks in batches first, then remove the document row."""
    from sqlalchemy import delete as sa_delete, select

    from app.db import Chunk, Document
    from app.file_storage.service import purge_document_blobs

    async with get_celery_session_maker()() as session:
        batch_size = 500
        while True:
            chunk_ids_result = await session.execute(
                select(Chunk.id)
                .where(Chunk.document_id == document_id)
                .limit(batch_size)
            )
            chunk_ids = chunk_ids_result.scalars().all()
            if not chunk_ids:
                break
            await session.execute(sa_delete(Chunk).where(Chunk.id.in_(chunk_ids)))
            await session.commit()

        # Remove stored blobs before the document_files rows cascade away.
        await purge_document_blobs(session, document_ids=[document_id])

        doc = await session.get(Document, document_id)
        if doc:
            await session.delete(doc)
            await session.commit()
@celery_app.task(
    name="delete_folder_documents_background",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=5,
)
def delete_folder_documents_task(
    self,
    document_ids: list[int],
    folder_subtree_ids: list[int] | None = None,
):
    """Celery task to delete documents first, then the folder rows."""
    return run_async_celery_task(
        lambda: _delete_folder_documents(document_ids, folder_subtree_ids)
    )
async def _delete_folder_documents(
    document_ids: list[int],
    folder_subtree_ids: list[int] | None = None,
) -> None:
    """Delete chunks in batches, then document rows, then folder rows."""
    from sqlalchemy import delete as sa_delete, select

    from app.db import Chunk, Document, Folder
    from app.file_storage.service import purge_document_blobs

    async with get_celery_session_maker()() as session:
        batch_size = 500
        for doc_id in document_ids:
            while True:
                chunk_ids_result = await session.execute(
                    select(Chunk.id)
                    .where(Chunk.document_id == doc_id)
                    .limit(batch_size)
                )
                chunk_ids = chunk_ids_result.scalars().all()
                if not chunk_ids:
                    break
                await session.execute(sa_delete(Chunk).where(Chunk.id.in_(chunk_ids)))
                await session.commit()

            # Remove stored blobs before the document_files rows cascade away.
            await purge_document_blobs(session, document_ids=[doc_id])

            doc = await session.get(Document, doc_id)
            if doc:
                await session.delete(doc)
                await session.commit()

        if folder_subtree_ids:
            await session.execute(
                sa_delete(Folder).where(Folder.id.in_(folder_subtree_ids))
            )
            await session.commit()
@celery_app.task(
    name="delete_search_space_background",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=5,
)
def delete_workspace_task(self, workspace_id: int):
    """Celery task to delete a workspace and heavy child rows in batches."""
    return run_async_celery_task(lambda: _delete_workspace_background(workspace_id))
async def _delete_workspace_background(workspace_id: int) -> None:
    """Delete chunks/docs in batches first, then delete the workspace."""
    from sqlalchemy import delete as sa_delete, select

    from app.db import Chunk, Document, Workspace
    from app.file_storage.service import purge_document_blobs

    async with get_celery_session_maker()() as session:
        batch_size = 500

        while True:
            chunk_ids_result = await session.execute(
                select(Chunk.id)
                .join(Document, Chunk.document_id == Document.id)
                .where(Document.workspace_id == workspace_id)
                .limit(batch_size)
            )
            chunk_ids = chunk_ids_result.scalars().all()
            if not chunk_ids:
                break
            await session.execute(sa_delete(Chunk).where(Chunk.id.in_(chunk_ids)))
            await session.commit()

        while True:
            doc_ids_result = await session.execute(
                select(Document.id)
                .where(Document.workspace_id == workspace_id)
                .limit(batch_size)
            )
            doc_ids = doc_ids_result.scalars().all()
            if not doc_ids:
                break
            # Remove stored blobs before the document_files rows cascade away.
            await purge_document_blobs(session, document_ids=list(doc_ids))
            await session.execute(sa_delete(Document).where(Document.id.in_(doc_ids)))
            await session.commit()

        space = await session.get(Workspace, workspace_id)
        if space:
            await session.delete(space)
            await session.commit()
