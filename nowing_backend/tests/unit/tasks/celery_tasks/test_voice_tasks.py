"""Unit tests for Voice AI SDR Celery background tasks (AI-38.2, AI-38.3)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
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
