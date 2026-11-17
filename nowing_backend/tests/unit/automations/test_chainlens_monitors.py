"""Unit tests for ChainLens Webhook Monitors (Story 20.8)."""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.automations.persistence.enums.trigger_type import TriggerType
from app.routes.chainlens_webhooks import router as chainlens_webhooks_router
from app.services.chainlens.monitors import (
    ChainLensMonitorClient,
    ChainLensMonitorError,
)

pytestmark = pytest.mark.unit

SECRET_KEY = "test_chainlens_secret_key_12345"


@pytest.fixture
def client_service():
    client = ChainLensMonitorClient(base_url="http://mock-chainlens:3001")
    client._get_secret = lambda: SECRET_KEY  # type: ignore[method-assign]
    return client


def _sign(body: bytes) -> str:
    return hmac.new(SECRET_KEY.encode("utf-8"), body, hashlib.sha256).hexdigest()


class TestTriggerTypeEnum:
    def test_enum_value(self):
        assert TriggerType.CHAINLENS_MONITOR == "chainlens_monitor"
        assert TriggerType("chainlens_monitor") == TriggerType.CHAINLENS_MONITOR


class TestSignatureVerification:
    def test_valid_hex_signature(self, client_service: ChainLensMonitorClient):
        body = b'{"monitorId":"m1","results":[]}'
        sig = _sign(body)
        assert client_service.verify_webhook_signature(body, sig) is True

    def test_valid_sha256_prefixed_signature(
        self, client_service: ChainLensMonitorClient
    ):
        body = b'{"monitorId":"m1"}'
        sig = f"sha256={_sign(body)}"
        assert client_service.verify_webhook_signature(body, sig) is True

    def test_tampered_body_fails(self, client_service: ChainLensMonitorClient):
        body = b'{"monitorId":"m1"}'
        sig = _sign(body)
        assert client_service.verify_webhook_signature(b'{"monitorId":"m2"}', sig) is False

    def test_empty_signature_fails(self, client_service: ChainLensMonitorClient):
        assert client_service.verify_webhook_signature(b"{}", "") is False
        assert client_service.verify_webhook_signature(b"{}", None) is False


class TestMonitorClientLifecycle:
    async def test_create_monitor_success(self, client_service: ChainLensMonitorClient):
        mock_res = MagicMock()
        mock_res.is_success = True
        mock_res.json.return_value = {
            "monitorId": "mon_xyz",
            "name": "Market Check",
            "cron": "0 9 * * *",
        }

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_res)
        mock_http.__aenter__.return_value = mock_http
        mock_http.__aexit__.return_value = False

        with patch("httpx.AsyncClient", return_value=mock_http):
            res = await client_service.create_monitor(
                workspace_id=15,
                name="Market Check",
                query="Bất động sản TP.HCM",
                cron="0 9 * * *",
                webhook_url="https://api.nowing.net/api/v1/webhooks/chainlens/monitors",
            )

        assert res["monitorId"] == "mon_xyz"
        mock_http.post.assert_awaited_once()

    async def test_create_monitor_http_error_raises_monitor_error(
        self, client_service: ChainLensMonitorClient
    ):
        mock_res = MagicMock()
        mock_res.is_success = False
        mock_res.status_code = 500
        mock_res.text = "Internal Engine Error"

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_res)
        mock_http.__aenter__.return_value = mock_http
        mock_http.__aexit__.return_value = False

        with (
            patch("httpx.AsyncClient", return_value=mock_http),
            pytest.raises(ChainLensMonitorError, match="500"),
        ):
            await client_service.create_monitor(
                workspace_id=15,
                name="Test",
                query="X",
                cron="@daily",
                webhook_url="https://example.com",
            )

    async def test_delete_monitor_success(self, client_service: ChainLensMonitorClient):
        mock_res = MagicMock()
        mock_res.is_success = True
        mock_res.status_code = 200

        mock_http = AsyncMock()
        mock_http.delete = AsyncMock(return_value=mock_res)
        mock_http.__aenter__.return_value = mock_http
        mock_http.__aexit__.return_value = False

        with patch("httpx.AsyncClient", return_value=mock_http):
            ok = await client_service.delete_monitor("mon_xyz")

        assert ok is True

    async def test_delete_monitor_404_treated_as_success(
        self, client_service: ChainLensMonitorClient
    ):
        """Idempotent delete: 404 means already deleted on ChainLens."""
        mock_res = MagicMock()
        mock_res.is_success = False
        mock_res.status_code = 404

        mock_http = AsyncMock()
        mock_http.delete = AsyncMock(return_value=mock_res)
        mock_http.__aenter__.return_value = mock_http
        mock_http.__aexit__.return_value = False

        with patch("httpx.AsyncClient", return_value=mock_http):
            ok = await client_service.delete_monitor("mon_already_gone")

        assert ok is True


class TestWebhookEndpoint:
    @pytest.fixture
    def app(self, client_service):
        test_app = FastAPI()
        test_app.include_router(chainlens_webhooks_router)
        return test_app

    @pytest.fixture
    def test_client(self, app):
        return TestClient(app)

    def test_missing_signature_returns_401(self, test_client):
        resp = test_client.post(
            "/api/v1/webhooks/chainlens/monitors",
            content=b'{"monitorId":"m1"}',
        )
        assert resp.status_code == 401

    def test_invalid_signature_returns_401(self, test_client):
        resp = test_client.post(
            "/api/v1/webhooks/chainlens/monitors",
            content=b'{"monitorId":"m1"}',
            headers={"X-ChainLens-Signature": "invalid_sig_abc123"},
        )
        assert resp.status_code == 401

    def test_valid_webhook_launches_automation_run(
        self, test_client, client_service
    ):
        from app.routes.chainlens_webhooks import _get_monitor_client

        body = json.dumps(
            {
                "monitorId": "mon_market_1",
                "query": "Bất động sản",
                "results": [{"title": "Dự án mới", "url": "https://cafef.vn/123"}],
                "event": "delta_findings",
            }
        ).encode("utf-8")
        sig = hmac.new(SECRET_KEY.encode("utf-8"), body, hashlib.sha256).hexdigest()

        # Mock trigger in DB
        mock_trigger = MagicMock()
        mock_trigger.id = uuid4()
        mock_trigger.params = {"monitor_id": "mon_market_1"}

        mock_session = AsyncMock()
        res_exec = MagicMock()
        res_exec.scalars.return_value.all.return_value = [mock_trigger]
        mock_session.execute = AsyncMock(return_value=res_exec)
        mock_session.commit = AsyncMock()

        mock_run = MagicMock()
        mock_run.id = uuid4()

        async def _gen():
            yield mock_session

        from app.db import get_async_session

        test_client.app.dependency_overrides[get_async_session] = _gen
        test_client.app.dependency_overrides[_get_monitor_client] = (
            lambda: client_service
        )

        with patch(
            "app.routes.chainlens_webhooks.launch_run",
            AsyncMock(return_value=mock_run),
        ) as launch_mock:
            resp = test_client.post(
                "/api/v1/webhooks/chainlens/monitors",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-ChainLens-Signature": sig,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "enqueued"
        assert data["run_id"] == str(mock_run.id)
        launch_mock.assert_awaited_once()
