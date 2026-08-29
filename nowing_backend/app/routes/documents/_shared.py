"""Shared helpers and schema models for document routes."""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel as PydanticBaseModel, Field

os.environ["UNSTRUCTURED_HAS_PATCHED_LOOP"] = "1"

MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB per file

_MAX_MTIME_CHECK_FILES = 10_000


class SemanticSearchRequest(PydanticBaseModel):
    """Request body for hybrid (semantic + keyword) knowledge-base search."""

    workspace_id: int
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    document_types: list[str] | None = Field(
        default=None,
        description="Optional DocumentType names to restrict the search to.",
    )


class SemanticSearchChunk(PydanticBaseModel):
    content: str
    position: int
    score: float


class SemanticSearchHit(PydanticBaseModel):
    document_id: int
    title: str
    document_type: str | None = None
    score: float
    chunks: list[SemanticSearchChunk]


class SemanticSearchResponse(PydanticBaseModel):
    items: list[SemanticSearchHit]


class FolderMtimeCheckFile(PydanticBaseModel):
    relative_path: str
    mtime: float


class FolderMtimeCheckRequest(PydanticBaseModel):
    folder_name: str
    workspace_id: int
    files: list[FolderMtimeCheckFile] = Field(max_length=_MAX_MTIME_CHECK_FILES)


class FolderUnlinkRequest(PydanticBaseModel):
    folder_name: str
    workspace_id: int
    root_folder_id: int | None = None
    relative_paths: list[str]


class FolderSyncFinalizeRequest(PydanticBaseModel):
    folder_name: str
    workspace_id: int
    root_folder_id: int | None = None
    all_relative_paths: list[str]


def _format_document_status(doc_status: dict[str, Any] | None) -> dict[str, Any]:
    """Return a JSON-serializable status summary for a document."""
    return {
        "state": (doc_status or {}).get("state", "ready"),
        "reason": (doc_status or {}).get("reason"),
    }
