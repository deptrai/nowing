"""Comprehensive API and route tests for ChainLens Websets idle webhook (Epic 41 / Story 41.1 & 41.2).

Covers:
- Status codes (200, 400, 401, 500)
- Response structure validation
- Idempotency & deduplication
- Secret token authentication & validation
- Fail-safe broker error handling (no phantom commit of delivery ID)
- Cost conversion and stats aggregation
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_async_session
from app.models.webset_campaign import WebsetCampaign
from app.routes.chainlens_webhooks import router

pytestmark = pytest.mark.unit


def _create_app_with_session(mock_session: AsyncMock) -> FastAPI:
    """Build a FastAPI test application with injected mock async session."""
    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_async_session] = lambda: mock_session
    return test_app


class TestChainLensWebsetsApiFlow:
    """API workflow & status code tests for Websets webhook endpoints."""

    def test_200_valid_webhook_accepted_and_dispatched(self) -> None:
        """Happy path: valid secret token, valid idle event, accepted & queued."""
        mock_session = AsyncMock()
        campaign = WebsetCampaign(
            webset_id="wbs_flow_01",
            campaign_id="camp_flow_01",
            workspace_id=1,
            webhook_secret="sec_flow_valid",
            status="pending",
            last_delivery_id=None,
            stats={"initial": "data"},
        )
        res_mock = MagicMock()
        res_mock.scalar_one_or_none.return_value = campaign
        mock_session.execute.return_value = res_mock

        app = _create_app_with_session(mock_session)
        client = TestClient(app)

        with patch(
            "app.routes.chainlens_webhooks.import_webset_leads.delay"
        ) as mock_delay:
            resp = client.post(
                "/api/v1/webhooks/chainlens/webset-idle?t=sec_flow_valid",
                json={
                    "event": "webset.idle",
                    "websetId": "wbs_flow_01",
                    "id": "del_flow_001",
                    "stats": {"readyCount": 25, "verifiedCount": 25},
                    "costDollars": 1.25,
                },
            )

            assert resp.status_code == 200
            assert resp.json() == {
                "status": "accepted",
                "webset_id": "wbs_flow_01",
            }
            # Verify database updates
            assert campaign.last_delivery_id == "del_flow_001"
            assert campaign.stats["cost_micros"] == 1_250_000
            assert campaign.stats["readyCount"] == 25
            assert campaign.stats["initial"] == "data"
            mock_session.commit.assert_awaited_once()
            mock_delay.assert_called_once_with("wbs_flow_01")

    def test_200_duplicate_delivery_id_idempotent_no_enqueue(self) -> None:
        """Idempotency: Re-delivery of same delivery ID returns status=duplicate and skips Celery."""
        mock_session = AsyncMock()
        campaign = WebsetCampaign(
            webset_id="wbs_flow_02",
            campaign_id="camp_flow_02",
            workspace_id=1,
            webhook_secret="sec_dup",
            status="pending",
            last_delivery_id="del_dup_already_processed",
        )
        res_mock = MagicMock()
        res_mock.scalar_one_or_none.return_value = campaign
        mock_session.execute.return_value = res_mock

        app = _create_app_with_session(mock_session)
        client = TestClient(app)

        with patch(
            "app.routes.chainlens_webhooks.import_webset_leads.delay"
        ) as mock_delay:
            resp = client.post(
                "/api/v1/webhooks/chainlens/webset-idle?t=sec_dup",
                json={
                    "event": "webset.idle",
                    "websetId": "wbs_flow_02",
                    "id": "del_dup_already_processed",
                },
            )

            assert resp.status_code == 200
            assert resp.json() == {
                "status": "duplicate",
                "webset_id": "wbs_flow_02",
            }
            # Celery MUST NOT be called again
            mock_delay.assert_not_called()

    def test_200_unknown_webset_returns_ignored(self) -> None:
        """Unknown webset in DB returns 200 with status=ignored so upstream stops retrying."""
        mock_session = AsyncMock()
        res_mock = MagicMock()
        res_mock.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = res_mock

        app = _create_app_with_session(mock_session)
        client = TestClient(app)

        resp = client.post(
            "/api/v1/webhooks/chainlens/webset-idle?t=any_token",
            json={
                "event": "webset.idle",
                "websetId": "wbs_not_in_db",
            },
        )
        assert resp.status_code == 200
        assert resp.json() == {
            "status": "ignored",
            "webset_id": "wbs_not_in_db",
        }

    def test_401_missing_secret_token_unauthorized(self) -> None:
        """Missing ?t= query parameter returns 401 Unauthorized."""
        mock_session = AsyncMock()
        app = _create_app_with_session(mock_session)
        client = TestClient(app)

        resp = client.post(
            "/api/v1/webhooks/chainlens/webset-idle",
            json={"event": "webset.idle", "websetId": "wbs_auth_01"},
        )
        assert resp.status_code == 401

    def test_401_invalid_secret_token_unauthorized(self) -> None:
        """Mismatched ?t= token returns 401 Unauthorized using constant-time comparison."""
        mock_session = AsyncMock()
        campaign = WebsetCampaign(
            webset_id="wbs_auth_02",
            webhook_secret="legitimate_secret_123",
        )
        res_mock = MagicMock()
        res_mock.scalar_one_or_none.return_value = campaign
        mock_session.execute.return_value = res_mock

        app = _create_app_with_session(mock_session)
        client = TestClient(app)

        resp = client.post(
            "/api/v1/webhooks/chainlens/webset-idle?t=tampered_or_wrong_secret",
            json={"event": "webset.idle", "websetId": "wbs_auth_02"},
        )
        assert resp.status_code == 401

    def test_400_invalid_event_type(self) -> None:
        """Event type other than webset.idle returns 400 Bad Request."""
        mock_session = AsyncMock()
        app = _create_app_with_session(mock_session)
        client = TestClient(app)

        resp = client.post(
            "/api/v1/webhooks/chainlens/webset-idle?t=token",
            json={"event": "webset.running", "websetId": "wbs_bad_event"},
        )
        assert resp.status_code == 400

    def test_400_missing_webset_id_in_payload(self) -> None:
        """Payload without websetId returns 400 Bad Request."""
        mock_session = AsyncMock()
        app = _create_app_with_session(mock_session)
        client = TestClient(app)

        resp = client.post(
            "/api/v1/webhooks/chainlens/webset-idle?t=token",
            json={"event": "webset.idle"},
        )
        assert resp.status_code == 400

    def test_400_non_dict_json_payload(self) -> None:
        """Array or scalar JSON root returns 400 instead of crashing with 500."""
        mock_session = AsyncMock()
        app = _create_app_with_session(mock_session)
        client = TestClient(app)

        resp = client.post(
            "/api/v1/webhooks/chainlens/webset-idle?t=token",
            json=["not", "a", "valid", "object"],
        )
        assert resp.status_code == 400

    def test_500_broker_failure_prevents_delivery_id_commit(self) -> None:
        """When task enqueue fails, delivery_id is NOT committed so retry can succeed."""
        mock_session = AsyncMock()
        campaign = WebsetCampaign(
            webset_id="wbs_fail_01",
            campaign_id="camp_fail_01",
            workspace_id=1,
            webhook_secret="sec_fail",
            status="pending",
            last_delivery_id=None,
        )
        res_mock = MagicMock()
        res_mock.scalar_one_or_none.return_value = campaign
        mock_session.execute.return_value = res_mock

        app = _create_app_with_session(mock_session)
        client = TestClient(app, raise_server_exceptions=False)

        with patch(
            "app.routes.chainlens_webhooks.import_webset_leads.delay",
            side_effect=RuntimeError("Redis connection lost"),
        ):
            resp = client.post(
                "/api/v1/webhooks/chainlens/webset-idle?t=sec_fail",
                json={
                    "event": "webset.idle",
                    "websetId": "wbs_fail_01",
                    "id": "del_fail_1",
                },
            )

        assert resp.status_code == 500
        # Critical verification: last_delivery_id must stay None so subsequent retries aren't dropped as duplicates
        assert campaign.last_delivery_id is None
        mock_session.commit.assert_not_awaited()
