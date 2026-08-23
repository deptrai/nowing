"""Aggregate a research thread's prior citations from its chat history.

Citations are not stored in a table; they live inline in assistant message
content as ``[citation:<payload>]`` markers, rewritten from the model's bare
``[n]`` ordinals during finalization (see
``app/tasks/chat/streaming/flows/shared/assistant_finalize.py``). To reconstruct
"the previous citations of a research thread" for research-continuity recall
(FR-33 / Story 4.6), we walk the assistant messages of every chat thread linked
to the ``ResearchThread``, parse the markers with the canonical citation parser,
deduplicate, and cap at a sane limit.

Isolation (AC-4): the query is scoped to chat threads that belong to *both* the
``ResearchThread`` and its workspace, so a marker can never leak across threads
or workspaces. Malformed markers are skipped by the parser rather than raising.

MVP source-of-truth decision (FR-33 [DECISION], resolved as URL-only): a web-URL
marker yields a citation with a resolvable ``url``; a knowledge-base chunk marker
has no persisted URL/label to render, so we surface it with a minimal label and
``url=None`` rather than enriching it from the (non-persisted) CitationRegistry.
"""

from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat.shared.citations import (
    ChunkCitationMarker,
    RunCitationMarker,
    UrlCitationMarker,
    parse_citation_markers,
)
from app.db import NewChatMessage, NewChatMessageRole, NewChatThread, ResearchThread
from app.schemas.memory import ThreadCitation

# Cap the number of distinct citations returned so a long-lived thread cannot
# produce an unbounded payload. Aggregation stops once the cap is reached.
DEFAULT_CITATION_LIMIT = 50


def _iter_text_parts(content: object) -> list[str]:
    """Yield the ``text`` of every text part in a JSONB message ``content`` list.

    Tolerates the many shapes persisted over time (a list of part dicts, or a
    bare string) and ignores non-text parts and malformed entries.
    """
    if isinstance(content, str):
        return [content]
    if isinstance(content, dict):
        # Some legacy rows persist a single part dict rather than a list.
        content = [content]
    if not isinstance(content, list):
        return []
    texts: list[str] = []
    for part in content:
        if (
            isinstance(part, dict)
            and part.get("type") == "text"
            and isinstance(part.get("text"), str)
        ):
            texts.append(part["text"])
    return texts


def _url_label(url: str) -> str:
    """Human-readable label for a URL citation: its host, else the raw URL."""
    try:
        netloc = urlparse(url).netloc
    except ValueError:
        netloc = ""
    return netloc or url


def _normalize_url(url: str) -> str:
    """Dedup key for a URL: lowercase scheme+host and drop a trailing slash so
    trivially different spellings of the same page collapse to one citation
    (e.g. ``…/p`` vs ``…/p/`` vs a differently-cased host). Query is preserved
    (it can be semantically significant); fragment is dropped."""
    try:
        parts = urlparse(url)
    except ValueError:
        return url.strip()
    if not parts.scheme or not parts.netloc:
        return url.strip()
    path = parts.path.rstrip("/")
    normalized = f"{parts.scheme.lower()}://{parts.netloc.lower()}{path}"
    if parts.query:
        normalized = f"{normalized}?{parts.query}"
    return normalized


def _marker_to_citation(
    marker: UrlCitationMarker | ChunkCitationMarker | RunCitationMarker,
) -> tuple[str, ThreadCitation]:
    """Map a parsed marker to a dedup key and its normalized ``ThreadCitation``."""
    if isinstance(marker, UrlCitationMarker):
        key = f"url:{_normalize_url(marker.url)}"
        return key, ThreadCitation(
            label=_url_label(marker.url),
            url=marker.url,
            source_type="url",
        )
    if isinstance(marker, RunCitationMarker):
        return f"run:{marker.run_id}", ThreadCitation(
            label=marker.run_id,
            url=None,
            source_type="run",
        )
    prefix = "doc-" if marker.is_docs_chunk else "chunk "
    source_type = "kb_document" if marker.is_docs_chunk else "kb_chunk"
    key = f"chunk:{'doc' if marker.is_docs_chunk else 'raw'}:{marker.chunk_id}"
    return key, ThreadCitation(
        label=f"{prefix}{marker.chunk_id}",
        url=None,
        source_type=source_type,
    )


async def collect_thread_citations(
    session: AsyncSession,
    research_thread: ResearchThread,
    *,
    limit: int = DEFAULT_CITATION_LIMIT,
) -> list[ThreadCitation]:
    """Return the deduplicated, capped citations of ``research_thread``.

    Scoped strictly to assistant messages of chat threads that belong to the
    thread *and* its workspace (AC-4 isolation). Ordered by recency of message,
    then by first appearance within a message. Never raises on malformed markers.
    """
    # AC-4 isolation: scope to the research thread's tenant (workspace + client).
    # Mirrors MemoryHybridSearch's client_id scoping so vertical-client contexts
    # only see citations from the same client.
    thread_client_id = research_thread.client_id or None
    stmt = (
        select(NewChatMessage.content)
        .join(NewChatThread, NewChatMessage.thread_id == NewChatThread.id)
        .where(
            NewChatThread.research_thread_id == research_thread.id,
            NewChatThread.workspace_id == research_thread.workspace_id,
            NewChatThread.client_id == thread_client_id,
            NewChatMessage.role == NewChatMessageRole.ASSISTANT,
        )
        .order_by(NewChatMessage.created_at.desc(), NewChatMessage.id.desc())
    )
    result = await session.execute(stmt)

    seen: set[str] = set()
    citations: list[ThreadCitation] = []
    for (content,) in result:
        for text in _iter_text_parts(content):
            for marker in parse_citation_markers(text):
                key, citation = _marker_to_citation(marker)
                if key in seen:
                    continue
                seen.add(key)
                citations.append(citation)
                if len(citations) >= limit:
                    return citations
    return citations


__all__ = ["DEFAULT_CITATION_LIMIT", "collect_thread_citations"]
