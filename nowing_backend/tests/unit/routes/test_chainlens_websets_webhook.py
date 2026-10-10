"""Unit tests for ChainLens Websets idle webhook route (Story 41.1)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_async_session
from app.models.webset_campaign import WebsetCampaign
from app.routes.chainlens_webhooks import router

pytestmark = pytest.mark.unit


def _make_test_app(mock_session: AsyncMock) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_async_session] = lambda: mock_session
    return app


class TestChainLensWebsetIdleWebhook:
    def test_webhook_successful_acceptance_and_enqueue(self) -> None:
        mock_session = AsyncMock()
        campaign = WebsetCampaign(
            webset_id="wbs_123",
            campaign_id="camp_abc",
            workspace_id=42,
            webhook_secret="super-secret-token",
            status="pending",
            last_delivery_id=None,
        )
        res_mock = MagicMock()
        res_mock.scalar_one_or_none.return_value = campaign
        mock_session.execute.return_value = res_mock

        app = _make_test_app(mock_session)
        client = TestClient(app)

        with patch(
            "app.routes.chainlens_webhooks.import_webset_leads.delay"
        ) as mock_delay:
            response = client.post(
                "/api/v1/webhooks/chainlens/webset-idle?t=super-secret-token",
                json={
                    "event": "webset.idle",
                    "websetId": "wbs_123",
                    "id": "del_001",
                    "stats": {"readyCount": 42},
                },
            )

            assert response.status_code == 200
            assert response.json() == {
                "status": "accepted",
                "webset_id": "wbs_123",
            }
            assert campaign.last_delivery_id == "del_001"
            assert campaign.stats == {"readyCount": 42}
            mock_session.commit.assert_awaited_once()
            mock_delay.assert_called_once_with("wbs_123")

    def test_webhook_deduplication_same_delivery_id(self) -> None:
        mock_session = AsyncMock()
        campaign = WebsetCampaign(
            webset_id="wbs_123",
            campaign_id="camp_abc",
            workspace_id=42,
            webhook_secret="super-secret-token",
            status="pending",
            last_delivery_id="del_001",
        )
        res_mock = MagicMock()
        res_mock.scalar_one_or_none.return_value = campaign
        mock_session.execute.return_value = res_mock

        app = _make_test_app(mock_session)
        client = TestClient(app)

        with patch(
            "app.routes.chainlens_webhooks.import_webset_leads.delay"
        ) as mock_delay:
            response = client.post(
                "/api/v1/webhooks/chainlens/webset-idle?t=super-secret-token",
                json={
                    "event": "webset.idle",
                    "websetId": "wbs_123",
                    "id": "del_001",
                },
            )

            assert response.status_code == 200
            assert response.json() == {
                "status": "duplicate",
                "webset_id": "wbs_123",
            }
            # Must NOT enqueue again
            mock_delay.assert_not_called()

    def test_webhook_unauthorized_missing_token(self) -> None:
        mock_session = AsyncMock()
        app = _make_test_app(mock_session)
        client = TestClient(app)

        response = client.post(
            "/api/v1/webhooks/chainlens/webset-idle",
            json={
                "event": "webset.idle",
                "websetId": "wbs_123",
            },
        )
        assert response.status_code == 401

    def test_webhook_unauthorized_invalid_token(self) -> None:
        mock_session = AsyncMock()
        campaign = WebsetCampaign(
            webset_id="wbs_123",
            webhook_secret="correct-secret",
        )
        res_mock = MagicMock()
        res_mock.scalar_one_or_none.return_value = campaign
        mock_session.execute.return_value = res_mock

        app = _make_test_app(mock_session)
        client = TestClient(app)

        response = client.post(
            "/api/v1/webhooks/chainlens/webset-idle?t=wrong-secret",
            json={
                "event": "webset.idle",
                "websetId": "wbs_123",
            },
        )
        assert response.status_code == 401

    def test_webhook_invalid_event_type(self) -> None:
        mock_session = AsyncMock()
        app = _make_test_app(mock_session)
        client = TestClient(app)

        response = client.post(
            "/api/v1/webhooks/chainlens/webset-idle?t=token",
            json={
                "event": "webset.created",
                "websetId": "wbs_123",
            },
        )
        assert response.status_code == 400

    def test_webhook_webset_not_found(self) -> None:
        mock_session = AsyncMock()
        res_mock = MagicMock()
        res_mock.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = res_mock

        app = _make_test_app(mock_session)
        client = TestClient(app)

        response = client.post(
            "/api/v1/webhooks/chainlens/webset-idle?t=token",
            json={
                "event": "webset.idle",
                "websetId": "wbs_nonexistent",
            },
        )
        assert response.status_code == 200
        assert response.json() == {
            "status": "ignored",
            "webset_id": "wbs_nonexistent",
        }

    def test_webhook_non_dict_body_returns_400(self) -> None:
        """Valid JSON nhưng không phải object (list/scalar) -> 400, không 500."""
        mock_session = AsyncMock()
        app = _make_test_app(mock_session)
        client = TestClient(app)

        response = client.post(
            "/api/v1/webhooks/chainlens/webset-idle?t=token",
            json=["not", "a", "dict"],
        )
        assert response.status_code == 400

    def test_webhook_broker_failure_does_not_commit_delivery_id(self) -> None:
        """delay() raise -> non-2xx và last_delivery_id KHÔNG được commit,
        để retry của ChainLens vẫn import được."""
        mock_session = AsyncMock()
        campaign = WebsetCampaign(
            webset_id="wbs_123",
            campaign_id="camp_abc",
            workspace_id=42,
            webhook_secret="super-secret-token",
            status="pending",
            last_delivery_id=None,
        )
        res_mock = MagicMock()
        res_mock.scalar_one_or_none.return_value = campaign
        mock_session.execute.return_value = res_mock

        app = _make_test_app(mock_session)
        client = TestClient(app, raise_server_exceptions=False)

        with patch(
            "app.routes.chainlens_webhooks.import_webset_leads.delay",
            side_effect=ConnectionError("broker down"),
        ):
            response = client.post(
                "/api/v1/webhooks/chainlens/webset-idle?t=super-secret-token",
                json={
                    "event": "webset.idle",
                    "websetId": "wbs_123",
                    "id": "del_001",
                },
            )

        assert response.status_code >= 500
        assert campaign.last_delivery_id is None
        mock_session.commit.assert_not_awaited()
