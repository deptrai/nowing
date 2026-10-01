"""Unit tests for TelephonyComplianceGate (Story 38.4 / Decree 91 / Decree 13 PDPD)."""

from __future__ import annotations

import unicodedata
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.sequencer.constants import VN_TZ
from app.services.voice.compliance_gate import (
    ComplianceVerdict,
    TelephonyComplianceGate,
    is_dtmf_opt_out,
    is_opt_out_utterance,
)

pytestmark = pytest.mark.unit


def _ict(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=VN_TZ)


@pytest.fixture
def gate():
    return TelephonyComplianceGate(
        secret_key="test_compliance_secret",
        soft_lock_micros=7_500_000,
    )


@pytest.fixture
def mock_session():
    return AsyncMock()


class TestCurfewLayer:
    """Layer 1: Decree 91 split calling window."""

    def test_curfew_blocks_outside_hours(self, gate: TelephonyComplianceGate):
        night = _ict(2026, 10, 5, 22, 0)
        assert gate.is_curfew(night) is True

    def test_curfew_blocks_lunch_break(self, gate: TelephonyComplianceGate):
        lunch = _ict(2026, 10, 5, 12, 15)
        assert gate.is_curfew(lunch) is True

    def test_curfew_allows_morning_window(self, gate: TelephonyComplianceGate):
        morning = _ict(2026, 10, 5, 10, 0)
        assert gate.is_curfew(morning) is False

    def test_curfew_allows_afternoon_window(self, gate: TelephonyComplianceGate):
        afternoon = _ict(2026, 10, 5, 15, 0)
        assert gate.is_curfew(afternoon) is False

    def test_curfew_blocks_weekend(self, gate: TelephonyComplianceGate):
        sunday = _ict(2026, 10, 11, 10, 0)
        assert gate.is_curfew(sunday) is True


class TestFrequencyCapLayer:
    """Layer 2: 24h frequency cap per E.164 phone per workspace."""

    async def test_first_call_acquires_lock(self, gate: TelephonyComplianceGate):
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True

        with patch("app.services.voice.compliance_gate.get_redis", return_value=mock_redis):
            acquired = await gate.acquire_frequency_lock(15, "+84901234567")

        assert acquired is True
        mock_redis.set.assert_called_once()
        args, kwargs = mock_redis.set.call_args
        assert args[0].startswith("voice:freq:15:")
        assert kwargs["ex"] == 86400
        assert kwargs["nx"] is True

    async def test_second_call_within_24h_is_blocked(self, gate: TelephonyComplianceGate):
        mock_redis = AsyncMock()
        mock_redis.set.return_value = False  # NX failed -> key already exists

        with patch("app.services.voice.compliance_gate.get_redis", return_value=mock_redis):
            acquired = await gate.acquire_frequency_lock(15, "+84901234567")

        assert acquired is False

    async def test_redis_failure_fails_closed(self, gate: TelephonyComplianceGate):
        """If Redis is down, we must not call to prevent spam violations."""
        with patch("app.services.voice.compliance_gate.get_redis", return_value=None):
            assert await gate.acquire_frequency_lock(15, "+84901234567") is False


class TestDNCLayer:
    """Layer 3: National DNC 5656 & Workspace DNC."""

    async def test_dnc_blocked_phone(self, gate: TelephonyComplianceGate, mock_session):
        mock_result = MagicMock()
        mock_result.is_blocked = True

        with patch(
            "app.lead_intelligence.dnc.service.DncComplianceService.check_phone",
            AsyncMock(return_value=mock_result),
        ):
            blocked = await gate.check_dnc(15, "+84901234567", session=mock_session)

        assert blocked is True

    async def test_dnc_clear_phone(self, gate: TelephonyComplianceGate, mock_session):
        mock_result = MagicMock()
        mock_result.is_blocked = False

        with patch(
            "app.lead_intelligence.dnc.service.DncComplianceService.check_phone",
            AsyncMock(return_value=mock_result),
        ):
            blocked = await gate.check_dnc(15, "+84901234567", session=mock_session)

        assert blocked is False

    async def test_dnc_failure_fails_closed(
        self, gate: TelephonyComplianceGate, mock_session
    ):
        with patch(
            "app.lead_intelligence.dnc.service.DncComplianceService.check_phone",
            AsyncMock(side_effect=RuntimeError("DB timeout")),
        ):
            assert await gate.check_dnc(15, "+84901234567", session=mock_session) is True


