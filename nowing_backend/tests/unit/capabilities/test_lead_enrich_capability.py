"""Unit tests for the ``lead.enrich`` capability registration (Story 21.3)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit


async def test_lead_enrich_capability_is_registered() -> None:
    import app.lead_intelligence.enrichment  # noqa: F401
    from app.capabilities.core.store import get_capability

    cap = get_capability("lead.enrich")
    assert cap is not None
    assert cap.name == "lead.enrich"
    assert cap.context_aware is True
    assert cap.billing_unit is None


async def test_lead_enrich_capability_executor_calls_service(monkeypatch) -> None:
    import app.lead_intelligence.enrichment  # noqa: F401
    from app.capabilities.core.store import get_capability

    cap = get_capability("lead.enrich")
    fake_output = MagicMock()
    fake_output.degraded = False

    enrich_mock = AsyncMock(return_value=fake_output)
    monkeypatch.setattr(
        "app.lead_intelligence.enrichment.service.EnrichmentService.enrich",
        enrich_mock,
    )

    session = MagicMock()
    ctx = SimpleNamespace(
        session=session,
        workspace_id=1,
        run_id="run-test",
        client_id=None,
        user_id=uuid4(),
    )

    from app.lead_intelligence.enrichment.schemas import EnrichmentInput

    payload = EnrichmentInput(lead_id=uuid4())
    output = await cap.executor(payload, ctx)

    assert output is fake_output
    enrich_mock.assert_awaited_once()
    call_kwargs = enrich_mock.call_args.kwargs
    assert call_kwargs["session"] is session
    assert call_kwargs["ctx"] is ctx
    assert call_kwargs["lead_id"] == payload.lead_id


async def test_lead_enrich_capability_degraded_when_no_lead(monkeypatch) -> None:
    import app.lead_intelligence.enrichment  # noqa: F401
    from app.capabilities.core.store import get_capability

    cap = get_capability("lead.enrich")

    session = MagicMock()
    ctx = SimpleNamespace(
        session=session,
        workspace_id=1,
        run_id="run-test",
        client_id=None,
        user_id=uuid4(),
    )

    from app.lead_intelligence.enrichment.schemas import EnrichmentInput

    payload = EnrichmentInput()
    output = await cap.executor(payload, ctx)

    assert output.degraded is True
    assert "lead_not_found" in output.degradation_reasons