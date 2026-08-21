"""Unit tests for Story 24.6: Two-Way AI Outreach Auto-Reply Agent & Intent Classifier.

Tests adhere to INV-24.7 (temperature=0.0, >=0.75 cosine threshold),
INV-24.8 (Human Escalation & 24h AI Pause), and 3s Inbound Debounce Buffer.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.auto_reply_agent import (
    AutoReplyAgent,
    InboundIntentClassifier,
    is_auto_reply_paused,
    pause_auto_reply,
)
from app.services.inbound_debounce_service import (
    InboundDebounceService,
)


@pytest.mark.unit
class TestAutoReplyAgentUnit:
    """ATDD Unit Tests for Story 24.6."""

    @pytest.mark.asyncio
    async def test_inbound_debounce_buffer_aggregation(self):
        """AC-1: Test rapid-fire burst messages are buffered and merged."""
        redis_mock = AsyncMock()
        service = InboundDebounceService(redis_client=redis_mock)

        channel = "zalo_oa"
        sender_id = "prospect_123"

        # Test empty input guard
        buffered_empty = await service.buffer_inbound_message(channel, sender_id, "   ")
        assert buffered_empty is False

        # Mock Redis list responses via Lua eval
        redis_mock.eval.return_value = [
            b"Xin chao",
            b"Minh muon hoi gia can 2 phong ngu",
            b"Co ho tro tra gop khong ban?",
        ]

        # Flush & Aggregate
        combined = await service.flush_and_aggregate_messages(channel, sender_id)
        assert "Xin chao" in combined
        assert "Minh muon hoi gia can 2 phong ngu" in combined
        assert "Co ho tro tra gop khong ban?" in combined

    @pytest.mark.asyncio
    async def test_rag_grounded_factual_answering_and_fallback(self):
        """AC-2: Test RAG retrieval >= 0.75 threshold and safe fallback."""
        agent = AutoReplyAgent()

        with patch("app.services.auto_reply_agent.is_auto_reply_paused", new_callable=AsyncMock, return_value=False):
            # Case 1: High Similarity Chunks Found (Cosine >= 0.75)
            with (
                patch.object(
                    agent,
                    "_retrieve_knowledge_chunks",
                    new_callable=AsyncMock,
                    return_value=[
                        {
                            "content": "Căn hộ 2PN Grand Park giá từ 2.8 tỷ, hỗ trợ vay 70% trong 20 năm.",
                            "similarity": 0.88,
                        }
                    ],
                ),
                patch.object(
                    agent,
                    "_generate_llm_response",
                    new_callable=AsyncMock,
                    return_value="Dạ căn hộ 2PN Grand Park hiện có giá từ 2.8 tỷ và được hỗ trợ vay ngân hàng đến 70% ạ!",
                ),
            ):
                result = await agent.generate_reply(
                    workspace_id=15,
                    channel="zalo_oa",
                    sender_id="user_123",
                    text="Căn 2 phòng ngủ giá bao nhiêu?",
                    thread_id="th_123",
                )
                assert result.is_answered is True
                assert result.is_fallback is False
                assert "2.8 tỷ" in result.reply_text

            # Case 2: Low Similarity Chunks (< 0.75) -> Safe Fallback Triggered
            with patch.object(
                agent,
                "_retrieve_knowledge_chunks",
                new_callable=AsyncMock,
                return_value=[
                    {
                        "content": "Thông tin thời tiết khu vực quận 9.",
                        "similarity": 0.52,
                    }
                ],
            ):
                result_fallback = await agent.generate_reply(
                    workspace_id=15,
                    channel="zalo_oa",
                    sender_id="user_123",
                    text="Có chiết khấu riêng 50% cho người quen không?",
                    thread_id="th_123",
                )
                assert result_fallback.is_fallback is True
                assert "chuyển chuyên viên phụ trách" in result_fallback.reply_text

    def test_buying_intent_classification_scores(self):
        """AC-3: Test buying intent classification triggers on hot phrases."""
        classifier = InboundIntentClassifier()

        # Hot buying signals
        score_hot, reason, is_hot = classifier.evaluate_intent("Cho mình xin bảng giá chi tiết và lịch hẹn xem nhà thứ 7 này")
        assert is_hot is True
        assert score_hot >= 0.80
        assert "bảng giá" in reason or "xem nhà" in reason

        # Normal inquiry / generic question
        score_normal, _, is_hot_normal = classifier.evaluate_intent("Công ty mình thành lập từ năm nào vậy?")
        assert is_hot_normal is False
        assert score_normal < 0.80

    @pytest.mark.asyncio
    async def test_human_takeover_24h_pause_guard(self):
        """AC-4: Test human takeover sets 24h pause preventing AI reply."""
        thread_id = "thread_zalo_999"

        with patch("app.services.auto_reply_agent.get_redis_client") as mock_get_redis:
            redis_mock = AsyncMock()
            mock_get_redis.return_value = redis_mock

            # Pause auto-reply
            await pause_auto_reply(thread_id, duration_seconds=86400)
            redis_mock.setex.assert_called_with(f"auto_reply_paused:{thread_id}", 86400, "1")

            # Check paused state
            redis_mock.exists.return_value = 1
            paused = await is_auto_reply_paused(thread_id)
            assert paused is True

    @pytest.mark.asyncio
    async def test_inbound_debounce_distributed_lock_prevents_double_flush(self):
        """Double-flush is prevented by the Redis distributed lock."""
        redis_mock = AsyncMock()
        # First call gets the lock; second call is denied.
        redis_mock.set.side_effect = [True, False]
        redis_mock.eval.return_value = [b"msg"]

        service = InboundDebounceService(redis_client=redis_mock)
        first = await service.flush_and_aggregate_messages("zalo_oa", "prospect_123")
        second = await service.flush_and_aggregate_messages("zalo_oa", "prospect_123")

        assert first == "msg"
        assert second == ""

    @pytest.mark.asyncio
    async def test_hot_lead_alert_dispatched(self):
        """Hot buying intent triggers the hot-lead alert dispatch."""
        agent = AutoReplyAgent()

        session = AsyncMock()

        with (
            patch("app.services.auto_reply_agent.is_auto_reply_paused", new_callable=AsyncMock, return_value=False),
            patch.object(
                agent,
                "_retrieve_knowledge_chunks",
                new_callable=AsyncMock,
                return_value=[
                    {
                        "content": "Căn hộ 2PN Grand Park giá từ 2.8 tỷ.",
                        "similarity": 0.88,
                    }
                ],
            ),
            patch.object(
                agent,
                "_generate_llm_response",
                new_callable=AsyncMock,
                return_value="Dạ căn hộ 2PN giá từ 2.8 tỷ ạ.",
            ),
            patch.object(agent, "_dispatch_hot_lead_alert", new_callable=AsyncMock) as mock_alert,
        ):
            result = await agent.generate_reply(
                workspace_id=15,
                channel="zalo_oa",
                sender_id="user_123",
                text="Cho mình xin bảng giá chi tiết và lịch hẹn xem nhà",
                thread_id="th_123",
                session=session,
            )
            assert result.is_hot_intent is True
            mock_alert.assert_awaited_once()