class TestPreflightOrchestrator:
    """Full 4-layer pre-flight check in sequence."""

    async def test_all_layers_pass(self, gate: TelephonyComplianceGate, mock_session):
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True

        mock_dnc = MagicMock()
        mock_dnc.is_blocked = False

        legal_time = _ict(2026, 10, 5, 10, 0)
        user_id = uuid4()

        with (
            patch("app.services.voice.compliance_gate.get_redis", return_value=mock_redis),
            patch(
                "app.lead_intelligence.dnc.service.DncComplianceService.check_phone",
                AsyncMock(return_value=mock_dnc),
            ),
            patch(
                "app.services.wallet_credit.reserve_credit",
                AsyncMock(return_value=7_500_000),
            ),
        ):
            result = await gate.evaluate_preflight(
                mock_session,
                workspace_id=15,
                raw_phone="0901234567",
                user_id=user_id,
                now=legal_time,
            )

        assert result.allowed is True
        assert result.verdict == ComplianceVerdict.APPROVED
        assert result.phone_e164 == "+84901234567"
        assert result.reserved_micros == 7_500_000

    async def test_curfew_rejects_first(self, gate: TelephonyComplianceGate, mock_session):
        curfew_time = _ict(2026, 10, 5, 23, 0)
        result = await gate.evaluate_preflight(
            mock_session,
            workspace_id=15,
            raw_phone="0901234567",
            now=curfew_time,
        )
        assert result.allowed is False
        assert result.verdict == ComplianceVerdict.CURFEW_BLOCKED

    async def test_invalid_phone_rejected(self, gate: TelephonyComplianceGate, mock_session):
        legal_time = _ict(2026, 10, 5, 10, 0)
        result = await gate.evaluate_preflight(
            mock_session,
            workspace_id=15,
            raw_phone="invalid_phone_string",
            now=legal_time,
        )
        assert result.allowed is False
        assert result.verdict == ComplianceVerdict.INVALID_PHONE

    async def test_dnc_blocks_before_frequency_lock(
        self, gate: TelephonyComplianceGate, mock_session
    ):
        """DNC check must run before frequency lock so blocked numbers don't burn the lock."""
        legal_time = _ict(2026, 10, 5, 10, 0)
        mock_dnc = MagicMock()
        mock_dnc.is_blocked = True
        mock_redis = AsyncMock()

        with (
            patch("app.services.voice.compliance_gate.get_redis", return_value=mock_redis),
            patch(
                "app.lead_intelligence.dnc.service.DncComplianceService.check_phone",
                AsyncMock(return_value=mock_dnc),
            ),
        ):
            result = await gate.evaluate_preflight(
                mock_session,
                workspace_id=15,
                raw_phone="0901234567",
                now=legal_time,
            )

        assert result.allowed is False
        assert result.verdict == ComplianceVerdict.DNC_BLOCKED
        mock_redis.set.assert_not_called()  # Lock NOT acquired

    async def test_insufficient_funds_releases_frequency_lock(
        self, gate: TelephonyComplianceGate, mock_session
    ):
        """If wallet deposit fails, the frequency lock must be released immediately."""
        legal_time = _ict(2026, 10, 5, 10, 0)
        mock_dnc = MagicMock()
        mock_dnc.is_blocked = False

        mock_redis = AsyncMock()
        mock_redis.set.return_value = True
        mock_redis.delete = AsyncMock()

        with (
            patch("app.services.voice.compliance_gate.get_redis", return_value=mock_redis),
            patch(
                "app.lead_intelligence.dnc.service.DncComplianceService.check_phone",
                AsyncMock(return_value=mock_dnc),
            ),
            patch(
                "app.services.wallet_credit.reserve_credit",
                AsyncMock(side_effect=RuntimeError("Insufficient credits")),
            ),
        ):
            result = await gate.evaluate_preflight(
                mock_session,
                workspace_id=15,
                raw_phone="0901234567",
                user_id=uuid4(),
                now=legal_time,
            )
        assert result.allowed is False
        assert result.verdict == ComplianceVerdict.INSUFFICIENT_FUNDS
        mock_redis.delete.assert_called_once()  # Released!


