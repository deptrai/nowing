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
from typing import Any

from deepagents.backends.protocol import (
    BackendProtocol,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.utils import (
    file_data_to_string,
)
from langchain.tools import ToolRuntime

from app.agents.chat.runtime.path_resolver import (
    DOCUMENTS_ROOT,
)

from ._helpers import _is_under
from .reads import ReadsMixin
from .search import SearchMixin
from .tree import TreeMixin
from .writes import WritesMixin

logger = logging.getLogger(__name__)


class KBPostgresBackend(
    ReadsMixin, WritesMixin, SearchMixin, TreeMixin, BackendProtocol
):
    """Lazy, read-only Postgres view for ``/documents/*`` virtual paths.

    The backend exposes a virtual ``/documents/`` namespace mirroring the
    ``Folder``/``Document`` graph. Reads materialize XML on first access and
    cache it via the overriding tool wrappers (NOT here). Writes never touch
    the DB — they return ``files_update`` deltas that the wrappers turn into
    Command updates, and the persistence middleware commits them at end of
    turn.
    """

    _IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp"})

    def __init__(self, workspace_id: int, runtime: ToolRuntime) -> None:
        self.workspace_id = workspace_id
        self.runtime = runtime

    @property
    def state(self) -> dict[str, Any]:
        return getattr(self.runtime, "state", {}) or {}

    # ------------------------------------------------------------------ helpers

    def _state_files(self) -> dict[str, Any]:
        return dict(self.state.get("files") or {})

    def _staged_dirs(self) -> list[str]:
        return list(self.state.get("staged_dirs") or [])

    def _pending_moves(self) -> list[dict[str, Any]]:
        return list(self.state.get("pending_moves") or [])

    def _pending_deletes(self) -> list[dict[str, Any]]:
        return list(self.state.get("pending_deletes") or [])

    def _pending_dir_deletes(self) -> list[dict[str, Any]]:
        return list(self.state.get("pending_dir_deletes") or [])

    def _kb_anon_doc(self) -> dict[str, Any] | None:
        anon = self.state.get("kb_anon_doc")
        return anon if isinstance(anon, dict) else None

    @staticmethod
    def _file_data_size(file_data: dict[str, Any]) -> int:
        try:
            return len("\n".join(file_data.get("content") or []))
        except Exception:  # malformed file data in DB; fall back to size 0
            return 0

    def _normalize_listing_path(self, path: str) -> str:
        if not path:
            return DOCUMENTS_ROOT
        if path == "/":
            return path
        return path.rstrip("/") if path != "/" else path

    def _pending_filesystem_view(
        self,
        existing: dict[str, dict[str, Any]],
    ) -> tuple[set[str], dict[str, str], set[str]]:
        """Compute removed/aliased/dir-suppressed paths from staged ops.

        Returns ``(removed, alias, deleted_dirs)`` where:

        * ``removed`` — paths to drop from listings (sources of pending moves
          AND paths queued for ``rm``).
        * ``alias`` — ``{source: dest}`` for pending moves; the dest should
          appear as a virtual entry even when no DB row is at that path yet.
        * ``deleted_dirs`` — folder paths queued for ``rmdir``; their entire
          subtree (descendants) is suppressed from listings/glob/grep.

        Entries in ``existing`` (the ``files`` state cache) keyed by a
        removed path are popped so a same-turn delete-after-write doesn't
        leave a stale virtual file in listings.
        """
        removed: set[str] = set()
        alias: dict[str, str] = {}
        deleted_dirs: set[str] = set()
        for move in self._pending_moves():
            src = move.get("source")
            dst = move.get("dest")
            if not src or not dst:
                continue
            removed.add(src)
            alias[src] = dst
            existing.pop(src, None)
        for entry in self._pending_deletes():
            path = entry.get("path") if isinstance(entry, dict) else None
            if not path:
                continue
            removed.add(path)
            existing.pop(path, None)
        for entry in self._pending_dir_deletes():
            path = entry.get("path") if isinstance(entry, dict) else None
            if not path:
                continue
            deleted_dirs.add(path)
        return removed, alias, deleted_dirs

    @staticmethod
    def _is_dir_suppressed(path: str, deleted_dirs: set[str]) -> bool:
        """Return True iff ``path`` is at-or-under any directory in ``deleted_dirs``."""
        return any(path == d or _is_under(path, d) for d in deleted_dirs)

    # ------------------------------------------------------------------ uploads (unsupported)

    def upload_files(  # type: ignore[override]
        self, files: list[tuple[str, bytes]]
    ) -> list[FileUploadResponse]:
        msg = "KBPostgresBackend does not support upload_files."
        raise NotImplementedError(msg)

    def download_files(  # type: ignore[override]
        self, paths: list[str]
    ) -> list[FileDownloadResponse]:
        responses: list[FileDownloadResponse] = []
        files = self._state_files()
        for path in paths:
            fd = files.get(path)
            if fd is None:
                responses.append(
                    FileDownloadResponse(
                        path=path, content=None, error="file_not_found"
                    )
                )
                continue
            content_str = file_data_to_string(fd)
            responses.append(
                FileDownloadResponse(
                    path=path,
                    content=content_str.encode("utf-8"),
                    error=None,
                )
            )
        return responses


# --- module-level small helpers ---------------------------------------------
