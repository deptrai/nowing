"""Unit tests for TelecomSignalClassifier, AMD & Dead-air Watchdog (Story 38.5)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.voice.telecom_classifier import (
    AMDDetector,
    AntiSpamCircuitBreaker,
    CallSignal,
    DeadAirState,
    DeadAirWatchdog,
)

pytestmark = pytest.mark.unit


class TestAMDDetector:
    """Answering Machine Detection (AMD) in <= 3 seconds."""

    def test_short_human_opening_classifies_human(self):
        detector = AMDDetector(max_initial_speech_duration=1.8)
        result = detector.evaluate("Alo em nghe đây", duration_seconds=0.7)
        assert result.is_machine is False
        assert result.signal == CallSignal.HUMAN
        assert detector.is_evaluated is True

    @pytest.mark.parametrize(
        "phrase",
        [
            "Thuê bao quý khách vừa gọi hiện không liên lạc được",
            "Vui lòng để lại lời nhắn sau tiếng bíp",
            "Hop thu thoai cua so 090...",
            "The person you are trying to reach is not available, please leave a message",
            "This is the voicemail for",
        ],
    )
    def test_voicemail_keyphrases_classify_machine(self, phrase: str):
        detector = AMDDetector(max_initial_speech_duration=1.8)
        result = detector.evaluate(phrase, duration_seconds=1.2)
        assert result.is_machine is True
        assert result.signal == CallSignal.MACHINE_VOICEMAIL
        assert detector.is_evaluated is True

    @pytest.mark.parametrize(
        "phrase",
        [
            "Cảm ơn quý khách đã gọi đến công ty bất động sản ABC",
            "Bấm phím 1 để gặp bộ phận kinh doanh",
            "Nhan phim 0 de gap tong dai vien",
        ],
    )
    def test_ivr_keyphrases_classify_machine(self, phrase: str):
        detector = AMDDetector(max_initial_speech_duration=1.8)
        result = detector.evaluate(phrase, duration_seconds=1.5)
        assert result.is_machine is True
        assert result.signal == CallSignal.MACHINE_IVR

    def test_long_opening_monologue_exceeding_threshold_classifies_machine(self):
        """Speech > 1.8s without natural pause is characteristic of automated greetings."""
        detector = AMDDetector(max_initial_speech_duration=1.8)
        detector.on_speech_started(timestamp=100.0)
        detector.on_speech_ended(timestamp=102.2)  # 2.2s > 1.8s
        result = detector.evaluate("một chuỗi âm thanh dài chưa rõ nội dung")
        assert result.is_machine is True
        assert result.signal == CallSignal.MACHINE_VOICEMAIL

    def test_evaluation_is_sticky(self):
        """Once classified, AMD does not re-evaluate subsequent turns."""
        detector = AMDDetector(max_initial_speech_duration=1.8)
        res1 = detector.evaluate("Alo", duration_seconds=0.5)
        assert res1.signal == CallSignal.HUMAN

        # Second turn should return sticky human result
        res2 = detector.evaluate("Sau tiếng bíp", duration_seconds=2.5)
        assert res2.signal == CallSignal.HUMAN


class TestDeadAirWatchdog:
    """Dead-air 2-phase silence detection: probe at 3.0s, hangup before 8.0s."""

    def test_silence_below_3s_stays_awaiting_reply(self):
        dog = DeadAirWatchdog(probe_seconds=3.0, hangup_seconds=6.5)
        dog.on_bot_speech_stopped(timestamp=100.0)

        assert dog.check_silence(timestamp=102.5) == DeadAirState.AWAITING_REPLY

    def test_silence_at_3s_triggers_probe(self):
        dog = DeadAirWatchdog(probe_seconds=3.0, hangup_seconds=6.5)
        dog.on_bot_speech_stopped(timestamp=100.0)

        # 3.0s elapsed -> transition to PROBE_TRIGGERED
        assert dog.check_silence(timestamp=103.0) == DeadAirState.PROBE_TRIGGERED

    def test_probe_dispatched_moves_to_awaiting_probe_ack(self):
        dog = DeadAirWatchdog(probe_seconds=3.0, hangup_seconds=6.5)
        dog.on_bot_speech_stopped(timestamp=100.0)
        dog.check_silence(timestamp=103.0)
        dog.on_probe_dispatched(timestamp=103.2)

        assert dog.state == DeadAirState.AWAITING_PROBE_ACK

    def test_continued_silence_past_hangup_threshold_drops_call(self):
        dog = DeadAirWatchdog(probe_seconds=3.0, hangup_seconds=6.5)
        dog.on_bot_speech_stopped(timestamp=100.0)
        dog.check_silence(timestamp=103.0)
        dog.on_probe_dispatched(timestamp=103.2)

        # Total silence reaches 6.5s -> DEAD_AIR_HANGUP (before 8.0s)
        assert dog.check_silence(timestamp=106.6) == DeadAirState.DEAD_AIR_HANGUP

    def test_customer_speech_resets_watchdog_to_idle(self):
        dog = DeadAirWatchdog(probe_seconds=3.0, hangup_seconds=6.5)
        dog.on_bot_speech_stopped(timestamp=100.0)
        assert dog.state == DeadAirState.AWAITING_REPLY

        # Customer speaks at 2.0s
        dog.on_customer_speech_started()
        assert dog.state == DeadAirState.IDLE
        # Further checks do nothing while customer speaks
        assert dog.check_silence(timestamp=110.0) == DeadAirState.IDLE


class TestAntiSpamCircuitBreaker:
    """Campaign short-call rate (> 40%) and spam complaints (> 6%) auto-pause."""

    async def test_does_not_trip_under_30_calls_threshold(self):
        breaker = AntiSpamCircuitBreaker(min_calls=30, short_call_threshold=0.40)
        mock_redis = AsyncMock()
        mock_pipe = AsyncMock()
        # 15 calls total, all 15 short (100% rate)
        mock_pipe.execute = AsyncMock(return_value=[15])
        mock_redis.pipeline = lambda: mock_pipe
        mock_redis.hgetall = AsyncMock(
            return_value={"short_calls": "15", "spam_complaints": "0"}
        )

        with patch("app.services.voice.telecom_classifier.get_redis", return_value=mock_redis):
            status = await breaker.record_call_outcome(campaign_id=1, duration_seconds=3.0)

        assert status.total_calls == 15
        assert status.is_tripped is False  # Under 30 calls min threshold

    async def test_trips_when_short_call_rate_exceeds_40_percent_after_30_calls(self):
        breaker = AntiSpamCircuitBreaker(min_calls=30, short_call_threshold=0.40)
        mock_redis = AsyncMock()
        mock_pipe = AsyncMock()
        # 35 calls total, 16 short calls -> 16/35 = 45.7% > 40%
        mock_pipe.execute = AsyncMock(return_value=[35])
        mock_redis.pipeline = lambda: mock_pipe
        mock_redis.hgetall = AsyncMock(
            return_value={"short_calls": "16", "spam_complaints": "0"}
        )

        with patch("app.services.voice.telecom_classifier.get_redis", return_value=mock_redis):
            status = await breaker.record_call_outcome(campaign_id=1, duration_seconds=2.0)

        assert status.total_calls == 35
        assert status.is_tripped is True
        assert "Short call rate" in (status.trip_reason or "")

    async def test_trips_when_spam_complaint_rate_exceeds_6_percent(self):
        breaker = AntiSpamCircuitBreaker(min_calls=30, spam_threshold=0.06)
        mock_redis = AsyncMock()
        mock_pipe = AsyncMock()
        # 40 calls, 3 spam complaints -> 3/40 = 7.5% > 6%
        mock_pipe.execute = AsyncMock(return_value=[40])
        mock_redis.pipeline = lambda: mock_pipe
        mock_redis.hgetall = AsyncMock(
            return_value={"short_calls": "4", "spam_complaints": "3"}
        )

        with patch("app.services.voice.telecom_classifier.get_redis", return_value=mock_redis):
            status = await breaker.record_call_outcome(
                campaign_id=2, duration_seconds=45.0, is_spam_complaint=True
            )

        assert status.is_tripped is True
        assert "Spam complaint rate" in (status.trip_reason or "")

    async def test_healthy_campaign_remains_active(self):
        breaker = AntiSpamCircuitBreaker(min_calls=30, short_call_threshold=0.40)
        mock_redis = AsyncMock()
        mock_pipe = AsyncMock()
        # 50 calls, 5 short -> 10% rate (< 40%)
        mock_pipe.execute = AsyncMock(return_value=[50])
        mock_redis.pipeline = lambda: mock_pipe
        mock_redis.hgetall = AsyncMock(
            return_value={"short_calls": "5", "spam_complaints": "0"}
        )

        with patch("app.services.voice.telecom_classifier.get_redis", return_value=mock_redis):
            status = await breaker.record_call_outcome(campaign_id=3, duration_seconds=30.0)

        assert status.is_tripped is False

    async def test_redis_failure_fails_open(self):
        breaker = AntiSpamCircuitBreaker(min_calls=30)
        with patch("app.services.voice.telecom_classifier.get_redis", return_value=None):
            status = await breaker.record_call_outcome(campaign_id=99, duration_seconds=2.0)

        assert status.is_tripped is False
        assert status.total_calls == 1

    async def test_reset_clears_metrics(self):
        breaker = AntiSpamCircuitBreaker()
        mock_redis = AsyncMock()
        with patch("app.services.voice.telecom_classifier.get_redis", return_value=mock_redis):
            await breaker.reset(campaign_id=1)

        mock_redis.delete.assert_awaited_once_with("voice:campaign:metrics:1")
