"""VietnamWorks scraper tool."""

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
    """Register the VietnamWorks tool."""

    @mcp.tool(
        name="nowing_vietnamworks_scrape",
        title="Scrape Vietnamese job postings from VietnamWorks",
        annotations=SCRAPE,
        structured_output=False,
    )
    async def vietnamworks_scrape(
        keyword: Annotated[str, Field(description="Job keyword, e.g. 'data engineer'.")],
        location: Annotated[
            str | None,
            Field(description="Optional city or province name, e.g. 'Hà Nội'.",),
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
        max_pages: Annotated[
            int, Field(ge=0, le=20, description="Maximum result pages to fetch.")
        ] = 5,
        max_items: Annotated[
            int, Field(ge=0, le=100, description="Maximum job listings to return.")
        ] = 50,
        workspace: WorkspaceParam = None,
        response_format: ResponseFormatParam = "markdown",
    ) -> str:
        """Search public VietnamWorks job postings.

        Use this for Vietnamese job market research: salary benchmarks, hiring
        trends, skill demand, and supply by location. Returns typed listings
        with title, company, location, salary, employment type, experience,
        skills, post date, and detail URL.
        Example: keyword='data engineer', location='Hà Nội', max_items=20.
        """
        payload: dict[str, Any] = {
            "keyword": keyword,
            "location": location,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "employment_type": employment_type,
            "experience_years": experience_years,
            "max_pages": max_pages,
            "max_items": max_items,
        }
        return await run_scraper(
            client,
            context,
            platform="vietnamworks",
            verb="scrape",
            payload=payload,
            workspace=workspace,
            response_format=response_format,
        )
