"""Memory tools: remember, recall, update facts, and continue research threads."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ...core.client import NowingClient
from ...core.errors import ToolError
from ...core.rendering import ResponseFormatParam, clip, to_json
from ...core.workspace_context import WorkspaceContext, WorkspaceParam
from .annotations import (
    READ,
    UPDATE,
    WRITE,
    MemoryId,
    MemoryTags,
    MemoryType,
    OptionalResearchThreadId,
    ResearchThreadId,
    TopK,
)


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register memory tools on the MCP server."""

    @mcp.tool(
        name="nowing_remember",
        title="Save a memory",
        annotations=WRITE,
        structured_output=False,
    )
    async def remember(
        content: Annotated[
            str,
            Field(min_length=1, description="The durable fact, decision, or preference to save."),
        ],
        type: MemoryType = "semantic",
        tags: MemoryTags = None,
        confidence: Annotated[
            float, Field(ge=0.0, le=1.0, description="Confidence in this memory.")
        ] = 1.0,
        source_type: Annotated[
            str,
            Field(description="Origin of the memory, e.g. 'manual' or 'chat_message'."),
        ] = "manual",
        source_id: Annotated[
            int | None,
            Field(description="Id of the source object, if any."),
        ] = None,
        research_thread_id: OptionalResearchThreadId = None,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Save a durable fact to the active workspace's long-term memory.

        Use this to preserve important context that later turns or agents will
        need, such as user preferences, key decisions, or discovered facts.
        Returns the saved memory id.
        """
        resolved = await context.resolve(workspace)
        payload = {
            "content": content,
            "type": type,
            "tags": tags or [],
            "confidence": confidence,
            "source_type": source_type,
            "source_id": source_id,
            "research_thread_id": research_thread_id,
        }
        memory = await client.request(
            "POST",
            f"/workspaces/{resolved.id}/memories",
            json=payload,
        )
        if response_format == "json":
            return to_json(memory)
        return _render_memory(memory, action="Saved")

    @mcp.tool(
        name="nowing_recall",
        title="Recall relevant memories",
        annotations=READ,
        structured_output=False,
    )
    async def recall(
        query: Annotated[
            str,
            Field(min_length=1, description="What to remember, e.g. 'pricing changes'."),
        ],
        top_k: TopK = 5,
        type: Annotated[
            str | None,
            Field(
                description="Memory type: semantic, episodic, procedural, or working. Omit for all types."
            ),
        ] = None,
        tags: MemoryTags = None,
        research_thread_id: OptionalResearchThreadId = None,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Retrieve the most relevant long-term memories for a query.

        Use this before answering a question that may depend on facts the user
        or assistant shared in earlier conversations.
        """
        resolved = await context.resolve(workspace)
        payload = {
            "query": query,
            "top_k": top_k,
            "type": type,
            "tags": tags or [],
            "research_thread_id": research_thread_id,
        }
        hits = await client.request(
            "POST",
            f"/workspaces/{resolved.id}/memories/search",
            json=payload,
        )
        items = (hits or {}).get("items", [])
        if response_format == "json":
            return to_json(items)
        return _render_recall(query, items)

    @mcp.tool(
        name="nowing_update_fact",
        title="Update a memory",
        annotations=UPDATE,
        structured_output=False,
    )
    async def update_fact(
        memory_id: MemoryId,
        corrected_content: Annotated[
            str,
            Field(min_length=1, description="The corrected or updated memory text."),
        ],
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Correct an existing memory while preserving its previous version."""
        memory = await client.request(
            "PATCH",
            f"/memories/{memory_id}",
            json={"corrected_content": corrected_content},
        )
        if response_format == "json":
            return to_json(memory)
        return _render_memory(memory, action="Updated")

    @mcp.tool(
        name="nowing_continue_research",
        title="Continue a research thread",
        annotations=READ,
        structured_output=False,
    )
    async def continue_research(
        research_thread_id: ResearchThreadId,
        query: Annotated[
            str,
            Field(
                description="Optional query to rank memories in the thread; "
                "empty returns the most recent thread context."
            ),
        ] = "",
        top_k: TopK = 5,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Resume a research thread with its prior memories and citations.

        Use this when the user asks to continue a research topic. It scopes
        recall to the research thread (same ranking as nowing_recall) and also
        returns the thread's previously cited sources, so you can pick up prior
        work with both the facts and where they came from. Fails with a clear
        error if the thread does not exist — it never creates one.
        """
        resolved = await context.resolve(workspace)
        params = {
            "query": query or None,
            "top_k": top_k,
        }
        try:
            data = await client.request(
                "GET",
                f"/workspaces/{resolved.id}/research-threads/{research_thread_id}/context",
                params=params,
            )
        except ToolError as exc:
            if "not found" in str(exc).lower():
                raise ToolError(
                    f"Research thread {research_thread_id} not found in workspace "
                    f"'{resolved.name}'. It may not exist or belongs to another "
                    "workspace; no thread was created."
                ) from exc
            raise
        data = data or {}
        if response_format == "json":
            return to_json(data)
        return _render_continue(
            query or "research context",
            data.get("memories", []),
            data.get("citations", []),
        )


def _source_suffix(item: dict) -> str:
    """Render run provenance as a markdown suffix, or "" when there is none.

    Story 3.13 (D7/AC-3): the JSON surface carries ``source_type``/
    ``source_run_id``/``citation`` for free because it is an untyped
    pass-through, but markdown is hand-rendered and silently dropped all three.
    A model reading the markdown had no way to tell a scraped-run fact from a
    chat fact, let alone cite it — so the citation is rendered explicitly here.

    Only run-derived facts get a suffix: chat/manual/document memories have no
    ``citation`` and must render exactly as before (no regression).
    """
    citation = item.get("citation")
    if not citation:
        return ""
    return f" [source: {citation}]"


def _render_memory(memory: dict | None, action: str) -> str:
    if not memory:
        return f"{action} memory, but the response was empty."
    lines = [
        f"# {action} memory (id {memory.get('id')})",
        f"- type: {memory.get('type')}",
        f"- confidence: {memory.get('confidence', 1.0)}",
        f"- updated: {memory.get('updated_at')}",
    ]
    if memory.get("citation"):
        lines.append(f"- source: {memory.get('source_type')} ({memory.get('citation')})")
    lines.extend(["", clip(memory.get('content', '') or '(empty)')])
    if memory.get('previous_versions'):
        lines.append("")
        lines.append("_Previous versions preserved._")
    return "\n".join(lines).strip()


def _render_recall(query: str, items: list[dict]) -> str:
    if not items:
        return f'No memories found for "{query}".'
    lines = [f'# {len(items)} result(s) for "{query}"', ""]
    for rank, hit in enumerate(items, start=1):
        score = hit.get("score")
        similarity = hit.get("similarity")
        if score is None and similarity is None:
            meta = f"rank=recency, rrf=n/a, similarity=n/a"
        else:
            try:
                score_num = float(score)
                sim_num = float(similarity)
                meta = f"rrf={score_num:.6f}, similarity={sim_num:.6f}"
            except (TypeError, ValueError):
                meta = f"rank={rank}, rrf=n/a, similarity=n/a"
        lines.append(
            f"- **id {hit.get('id')}** ({hit.get('type')}, "
            f"confidence {hit.get('confidence', 1.0):.2f}, {meta}): "
            f"{clip(hit.get('content', '') or '(empty)', 500)}"
            f"{_source_suffix(hit)}"
        )
    return "\n".join(lines).strip()


def _render_continue(query: str, memories: list[dict], citations: list[dict]) -> str:
    """Render a research-thread continuity view: recalled memories + citations."""
    sections = [_render_recall(query, memories), _render_citations(citations)]
    return "\n\n".join(section for section in sections if section).strip()


def _render_citations(citations: list[dict]) -> str:
    if not citations:
        return "## Previous citations\n\n_No prior citations recorded for this thread._"
    lines = [f"## {len(citations)} previous citation(s)", ""]
    for citation in citations:
        label = citation.get("label") or citation.get("url") or "source"
        url = citation.get("url")
        lines.append(f"- [{label}]({url})" if url else f"- {label}")
    return "\n".join(lines).strip()
