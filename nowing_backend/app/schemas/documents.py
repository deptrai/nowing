from datetime import datetime
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db import DocumentType

from .chunks import ChunkRead

T = TypeVar("T")


class ExtensionDocumentMetadata(BaseModel):
    BrowsingSessionId: str
    VisitedWebPageURL: str
    VisitedWebPageTitle: str
    VisitedWebPageDateWithTimeInISOString: str
    VisitedWebPageReffererURL: str
    VisitedWebPageVisitDurationInMilliseconds: str


class ExtensionDocumentContent(BaseModel):
    metadata: ExtensionDocumentMetadata
    pageContent: str  # noqa: N815


class DocumentBase(BaseModel):
    document_type: DocumentType
    content: (
        list[ExtensionDocumentContent] | list[str] | str
    )  # Updated to allow string content
    workspace_id: int


class DocumentsCreate(DocumentBase):
    pass


class DocumentUpdate(DocumentBase):
    pass


class DocumentStatusSchema(BaseModel):
    """Document processing status."""

    state: str  # "ready", "processing", "failed"
    reason: str | None = None


class DocumentRead(BaseModel):
    id: int
    title: str
    document_type: DocumentType
    document_metadata: dict = Field(default_factory=dict)
    content: str = ""
    content_preview: str = ""
    content_hash: str
    unique_identifier_hash: str | None
    created_at: datetime
    updated_at: datetime | None
    archived_at: datetime | None = None
    workspace_id: int
    folder_id: int | None = None
    created_by_id: UUID | None = None
    created_by_name: str | None = None
    created_by_email: str | None = None
    status: DocumentStatusSchema | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("document_metadata", mode="before")
    @classmethod
    def _ensure_document_metadata_dict(cls, v: object) -> dict:
        return v if isinstance(v, dict) else {}


class DocumentWithChunksRead(DocumentRead):
    chunks: list[ChunkRead] = []
    total_chunks: int = 0
    chunk_start_index: int = 0

    model_config = ConfigDict(from_attributes=True)


class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
    has_more: bool


class DocumentTitleRead(BaseModel):
    """Lightweight document response for mention picker - only essential fields."""

    id: int
    title: str
    document_type: DocumentType
    folder_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentTitleSearchResponse(BaseModel):
    """Response for document title search - optimized for typeahead."""

    items: list[DocumentTitleRead]
    has_more: bool


class DocumentStatusItemRead(BaseModel):
    """Lightweight document status payload for batch status polling."""

    id: int
    title: str
    document_type: DocumentType
    status: DocumentStatusSchema

    model_config = ConfigDict(from_attributes=True)


class DocumentStatusBatchResponse(BaseModel):
    """Batch status response for a set of document IDs."""

    items: list[DocumentStatusItemRead]
