from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import object_session
from sqlalchemy.orm.attributes import set_committed_value

from app.db import Chunk, Document, DocumentStatus
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.document_chunker import chunk_text
from app.indexing_pipeline.document_embedder import embed_text
from app.indexing_pipeline.document_hashing import compute_content_hash, compute_unique_identifier_hash
from app.indexing_pipeline.document_summarizer import summarize_document


def _safe_set_chunks(document: Document, chunks: list) -> None:
    """Assign chunks to a document without triggering SQLAlchemy async lazy loading."""
    set_committed_value(document, "chunks", chunks)
    session = object_session(document)
    if session is not None:
        if document.id is not None:
            for chunk in chunks:
                chunk.document_id = document.id
        session.add_all(chunks)


class IndexingPipelineService:
    """Single pipeline for indexing connector documents. All connectors use this service."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def prepare_for_indexing(
        self, connector_docs: list[ConnectorDocument]
    ) -> list[Document]:
        """
        Persist new documents and detect changes, returning only those that need indexing.
        """
        documents = []
        seen_hashes: set[str] = set()

        for connector_doc in connector_docs:
            try:
                unique_identifier_hash = compute_unique_identifier_hash(connector_doc)
                content_hash = compute_content_hash(connector_doc)

                if unique_identifier_hash in seen_hashes:
                    continue
                seen_hashes.add(unique_identifier_hash)

                result = await self.session.execute(
                    select(Document).filter(Document.unique_identifier_hash == unique_identifier_hash)
                )
                existing = result.scalars().first()

                if existing is not None:
                    if existing.content_hash == content_hash:
                        if existing.title != connector_doc.title:
                            existing.title = connector_doc.title
                            existing.updated_at = datetime.now(UTC)
                        if not DocumentStatus.is_state(existing.status, DocumentStatus.READY):
                            existing.status = DocumentStatus.pending()
                            existing.updated_at = datetime.now(UTC)
                            documents.append(existing)
                        continue

                    existing.title = connector_doc.title
                    existing.content_hash = content_hash
                    existing.source_markdown = connector_doc.source_markdown
                    existing.document_metadata = connector_doc.metadata
                    existing.updated_at = datetime.now(UTC)
                    existing.status = DocumentStatus.pending()
                    documents.append(existing)
                    continue

                duplicate = await self.session.execute(
                    select(Document).filter(Document.content_hash == content_hash)
                )
                if duplicate.scalars().first() is not None:
                    continue

                document = Document(
                    title=connector_doc.title,
                    document_type=connector_doc.document_type,
                    content="Pending...",
                    content_hash=content_hash,
                    unique_identifier_hash=unique_identifier_hash,
                    source_markdown=connector_doc.source_markdown,
                    document_metadata=connector_doc.metadata,
                    search_space_id=connector_doc.search_space_id,
                    connector_id=connector_doc.connector_id,
                    created_by_id=connector_doc.created_by_id,
                    updated_at=datetime.now(UTC),
                    status=DocumentStatus.pending(),
                )
                self.session.add(document)
                documents.append(document)

            except Exception:
                continue

        try:
            await self.session.commit()
            return documents
        except IntegrityError:
            # A concurrent worker committed a document with the same content_hash
            # or unique_identifier_hash between our check and our INSERT.
            # The document already exists — roll back and let the next sync run handle it.
            await self.session.rollback()
            return []

    async def index(
        self, document: Document, connector_doc: ConnectorDocument, llm
    ) -> None:
        """
        Run summarization, embedding, and chunking for a document and persist the results.
        """
        try:
            document.status = DocumentStatus.processing()
            await self.session.commit()

            if connector_doc.should_summarize and llm is not None:
                content = await summarize_document(
                    connector_doc.source_markdown, llm, connector_doc.metadata
                )
            elif connector_doc.should_summarize and connector_doc.fallback_summary:
                content = connector_doc.fallback_summary
            else:
                content = connector_doc.source_markdown

            embedding = embed_text(content)

            await self.session.execute(
                delete(Chunk).where(Chunk.document_id == document.id)
            )

            chunks = [
                Chunk(content=text, embedding=embed_text(text))
                for text in chunk_text(
                    connector_doc.source_markdown,
                    use_code_chunker=connector_doc.should_use_code_chunker,
                )
            ]

            document.content = content
            document.embedding = embedding
            _safe_set_chunks(document, chunks)
            document.updated_at = datetime.now(UTC)
            document.status = DocumentStatus.ready()
            await self.session.commit()

        except Exception as e:
            await self.session.rollback()
            await self.session.refresh(document)
            document.updated_at = datetime.now(UTC)
            document.status = DocumentStatus.failed(str(e))
            await self.session.commit()
