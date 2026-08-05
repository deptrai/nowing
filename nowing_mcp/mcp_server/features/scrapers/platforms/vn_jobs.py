"""Vietnam job market aggregate tool."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ....core.client import NowingClient
from ....core.rendering import ResponseFormatParam
from ....core.workspace_context import WorkspaceContext, WorkspaceParam
from ..annotations import SCRAPE
from ..capability import run_scraper

EmploymentType = Literal["full_time", "contract", "part_time", "intern"]


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
    """Register the Vietnam job market aggregate tool."""

    @mcp.tool(
        name="nowing_vn_jobs_aggregate",
        title="Aggregate Vietnamese job postings from multiple sources",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def vn_jobs_aggregate(
        keyword: Annotated[str, Field(description="Job keyword, e.g. 'data engineer'.")],
        location: Annotated[
            str | None,
            Field(description="Optional city or province name, e.g. 'Hà Nội'."),
        ] = None,
        salary_min: Annotated[
            int | None,
            Field(description="Optional minimum monthly salary in VND."),
        ] = None,
        salary_max: Annotated[
            int | None,
            Field(description="Optional maximum monthly salary in VND."),
        ] = None,
        employment_type: Annotated[
            EmploymentType | None,
            Field(description="Optional employment type filter."),
        ] = None,
        experience_years: Annotated[
            int | None,
            Field(description="Optional minimum years of experience."),
        ] = None,
        sources: Annotated[
            list[str],
            Field(
                description="Sources to aggregate. Defaults to all: vietnamworks, topcv, itviec."
            ),
        ] = None,
        max_items_per_source: Annotated[
            int,
            Field(ge=0, le=100, description="Maximum job listings to fetch per source."),
        ] = 50,
        max_pages: Annotated[
            int,
            Field(ge=0, le=20, description="Maximum pages to fetch per source."),
        ] = 5,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Aggregate and compare Vietnamese job postings from multiple sources.

        Use this to cross-source salary, location, and skills for Vietnamese
        job market research. Returns deduplicated listings with a cross-source
        confidence score and salary-conflict flags.
        Example: keyword='data engineer', location='Hà Nội', max_items_per_source=20.
        """
        payload: dict[str, Any] = {
            "keyword": keyword,
            "location": location,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "employment_type": employment_type,
            "experience_years": experience_years,
            "max_items_per_source": max_items_per_source,
            "max_pages": max_pages,
        }
        if sources:
            payload["sources"] = sources

        return await run_scraper(
            client,
            context,
            platform="vn_jobs",
            verb="aggregate",
            payload=payload,
            workspace=workspace,
            response_format=response_format,
        )
