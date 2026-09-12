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

import contextlib
import logging
from datetime import UTC
from typing import Any

from sqlalchemy import select

from app.agents.chat.runtime.path_resolver import (
    DOCUMENTS_ROOT,
    build_path_index,
    doc_to_virtual_path,
)
from app.db import Document, shielded_async_session

from ._helpers import _TEMP_PREFIX, _basename, _is_under

logger = logging.getLogger(__name__)


class TreeMixin:
    # ------------------------------------------------------------------ list_tree (helper)

    async def alist_tree_listing(
        self,
        path: str = DOCUMENTS_ROOT,
        *,
        max_depth: int | None = 8,
        page_size: int = 500,
        include_files: bool = True,
        include_dirs: bool = True,
    ) -> dict[str, Any]:
        """Recursive tree listing for cloud mode.

        Mirrors the shape returned by :class:`MultiRootLocalFolderBackend.list_tree`:
        ``{"entries": [{path, is_dir, size, modified_at, depth}, ...], "truncated": bool}``.
        """
        normalized = self._normalize_listing_path(path or DOCUMENTS_ROOT)
        if not normalized.startswith(DOCUMENTS_ROOT) and normalized != "/":
            return {"error": "Error: path must be under /documents/"}

        entries: list[dict[str, Any]] = []
        truncated = False

        try:
            async with shielded_async_session() as session:
                index = await build_path_index(session, self.workspace_id)
                doc_rows_raw = await session.execute(
                    select(
                        Document.id,
                        Document.title,
                        Document.folder_id,
                        Document.updated_at,
                    ).where(Document.workspace_id == self.workspace_id)
                )
                doc_rows = list(doc_rows_raw.all())
        except Exception as exc:  # pragma: no cover
            logger.warning("KBPostgresBackend.alist_tree_listing DB error: %s", exc)
            return {"entries": [], "truncated": False}

        files = self._state_files()
        moved_removed, _, deleted_dirs = self._pending_filesystem_view(files)
        anon = self._kb_anon_doc()
        anon_path = str(anon.get("path") or "") if anon else ""

        def _depth_of(p: str) -> int:
            if p == DOCUMENTS_ROOT:
                return 0
            rel_root = (
                p[len(DOCUMENTS_ROOT) :].lstrip("/")
                if normalized.startswith(DOCUMENTS_ROOT)
                else p.lstrip("/")
            )
            return len([part for part in rel_root.split("/") if part])

        def _add_entry(entry: dict[str, Any]) -> bool:
            nonlocal truncated
            if len(entries) >= page_size:
                truncated = True
                return False
            entries.append(entry)
            return True

        if include_dirs:
            for _fid, fpath in sorted(index.folder_paths.items(), key=lambda kv: kv[1]):
                if not _is_under(fpath, normalized):
                    continue
                if self._is_dir_suppressed(fpath, deleted_dirs):
                    continue
                depth = _depth_of(fpath)
                if max_depth is not None and depth > max_depth:
                    continue
                if not _add_entry(
                    {
                        "path": fpath,
                        "is_dir": True,
                        "size": 0,
                        "modified_at": "",
                        "depth": depth,
                    }
                ):
                    return {"entries": entries, "truncated": True}
            for staged in self._staged_dirs():
                if not _is_under(staged, normalized):
                    continue
                if self._is_dir_suppressed(staged, deleted_dirs):
                    continue
                depth = _depth_of(staged)
                if max_depth is not None and depth > max_depth:
                    continue
                if any(e["path"] == staged for e in entries):
                    continue
                if not _add_entry(
                    {
                        "path": staged,
                        "is_dir": True,
                        "size": 0,
                        "modified_at": "",
                        "depth": depth,
                    }
                ):
                    return {"entries": entries, "truncated": True}

        if include_files:
            for row in sorted(doc_rows, key=lambda r: str(r.title or "")):
                candidate = doc_to_virtual_path(
                    doc_id=row.id,
                    title=str(row.title or "untitled"),
                    folder_id=row.folder_id,
                    index=index,
                )
                if candidate in moved_removed or self._is_dir_suppressed(
                    candidate, deleted_dirs
                ):
                    continue
                if not _is_under(candidate, normalized):
                    continue
                depth = _depth_of(candidate)
                if max_depth is not None and depth > max_depth:
                    continue
                modified = ""
                if row.updated_at is not None:
                    with contextlib.suppress(Exception):
                        modified = row.updated_at.astimezone(UTC).isoformat()
                if not _add_entry(
                    {
                        "path": candidate,
                        "is_dir": False,
                        "size": 0,
                        "modified_at": modified,
                        "depth": depth,
                    }
                ):
                    return {"entries": entries, "truncated": True}

            if anon_path and _is_under(anon_path, normalized):
                depth = _depth_of(anon_path)
                if (max_depth is None or depth <= max_depth) and not _add_entry(
                    {
                        "path": anon_path,
                        "is_dir": False,
                        "size": len(str(anon.get("content") or "")),
                        "modified_at": "",
                        "depth": depth,
                    }
                ):
                    return {"entries": entries, "truncated": True}

            for path_key, fd in files.items():
                if not isinstance(path_key, str):
                    continue
                if not _is_under(path_key, normalized):
                    continue
                if path_key in moved_removed or self._is_dir_suppressed(
                    path_key, deleted_dirs
                ):
                    continue
                if any(e["path"] == path_key for e in entries):
                    continue
                if not (
                    path_key.startswith(DOCUMENTS_ROOT)
                    or _basename(path_key).startswith(_TEMP_PREFIX)
                ):
                    continue
                depth = _depth_of(path_key)
                if max_depth is not None and depth > max_depth:
                    continue
                size = self._file_data_size(fd) if isinstance(fd, dict) else 0
                if not _add_entry(
                    {
                        "path": path_key,
                        "is_dir": False,
                        "size": int(size),
                        "modified_at": fd.get("modified_at", "")
                        if isinstance(fd, dict)
                        else "",
                        "depth": depth,
                    }
                ):
                    return {"entries": entries, "truncated": True}

        return {"entries": entries, "truncated": truncated}
