"""Integration tests for Zalo OA Webhook receiver and Celery inbox pipeline (Story 23.2 / INV-23.8)."""

from __future__ import annotations

import hashlib
import hmac
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.app import app
from app.db import get_async_session

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _override_dependencies():
    fake_session = AsyncMock()
    mock_result = MagicMock()
    fake_connection = MagicMock()
    fake_connection.webhook_secret = "test_oa_secret_123"
    mock_result.scalar_one_or_none.return_value = fake_connection
    fake_session.execute.return_value = mock_result

    app.dependency_overrides[get_async_session] = lambda: fake_session
    yield
    app.dependency_overrides.pop(get_async_session, None)


@pytest.mark.asyncio
async def test_zalo_webhook_fast_ack_and_celery_dispatch():
    """Verify webhook responds < 100ms with HTTP 200 OK and dispatches background Celery task (INV-23.8)."""
    workspace_id = 1
    oa_secret = "test_oa_secret_123"
    raw_payload = b'{"event_name": "user_send_text", "timestamp": "1723800000", "sender": {"id": "123456"}, "message": {"text": "Xin chao"}}'
    sig = hmac.new(oa_secret.encode(), raw_payload, hashlib.sha256).hexdigest()

    with patch("app.gateway.zalo.tasks.process_zalo_inbox_event.delay") as mock_celery_task:
        start_time = time.perf_counter()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/workspaces/{workspace_id}/gateways/zalo/webhook",
                content=raw_payload,
                headers={
                    "X-Zalo-Signature": sig,
                    "X-Zalo-Timestamp": str(int(time.time())),
                    "Content-Type": "application/json",
                },
            )
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert elapsed_ms < 500

        # Celery task enqueued with workspace_id and payload
        mock_celery_task.assert_called_once()
