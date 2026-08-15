"""Red-phase unit tests for LeadGenOrchestrator and AI Agent Tool (Story 21.15)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Target modules to be implemented in Story 21.15:
# from app.lead_intelligence.services.lead_gen_orchestrator import (
#     LeadGenOrchestrator,
#     LeadGenOrchestratorResult,
#     SubTaskPlan,
# )
# from app.capabilities.leads.orchestrator_tool import MultiSourceLeadGenTool

pytestmark = pytest.mark.unit


class TestLeadGenOrchestrator:
    """Test AI Orchestrator query decomposition, concurrency limits, timeouts, and degradation."""

    @pytest.mark.asyncio
    async def test_decompose_query_into_subtasks(self) -> None:
        """Should decompose composite user queries into targeted sub-tasks for multiple adapters."""
        from app.lead_intelligence.services.lead_gen_orchestrator import (
            LeadGenOrchestrator,
        )

        orchestrator = LeadGenOrchestrator()
        prompt = "Tìm 30 công ty IT tại Hà Nội và 20 môi giới BĐS Cầu Giấy"

        with patch.object(
            orchestrator,
            "_plan_subtasks_with_llm",
            AsyncMock(
                return_value=[
                    {
                        "source_name": "job_market",
                        "query": "công ty IT Hà Nội",
                        "limit": 30,
                        "category": "JOB_MARKET",
                    },
                    {
                        "source_name": "batdongsan",
                        "query": "môi giới BĐS Cầu Giấy",
                        "limit": 20,
                        "category": "REAL_ESTATE",
                    },
                ]
            ),
        ):
            subtasks = await orchestrator.decompose_query(prompt)
            assert len(subtasks) == 2
            sources = [t.source_name for t in subtasks]
            assert "job_market" in sources
            assert "batdongsan" in sources

    @pytest.mark.asyncio
    async def test_concurrency_bounded_by_semaphore_5(self) -> None:
        """Should execute no more than 5 adapter tasks concurrently."""
        from app.lead_intelligence.services.lead_gen_orchestrator import (
            LeadGenOrchestrator,
        )

        orchestrator = LeadGenOrchestrator()
        active_tasks = 0
        max_active_tasks = 0

        async def slow_mock_search(*args: Any, **kwargs: Any) -> list[Any]:
            nonlocal active_tasks, max_active_tasks
            active_tasks += 1
            max_active_tasks = max(max_active_tasks, active_tasks)
            await asyncio.sleep(0.05)
            active_tasks -= 1
            return []

        # Create 8 mock subtasks to stress the concurrency limit
        mock_adapters = [
            MagicMock(
                source_name=f"adapter_{i}",
                search_leads=AsyncMock(side_effect=slow_mock_search),
            )
            for i in range(8)
        ]

        with patch.object(
            orchestrator.registry,
            "resolve_adapters_for_intent",
            return_value=mock_adapters,
        ):
            result = await orchestrator.execute_multi_source_lead_gen(
                workspace_id=1,
                query="Tìm thông tin đa nguồn trên 8 kênh",
                concurrency_limit=5,
            )

            assert max_active_tasks <= 5
            assert result.status in ("completed", "partial")

    @pytest.mark.asyncio
    async def test_per_adapter_timeout_12s_enforced_individually(self) -> None:
        """A hanging or slow adapter should be canceled after 12s while fast adapters finish successfully."""
        from app.lead_intelligence.adapters.base import (
            NormalizedLead,
            RawLeadRecord,
        )
        from app.lead_intelligence.services.lead_gen_orchestrator import (
            LeadGenOrchestrator,
        )

        orchestrator = LeadGenOrchestrator()

        async def hanging_search(*args: Any, **kwargs: Any) -> list[Any]:
            await asyncio.sleep(20.0)  # Exceeds 12s timeout
            return []

        async def fast_search(*args: Any, **kwargs: Any) -> list[Any]:
            return [
                RawLeadRecord(
                    source_name="fast_source",
                    source_id="f1",
                    data={"title": "Fast Lead", "phone": "0911223344"},
                )
            ]

        adapter_slow = MagicMock(
            source_name="slow_source",
            search_leads=AsyncMock(side_effect=hanging_search),
            normalize_lead=MagicMock(),
            extract_contact_candidates=MagicMock(return_value=[]),
        )
        adapter_fast = MagicMock(
            source_name="fast_source",
            search_leads=AsyncMock(side_effect=fast_search),
            normalize_lead=MagicMock(
                return_value=NormalizedLead(
                    source_name="fast_source",
                    source_id="f1",
                    primary_phone="0911223344",
                    confidence_score=80.0,
                    sources=["fast_source"],
                )
            ),
            extract_contact_candidates=MagicMock(return_value=[]),
        )

        with patch.object(
            orchestrator.registry,
            "resolve_adapters_for_intent",
            return_value=[adapter_slow, adapter_fast],
        ):
            # Pass timeout=0.1 for fast unit testing execution
            result = await orchestrator.execute_multi_source_lead_gen(
                workspace_id=1,
                query="Tìm kiếm đa nguồn kèm 1 nguồn bị treo",
                adapter_timeout_seconds=0.1,
            )

            # Fast adapter returned leads
            assert len(result.leads) == 1
            # Slow adapter recorded as timed_out / degraded
            assert "slow_source" in result.degraded_sources
            assert result.status == "partial"

    @pytest.mark.asyncio
    async def test_anti_loop_and_max_1_retry_on_failure(self) -> None:
        """When an adapter fails, it retries at most once and never enters an infinite loop."""
        from app.lead_intelligence.services.lead_gen_orchestrator import (
            LeadGenOrchestrator,
        )

        orchestrator = LeadGenOrchestrator()
        call_count = 0

        async def failing_search(*args: Any, **kwargs: Any) -> list[Any]:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Upstream 502 Bad Gateway")

        adapter_failing = MagicMock(
            source_name="failing_source",
            search_leads=AsyncMock(side_effect=failing_search),
            normalize_lead=MagicMock(),
            extract_contact_candidates=MagicMock(return_value=[]),
        )

        with patch.object(
            orchestrator.registry,
            "resolve_adapters_for_intent",
            return_value=[adapter_failing],
        ):
            result = await orchestrator.execute_multi_source_lead_gen(
                workspace_id=1,
                query="Tìm kiếm nguồn bị lỗi mạng",
            )

            # 1 initial attempt + 1 retry = exactly 2 calls
            assert call_count == 2
            assert result.status == "degraded"
            assert len(result.leads) == 0
            assert "failing_source" in result.degraded_sources

    @pytest.mark.asyncio
    async def test_fail_soft_when_all_adapters_degraded(self) -> None:
        """When all scrapers fail, return structured degraded response without throwing unhandled 500 (AD-19.1)."""
        from app.lead_intelligence.services.lead_gen_orchestrator import (
            LeadGenOrchestrator,
        )

        orchestrator = LeadGenOrchestrator()
        adapter_err = MagicMock(
            source_name="err_source",
            search_leads=AsyncMock(
                side_effect=RuntimeError("Cloudflare Turnstile Blocked")
            ),
        )

        with patch.object(
            orchestrator.registry,
            "resolve_adapters_for_intent",
            return_value=[adapter_err],
        ):
            result = await orchestrator.execute_multi_source_lead_gen(
                workspace_id=1,
                query="Quét nguồn bảo vệ nghiêm ngặt",
            )

            assert result.status == "degraded"
            assert result.total_discovered == 0
            assert "err_source" in result.degraded_sources


# ---------------------------------------------------------------------------
# 2. Agent Tool Bridge Tests (AC-6)
# ---------------------------------------------------------------------------
class TestMultiSourceLeadGenAgentTool:
    """Validate Chat Agent Tool wrapper for LeadGenOrchestrator."""

    @pytest.mark.asyncio
    async def test_agent_tool_schema_and_execution(self) -> None:
        """Should expose proper schema and return formatted markdown summary with Table link."""
        from app.capabilities.leads.orchestrator_tool import MultiSourceLeadGenTool
        from app.lead_intelligence.adapters.base import NormalizedLead
        from app.lead_intelligence.services.lead_gen_orchestrator import (
            LeadGenOrchestratorResult,
        )

        tool = MultiSourceLeadGenTool()
        assert tool.name == "multi_source_lead_gen"
        assert "query" in tool.parameters["properties"]

        mock_lead = NormalizedLead(
            source_name="batdongsan",
            source_id="bds_test",
            primary_phone="0912345678",
            contact_name="Nguyễn Văn A",
            company_name="Vinhomes",
            title="Bán biệt thự Ocean Park",
            confidence_score=90.0,
            sources=["batdongsan", "chotot"],
        )
        mock_result = LeadGenOrchestratorResult(
            status="completed",
            total_discovered=10,
            total_deduplicated=8,
            leads=[mock_lead],
            degraded_sources=[],
            table_id="tab_lead_123",
        )

        with patch(
            "app.lead_intelligence.services.lead_gen_orchestrator.LeadGenOrchestrator.execute_multi_source_lead_gen",
            AsyncMock(return_value=mock_result),
        ):
            tool_output = await tool.execute(
                workspace_id=1,
                query="Tìm 20 môi giới BĐS Gia Lâm",
                table_id="tab_lead_123",
            )

            assert isinstance(tool_output, str)
            assert "Đã tìm thấy 8 leads" in tool_output or "8 leads" in tool_output
            assert "tab_lead_123" in tool_output
            assert "batdongsan" in tool_output

