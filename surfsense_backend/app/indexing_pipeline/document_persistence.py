from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import object_session
from sqlalchemy.orm.attributes import set_committed_value

from app.db import Document, DocumentStatus


async def rollback_and_persist_failure(
    session: AsyncSession, document: Document, message: str
) -> None:
    """Roll back the current transaction, refresh the document, and persist a failed status."""
    await session.rollback()
    await session.refresh(document)
    document.updated_at = datetime.now(UTC)
    document.status = DocumentStatus.failed(message)
    await session.commit()


def attach_chunks_to_document(document: Document, chunks: list) -> None:
    """Assign chunks to a document without triggering SQLAlchemy async lazy loading."""
    set_committed_value(document, "chunks", chunks)
    session = object_session(document)
    if session is not None:
        if document.id is not None:
            for chunk in chunks:
                chunk.document_id = document.id
        session.add_all(chunks)
