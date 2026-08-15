"""Unit tests for the ``lead.enrich`` capability registration & MCP catalog (Story 21.3 AC-9).

Tests contract invariants:
- ``lead.enrich`` capability registration
- ``billing_unit=None`` (TokenUsage is for LLM steps only; business events use BillingEvent)
- ``context_aware=True``
- ``metadata={"emits_leads": False, "requires_pii_redaction_context": "lead_enrichment"}``
- Input/Output schemas (EnrichmentInput / EnrichmentOutput)
- Executor delegating to EnrichmentService.enrich
- MCP tools registered in MCP_TOOL_CATALOG under LEAD_INTELLIGENCE
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit


async def test_lead_enrich_capability_is_registered() -> None:
    """AC-9: lead.enrich registered with billing_unit=None and specific metadata."""
    import app.lead_intelligence.enrichment  # noqa: F401
    from app.capabilities.core.store import get_capability
    from app.lead_intelligence.enrichment.schemas import (
        EnrichmentInput,
        EnrichmentOutput,
    )

    cap = get_capability("lead.enrich")
    assert cap is not None
    assert cap.name == "lead.enrich"
    assert cap.context_aware is True
    assert cap.billing_unit is None, (
        "Story 21.3 requires billing_unit=None (no TokenUsage)"
    )
    assert cap.input_schema == EnrichmentInput
    assert cap.output_schema == EnrichmentOutput
    assert cap.metadata == {
        "emits_leads": False,
        "requires_pii_redaction_context": "lead_enrichment",
    }


async def test_lead_enrich_capability_executor_calls_enrichment_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-9: Executor forwards input and context to EnrichmentService.enrich."""
    import app.lead_intelligence.enrichment  # noqa: F401
    from app.capabilities.core.store import get_capability
    from app.lead_intelligence.enrichment.schemas import EnrichmentInput

    cap = get_capability("lead.enrich")
    fake_output = MagicMock()
    fake_output.enrichment_request_id = uuid4()
    fake_output.contact_count = 1
    fake_output.cost_micros = 50000
    fake_output.degraded = False

    enrich_mock = AsyncMock(return_value=fake_output)
    monkeypatch.setattr(
        "app.lead_intelligence.enrichment.service.EnrichmentService.enrich",
        enrich_mock,
    )

    session = MagicMock()
    lead_id = uuid4()
    user_id = uuid4()
    ctx = SimpleNamespace(
        session=session,
        workspace_id=1,
        run_id="run-enrich-cap-test",
        client_id=None,
        user_id=user_id,
    )

    payload = EnrichmentInput(lead_id=lead_id, requested_count=2)
    output = await cap.executor(payload, ctx)

    assert output is fake_output
    enrich_mock.assert_awaited_once()
    call_kwargs = enrich_mock.call_args.kwargs
    assert call_kwargs["session"] is session
    assert call_kwargs["ctx"] is ctx
    assert call_kwargs["lead_id"] == lead_id
    assert call_kwargs["requested_count"] == 2


def test_mcp_tool_catalog_includes_enrichment_tools() -> None:
    """AC-9: MCP tools are cataloged under LEAD_INTELLIGENCE."""
    from app.mcp_tools import MCP_TOOL_CATALOG, MCPToolGroup

    lead_intelligence_tools = MCP_TOOL_CATALOG.get(MCPToolGroup.LEAD_INTELLIGENCE, [])
    tool_names = [
        t.name if hasattr(t, "name") else str(t) for t in lead_intelligence_tools
    ]

    assert "nowing_enrich_lead" in tool_names
    assert "nowing_list_contacts" in tool_names
