"""Unit tests for B2B Decision Maker Capability & MCP Tool Registration (Story 21.9 / AD-LI-6)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.capabilities.b2b.definition import B2B_FIND_DECISION_MAKERS
from app.capabilities.b2b.schemas import (
    B2BDecisionMakerInput,
    B2BDecisionMakerOutput,
)
from app.mcp_tools import MCP_TOOL_CATALOG, McpToolGroup
from app.proprietary.platforms.linkedin.schemas import ExecutiveProfile


def test_mcp_tool_catalog_contains_b2b_decision_makers() -> None:
    """Check that nowing_b2b_find_decision_makers is registered in MCP tool catalog."""
    matching_tools = [
        t for t in MCP_TOOL_CATALOG if t["name"] == "nowing_b2b_find_decision_makers"
    ]
    assert len(matching_tools) == 1
    assert matching_tools[0]["group"] == McpToolGroup.LEAD_INTELLIGENCE


@pytest.mark.asyncio
async def test_b2b_find_decision_makers_executor() -> None:
    """Capability executor runs search and returns structured DecisionMaker output."""
    mock_executives = [
        ExecutiveProfile(
            full_name="Pham Nhat Vu",
            title="Chairman & Founder",
            company_name="Vingroup",
            linkedin_url="https://vn.linkedin.com/in/pham-nhat-vu",
            linkedin_slug="pham-nhat-vu",
            department="Executive Leadership",
            inferred_emails=["vu.pham@vingroup.net"],
            email_prediction="vu.pham@vingroup.net",
            confidence_score=0.9,
            verified_mx=True,
            source_query='site:linkedin.com/in/ "Vingroup"',
        )
    ]

    with patch(
        "app.capabilities.b2b.executor.dork_executives",
        new=AsyncMock(return_value=mock_executives),
    ):
        input_payload = B2BDecisionMakerInput(
            company_name="Vingroup",
            domain="vingroup.net",
            roles=["Chairman", "CEO"],
            limit=5,
        )
        output: B2BDecisionMakerOutput = await B2B_FIND_DECISION_MAKERS.executor(input_payload)

        assert len(output.executives) == 1
        assert output.executives[0].full_name == "Pham Nhat Vu"
        assert output.executives[0].email_prediction == "vu.pham@vingroup.net"
        assert output.executives[0].confidence_score >= 0.8
