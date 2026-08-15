"""Unit tests for the ``lead.score`` capability registration (Story 21.2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit


async def test_lead_score_capability_is_registered() -> None:
    import app.lead_intelligence.scoring  # noqa: F401
    from app.capabilities.core.store import get_capability

    cap = get_capability("lead.score")
    assert cap is not None
    assert cap.name == "lead.score"
    assert cap.context_aware is True
    assert cap.billing_unit is not None
    assert cap.billing_unit.value == "lead_score"


async def test_lead_score_capability_executor_calls_service(monkeypatch) -> None:
    from types import SimpleNamespace

    import app.lead_intelligence.scoring  # noqa: F401
    from app.capabilities.core.store import get_capability

    cap = get_capability("lead.score")
    fake_output = MagicMock()
    fake_output.items = []
    fake_output.cost_micros = 0
    fake_output.degraded = False

    score_mock = AsyncMock(return_value=fake_output)
    monkeypatch.setattr(
        "app.lead_intelligence.scoring.service.LeadScoringService.score",
        score_mock,
    )

    session = MagicMock()
    ctx = SimpleNamespace(
        session=session,
        workspace_id=1,
        run_id="run-test",
        client_id=None,
        user_id=uuid4(),
    )

    from app.lead_intelligence.scoring.schemas import LeadScoreInput

    payload = LeadScoreInput(lead_ids=[uuid4()])
    output = await cap.executor(payload, ctx)

    assert output is fake_output
    score_mock.assert_awaited_once()
    call_kwargs = score_mock.call_args.kwargs
    assert call_kwargs["session"] is session
    assert call_kwargs["ctx"] is ctx
    assert call_kwargs["inp"] is payload
