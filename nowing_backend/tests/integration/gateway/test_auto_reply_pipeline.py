"""Integration tests for Story 24.6: Inbound Webhook -> Debounce -> RAG -> Telegram Alert Pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.gateway.telegram.callbacks import handle_telegram_callback_nhan_tu_van


@pytest.mark.integration
class TestAutoReplyPipelineIntegration:
    """Integration test suite for Story 24.6."""

    @pytest.mark.asyncio
    async def test_telegram_buying_intent_escalation_callback(self):
        """AC-3 / AC-4: Test clicking [Nhận Tư Vấn] assigns lead and sets 24h AI pause."""
        thread_id = "thread_zalo_lead_777"
        lead_id = "lead_888"
        admin_user_id = "user_admin_001"

        with patch("app.services.auto_reply_agent.get_redis_client") as mock_get_redis:
            redis_mock = AsyncMock()
            mock_get_redis.return_value = redis_mock

            # Execute callback action
            result = await handle_telegram_callback_nhan_tu_van(
                thread_id=thread_id,
                lead_id=lead_id,
                claimed_by_user_id=admin_user_id,
            )

            assert result["status"] == "success"
            assert result["thread_id"] == thread_id
            assert result["assigned_to"] == admin_user_id
            redis_mock.setex.assert_called_with(f"auto_reply_paused:{thread_id}", 86400, "1")

    @pytest.mark.asyncio
    async def test_nhan_tu_van_claims_lead_and_replies_prospect(self):
        """AC-3: [Nhận Tư Vấn] updates lead status and sends a prospect handoff message."""
        from uuid import UUID

        thread_id = "thread_zalo_lead_777"
        lead_id = str(uuid4())
        admin_user_id = str(uuid4())
        workspace_id = 42
        external_peer_id = "123456789"

        binding = MagicMock()
        binding.workspace_id = workspace_id
        binding.external_peer_id = external_peer_id
        binding.user_id = UUID(admin_user_id)

        lead = MagicMock()
        lead.status = "new"

        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = lead

        session = AsyncMock()
        session.execute.return_value = execute_result

        adapter = AsyncMock()

        with patch("app.services.auto_reply_agent.get_redis_client") as mock_get_redis:
            redis_mock = AsyncMock()
            mock_get_redis.return_value = redis_mock

            result = await handle_telegram_callback_nhan_tu_van(
                thread_id=thread_id,
                lead_id=lead_id,
                claimed_by_user_id=admin_user_id,
                session=session,
                adapter=adapter,
                binding=binding,
            )

            assert result["status"] == "success"
            assert lead.status == "warm"
            assert lead.user_id == binding.user_id
            session.commit.assert_awaited_once()
            adapter.send_message.assert_awaited_once()
            assert adapter.send_message.call_args.kwargs["external_peer_id"] == external_peer_id
