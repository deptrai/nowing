"""Executive Dorker Engine for Privacy-Compliant LinkedIn Discovery (Story 21.9 / AD-LI-4)."""

from __future__ import annotations

import asyncio
import logging
import random

import httpx

from app.proprietary.platforms.linkedin.executive_parser import ExecutiveParser
from app.proprietary.platforms.linkedin.query_builder import build_serp_dork_query
from app.proprietary.platforms.linkedin.schemas import ExecutiveProfile

logger = logging.getLogger(__name__)

_DEFAULT_SEARCH_ENDPOINT = "https://html.duckduckgo.com/html/"
_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
]


class ExecutiveDorker:
    """Zero-login Public SERP Dorking engine for B2B Executive Discovery."""

    def __init__(
        self,
        search_endpoint: str | None = None,
        timeout: float = 15.0,
        parser: ExecutiveParser | None = None,
    ) -> None:
        self.search_endpoint = search_endpoint or _DEFAULT_SEARCH_ENDPOINT
        self.timeout = timeout
        self.parser = parser or ExecutiveParser()

    async def dork_executives(
        self,
        company_name: str,
        roles: list[str] | None = None,
        domain: str | None = None,
        limit: int = 10,
        client: httpx.AsyncClient | None = None,
    ) -> list[ExecutiveProfile]:
        """Execute dork query against SERP engine and parse leadership profiles."""
        if not company_name or not company_name.strip():
            return []

        query = build_serp_dork_query(company_name=company_name, roles=roles, domain=domain)
        headers = {
            "User-Agent": random.choice(_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=self.timeout, follow_redirects=True)
            should_close = True

        try:
            # Human jitter to avoid burst patterns (AD-LI-2)
            await asyncio.sleep(random.uniform(0.1, 0.3))

            response = await client.get(
                self.search_endpoint,
                params={"q": query},
                headers=headers,
            )

            if response.status_code != 200:
                logger.warning(
                    f"SERP dork request returned non-200 status {response.status_code} for query: {query}"
                )
                return []

            html_content = response.text
            profiles = self.parser.parse_serp_html(
                html_content=html_content,
                target_company=company_name,
                domain=domain,
            )

            return profiles[:limit]

        except httpx.RequestError as exc:
            logger.error(f"HTTP error during SERP dorking for '{company_name}': {exc}")
            return []
        except Exception as exc:
            logger.exception(f"Unexpected error during SERP dorking for '{company_name}': {exc}")
            return []
        finally:
            if should_close:
                await client.aclose()


async def dork_executives(
    company_name: str,
    roles: list[str] | None = None,
    domain: str | None = None,
    limit: int = 10,
    client: httpx.AsyncClient | None = None,
) -> list[ExecutiveProfile]:
    """Module-level convenience function for executive dorking."""
    dorker = ExecutiveDorker()
    return await dorker.dork_executives(
        company_name=company_name,
        roles=roles,
        domain=domain,
        limit=limit,
        client=client,
    )
