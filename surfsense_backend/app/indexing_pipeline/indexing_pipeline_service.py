from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentStatus
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.document_hashing import compute_content_hash, compute_unique_identifier_hash


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
