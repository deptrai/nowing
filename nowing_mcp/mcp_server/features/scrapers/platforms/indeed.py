"""Indeed scraper tool."""

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
SortBy = Literal["relevance", "date"]


def register(mcp: FastMCP, client: NowingClient, context: WorkspaceContext) -> None:
	"""Register the Indeed tool."""

	@mcp.tool(
		name="nowing_indeed_scrape",
		title="Scrape job postings from Indeed",
		annotations=SCRAPE,
		structured_output=False,
	)
	async def indeed_scrape(
		keyword: Annotated[str, Field(description="Job keyword, e.g. 'data engineer'.")],
		location: Annotated[
			str | None,
			Field(description="Optional city, state, or country, e.g. 'Hanoi, Vietnam'."),
		] = None,
		radius: Annotated[
			int,
			Field(ge=0, le=100, description="Search radius in miles."),
		] = 25,
		sort: Annotated[
			SortBy,
			Field(description="Sort results by relevance or date."),
		] = "relevance",
		salary_min: Annotated[
			int | None,
			Field(description="Optional minimum annual salary in USD."),
		] = None,
		salary_max: Annotated[
			int | None,
			Field(description="Optional maximum annual salary in USD."),
		] = None,
		employment_type: Annotated[
			EmploymentType | None,
			Field(description="Optional employment type filter."),
		] = None,
		max_pages: Annotated[
			int, Field(ge=0, le=5, description="Maximum result pages to fetch.")
		] = 3,
		max_items: Annotated[
			int, Field(ge=0, le=100, description="Maximum job listings to return.")
		] = 50,
		workspace: WorkspaceParam = None,
		response_format: ResponseFormatParam = "markdown",
	) -> str:
		"""Search Indeed job postings.

		May return degraded results if anti-bot protection blocks access. Salary and
		posting-date data may be partial. Use this for job market research.
		Example: keyword='data engineer', location='Hanoi, Vietnam', max_items=20.
		"""
		payload: dict[str, Any] = {
			"keyword": keyword,
			"location": location,
			"radius": radius,
			"sort": sort,
			"salary_min": salary_min,
			"salary_max": salary_max,
			"employment_type": employment_type,
			"max_pages": max_pages,
			"max_items": max_items,
		}
		return await run_scraper(
			client,
			context,
			platform="indeed",
			verb="scrape",
			payload=payload,
			workspace=workspace,
			response_format=response_format,
		)
