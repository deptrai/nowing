"""Memory injection middleware for the Nowing agent (Story 3.14).

Injects a bounded, search-ranked memory block into the system prompt on
every turn:
- Private threads: only personal memory (``<user_memory>``)
- Shared threads: only team memory (``<team_memory>``)

See the story's D2/D4/D8 design decisions for the exact contract: a fixed
bounded recent-transcript query (D2), the private-owner guard and transcript
normalization rules (D4), and the single-attempt failure telemetry
precedence (D8).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.runtime import Runtime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.shared.middleware.compaction import PROTECTED_SYSTEM_PREFIXES
from app.config import config
from app.db import ChatVisibility, shielded_async_session
from app.observability.metrics import record_memory_injection_failure
from app.services.memory.renderer import (
    MemoryRenderError,
    render_bounded_memory_injection,
)
from app.services.memory.search import MemoryHybridSearch, ScoredMemory
from app.services.memory.vector import (
    VectorValidationError,
    validate_embedding_vector,
    validate_single_embedding_result,
)
from app.utils.document_converters import embed_texts

logger = logging.getLogger(__name__)

#: D2: fixed constants for the bounded-injection hot path — module-local,
#: never configurable via env/config.
_MEMORY_INJECTION_TOP_K = 5
_MEMORY_QUERY_MAX_CHARS = 4_000
_MEMORY_INJECTION_MAX_CHARS = 8_000
#: D4: distinct from the renderer's ``_TRUNCATION_MARKER`` (no trailing
#: space) — this one carries a trailing space to separate it from the tail.
_QUERY_TRUNCATION_MARKER = "[...truncated...] "

_ROLE_FOR_MESSAGE_TYPE: dict[type, str] = {
    HumanMessage: "human",
    AIMessage: "assistant",
    SystemMessage: "system",
    ToolMessage: "tool",
}


def _role_for(message: Any) -> str | None:
    """D4 role mapping; subclasses inherit, unknown types are skipped."""
    for cls, role in _ROLE_FOR_MESSAGE_TYPE.items():
        if isinstance(message, cls):
            return role
    return None


def _normalize_text(message: Any) -> str:
    """D4: ``str.splitlines()`` is the source of truth for all newline variants."""
    return "\n".join(str(message.text).splitlines()).strip()


def _is_protected(normalized: str) -> bool:
    stripped = normalized.lstrip()
    return any(stripped.startswith(prefix) for prefix in PROTECTED_SYSTEM_PREFIXES)


def _usable_records(messages: list[Any]) -> list[tuple[str, str]]:
    """Newest-first ``(role, text)`` pairs; skips unusable messages silently."""
    records: list[tuple[str, str]] = []
    for message in reversed(messages):
        role = _role_for(message)
        if role is None:
            continue
        normalized = _normalize_text(message)
        if not normalized:
            continue
        if isinstance(message, SystemMessage) and _is_protected(normalized):
            continue
        records.append((role, normalized))
    return records


def _build_transcript_query(messages: list[Any]) -> str | None:
    """D4: bounded recent-transcript query, newest-to-oldest windowed.

    Returns ``None`` when the transcript has nothing usable at all (no
    recency fallback).
    """
    records = _usable_records(messages)
    if not records:
        return None

    separator = "\n\n"
    budget = _MEMORY_QUERY_MAX_CHARS
    selected: list[str] = []
    used = 0

    for role, text in records:
        rendered = f"{role}: {text}"
        sep_len = len(separator) if selected else 0
        if used + sep_len + len(rendered) <= budget:
            selected.append(rendered)
            used += sep_len + len(rendered)
            continue

        prefix = f"{role}: "
        remaining = budget - used - sep_len - len(prefix)
        if remaining >= len(_QUERY_TRUNCATION_MARKER) + 1:
            tail_budget = remaining - len(_QUERY_TRUNCATION_MARKER)
            tail = text[-tail_budget:] if tail_budget > 0 else ""
            selected.append(prefix + _QUERY_TRUNCATION_MARKER + tail)
        break

    if not selected:
        return None
    return separator.join(reversed(selected))


class MemoryInjectionMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """Injects a bounded, search-ranked memory block on every turn."""

    tools = ()

    def __init__(
        self,
        *,
        user_id: str | UUID | None,
        workspace_id: int,
        thread_visibility: ChatVisibility | None = None,
    ) -> None:
        self.user_id = UUID(user_id) if isinstance(user_id, str) else user_id
        self.workspace_id = workspace_id
        self.visibility = thread_visibility or ChatVisibility.PRIVATE

    async def abefore_agent(  # type: ignore[override]
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        del runtime
        messages = state.get("messages") or []
        if not messages:
            return None

        is_team = self.visibility == ChatVisibility.SEARCH_SPACE
        scope = "team" if is_team else "user"

        # D4 earliest-possible guard: team bypasses this guard entirely.
        if not is_team and self.user_id is None:
            return None

        if not isinstance(messages[-1], HumanMessage):
            return None

        query = _build_transcript_query(messages)
        if query is None:
            return None

        try:
            embedding = await self._embed_query(query)
        except VectorValidationError as exc:
            record_memory_injection_failure(
                scope=scope, stage="embedding", reason=exc.reason
            )
            return None

        cm = shielded_async_session()
        try:
            session = await cm.__aenter__()
        except Exception:
            record_memory_injection_failure(
                scope=scope, stage="session", reason="enter_error"
            )
            return None

        terminal = False
        pending: tuple[str, str] | None = None
        hits: list[ScoredMemory] = []
        display_name: str | None = None
        try:
            try:
                hits = await self._run_search(
                    session, scope=scope, query=query, embedding=embedding
                )
            except Exception:
                record_memory_injection_failure(
                    scope=scope, stage="search", reason="query_error"
                )
                terminal = True

            if not terminal and not is_team:
                try:
                    async with session.begin_nested():
                        display_name = await self._lookup_display_name(session)
                except Exception:
                    pending = ("display_name", "lookup_error")
        finally:
            try:
                await cm.__aexit__(None, None, None)
            except Exception:
                if not terminal:
                    record_memory_injection_failure(
                        scope=scope, stage="session", reason="exit_error"
                    )
                    terminal = True
                    pending = None

        if terminal:
            return None

        if not hits and not display_name:
            if pending is not None:
                record_memory_injection_failure(
                    scope=scope, stage=pending[0], reason=pending[1]
                )
            return None

        try:
            rendered = render_bounded_memory_injection(
                hits,
                scope=scope,
                display_name=None if is_team else display_name,
                max_chars=_MEMORY_INJECTION_MAX_CHARS,
            )
        except MemoryRenderError as exc:
            record_memory_injection_failure(
                scope=scope, stage="render", reason=exc.reason
            )
            return None

        if rendered is None:
            if pending is not None:
                record_memory_injection_failure(
                    scope=scope, stage=pending[0], reason=pending[1]
                )
            return None

        if pending is not None:
            record_memory_injection_failure(
                scope=scope, stage=pending[0], reason=pending[1]
            )

        new_messages = list(messages)
        insert_idx = 1 if len(new_messages) > 1 else 0
        new_messages.insert(insert_idx, SystemMessage(content=rendered))
        return {"messages": new_messages}

    async def _embed_query(self, query: str) -> Any:
        try:
            embeddings = await asyncio.to_thread(embed_texts, [query])
        except Exception as exc:
            raise VectorValidationError("provider_error") from exc
        embedding = validate_single_embedding_result(embeddings)
        return validate_embedding_vector(
            embedding, dimension=config.embedding_model_instance.dimension
        )

    async def _run_search(
        self,
        session: AsyncSession,
        *,
        scope: str,
        query: str,
        embedding: Any,
    ) -> list[ScoredMemory]:
        search = MemoryHybridSearch(session)
        if scope == "team":
            return await search.search(
                workspace_id=self.workspace_id,
                query=query,
                query_embedding=embedding,
                top_k=_MEMORY_INJECTION_TOP_K,
            )
        return await search.search(
            user_id=self.user_id,
            query=query,
            query_embedding=embedding,
            top_k=_MEMORY_INJECTION_TOP_K,
        )

    async def _lookup_display_name(self, session: AsyncSession) -> str | None:
        from app.db import User

        result = await session.execute(
            select(User.display_name).where(User.id == self.user_id)
        )
        return result.scalar_one_or_none()
