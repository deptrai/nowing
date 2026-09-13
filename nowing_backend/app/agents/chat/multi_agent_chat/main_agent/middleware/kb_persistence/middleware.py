"""End-of-turn KB persistence middleware (main-agent only).

Defines :class:`KnowledgeBasePersistenceMiddleware` and re-exports
``commit_staged_filesystem_state``.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langgraph.config import get_config
from langgraph.runtime import Runtime

from app.agents.chat.multi_agent_chat.main_agent.middleware.kb_persistence._commit import (
    commit_staged_filesystem_state,
)
from app.agents.chat.multi_agent_chat.main_agent.middleware.kb_persistence._helpers import (
    _apply_move,
    _basename,
    _create_document,
    _dispatch_reversibility_update,
    _doc_revision_payload,
    _ensure_folder_hierarchy,
    _find_action_ids_batch,
    _load_chunks_for_snapshot,
    _mark_action_reversible,
    _resolve_folder_id,
    _snapshot_document_pre_create,
    _snapshot_document_pre_move,
    _snapshot_document_pre_write,
    _snapshot_folder_pre_mkdir,
    _split_folder_path,
    _update_document,
)
from app.agents.chat.multi_agent_chat.shared.filesystem_selection import FilesystemMode
from app.agents.chat.multi_agent_chat.shared.state.filesystem_state import (
    NowingFilesystemState,
)

logger = logging.getLogger(__name__)


class KnowledgeBasePersistenceMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """End-of-turn cloud persistence for the Nowing filesystem agent."""

    tools = ()
    state_schema = NowingFilesystemState

    def __init__(
        self,
        *,
        workspace_id: int,
        created_by_id: str | None,
        filesystem_mode: FilesystemMode,
        thread_id: int | None = None,
    ) -> None:
        self.workspace_id = workspace_id
        self.created_by_id = created_by_id
        self.filesystem_mode = filesystem_mode
        self.thread_id = thread_id

    async def aafter_agent(  # type: ignore[override]
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        del runtime
        if self.filesystem_mode != FilesystemMode.CLOUD:
            return None
        return await commit_staged_filesystem_state(
            state,
            workspace_id=self.workspace_id,
            created_by_id=self.created_by_id,
            filesystem_mode=self.filesystem_mode,
            thread_id=self._resolve_thread_id(),
        )

    def _resolve_thread_id(self) -> int | None:
        """Resolve the live thread id from the active ``RunnableConfig``.

        ``aafter_agent`` only receives a ``Runtime`` (which does NOT carry the
        config), so we read ``configurable.thread_id`` via
        :func:`langgraph.config.get_config` — the same node-context pattern used
        by ``BusyMutexMiddleware``. Resolving at runtime (rather than using the
        value captured at ``__init__``) lets one cached compiled graph commit
        staged writes against the correct thread across many chats. Falls back
        to the constructor value for legacy/test runtimes.
        """
        try:
            config = get_config()
        except Exception:  # LangGraph config resolution failure; fall back to constructor thread_id
            config = None
        if isinstance(config, dict):
            value = (config.get("configurable") or {}).get("thread_id")
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None
        return self.thread_id


__all__ = [
    "KnowledgeBasePersistenceMiddleware",
    "_apply_move",
    "_basename",
    "_create_document",
    "_dispatch_reversibility_update",
    "_doc_revision_payload",
    "_ensure_folder_hierarchy",
    "_find_action_ids_batch",
    "_load_chunks_for_snapshot",
    "_mark_action_reversible",
    "_resolve_folder_id",
    "_snapshot_document_pre_create",
    "_snapshot_document_pre_move",
    "_snapshot_document_pre_write",
    "_snapshot_folder_pre_mkdir",
    "_split_folder_path",
    "_update_document",
    "commit_staged_filesystem_state",
]
