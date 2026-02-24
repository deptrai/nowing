import hashlib

from app.indexing_pipeline.connector_document import ConnectorDocument


def compute_unique_identifier_hash(doc: ConnectorDocument) -> str:
    combined = f"{doc.document_type.value}:{doc.unique_id}:{doc.search_space_id}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def compute_content_hash(doc: ConnectorDocument) -> str:
    combined = f"{doc.search_space_id}:{doc.source_markdown}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()
