"""Unit tests for CrmWebhookService (Story 34.1)."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.models.leads.main import Lead
from app.routes.crm_routes import hubspot_webhook, salesforce_webhook
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

    def test_verify_hubspot_signature_empty_secret_rejects(self, monkeypatch):
        """Empty or unset secret must reject (no fail-open)."""
        monkeypatch.setattr("app.config.config.HUBSPOT_WEBHOOK_SECRET", "")
        assert verify_hubspot_signature(b"{}", "some-sig", secret="") is False
        assert verify_hubspot_signature(b"{}", "some-sig", secret=None) is False

    def test_verify_hubspot_signature_wrong_signature_rejects(self):
        """Invalid signature must be rejected."""
        assert (
            verify_hubspot_signature(
                b'{"test": 123}',
                "invalid-signature",
                secret="test-secret-key",
                method="POST",
                request_uri="http://test/api/v1/workspaces/webhooks/hubspot",
                timestamp="1700000000000",
            )
            is False
        )

    def test_verify_hubspot_signature_valid_v3_accepts(self):
        """Valid v3 signature (base64 HMAC-SHA256) must be accepted."""
        import base64
        import hashlib
        import hmac

        secret = "test-secret-key"
        body = b'{"test": 123}'
        method = "POST"
        uri = "http://test/api/v1/workspaces/webhooks/hubspot"
        timestamp = "1700000000000"

        source = f"{method}{uri}".encode() + body + timestamp.encode()
        sig = base64.b64encode(
            hmac.new(secret.encode(), source, hashlib.sha256).digest()
        ).decode()

        assert (
            verify_hubspot_signature(
                body,
                sig,
                secret=secret,
                method=method,
                request_uri=uri,
                timestamp=timestamp,
            )
            is True
        )

    def test_verify_hubspot_signature_valid_legacy(self):
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


def _make_http_request(body: bytes, headers: dict[str, str] | None = None) -> Request:
    raw_headers = [
        (k.lower().encode("latin1"), v.encode("latin1"))
        for k, v in (headers or {}).items()
    ]

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        scope={
            "type": "http",
            "method": "POST",
            "path": "/api/v1/workspaces/webhooks/hubspot",
            "headers": raw_headers,
        },
        receive=receive,
    )


class TestHubspotWebhookAuth:
    """Test fail-closed authentication for HubSpot webhook endpoint."""

    @pytest.mark.asyncio
    async def test_hubspot_webhook_auth_missing_secret(self, monkeypatch):
        from app.config import config

        monkeypatch.setattr(config, "HUBSPOT_WEBHOOK_SECRET", "")

        session = _make_mock_session()
        req = _make_http_request(b'{"test": 1}')

        with pytest.raises(HTTPException) as exc_info:
            await hubspot_webhook(req, session, x_hubspot_signature_v3="some-sig")
        assert exc_info.value.status_code == 401
        assert "Invalid HubSpot signature" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_hubspot_webhook_auth_missing_or_invalid_signature(self, monkeypatch):
        from app.config import config

        secret = "test-hubspot-secret"
        monkeypatch.setattr(config, "HUBSPOT_WEBHOOK_SECRET", secret)

        session = _make_mock_session()
        req = _make_http_request(b'{"test": 1}')

        # Missing signature
        with pytest.raises(HTTPException) as exc_info:
            await hubspot_webhook(req, session, x_hubspot_signature_v3=None)
        assert exc_info.value.status_code == 401

        # Invalid signature
        with pytest.raises(HTTPException) as exc_info:
            await hubspot_webhook(req, session, x_hubspot_signature_v3="wrong-sig")
        assert exc_info.value.status_code == 401


class TestSalesforceWebhookAuth:
    """Test fail-closed authentication for Salesforce webhook endpoint."""

    @pytest.mark.asyncio
    async def test_salesforce_webhook_auth_missing_secret(self, monkeypatch):
        from app.config import config

        monkeypatch.setattr(config, "SALESFORCE_WEBHOOK_SECRET", "")

        session = _make_mock_session()
        req = _make_http_request(b'{"test": 1}')

        with pytest.raises(HTTPException) as exc_info:
            await salesforce_webhook(
                req, session, x_salesforce_webhook_secret="some-sig"
            )
        assert exc_info.value.status_code == 401
        assert "Invalid Salesforce webhook secret" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_salesforce_webhook_auth_missing_or_invalid_signature(
        self, monkeypatch
    ):
        from app.config import config

        monkeypatch.setattr(
            config, "SALESFORCE_WEBHOOK_SECRET", "super-secret-salesforce"
        )

        session = _make_mock_session()
        req = _make_http_request(b'{"test": 1}')

        # Missing signature (None)
        with pytest.raises(HTTPException) as exc_info:
            await salesforce_webhook(req, session, x_salesforce_webhook_secret=None)
        assert exc_info.value.status_code == 401
        assert "Invalid Salesforce webhook secret" in exc_info.value.detail

        # Empty header signature
        with pytest.raises(HTTPException) as exc_info_empty:
            await salesforce_webhook(req, session, x_salesforce_webhook_secret="")
        assert exc_info_empty.value.status_code == 401
        assert "Invalid Salesforce webhook secret" in exc_info_empty.value.detail

        # Invalid signature
        with pytest.raises(HTTPException) as exc_info2:
            await salesforce_webhook(
                req, session, x_salesforce_webhook_secret="wrong-signature"
            )
        assert exc_info2.value.status_code == 401
        assert "Invalid Salesforce webhook secret" in exc_info2.value.detail

    @pytest.mark.asyncio
    async def test_salesforce_webhook_auth_valid_signature_processes(self, monkeypatch):
        from app.config import config

        secret = "super-secret-salesforce"
        monkeypatch.setattr(config, "SALESFORCE_WEBHOOK_SECRET", secret)

        body = b'{"StageName": "unknown"}'

        session = _make_mock_session()
        req = _make_http_request(body)

        result = await salesforce_webhook(
            req, session, x_salesforce_webhook_secret=secret
        )
        assert result["status"] == "ok"
        session.commit.assert_awaited_once()


class TestCrmWebhookLeadStatusTransaction:
    """Test transactional commit and rollback for CRM webhooks."""

    @pytest.mark.asyncio
    async def test_crm_webhook_lead_status_transaction_commit(self, monkeypatch):
        """Valid deal change updates Lead.status and CrmSyncLog in a single transaction."""
        import hashlib
        import hmac

        from app.config import config

        secret = "test-hubspot-secret"
        monkeypatch.setattr(config, "HUBSPOT_WEBHOOK_SECRET", secret)

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

        body = b'[{"objectId": 12345, "propertyName": "dealstage", "propertyValue": "closedwon", "subscriptionType": "deal.propertyChange"}]'
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        req = _make_http_request(body)

        resp = await hubspot_webhook(req, session, x_hubspot_signature_v3=sig)
        assert resp["status"] == "ok"
        assert lead.status == "converted"
        session.commit.assert_awaited_once()
        session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_crm_webhook_lead_status_transaction_rollback_on_error(
        self, monkeypatch
    ):
        """Failure during webhook processing triggers session rollback and raises 500."""
        import hashlib
        import hmac

        from app.config import config

        secret = "test-hubspot-secret"
        monkeypatch.setattr(config, "HUBSPOT_WEBHOOK_SECRET", secret)

        session = _make_mock_session()
        session.execute.side_effect = RuntimeError("DB connection dropped")

        body = b'[{"objectId": 12345, "propertyName": "dealstage", "propertyValue": "closedwon", "subscriptionType": "deal.propertyChange"}]'
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        req = _make_http_request(body)

        with pytest.raises(HTTPException) as exc_info:
            await hubspot_webhook(req, session, x_hubspot_signature_v3=sig)

        assert exc_info.value.status_code == 500
        session.rollback.assert_awaited_once()
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_salesforce_webhook_rollback_on_error(self, monkeypatch):
        """Failure during Salesforce webhook processing triggers session rollback and raises 500."""
        from app.config import config

        secret = "super-secret-salesforce"
        monkeypatch.setattr(config, "SALESFORCE_WEBHOOK_SECRET", secret)

        session = _make_mock_session()
        session.execute.side_effect = RuntimeError("DB connection dropped")

        body = b'{"Id": "006xx000001", "StageName": "closed won"}'
        req = _make_http_request(body)

        with pytest.raises(HTTPException) as exc_info:
            await salesforce_webhook(req, session, x_salesforce_webhook_secret=secret)

        assert exc_info.value.status_code == 500
        session.rollback.assert_awaited_once()
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_crm_webhooks_do_not_coerce_http_exception(self, monkeypatch):
        """HTTPException raised inside webhook processing should be re-raised, not coerced to 500."""
        from unittest.mock import patch

        from app.config import config

        hs_secret = "test-hubspot-secret"
        monkeypatch.setattr(config, "HUBSPOT_WEBHOOK_SECRET", hs_secret)
        monkeypatch.setattr(config, "SALESFORCE_WEBHOOK_SECRET", "sf-secret")

        session = _make_mock_session()

        # Test HubSpot webhook re-raises HTTPException
        hs_body = b'[{"objectId": 123}]'
        hs_sig = hmac.new(hs_secret.encode(), hs_body, hashlib.sha256).hexdigest()
        req_hs = _make_http_request(hs_body)
        with patch(
            "app.services.crm_webhook_service.CrmWebhookService.handle_hubspot_deal_change",
            side_effect=HTTPException(status_code=400, detail="Custom client error"),
        ):
            with pytest.raises(HTTPException) as exc_hs:
                await hubspot_webhook(req_hs, session, x_hubspot_signature_v3=hs_sig)
            assert exc_hs.value.status_code == 400
            assert exc_hs.value.detail == "Custom client error"

        # Test Salesforce webhook re-raises HTTPException
        req_sf = _make_http_request(b'{"StageName": "Prospecting"}')
        with patch(
            "app.services.crm_webhook_service.CrmWebhookService.handle_salesforce_deal_change",
            side_effect=HTTPException(status_code=422, detail="Validation error"),
        ):
            with pytest.raises(HTTPException) as exc_sf:
                await salesforce_webhook(
                    req_sf, session, x_salesforce_webhook_secret="sf-secret"
                )
            assert exc_sf.value.status_code == 422
            assert exc_sf.value.detail == "Validation error"
