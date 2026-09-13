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
import fnmatch
import logging
import re

from deepagents.backends.protocol import (
    FileInfo,
    GrepMatch,
)
from sqlalchemy import select

from app.agents.chat.runtime.path_resolver import (
    DOCUMENTS_ROOT,
    build_path_index,
    doc_to_virtual_path,
)
from app.db import Chunk, Document, shielded_async_session

from ._helpers import _GREP_MAX_PER_DOC, _GREP_MAX_TOTAL_MATCHES, _basename, _is_under

logger = logging.getLogger(__name__)


class SearchMixin:
    # ------------------------------------------------------------------ glob/grep

    async def aglob_info(self, pattern: str, path: str = "/") -> list[FileInfo]:  # type: ignore[override]
        normalized = self._normalize_listing_path(path)
        results: list[FileInfo] = []
        seen: set[str] = set()

        files = self._state_files()
        moved_removed, _, deleted_dirs = self._pending_filesystem_view(files)
        regex = re.compile(fnmatch.translate(pattern))
        for path_key, fd in files.items():
            if path_key in moved_removed or self._is_dir_suppressed(
                path_key, deleted_dirs
            ):
                continue
            if not _is_under(path_key, normalized):
                continue
            rel = (
                path_key[len(normalized) :].lstrip("/")
                if normalized != "/"
                else path_key.lstrip("/")
            )
            if not regex.match(rel) and not regex.match(path_key):
                continue
            if path_key in seen:
                continue
            size = self._file_data_size(fd) if isinstance(fd, dict) else 0
            results.append(
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

        if normalized.startswith(DOCUMENTS_ROOT) or normalized == "/":
            try:
                async with shielded_async_session() as session:
                    index = await build_path_index(session, self.workspace_id)
                    rows = await session.execute(
                        select(Document.id, Document.title, Document.folder_id).where(
                            Document.workspace_id == self.workspace_id
                        )
                    )
                    for row in rows.all():
                        candidate = doc_to_virtual_path(
                            doc_id=row.id,
                            title=str(row.title or "untitled"),
                            folder_id=row.folder_id,
                            index=index,
                        )
                        if (
                            candidate in seen
                            or candidate in moved_removed
                            or self._is_dir_suppressed(candidate, deleted_dirs)
                        ):
                            continue
                        if not _is_under(candidate, normalized):
                            continue
                        rel = (
                            candidate[len(normalized) :].lstrip("/")
                            if normalized != "/"
                            else candidate.lstrip("/")
                        )
                        if not regex.match(rel) and not regex.match(candidate):
                            continue
                        results.append(
                            FileInfo(
                                path=candidate, is_dir=False, size=0, modified_at=""
                            )
                        )
                        seen.add(candidate)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("KBPostgresBackend.aglob_info DB error: %s", exc)

        results.sort(key=lambda fi: fi.get("path", ""))
        return results

    def glob_info(self, pattern: str, path: str = "/") -> list[FileInfo]:  # type: ignore[override]
        return asyncio.run(self.aglob_info(pattern, path))

    async def agrep_raw(  # type: ignore[override]
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
    ) -> list[GrepMatch] | str:
        if not pattern:
            return "Error: pattern cannot be empty"

        normalized = self._normalize_listing_path(path or "/")
        matches: list[GrepMatch] = []

        files = self._state_files()
        moved_removed, _, deleted_dirs = self._pending_filesystem_view(files)
        glob_re = re.compile(fnmatch.translate(glob)) if glob else None
        for path_key, fd in files.items():
            if path_key in moved_removed or self._is_dir_suppressed(
                path_key, deleted_dirs
            ):
                continue
            if not _is_under(path_key, normalized):
                continue
            if glob_re is not None and not glob_re.match(_basename(path_key)):
                continue
            if not isinstance(fd, dict):
                continue
            for line_no, line in enumerate(fd.get("content") or [], 1):
                if pattern in line:
                    matches.append(
                        GrepMatch(path=path_key, line=int(line_no), text=str(line))
                    )
                    if len(matches) >= _GREP_MAX_TOTAL_MATCHES:
                        return matches

        if normalized.startswith(DOCUMENTS_ROOT) or normalized == "/":
            try:
                async with shielded_async_session() as session:
                    index = await build_path_index(session, self.workspace_id)
                    sub = (
                        select(Chunk.document_id, Chunk.id, Chunk.content)
                        .join(Document, Document.id == Chunk.document_id)
                        .where(Document.workspace_id == self.workspace_id)
                        .where(Chunk.content.ilike(f"%{pattern}%"))
                        .order_by(Chunk.document_id, Chunk.position, Chunk.id)
                    )
                    chunk_rows = await session.execute(sub)
                    per_doc: dict[int, int] = {}
                    doc_id_to_path: dict[int, str] = {}
                    needed_doc_ids: set[int] = set()
                    chunk_buffer: list[tuple[int, int, str]] = []
                    for row in chunk_rows.all():
                        per_doc.setdefault(row.document_id, 0)
                        if per_doc[row.document_id] >= _GREP_MAX_PER_DOC:
                            continue
                        per_doc[row.document_id] += 1
                        chunk_buffer.append((row.document_id, row.id, row.content))
                        needed_doc_ids.add(row.document_id)
                        if sum(per_doc.values()) >= _GREP_MAX_TOTAL_MATCHES - len(
                            matches
                        ):
                            break
                    if needed_doc_ids:
                        doc_rows = await session.execute(
                            select(
                                Document.id, Document.title, Document.folder_id
                            ).where(Document.id.in_(list(needed_doc_ids)))
                        )
                        for row in doc_rows.all():
                            doc_id_to_path[row.id] = doc_to_virtual_path(
                                doc_id=row.id,
                                title=str(row.title or "untitled"),
                                folder_id=row.folder_id,
                                index=index,
                            )
                    for doc_id, chunk_id, content in chunk_buffer:
                        candidate = doc_id_to_path.get(doc_id)
                        if (
                            not candidate
                            or candidate in moved_removed
                            or self._is_dir_suppressed(candidate, deleted_dirs)
                        ):
                            continue
                        if not _is_under(candidate, normalized):
                            continue
                        if glob_re is not None and not glob_re.match(
                            _basename(candidate)
                        ):
                            continue
                        snippet = " ".join(str(content).split())[:240]
                        matches.append(
                            GrepMatch(
                                path=candidate,
                                line=0,
                                text=(
                                    f"<chunk-match in {candidate} chunk_id={chunk_id}>: "
                                    f"{snippet}"
                                ),
                            )
                        )
                        if len(matches) >= _GREP_MAX_TOTAL_MATCHES:
                            break
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("KBPostgresBackend.agrep_raw DB error: %s", exc)

        return matches

    def grep_raw(  # type: ignore[override]
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
    ) -> list[GrepMatch] | str:
        return asyncio.run(self.agrep_raw(pattern, path, glob))
