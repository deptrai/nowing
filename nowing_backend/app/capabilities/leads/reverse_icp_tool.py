"""AI Agent tool for 1-Click Reverse-ICP URL analysis (Story 21.10)."""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.lead_intelligence.reverse_icp import ReverseIcpService

logger = logging.getLogger(__name__)


class ReverseIcpToolInput(BaseModel):
    """Input schema for reverse-ICP agent tool."""

    url: str = Field(..., description="The website domain or project landing page URL to analyze for ICP")
    custom_instructions: str | None = Field(
        default=None, description="Optional custom focus instructions (e.g. target high-end buyers)"
    )


@tool("leads_reverse_icp", args_schema=ReverseIcpToolInput)
async def leads_reverse_icp(url: str, custom_instructions: str | None = None) -> str:
    """Analyze a website or landing page to extract ICP, buyer personas, search queries, and filter presets.

    Returns a structured analysis with buyer personas, ready-to-run lead search queries, negative keywords,
    and filter presets for multi-platform lead discovery.
    """
    service = ReverseIcpService()
    try:
        response = await service.analyze_url(url=url, custom_instructions=custom_instructions)
        payload = response.model_dump()
        return json.dumps(payload, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("[ReverseIcpTool] Error executing leads_reverse_icp for %s: %s", url, exc)
        return json.dumps({
            "error": f"Failed to analyze URL for ICP: {exc}",
            "url": url,
        }, ensure_ascii=False)
