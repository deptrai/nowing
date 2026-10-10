"""Unit tests for Voice AI SDR Celery background tasks (AI-38.2, AI-38.3)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit


def test_consume_prospect_engagement_stream_task():
    """consume_prospect_engagement_stream_task invokes the async consumer."""
    from app.tasks.celery_tasks.voice_tasks import (
        consume_prospect_engagement_stream_task,
    )

    with patch(
        "app.services.voice.outbound_trigger.consume_prospect_engagement_stream",
        new_callable=AsyncMock,
        return_value=5,
    ) as mock_consume:
        result = consume_prospect_engagement_stream_task()

    assert result == 5
    mock_consume.assert_awaited_once()


def test_process_post_call_qa_task():
    """process_post_call_qa_task runs post-call QA flow."""
    from app.tasks.celery_tasks.voice_tasks import process_post_call_qa_task

    lead_id = str(uuid4())
    expected_result = {"status": "processed", "billed_seconds": 18}

    with patch(
        "app.tasks.celery_tasks.voice_tasks._async_process_post_call_qa",
        new_callable=AsyncMock,
        return_value=expected_result,
    ) as mock_impl:
        result = process_post_call_qa_task(
            workspace_id=1,
            lead_id=lead_id,
            duration_seconds=15.0,
        )

    assert result == expected_result
    mock_impl.assert_awaited_once_with(
        workspace_id=1,
        lead_id=lead_id,
        user_id=None,
        call_session_id="",
        duration_seconds=15.0,
        transcript="",
        campaign_id=None,
        hangup_cause="completed",
        room_name=None,
    )


async def test_async_dispatch_voice_call_happy_path(monkeypatch):
    """_async_dispatch_voice_call creates room with metadata and dispatches SIP call."""
    import json

    from app.services.voice.compliance_gate import ComplianceCheckResult
    from app.tasks.celery_tasks.voice_tasks import _async_dispatch_voice_call

    user_id = str(uuid4())
    lead_id = str(uuid4())

    mock_session = AsyncMock()

    class _MockSessionCtx:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(
        "app.tasks.celery_tasks.voice_tasks.get_celery_session_maker",
        lambda: lambda: _MockSessionCtx(),
    )

    async def _approved(self, session, workspace_id, raw_phone, **kwargs):
        return ComplianceCheckResult.allow(
            phone_e164="+84988776655", lock_key="k", reserved_micros=7_500_000
        )

    monkeypatch.setattr(
        "app.services.voice.compliance_gate.TelephonyComplianceGate.evaluate_preflight",
        _approved,
    )
    monkeypatch.setattr(
        "app.services.voice.sip_manager.SipTrunkManager.resolve_workspace_trunk",
        AsyncMock(return_value=MagicMock(trunk_id="trunk_celery_1")),
    )

    calls = {}

    class _MockTelephony:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def create_call_room(self, session_id, metadata=None, **kwargs):
            calls["created_room"] = {
                "session_id": session_id,
                "metadata": json.loads(metadata) if metadata else None,
            }
            return MagicMock(name=session_id)

        async def dispatch_sip_outbound(self, **kwargs):
            calls["dispatched"] = kwargs
            return MagicMock(sip_call_id="sip_call_celery_123")

    monkeypatch.setattr(
        "app.services.voice.telephony_client.LiveKitTelephonyClient",
        _MockTelephony,
    )

    result = await _async_dispatch_voice_call(
        workspace_id=10,
        phone_e164="+84988776655",
        user_id=user_id,
        lead_id=lead_id,
    )

    assert result["status"] == "dispatched"
    assert result["sip_call_id"] == "sip_call_celery_123"
    assert result["trunk_id"] == "trunk_celery_1"
    assert result["reserved_micros"] == 7_500_000

    assert "created_room" in calls
    room_meta = calls["created_room"]["metadata"]
    assert room_meta["workspace_id"] == 10
    assert room_meta["user_id"] == user_id
    assert room_meta["lead_id"] == lead_id
    assert room_meta["phone_e164"] == "+84988776655"
    assert room_meta["session_id"].startswith("call_")

    assert "dispatched" in calls
    assert calls["dispatched"]["phone_number"] == "+84988776655"
    assert calls["dispatched"]["trunk_id"] == "trunk_celery_1"
    assert calls["dispatched"]["participant_identity"] == "sip_+84988776655"


async def test_async_dispatch_voice_call_compliance_rejected(monkeypatch):
    """_async_dispatch_voice_call returns rejected payload when compliance fails."""

    from app.services.voice.compliance_gate import ComplianceVerdict
    from app.tasks.celery_tasks.voice_tasks import _async_dispatch_voice_call

    class _MockSessionCtx:
        async def __aenter__(self):
            return AsyncMock()

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(
        "app.tasks.celery_tasks.voice_tasks.get_celery_session_maker",
        lambda: lambda: _MockSessionCtx(),
    )

    async def _rejected(self, session, workspace_id, raw_phone, **kwargs):
        return MagicMock(
            allowed=False,
            verdict=ComplianceVerdict.CURFEW_BLOCKED,
            reason="Night hours 21:00-08:00",
            phone_e164="+84988776655",
            reserved_micros=0,
        )

    monkeypatch.setattr(
        "app.services.voice.compliance_gate.TelephonyComplianceGate.evaluate_preflight",
        _rejected,
    )

    result = await _async_dispatch_voice_call(
        workspace_id=10,
        phone_e164="+84988776655",
    )

    assert result["status"] == "rejected"
    assert result["verdict"] == "CURFEW_BLOCKED"
    assert "Night hours" in result["reason"]
