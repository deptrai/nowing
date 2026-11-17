"""Unit tests for Voice Billing, Realtime Metering & QA Scorecard (Story 38.8)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.voice.billing import (
    calculate_telecom_block_charge,
    evaluate_bant_score,
    evaluate_hangup_protection,
    finalize_call_billing,
)

pytestmark = pytest.mark.unit


class TestTelecomBlockCharge:
    """6s + 1s block billing standard (2,500 VND/minute)."""

    def test_zero_duration_bills_nothing(self):
        billed, cost = calculate_telecom_block_charge(0.0)
        assert billed == 0
        assert cost == 0

    def test_negative_duration_returns_zero(self):
        billed, cost = calculate_telecom_block_charge(-5.0)
        assert billed == 0
        assert cost == 0

    def test_duration_under_6s_billed_as_6s_block(self):
        """5-second call is billed as a full 6-second block."""
        billed, cost = calculate_telecom_block_charge(5.0)
        assert billed == 6
        # 6s * (2,500,000 / 60) = 250,000 micros
        assert cost == 250_000

    def test_exactly_6s_billed_as_one_block(self):
        billed, cost = calculate_telecom_block_charge(6.0)
        assert billed == 6
        assert cost == 250_000

    def test_45s_call_billed_46_seconds(self):
        """45.2s -> 6s block + ceil(39.2) = 46s billed."""
        billed, cost = calculate_telecom_block_charge(45.2)
        assert billed == 46
        # 46 * (2,500,000 / 60) = 1,916,666.67 -> rounds to 1,916,667
        assert cost == 1_916_667

    def test_180s_hard_ceiling_full_charge(self):
        billed, cost = calculate_telecom_block_charge(178.0)
        # 6 + ceil(172) = 178s billed
        assert billed == 178
        # 178 * (2,500,000 / 60) = 7,416,666.67 -> 7,416,667
        assert cost == 7_416_667

    def test_180s_exactly_billed_180s(self):
        billed, cost = calculate_telecom_block_charge(180.0)
        assert billed == 180
        assert cost == 7_500_000

    def test_just_over_6s_adds_one_second(self):
        billed, _cost = calculate_telecom_block_charge(6.1)
        assert billed == 7  # 6s block + 1s

    def test_custom_rate(self):
        billed, cost = calculate_telecom_block_charge(
            60.0, rate_per_minute_micros=6_000_000
        )
        assert billed == 60
        assert cost == 6_000_000


class TestHangupProtection:
    """100% free for calls < 10s within campaign 15% quota."""

    async def test_short_call_within_quota_is_free(self):
        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {"total_calls": "50", "short_calls": "5"}

        with patch("app.services.voice.billing.get_redis", return_value=mock_redis):
            waived = await evaluate_hangup_protection(
                campaign_id=1, duration_seconds=4.5
            )

        assert waived is True

    async def test_short_call_exceeding_quota_is_charged(self):
        """Campaign has 22% short calls (> 15%) — no waiver, 6s block billed."""
        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {"total_calls": "50", "short_calls": "11"}

        with patch("app.services.voice.billing.get_redis", return_value=mock_redis):
            waived = await evaluate_hangup_protection(
                campaign_id=2, duration_seconds=5.0
            )

        assert waived is False

    async def test_long_call_never_qualifies(self):
        assert await evaluate_hangup_protection(None, 15.0) is False

    async def test_no_campaign_id_defaults_to_waiver(self):
        waived = await evaluate_hangup_protection(None, 5.0)
        assert waived is True

    async def test_redis_failure_fails_safe_to_waiver(self):
        with patch("app.services.voice.billing.get_redis", return_value=None):
            waived = await evaluate_hangup_protection(
                campaign_id=1, duration_seconds=5.0
            )
        assert waived is True


class TestFinalizeCallBilling:
    """2-phase commit wallet reconciliation."""

    async def test_partial_commit_and_release(self):
        """45s call: commit 1,875,000 micros, release remaining 5,625,000."""
        mock_session = MagicMock()
        user_id = uuid4()

        with (
            patch(
                "app.services.voice.billing.commit_reserved_credit",
                AsyncMock(return_value=0),
            ) as commit_mock,
            patch(
                "app.services.voice.billing.release_credit",
                AsyncMock(return_value=0),
            ) as release_mock,
        ):
            committed = await finalize_call_billing(
                mock_session,
                user_id,
                reserved_micros=7_500_000,
                actual_cost_micros=1_875_000,
            )

        assert committed == 1_875_000
        commit_mock.assert_awaited_once_with(mock_session, user_id, 1_875_000)
        release_mock.assert_awaited_once_with(mock_session, user_id, 5_625_000)

    async def test_zero_cost_releases_entire_deposit(self):
        """Hang-up protection: cost = 0, entire 7.5M micros released."""
        mock_session = MagicMock()
        user_id = uuid4()

        with (
            patch(
                "app.services.voice.billing.commit_reserved_credit", AsyncMock()
            ) as commit_mock,
            patch(
                "app.services.voice.billing.release_credit", AsyncMock()
            ) as release_mock,
        ):
            committed = await finalize_call_billing(
                mock_session, user_id, reserved_micros=7_500_000, actual_cost_micros=0
            )

        assert committed == 0
        commit_mock.assert_not_called()
        release_mock.assert_awaited_once_with(mock_session, user_id, 7_500_000)

    async def test_cost_exceeding_reserved_is_capped(self):
        """Commit cannot exceed the reserved deposit."""
        mock_session = MagicMock()
        user_id = uuid4()

        with (
            patch(
                "app.services.voice.billing.commit_reserved_credit", AsyncMock()
            ) as commit_mock,
            patch(
                "app.services.voice.billing.release_credit", AsyncMock()
            ) as release_mock,
        ):
            committed = await finalize_call_billing(
                mock_session,
                user_id,
                reserved_micros=7_500_000,
                actual_cost_micros=9_000_000,
            )

        # Commit capped at reserved amount; nothing left to release
        commit_mock.assert_awaited_once_with(mock_session, user_id, 7_500_000)
        release_mock.assert_not_awaited()
        assert committed == 7_500_000

    async def test_zero_reserved_is_noop(self):
        mock_session = MagicMock()
        with (
            patch(
                "app.services.voice.billing.commit_reserved_credit", AsyncMock()
            ) as c,
            patch("app.services.voice.billing.release_credit", AsyncMock()) as r,
        ):
            committed = await finalize_call_billing(mock_session, uuid4(), 0, 500)

        assert committed == 0
        c.assert_not_awaited()
        r.assert_not_awaited()


class TestBANTScorecard:
    """BANT scoring heuristics (Budget, Authority, Need, Timeline)."""

    def test_empty_transcript_scores_zero(self):
        score, breakdown = evaluate_bant_score("")
        assert score == 0
        assert breakdown == {"budget": 0, "authority": 0, "need": 0, "timeline": 0}

    def test_full_bant_transcript_scores_100(self):
        transcript = (
            "Bên em đang cần giải pháp tối ưu chi phí, ngân sách khoảng 200 triệu. "
            "Anh là giám đốc kinh doanh, anh quyết được. Tuần này anh có thể gặp em."
        )
        score, breakdown = evaluate_bant_score(transcript)
        assert score == 100
        assert breakdown == {"budget": 25, "authority": 25, "need": 25, "timeline": 25}

    async def test_rejection_transcript_scores_low(self):
        transcript = "Không có nhu cầu đâu, đừng gọi nữa"
        score, _breakdown = evaluate_bant_score(transcript)
        # 'không có nhu cầu' contains 'có nhu cầu' -> Need 25; but refusal dominates
        assert score < 50

    def test_partial_match_scores_correctly(self):
        transcript = "Bên em đang cần giải pháp, để anh xem báo giá tuần này nhé"
        score, _breakdown = evaluate_bant_score(transcript)
        # Need: "đang cần" ✓ (25), Authority: "để anh xem" ✓ (25),
        # Budget: "báo giá" ✓ (25), Timeline: "tuần này" ✓ (25)
        assert score == 100

    async def test_bant_score_via_decision_service(self, monkeypatch):
        from app.services.decision.types import Answer, DecisionResult
        from app.services.voice.billing import aevaluate_bant_score

        monkeypatch.setattr("app.config.decision.decision_enabled", lambda: True)
        monkeypatch.setattr(
            "app.config.decision.decision_task_enabled", lambda task: task == "voice"
        )

        class _MockDecisionService:
            async def decide(self, **kwargs):
                return DecisionResult(
                    answers={
                        "budget": Answer(kind="score", value=3.0, confidence=0.9),
                        "authority": Answer(kind="score", value=2.0, confidence=0.8),
                        "need": Answer(kind="score", value=2.0, confidence=0.85),
                        "timeline": Answer(kind="score", value=1.0, confidence=0.7),
                    },
                    model="jev-1.13.0",
                    backend="jev",
                    latency_ms=15.0,
                )

        monkeypatch.setattr(
            "app.services.decision.service.get_decision_service",
            lambda: _MockDecisionService(),
        )

        total, breakdown = await aevaluate_bant_score(
            "Khách hàng trao đổi qua điện thoại"
        )
        assert breakdown == {"budget": 25, "authority": 17, "need": 17, "timeline": 8}
        assert total == 67

    async def test_bant_score_decision_failure_falls_back_to_keywords(
        self, monkeypatch
    ):
        from app.services.voice.billing import aevaluate_bant_score

        monkeypatch.setattr("app.config.decision.decision_enabled", lambda: True)
        monkeypatch.setattr(
            "app.config.decision.decision_task_enabled", lambda task: task == "voice"
        )

        class _FailingDecisionService:
            async def decide(self, **kwargs):
                raise RuntimeError("Jev backend unavailable")

        monkeypatch.setattr(
            "app.services.decision.service.get_decision_service",
            lambda: _FailingDecisionService(),
        )

        transcript = "ngân sách khoảng 200 triệu, anh quyết được"
        total, breakdown = await aevaluate_bant_score(transcript)
        assert breakdown["budget"] == 25
        assert breakdown["authority"] == 25
        assert total >= 50
