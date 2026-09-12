"""Postgres-backed virtual filesystem for the Nowing agent (cloud mode).

The backend is **strictly conforming** to deepagents'
:class:`BackendProtocol`. It returns ``WriteResult`` / ``EditResult`` / list
shapes exactly as upstream expects (no extra fields). All side-state
plumbing — ``dirty_paths``, ``doc_id_by_path``, ``staged_dirs``,
``pending_moves``, ``files`` cache — is appended by the overridden tool
wrappers in :class:`NowingFilesystemMiddleware` via ``Command.update``.

The backend never writes to Postgres. End-of-turn persistence is handled by
:class:`KnowledgeBasePersistenceMiddleware`. This module is purely a
read-side and a state-merging helper.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from deepagents.backends.protocol import (
    FileInfo,
)

from app.agents.chat.multi_agent_chat.shared.citations import (
    CitationRegistry,
)
from app.agents.chat.multi_agent_chat.shared.document_render import (
    RenderableDocument,
    render_document,
)

logger = logging.getLogger(__name__)

_TEMP_PREFIX = "temp_"
_GREP_MAX_TOTAL_MATCHES = 50
_GREP_MAX_PER_DOC = 5

_EMPTY_DOCUMENT_NOTICE = "(This document has no readable content.)"


def render_full_document(
    document: RenderableDocument,
    registry: CitationRegistry,
) -> str:
    """Render a whole KB document (``view="full"``), registering each chunk's ``[n]``.

    Falls back to a short notice when the document has no chunks, so a read never
    returns blank.
    """
    rendered = render_document(document, view="full", registry=registry)
    return rendered if rendered is not None else _EMPTY_DOCUMENT_NOTICE


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def _is_under(child: str, parent: str) -> bool:
    """Return True iff ``child`` is at-or-under ``parent`` (directory semantics)."""
    if parent == "/":
        return child.startswith("/")
    return child == parent or child.startswith(parent.rstrip("/") + "/")


def paginate_listing(
    infos: list[FileInfo],
    *,
    offset: int = 0,
    limit: int | None = None,
) -> list[FileInfo]:
    """Paginate a listing produced by :meth:`KBPostgresBackend.als_info`."""
    if offset < 0:
        offset = 0
    end: int | None
    end = None if limit is None or limit < 0 else offset + limit
    return list(infos[offset:end])


async def list_tree_listing(
    backend: KBPostgresBackend,
    path: str,
    *,
    max_depth: int | None = 8,
    page_size: int = 500,
    include_files: bool = True,
    include_dirs: bool = True,
) -> dict[str, Any]:
    """Async helper used by the overridden ``list_tree`` tool wrapper."""
    return await backend.alist_tree_listing(
        path,
        max_depth=max_depth,
        page_size=page_size,
        include_files=include_files,
        include_dirs=include_dirs,
    )


__all__ = ["list_tree_listing", "paginate_listing", "render_full_document"]

if TYPE_CHECKING:
    from .backend import KBPostgresBackend
