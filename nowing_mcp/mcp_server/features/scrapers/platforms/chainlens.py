"""ChainLens Research scraper tool."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ....core.client import NowingClient
from ....core.rendering import ResponseFormatParam
from ....core.workspace_context import WorkspaceContext, WorkspaceParam
from ..annotations import SCRAPE
from ..capability import run_scraper


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register the ChainLens Research tool."""

    @mcp.tool(
        name="nowing_chainlens_research",
        title="ChainLens Research",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def chainlens_research(
        query: Annotated[
            str,
            Field(
                min_length=1,
                max_length=500,
                description="The research question or topic to investigate.",
            ),
        ],
        mode: Annotated[
            Literal["speed", "balanced", "quality", "auto"],
            Field(
                description="Research depth: speed (fast), balanced, or quality (thorough)."
            ),
        ] = "quality",
        sources: Annotated[
            list[Literal["web", "discussions", "academic"]],
            Field(
                min_length=1,
                description="Source categories to search.",
            ),
        ] = ["web", "academic"],
        system_instructions: Annotated[
            str | None,
            Field(
                max_length=2000,
                description="Optional instructions for the synthesis writer, e.g. language or format.",
            ),
        ] = None,
        chat_id: Annotated[
            str | None,
            Field(description="Optional ChainLens chat session handle for continuity."),
        ] = None,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Run a ChainLens Research query and get a synthesized answer with cited sources.

        Use this for literature reviews, due diligence, and deep factual Q&A
        across web and academic sources. Returns a synthesized answer plus a
        list of grounding sources. To continue an existing research thread,
        pass the chat_id returned by a previous call.
        Example: query='latest advances in retrieval-augmented generation 2026'.
        """
        return await run_scraper(
            client,
            context,
            platform="chainlens",
            verb="research",
            payload={
                "query": query,
                "mode": mode,
                "sources": sources,
                "system_instructions": system_instructions,
                "chat_id": chat_id,
            },
            workspace=workspace,
            response_format=response_format,
        )
