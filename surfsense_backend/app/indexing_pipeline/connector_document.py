from pydantic import BaseModel, field_validator

from app.db import DocumentType


class ConnectorDocument(BaseModel):
    title: str
    source_markdown: str
    unique_id: str
    document_type: DocumentType
    search_space_id: int
    should_summarize: bool = True
    should_use_code_chunker: bool = False
    metadata: dict = {}
    connector_id: int | None = None
    created_by_id: str | None = None

    @field_validator("title", "source_markdown", "unique_id")
    @classmethod
    def not_empty(cls, v: str, info) -> str:
        if not v.strip():
            raise ValueError(f"{info.field_name} must not be empty or whitespace")
        return v
