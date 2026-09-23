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
import logging

from deepagents.backends.protocol import (
    EditResult,
    WriteResult,
)
from deepagents.backends.utils import (
    create_file_data,
    file_data_to_string,
    perform_string_replacement,
    update_file_data,
)

logger = logging.getLogger(__name__)


class WritesMixin:
    # ------------------------------------------------------------------ writes

    async def awrite(self, file_path: str, content: str) -> WriteResult:  # type: ignore[override]
        files = self._state_files()
        if file_path in files:
            return WriteResult(
                error=(
                    f"Cannot write to {file_path} because it already exists. "
                    "Read and then make an edit, or write to a new path."
                )
            )
        new_file_data = create_file_data(content)
        return WriteResult(path=file_path, files_update={file_path: new_file_data})

    def write(self, file_path: str, content: str) -> WriteResult:  # type: ignore[override]
        return asyncio.run(self.awrite(file_path, content))

    async def aedit(  # type: ignore[override]
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        files = self._state_files()
        file_data = files.get(file_path)
        if file_data is None:
            loaded = await self._load_file_data(file_path)
            if loaded is None:
                return EditResult(error=f"Error: File '{file_path}' not found")
            file_data, _ = loaded

        content = file_data_to_string(file_data)
        result = perform_string_replacement(
            content, old_string, new_string, replace_all
        )
        if isinstance(result, str):
            return EditResult(error=result)

        new_content, occurrences = result
        new_file_data = update_file_data(file_data, new_content)
        return EditResult(
            path=file_path,
            files_update={file_path: new_file_data},
            occurrences=int(occurrences),
        )

    def edit(  # type: ignore[override]
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        return asyncio.run(self.aedit(file_path, old_string, new_string, replace_all))
