"""
Schemas for Nowing documentation.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NowingDocsChunkRead(BaseModel):
    """Schema for a Nowing docs chunk."""

    id: int
    content: str

    model_config = ConfigDict(from_attributes=True)


class NowingDocsDocumentRead(BaseModel):
    """Schema for a Nowing docs document (without chunks)."""

    id: int
    title: str
    source: str
    content: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class NowingDocsDocumentWithChunksRead(BaseModel):
    """Schema for a Nowing docs document with its chunks."""

    id: int
    title: str
    source: str
    content: str
    chunks: list[NowingDocsChunkRead]

    model_config = ConfigDict(from_attributes=True)
