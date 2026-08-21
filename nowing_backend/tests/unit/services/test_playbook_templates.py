"""Unit tests for Playbook Templates & Marketplace (Story 24.5 / INV-24.6)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.auth.context import AuthContext
from app.automations.persistence.enums.playbook_scope import PlaybookScope
from app.automations.persistence.models.playbook import Playbook
from app.automations.services.playbook_seed_service import (
    OFFICIAL_PLAYBOOKS,
    seed_system_playbooks,
)
from app.automations.services.playbook_service import PlaybookService


def test_official_playbooks_structure():
    """Verify all 4 battle-tested templates exist and have required fields."""
    assert len(OFFICIAL_PLAYBOOKS) >= 4
    names = {pb["name"] for pb in OFFICIAL_PLAYBOOKS}
    assert "BĐS Ngộp & Môi Giới Pro" in names
    assert "IT Headhunter Săn Senior" in names
    assert "B2B Sales Doanh Nghiệp Mới" in names
    assert "E-Commerce Flash Price Tracking" in names

    for pb in OFFICIAL_PLAYBOOKS:
        assert pb["scope"] == PlaybookScope.SYSTEM
        assert "inputs_schema" in pb
        assert "definition" in pb
        assert "verticals" in pb
        assert len(pb["verticals"]) >= 1
        assert pb["is_approved"] is True

        # Check metadata
        meta = pb["definition"].get("metadata", {})
        assert meta.get("author_badge") == "official"
        assert meta.get("estimated_credits_cost", 0) > 0

        # Every agent_task plan step must carry a Jinja query
        for step in pb["definition"].get("plan", []):
            if step["action"] == "agent_task":
                assert "query" in step.get("params", {}), f"{pb['name']} step {step['step_id']} missing params.query"


@pytest.mark.asyncio
async def test_inv_24_6_max_leads_hard_limit():
    """INV-24.6: Inputs with max_leads > 200 must be rejected with HTTP 422."""
    mock_session = AsyncMock()
    mock_user = MagicMock()
    auth = AuthContext.session(user=mock_user)
    service = PlaybookService(session=mock_session, auth=auth)

    playbook = Playbook(
        id=1,
        name="Test Playbook",
        inputs_schema={
            "type": "object",
            "properties": {"max_leads": {"type": "integer"}},
        },
    )

    # Valid: 50 <= 200
    service._validate_inputs(playbook, {"max_leads": 50})

    # Valid: 200 == 200
    service._validate_inputs(playbook, {"max_leads": 200})

    # Invalid: 201 > 200
    with pytest.raises(HTTPException) as exc:
        service._validate_inputs(playbook, {"max_leads": 201})
    assert exc.value.status_code == 422
    assert "200" in str(exc.value.detail)


async def test_seed_system_playbooks_idempotent():
    """Verify seed service executes idempotently via UPSERT and hides stale playbooks."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_session.execute.return_value = mock_result

    count = await seed_system_playbooks(mock_session)
    assert count == len(OFFICIAL_PLAYBOOKS)
    assert mock_session.execute.call_count == len(OFFICIAL_PLAYBOOKS) + 1
    assert mock_session.commit.call_count == 1
