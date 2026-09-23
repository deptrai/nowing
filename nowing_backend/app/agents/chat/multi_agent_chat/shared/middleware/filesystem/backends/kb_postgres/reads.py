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

import asyncio
import contextlib
import logging
from datetime import UTC
from typing import Any

from deepagents.backends.protocol import (
    FileInfo,
)
from deepagents.backends.utils import (
    create_file_data,
    format_read_response,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat.shared.citations import (
    CitationRegistry,
    CitationSourceType,
)
from app.agents.chat.multi_agent_chat.shared.document_render import (
    RenderableDocument,
    RenderablePassage,
    source_label,
)
from app.agents.chat.runtime.path_resolver import (
    DOCUMENTS_ROOT,
    build_path_index,
    doc_to_virtual_path,
    virtual_path_to_doc,
)
from app.db import Chunk, Document, shielded_async_session

from ._helpers import _TEMP_PREFIX, _basename, _is_under, render_full_document

logger = logging.getLogger(__name__)


class ReadsMixin:
    # ------------------------------------------------------------------ ls/read

    async def als_info(self, path: str) -> list[FileInfo]:  # type: ignore[override]
        normalized = self._normalize_listing_path(path)
        infos: list[FileInfo] = []
        seen: set[str] = set()

        anon = self._kb_anon_doc()
        if anon:
            anon_path = str(anon.get("path") or "")
            if (
                anon_path
                and _is_under(anon_path, normalized)
                and anon_path != normalized
                and anon_path not in seen
            ):
                infos.append(
                    FileInfo(
                        path=anon_path,
                        is_dir=False,
                        size=len(str(anon.get("content") or "")),
                        modified_at="",
                    )
                )
                seen.add(anon_path)

        files = self._state_files()
        moved_removed, moved_alias, deleted_dirs = self._pending_filesystem_view(files)

        if normalized.startswith(DOCUMENTS_ROOT) or normalized == "/":
            try:
                async with shielded_async_session() as session:
                    db_infos, subdir_paths = await self._list_db_directory(
                        session, normalized
                    )
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("KBPostgresBackend.als_info DB error: %s", exc)
                db_infos, subdir_paths = [], set()

            for info in db_infos:
                p = info.get("path", "")
                if (
                    not p
                    or p in seen
                    or p in moved_removed
                    or self._is_dir_suppressed(p, deleted_dirs)
                ):
                    continue
                infos.append(info)
                seen.add(p)

            for src, dst in moved_alias.items():
                if src not in seen:
                    if not _is_under(dst, normalized):
                        continue
                    if self._is_dir_suppressed(dst, deleted_dirs):
                        continue
                    rel = (
                        dst[len(normalized) :].lstrip("/")
                        if normalized != "/"
                        else dst.lstrip("/")
                    )
                    if "/" in rel:
                        subdir_paths.add(
                            (normalized.rstrip("/") + "/" + rel.split("/", 1)[0])
                            if normalized != "/"
                            else "/" + rel.split("/", 1)[0]
                        )
                        continue
                    if dst in seen:
                        continue
                    fd = files.get(dst)
                    size = self._file_data_size(fd) if isinstance(fd, dict) else 0
                    infos.append(
                        FileInfo(
                            path=dst,
                            is_dir=False,
                            size=int(size),
                            modified_at=fd.get("modified_at", "")
                            if isinstance(fd, dict)
                            else "",
                        )
                    )
                    seen.add(dst)

            for staged in self._staged_dirs():
                if not staged or not staged.startswith(DOCUMENTS_ROOT):
                    continue
                if staged == normalized:
                    continue
                if not _is_under(staged, normalized):
                    continue
                if self._is_dir_suppressed(staged, deleted_dirs):
                    continue
                rel = (
                    staged[len(normalized) :].lstrip("/")
                    if normalized != "/"
                    else staged.lstrip("/")
                )
                if not rel:
                    continue
                first = rel.split("/", 1)[0]
                immediate = (
                    normalized.rstrip("/") + "/" + first
                    if normalized != "/"
                    else "/" + first
                )
                subdir_paths.add(immediate)

            for sub in sorted(subdir_paths):
                if sub in seen:
                    continue
                if self._is_dir_suppressed(sub, deleted_dirs):
                    continue
                infos.append(FileInfo(path=sub, is_dir=True, size=0, modified_at=""))
                seen.add(sub)

        for path_key, fd in files.items():
            if not isinstance(path_key, str) or path_key in seen:
                continue
            # Tombstones (None values) are deletion markers from `rm`. The
            # deepagents reducer normally pops them, but a stale tombstone
            # surviving a checkpoint must NOT be reported as a child here —
            # otherwise rmdir mistakenly sees the deleted file as content.
            if fd is None:
                continue
            if not _is_under(path_key, normalized) or path_key == normalized:
                continue
            if path_key in moved_removed or self._is_dir_suppressed(
                path_key, deleted_dirs
            ):
                continue
            if normalized == "/":
                rel = path_key.lstrip("/")
            else:
                rel = path_key[len(normalized) :].lstrip("/")
            if not rel:
                continue
            if "/" in rel:
                first = rel.split("/", 1)[0]
                immediate = (
                    normalized.rstrip("/") + "/" + first
                    if normalized != "/"
                    else "/" + first
                )
                if immediate not in seen:
                    infos.append(
                        FileInfo(path=immediate, is_dir=True, size=0, modified_at="")
                    )
                    seen.add(immediate)
                continue
            include = path_key.startswith(DOCUMENTS_ROOT) or _basename(
                path_key
            ).startswith(_TEMP_PREFIX)
            if not include:
                continue
            size = self._file_data_size(fd) if isinstance(fd, dict) else 0
            infos.append(
                FileInfo(
                    path=path_key,
                    is_dir=False,
                    size=int(size),
                    modified_at=fd.get("modified_at", "")
                    if isinstance(fd, dict)
                    else "",
                )
            )
            seen.add(path_key)

        infos.sort(key=lambda fi: (not fi.get("is_dir", False), fi.get("path", "")))
        return infos

    def ls_info(self, path: str) -> list[FileInfo]:  # type: ignore[override]
        return asyncio.run(self.als_info(path))

    async def _list_db_directory(
        self,
        session: AsyncSession,
        normalized_path: str,
    ) -> tuple[list[FileInfo], set[str]]:
        """List immediate Folders + Documents at ``normalized_path``.

        Returns ``(file_infos, subdirectory_paths)``. ``normalized_path`` may
        be ``/`` (synthesizes ``/documents``) or a path under ``/documents``.
        """
        if normalized_path == "/":
            return (
                [],
                {DOCUMENTS_ROOT},
            )

        if not normalized_path.startswith(DOCUMENTS_ROOT):
            return [], set()

        index = await build_path_index(session, self.workspace_id)
        target_folder_id: int | None = None
        if normalized_path != DOCUMENTS_ROOT:
            target_path = normalized_path
            matches = [
                fid for fid, fpath in index.folder_paths.items() if fpath == target_path
            ]
            if not matches:
                return [], set()
            target_folder_id = matches[0]

        result = await session.execute(
            select(Document.id, Document.title, Document.folder_id, Document.updated_at)
            .where(Document.workspace_id == self.workspace_id)
            .where(
                Document.folder_id == target_folder_id
                if target_folder_id is not None
                else Document.folder_id.is_(None)
            )
        )
        rows = result.all()

        file_infos: list[FileInfo] = []
        for row in rows:
            path = doc_to_virtual_path(
                doc_id=row.id,
                title=str(row.title or "untitled"),
                folder_id=row.folder_id,
                index=index,
            )
            modified = ""
            if row.updated_at is not None:
                with contextlib.suppress(Exception):
                    modified = row.updated_at.astimezone(UTC).isoformat()
            file_infos.append(
                FileInfo(
                    path=path,
                    is_dir=False,
                    size=0,
                    modified_at=modified,
                )
            )

        subdirs: set[str] = set()
        for _fid, fpath in index.folder_paths.items():
            if fpath == normalized_path:
                continue
            base = normalized_path.rstrip("/")
            if not fpath.startswith(base + "/"):
                continue
            rel = fpath[len(base) + 1 :]
            if "/" in rel:
                continue
            subdirs.add(base + "/" + rel)
        return file_infos, subdirs

    async def aread(  # type: ignore[override]
        self,
        file_path: str,
        offset: int = 0,
        limit: int = 2000,
    ) -> str:
        files = self._state_files()
        file_data = files.get(file_path)
        if file_data is not None:
            return format_read_response(file_data, offset, limit)

        loaded = await self._load_file_data(file_path)
        if loaded is None:
            return f"Error: File '{file_path}' not found"
        file_data, _ = loaded
        return format_read_response(file_data, offset, limit)

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:  # type: ignore[override]
        return asyncio.run(self.aread(file_path, offset, limit))

    async def aload_document(
        self,
        path: str,
    ) -> tuple[RenderableDocument, int | None] | None:
        """Lazy-load a virtual KB document as a :class:`RenderableDocument`.

        Returns ``(document, doc_id)`` with every chunk in document order, or
        ``None`` if the path maps to no known document. ``doc_id`` is ``None``
        for the synthetic anonymous upload so the caller doesn't track it as a
        DB-backed file. Pure data — rendering and citation registration happen in
        the caller (see :meth:`_load_file_data` and the ``read_file`` tool).
        """
        anon = self._kb_anon_doc()
        if anon and str(anon.get("path") or "") == path:
            document = RenderableDocument(
                title=str(anon.get("title") or "uploaded_document"),
                source="Uploaded file",
                passages=[
                    RenderablePassage(
                        content=str(chunk.get("content", "")),
                        locator={
                            "document_id": -1,
                            "chunk_id": int(chunk["chunk_id"]),
                        },
                        source_type=CitationSourceType.ANON_CHUNK,
                    )
                    for chunk in (anon.get("chunks") or [])
                    if isinstance(chunk, dict) and chunk.get("chunk_id") is not None
                ],
            )
            return document, None

        if not path.startswith(DOCUMENTS_ROOT):
            return None

        async with shielded_async_session() as session:
            document_row = await virtual_path_to_doc(
                session,
                workspace_id=self.workspace_id,
                virtual_path=path,
            )
            if document_row is None:
                return None
            chunk_rows = await session.execute(
                select(Chunk.id, Chunk.content)
                .where(Chunk.document_id == document_row.id)
                .order_by(Chunk.position, Chunk.id)
            )
            chunks = chunk_rows.all()

        document_type = (
            document_row.document_type.value
            if getattr(document_row, "document_type", None) is not None
            else None
        )
        metadata = dict(document_row.document_metadata or {})
        document = RenderableDocument(
            title=document_row.title,
            source=source_label(document_type, metadata),
            passages=[
                RenderablePassage(
                    content=row.content,
                    locator={"document_id": document_row.id, "chunk_id": row.id},
                )
                for row in chunks
            ],
        )
        return document, document_row.id

    async def _load_file_data(
        self,
        path: str,
    ) -> tuple[dict[str, Any], int | None] | None:
        """Render a virtual KB document into a deepagents ``FileData``.

        Used by the filesystem ops (move/edit existence + content staging) and the
        backend's own ``aread``/``aedit``. These have no conversation registry to
        persist into, so the ``[n]`` labels are minted into a throwaway registry —
        the canonical, citation-persisting read is the ``read_file`` tool, which
        renders from :meth:`aload_document` against the state registry.
        """
        loaded = await self.aload_document(path)
        if loaded is None:
            return None
        document, doc_id = loaded
        rendered = render_full_document(document, CitationRegistry())
        return create_file_data(rendered), doc_id
