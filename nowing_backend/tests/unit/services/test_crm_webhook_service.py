"""Unit tests for CrmWebhookService (Story 34.1)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.leads.main import Lead
from app.services.crm_webhook_service import (
    CrmWebhookService,
    map_stage_to_status,
    verify_hubspot_signature,
)

pytestmark = [pytest.mark.unit]

def _make_mock_session() -> MagicMock:
    """Mock AsyncSession where add() is sync, execute/flush/commit are async."""
    session = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.delete = AsyncMock()
    session.execute = AsyncMock()
    session.get = AsyncMock()
    return session



class TestStageMapping:
    """Test external deal stage to lead status mapping."""

    def test_hubspot_stages(self):
        assert map_stage_to_status("appointmentscheduled") == "contacted"
        assert map_stage_to_status("qualifiedtobuy") == "qualified"
        assert map_stage_to_status("closedwon") == "converted"
        assert map_stage_to_status("closedlost") == "lost"

    def test_salesforce_stages(self):
        assert map_stage_to_status("prospecting") == "contacted"
        assert map_stage_to_status("qualification") == "qualified"
        assert map_stage_to_status("closed won") == "converted"
        assert map_stage_to_status("closed lost") == "lost"

    def test_unknown_stage_returns_none(self):
        assert map_stage_to_status("custom_stage_unknown") is None


class TestSignatureVerification:
    """Test webhook signature validation."""

    def test_verify_hubspot_signature_missing(self):
        assert verify_hubspot_signature(b"{}", None) is False

    def test_verify_hubspot_signature_valid(self):
        import hashlib
        import hmac

        secret = "test-secret-key"
        body = b'{"test": 123}'
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert verify_hubspot_signature(body, sig, secret=secret) is True


class TestCrmWebhookService:
    """Test processing webhook events."""

    @pytest.mark.asyncio
    async def test_handle_hubspot_deal_change_updates_lead(self):
        """HubSpot deal change should update Lead status and record log."""
        session = _make_mock_session()

        lead = MagicMock(spec=Lead)
        lead.id = uuid.uuid4()
        lead.workspace_id = 1
        lead.status = "new"

        contact = MagicMock()
        contact.lead_id = lead.id
        contact.workspace_id = 1

        scalars_mock = MagicMock()
        scalars_mock.first.return_value = contact
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        session.execute.return_value = result_mock
        session.get.return_value = lead

        service = CrmWebhookService(session)
        events = [
            {
                "objectId": 12345,
                "propertyName": "dealstage",
                "propertyValue": "closedwon",
                "subscriptionType": "deal.propertyChange",
            }
        ]

        results = await service.handle_hubspot_deal_change(events)

        assert len(results) == 1
        assert results[0]["status"] == "updated"
        assert results[0]["new_lead_status"] == "converted"
        assert lead.status == "converted"
        session.add.assert_called_once()
