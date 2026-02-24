from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import object_session
from sqlalchemy.orm.attributes import set_committed_value

from app.config import config
from app.db import Document, DocumentStatus
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.document_hashing import compute_content_hash, compute_unique_identifier_hash
from app.utils.document_converters import create_document_chunks, generate_document_summary


def _safe_set_chunks(document: Document, chunks: list) -> None:
    set_committed_value(document, "chunks", chunks)
    session = object_session(document)
    if session is not None:
        if document.id is not None:
            for chunk in chunks:
                chunk.document_id = document.id
        session.add_all(chunks)


class IndexingPipelineService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def prepare_for_indexing(
        self, connector_docs: list[ConnectorDocument]
    ) -> list[Document]:
        documents = []

        for connector_doc in connector_docs:
            unique_identifier_hash = compute_unique_identifier_hash(connector_doc)
            content_hash = compute_content_hash(connector_doc)

            result = await self.session.execute(
                select(Document).filter(Document.unique_identifier_hash == unique_identifier_hash)
            )
            existing = result.scalars().first()

            if existing is not None:
                if existing.content_hash == content_hash:
                    if existing.title != connector_doc.title:
                        existing.title = connector_doc.title
                    continue

                existing.title = connector_doc.title
                existing.content_hash = content_hash
                existing.source_markdown = connector_doc.source_markdown
                existing.status = DocumentStatus.pending()
                documents.append(existing)
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
                status=DocumentStatus.pending(),
            )
            self.session.add(document)
            documents.append(document)

        await self.session.commit()
        return documents

    async def index(
        self, document: Document, connector_doc: ConnectorDocument, llm
    ) -> None:
        try:
            document.status = DocumentStatus.processing()
            await self.session.commit()

            if connector_doc.should_summarize:
                content, embedding = await generate_document_summary(
                    connector_doc.source_markdown, llm, connector_doc.metadata
                )
            else:
                content = connector_doc.source_markdown
                embedding = config.embedding_model_instance.embed(content)

            chunks = await create_document_chunks(connector_doc.source_markdown)

            document.source_markdown = connector_doc.source_markdown
            document.content = content
            document.embedding = embedding
            _safe_set_chunks(document, chunks)
            document.status = DocumentStatus.ready()
            await self.session.commit()

        except Exception as e:
            await self.session.rollback()
            await self.session.refresh(document)
            document.status = DocumentStatus.failed(str(e))
            await self.session.commit()
