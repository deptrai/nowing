"""Unit tests for Real Estate Zoning capability and Agent Tool registration (Story 10.8 / AC-5 / AD-GIS-6)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.capabilities.core import get_capability
from app.capabilities.core.access.agent import build_capability_tools
from app.capabilities.core.types import CapabilityContext
from app.capabilities.realestate.zoning.definition import REALESTATE_ZONING
from app.capabilities.realestate.zoning.executor import build_zoning_executor
from app.capabilities.realestate.zoning.schemas import (
    ZoningCheckInput,
    ZoningCheckOutput,
)
from app.mcp_tools import MCP_TOOL_CATALOG, MCP_TOOL_NAMES, McpToolGroup
from app.proprietary.platforms.spatial_planning.schemas import (
    LandZoningPolarity,
    PlanningZoneItem,
    ZoningCheckResult,
)

pytestmark = pytest.mark.unit


class TestRealEstateZoningCapabilities:
    """AC-5: Capability registration, schema validation, and tool execution."""

    def test_capability_registration(self):
        """Ensure realestate.zoning capability is registered in the global capability registry."""
        cap = get_capability("realestate.zoning")
        assert cap is not None
        assert cap.name == "realestate.zoning"
        assert cap.input_schema == ZoningCheckInput
        assert cap.output_schema == ZoningCheckOutput

    def test_mcp_tool_catalog_registration(self):
        """Ensure nowing_realestate_check_zoning is registered in MCP catalog."""
        assert "nowing_realestate_check_zoning" in MCP_TOOL_NAMES
        tool_entry = next(t for t in MCP_TOOL_CATALOG if t["name"] == "nowing_realestate_check_zoning")
        assert tool_entry["group"] in (McpToolGroup.LEAD_INTELLIGENCE, McpToolGroup.SCRAPER)

    @pytest.mark.asyncio
    async def test_zoning_executor_success(self):
        """Test capability executor invoking SpatialPlanningService."""
        executor = build_zoning_executor()

        mock_result = ZoningCheckResult(
            latitude=21.0285,
            longitude=105.8542,
            has_road_expansion_risk=True,
            zones=[
                PlanningZoneItem(
                    id=1,
                    province="Hà Nội",
                    district="Cầu Giấy",
                    ward="Yên Hòa",
                    zone_code="ODT",
                    zone_name="Đất ở đô thị",
                    planning_period="2021-2030",
                    polarity=LandZoningPolarity.SAFE,
                ),
                PlanningZoneItem(
                    id=2,
                    province="Hà Nội",
                    district="Cầu Giấy",
                    ward="Yên Hòa",
                    zone_code="DGT",
                    zone_name="Đất giao thông mở đường",
                    planning_period="2021-2030",
                    polarity=LandZoningPolarity.DANGER,
                ),
            ],
            summary="Thửa đất có 85% Đất ở (ODT) và 15% diện tích dính quy hoạch mở đường (DGT).",
            risk_notes=["Thửa đất nằm trong chỉ giới mở rộng đường 20m."],
        )

        with patch("app.proprietary.platforms.spatial_planning.service.SpatialPlanningService.check_zoning", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = mock_result

            mock_session = AsyncMock()
            ctx = CapabilityContext(session=mock_session, workspace_id=1)

            input_data = ZoningCheckInput(
                latitude=21.0285,
                longitude=105.8542,
                address="45 Nguyễn Khang, Cầu Giấy, Hà Nội",
            )

            output: ZoningCheckOutput = await executor(input_data, ctx=ctx)

            assert output.has_road_expansion_risk is True
            assert len(output.zones) == 2
            assert output.zones[0].zone_code == "ODT"
            assert output.zones[1].zone_code == "DGT"
            assert "mở đường" in output.summary

    def test_agent_tool_construction(self):
        """Test LangChain tool generation for the AI Agent door."""
        tools = build_capability_tools(workspace_id=1, capabilities=[REALESTATE_ZONING])
        zoning_tool = next((t for t in tools if t.name == "realestate_zoning"), None)
        assert zoning_tool is not None
        assert "zoning" in zoning_tool.description.lower() or "quy hoạch" in zoning_tool.description.lower()