class TestDepositRelease:
    """Pre-call wallet soft-lock release on failed/rejected calls."""

    async def test_release_deposit_restores_reserved_funds(self):
        """release_deposit must call wallet_credit.release_credit with the amount."""
        from app.services.voice.compliance_gate import TelephonyComplianceGate as G

        mock_session = AsyncMock()
        user_id = uuid4()

        with patch(
            "app.services.wallet_credit.release_credit",
            AsyncMock(return_value=0),
        ) as release_mock:
            await G.release_deposit(mock_session, user_id, 7_500_000)

        release_mock.assert_awaited_once_with(mock_session, user_id, 7_500_000)

    async def test_release_frequency_lock_deletes_redis_key(
        self, gate: TelephonyComplianceGate
    ):
        mock_redis = AsyncMock()
        with patch("app.services.voice.compliance_gate.get_redis", return_value=mock_redis):
            await gate.release_frequency_lock(15, "+84901234567")

        mock_redis.delete.assert_awaited_once()
        key = mock_redis.delete.call_args[0][0]
        assert key.startswith("voice:freq:15:")

    async def test_release_frequency_lock_noop_when_redis_down(
        self, gate: TelephonyComplianceGate
    ):
        """Redis unavailable must not raise — release is best-effort."""
        with patch("app.services.voice.compliance_gate.get_redis", return_value=None):
            await gate.release_frequency_lock(15, "+84901234567")  # no raise

    async def test_optout_phrase_phien_qua_triggers_hard_optout(self):
        """'phiền quá' is a hard opt-out per spec I/O matrix."""
        assert is_opt_out_utterance("thôi phiền quá đi") is True
        assert is_opt_out_utterance("phien qua") is True

    async def test_nfd_diacritics_still_match(self):
        """STT may emit NFD combining diacritics — matching must survive."""
        nfd_text = unicodedata.normalize("NFD", "đừng gọi nữa")
        assert is_opt_out_utterance(nfd_text) is True


class TestOptOutHelpers:
    """Vietnamese customer refusal & DTMF opt-out detectors."""

    @pytest.mark.parametrize(
        "phrase",
        [
            "đừng gọi nữa em ơi",
            "Dạ thôi đừng gọi nữa",
            "anh không có nhu cầu đâu",
            "khong co nhu cau nhe",
            "làm phiền quá đấy",
            "xóa số tôi đi",
            "xoa so khoi he thong dum",
            "anh không quan tâm",
        ],
    )
    def test_recognizes_vietnamese_hard_optouts(self, phrase: str):
        assert is_opt_out_utterance(phrase) is True

    @pytest.mark.parametrize(
        "phrase",
        [
            "chào em",
            "dạ vâng",
            "ừ anh nghe",
            "giá cả thế nào",
            "gửi thông tin qua zalo cho anh nhé",
            "ok em",
        ],
    )
    def test_does_not_false_positive_on_normal_conversation(self, phrase: str):
        assert is_opt_out_utterance(phrase) is False

    @pytest.mark.parametrize("key", ["0", "9", 0, 9])
    def test_dtmf_keys_0_and_9_trigger_optout(self, key):
        assert is_dtmf_opt_out(key) is True

    @pytest.mark.parametrize("key", ["1", "2", "#", "*", 5])
    def test_other_dtmf_keys_do_not_optout(self, key):
        assert is_dtmf_opt_out(key) is False
