"""Production chat query sampler + PII redaction + case tagging.

This module is intentionally read-only: it queries ``NewChatMessage`` and
writes no rows. It is meant to be run against a read-replica or sanitized
backup by an operator with a valid admin personal access token.

ponytail: the tag heuristics are lightweight and best-effort. There is no
column for ``mentioned_document_ids`` on ``NewChatThread``; we infer the
``document`` tag from knowledge-base tool calls in the same turn and extract
any ``document_id`` values from tool-call ``args``.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    AgentActionLog,
    NewChatMessage,
    NewChatMessageRole,
    NewChatThread,
    Workspace,
)

logger = logging.getLogger(__name__)

# Redaction is ordered: SSN -> CC -> phone -> email. The earlier, more specific
# patterns run first so that dashed numeric strings are classified correctly.
_PII_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\b(?:\d{3}-\d{2}-\d{4}|\d{3}\.\d{2}\.\d{4}|\d{3}\s\d{2}\s\d{4})\b"
        ),
        "<SSN>",
    ),
    (
        re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b|\b\d{13,16}\b"),
        "<CC>",
    ),
    (
        re.compile(
            r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?){1,2}\d{4}\b"
            r"|"
            r"\b(?:\+?84|0)\d[\s.-]?\d{3}[\s.-]?\d{3,5}\b"
        ),
        "<PHONE>",
    ),
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        "<EMAIL>",
    ),
]

_MEMORY_KEYWORDS = {"we", "our", "team", "remember", "memory"}
_CREATIVE_KEYWORDS = {"draft", "summarize", "write", "create"}
_DOCUMENT_TOOLS = {
    "search_knowledge_base",
    "get_document",
    "read_document",
    "search_documents",
}
_DEEP_RESEARCH_TOOLS = {"chainlens.research", "deep_research", "research"}
_MULTI_TOOL_THRESHOLD = 2


def redact_pii(text: str) -> str:
    """Replace email, phone, SSN and credit-card patterns with placeholders."""
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _extract_text(content: Any) -> str:
    """Best-effort extraction of user text from assistant-ui JSONB content."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(part.get("text", ""))
            elif isinstance(part, str):
                parts.append(part)
        return " ".join(parts)
    return str(content or "")


def _hash_workspace(name: str, salt: str) -> str:
    """Stable hash of a workspace name used in exported dataset rows."""
    digest = hashlib.sha256(f"{salt}:{name}".encode()).hexdigest()[:16]
    return f"w-{digest}"


def _classify_tags(
    query: str, tool_names: list[str], mentioned_doc_ids: list[int]
) -> list[str]:
    """Assign case tags from the query text and tool calls of a turn."""
    words = set(re.findall(r"\b\w+\b", query.lower()))
    tags: set[str] = set()

    if _MEMORY_KEYWORDS & words:
        tags.add("memory")
    if _CREATIVE_KEYWORDS & words:
        tags.add("creative")

    tnames = {t.lower() for t in tool_names if t}
    if tnames & _DOCUMENT_TOOLS or mentioned_doc_ids:
        tags.add("document")
    if tnames & _DEEP_RESEARCH_TOOLS:
        tags.add("deep-research")
    if len(tnames) >= _MULTI_TOOL_THRESHOLD:
        tags.add("multi-tool")

    if not tags:
        tags.add("factual")

    # Deterministic order matching the AC listing.
    order = ["memory", "document", "deep-research", "multi-tool", "creative", "factual"]
    return [t for t in order if t in tags]


def _extract_document_ids(args: Any) -> list[int]:
    """Pull document ids from tool-call args when available."""
    if not isinstance(args, dict):
        return []

    ids: list[int] = []
    for key in ("document_id", "document_ids", "mentioned_document_ids"):
        value = args.get(key)
        if isinstance(value, int):
            ids.append(value)
        elif isinstance(value, list):
            ids.extend(v for v in value if isinstance(v, int))
    return ids


async def sample_chat_queries(
    session: AsyncSession,
    *,
    days: int = 30,
    max_queries: int | None = None,
    salt: str,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Sample recent user chat queries, redact PII, tag and anonymize.

    The function never writes to the database.
    """
    cutoff = datetime.now(UTC) - timedelta(days=days)

    stmt = (
        select(NewChatMessage, NewChatThread, Workspace)
        .join(NewChatThread, NewChatMessage.thread_id == NewChatThread.id)
        .join(Workspace, NewChatThread.workspace_id == Workspace.id)
        .where(NewChatMessage.role == NewChatMessageRole.USER)
        .where(NewChatMessage.created_at >= cutoff)
        .order_by(func.random())
    )
    if max_queries:
        stmt = stmt.limit(max_queries)

    rows = (await session.execute(stmt)).all()

    # Gather the threads/turns we need action logs for.
    thread_ids: set[int] = set()
    turn_ids: set[str] = set()
    for msg, _, _ in rows:
        thread_ids.add(msg.thread_id)
        if msg.turn_id:
            turn_ids.add(msg.turn_id)

    action_stmt = select(AgentActionLog).where(AgentActionLog.thread_id.in_(thread_ids))
    if turn_ids:
        action_stmt = action_stmt.where(
            (AgentActionLog.chat_turn_id.in_(turn_ids))
            | (AgentActionLog.chat_turn_id.is_(None))
        )
    action_rows = (await session.execute(action_stmt)).scalars().all()

    actions_by_key: dict[tuple[int, str | None], list[AgentActionLog]] = {}
    for log in action_rows:
        key = (log.thread_id, log.chat_turn_id)
        actions_by_key.setdefault(key, []).append(log)

    results: list[dict[str, Any]] = []
    for msg, _thread, workspace in rows:
        query_text = redact_pii(_extract_text(msg.content))
        if not query_text.strip():
            continue

        key = (msg.thread_id, msg.turn_id)
        actions = actions_by_key.get(key, [])
        if not actions and msg.turn_id:
            # Some legacy action logs may not record a chat_turn_id; fall back
            # to thread-level logs for this turn.
            actions = actions_by_key.get((msg.thread_id, None), [])

        tool_names = [log.tool_name for log in actions]
        mentioned_doc_ids: list[int] = []
        for log in actions:
            mentioned_doc_ids.extend(_extract_document_ids(log.args))
        # Deduplicate while preserving order.
        mentioned_doc_ids = list(dict.fromkeys(mentioned_doc_ids))

        tags = _classify_tags(query_text, tool_names, mentioned_doc_ids)

        if dry_run:
            continue

        results.append(
            {
                "case_id": f"prod-{msg.id}",
                "query": query_text,
                "tags": tags,
                "mentioned_document_ids": mentioned_doc_ids,
                "disabled_tools": [],
                "workspace_id_hash": _hash_workspace(workspace.name, salt),
            }
        )

    if dry_run:
        logger.info("Dry run: would sample %d queries", len(results))

    return results
