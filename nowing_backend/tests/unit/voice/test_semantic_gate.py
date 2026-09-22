"""Unit tests for the voice semantic gate (Story 39.6).

Covers the I/O matrix: flag gating (zero overhead), transcript noise
skip, suppress/transfer confidence bars, frustration logging, and
fail-open on every backend failure mode.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.decision.errors import DecisionError, InvalidDecisionAnswer
from app.services.decision.questions import get_question_registry
from app.services.decision.types import Answer, DecisionResult
from app.services.voice import semantic_gate
from app.services.voice.semantic_gate import (
    VoiceTurnAssessment,
    evaluate_voice_turn,
)


def _noul(value: float) -> Answer:
    return Answer(kind="noul", value=value, confidence=value)


def _score(value: float) -> Answer:
    return Answer(kind="score", value=value, confidence=0.9)


def _result(answers: dict[str, Answer]) -> DecisionResult:
    return DecisionResult(
        answers=answers,
        model="jev-1.13.0",
        backend="jev",
        latency_ms=120.0,
    )


def _answers(
    should_respond: float = 0.9,
    frustration: float = 0.0,
    transfer: float = 0.1,
) -> dict[str, Answer]:
    return {
        "should_respond": _noul(should_respond),
        "caller_frustration": _score(frustration),
        "transfer_to_human": _noul(transfer),
    }


@pytest.fixture
def flags_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DECISION_ENABLED", "true")
    monkeypatch.setenv("DECISION_VOICE_ENABLED", "true")


@pytest.fixture
def mock_decide(flags_on):
    """Patch the decision service singleton; yield its decide mock."""
    service = MagicMock()
    service.decide = AsyncMock(return_value=_result(_answers()))
    with patch.object(
        semantic_gate, "get_decision_service", return_value=service
    ):
        yield service.decide


@pytest.mark.unit
class TestVoiceTurnQuestionSet:
    """The voice_turn set is registered with the contract shape."""

    def test_registered_with_expected_questions(self):
        qs = get_question_registry().get_set("voice_turn")
        assert qs.name == "voice_turn"
        assert qs.version == "1.0.0"
        assert list(qs.questions) == [
            "should_respond",
            "caller_frustration",
            "transfer_to_human",
        ]
        assert qs.required_state_keys == ("transcript",)


@pytest.mark.unit
class TestEvaluateVoiceTurnGating:
    """Flag and transcript gates — zero paid calls when they trip."""

    @pytest.mark.asyncio
    async def test_master_flag_off_is_zero_overhead(self, monkeypatch):
        monkeypatch.setenv("DECISION_ENABLED", "false")
        service = MagicMock()
        service.decide = AsyncMock()
        with patch.object(
            semantic_gate, "get_decision_service", return_value=service
        ) as factory:
            assessment = await evaluate_voice_turn("cho tôi hỏi giá nhà quận 7")
        assert assessment == VoiceTurnAssessment()
        factory.assert_not_called()
        service.decide.assert_not_called()

    @pytest.mark.asyncio
    async def test_voice_task_flag_off_skips_decide(self, monkeypatch):
        monkeypatch.setenv("DECISION_ENABLED", "true")
        monkeypatch.setenv("DECISION_VOICE_ENABLED", "false")
        service = MagicMock()
        service.decide = AsyncMock()
        with patch.object(
            semantic_gate, "get_decision_service", return_value=service
        ):
            assessment = await evaluate_voice_turn("cho tôi hỏi giá nhà quận 7")
        assert assessment == VoiceTurnAssessment()
        service.decide.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "transcript", ["", "   ", "ab", "a ", None, 123]
    )
    async def test_short_or_noise_transcript_skips_decide(
        self, mock_decide, transcript
    ):
        assessment = await evaluate_voice_turn(transcript)
        assert assessment == VoiceTurnAssessment()
        mock_decide.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "transcript", ["ừ", "Ừ.", "vâng ạ", "  à  ", "ừm,", "ư", "dạ!"]
    )
    async def test_local_backchannel_suppresses_without_call(
        self, mock_decide, transcript
    ):
        """Pure backchannels suppress locally — zero Jev calls even for
        utterances under the 3-char minimum."""
        assessment = await evaluate_voice_turn(transcript)
        assert assessment.suppress_response is True
        assert assessment.transfer is False
        mock_decide.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_backchannel_short_utterance_still_skips(
        self, mock_decide
    ):
        """A short non-backchannel ('ab') skips decide AND responds."""
        assessment = await evaluate_voice_turn("ab")
        assert assessment == VoiceTurnAssessment()
        mock_decide.assert_not_called()


@pytest.mark.unit
class TestEvaluateVoiceTurnDecisions:
    """Answer → assessment mapping at the pinned 0.7 bars."""

    @pytest.mark.asyncio
    async def test_normal_utterance_responds(self, mock_decide):
        assessment = await evaluate_voice_turn("cho tôi hỏi giá nhà quận 7")
        assert assessment.suppress_response is False
        assert assessment.transfer is False
        mock_decide.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_suppress_when_confidently_no(self, mock_decide):
        # 1 - 0.1 = 0.9 >= 0.7 → suppress
        mock_decide.return_value = _result(_answers(should_respond=0.1))
        assessment = await evaluate_voice_turn("vâng ạ")
        assert assessment.suppress_response is True
        assert assessment.transfer is False

    @pytest.mark.asyncio
    async def test_no_suppress_below_pinned_bar(self, mock_decide):
        # 1 - 0.4 = 0.6 < 0.7 — the task gate's 0.5 default must NOT
        # suppress here (spec: pin the bar at 0.7).
        mock_decide.return_value = _result(_answers(should_respond=0.4))
        assessment = await evaluate_voice_turn("à ừ vâng")
        assert assessment.suppress_response is False

    @pytest.mark.asyncio
    async def test_uncertain_noul_responds(self, mock_decide):
        mock_decide.return_value = _result(
            _answers(should_respond=0.5, transfer=0.5)
        )
        assessment = await evaluate_voice_turn("thì ừm chắc là")
        assert assessment == VoiceTurnAssessment(frustration_score=0.0)

    @pytest.mark.asyncio
    async def test_transfer_when_confident(self, mock_decide):
        mock_decide.return_value = _result(_answers(transfer=0.8))
        assessment = await evaluate_voice_turn(
            "cho tôi nói chuyện với người thật"
        )
        assert assessment.transfer is True
        assert assessment.suppress_response is False

    @pytest.mark.asyncio
    async def test_transfer_below_bar_ignored(self, mock_decide):
        # 0.6 passes the 0.5 task gate but not the pinned 0.7 bar.
        mock_decide.return_value = _result(_answers(transfer=0.6))
        assessment = await evaluate_voice_turn("gặp người thật được không")
        assert assessment.transfer is False

    @pytest.mark.asyncio
    async def test_transfer_and_suppress_both_set(self, mock_decide):
        # Both fire — the assessment carries both flags; the consumer
        # escalates first and ignores suppression (spec precedence).
        mock_decide.return_value = _result(
            _answers(should_respond=0.0, transfer=0.95)
        )
        assessment = await evaluate_voice_turn(
            "cho tôi gặp người thật, đừng nói nữa"
        )
        assert assessment.transfer is True
        assert assessment.suppress_response is True

    @pytest.mark.asyncio
    async def test_frustration_score_returned(self, mock_decide):
        mock_decide.return_value = _result(_answers(frustration=2.4))
        assessment = await evaluate_voice_turn("sao gọi hoài vậy, phiền quá")
        assert assessment.frustration_score == pytest.approx(2.4)
        # Frustration alone never suppresses or transfers.
        assert assessment.suppress_response is False
        assert assessment.transfer is False

    @pytest.mark.asyncio
    async def test_frustration_score_logged(self, mock_decide, caplog):
        """The [voice_turn] frustration=N structured line is emitted."""
        mock_decide.return_value = _result(_answers(frustration=2.4))
        with caplog.at_level(
            "INFO", logger="app.services.voice.semantic_gate"
        ):
            await evaluate_voice_turn("sao gọi hoài vậy, phiền quá")
        assert "[voice_turn] frustration=2.4" in caplog.text

    @pytest.mark.asyncio
    async def test_decide_called_with_voice_task_no_fallback(
        self, mock_decide
    ):
        workspace_id, user_id = 42, uuid4()
        await evaluate_voice_turn(
            "cho tôi hỏi giá nhà",
            workspace_id=workspace_id,
            user_id=user_id,
            client_id="call-sess-9",
        )
        args, kwargs = mock_decide.call_args
        # transcript state is the positional first arg
        assert args[0] == {"transcript": "cho tôi hỏi giá nhà"}
        assert kwargs["task"] == "voice"
        assert kwargs["use_fallback"] is False
        assert kwargs["timeout"] == 0.45
        assert kwargs["question_set"] == "voice_turn@1.0.0"
        assert kwargs["required_state_keys"] == ("transcript",)
        assert kwargs["workspace_id"] == workspace_id
        assert kwargs["user_id"] == user_id
        assert kwargs["client_id"] == "call-sess-9"
        # An AgentSession is not an AsyncSession — session is never
        # forwarded; _record_usage opens its own.
        assert "session" not in kwargs

    @pytest.mark.asyncio
    async def test_long_transcript_truncated_before_paid_call(
        self, mock_decide
    ):
        """Transcripts are capped at _MAX_TRANSCRIPT_CHARS (4000)."""
        await evaluate_voice_turn("x" * 5000)
        args, _ = mock_decide.call_args
        assert args[0]["transcript"] == "x" * 4000


@pytest.mark.unit
class TestEvaluateVoiceTurnFailOpen:
    """Every failure mode resolves to respond-normally defaults."""

    @pytest.mark.asyncio
    async def test_decision_error_fails_open(self, mock_decide):
        mock_decide.side_effect = DecisionError("boom", code="timeout")
        assessment = await evaluate_voice_turn("cho tôi hỏi giá nhà")
        assert assessment == VoiceTurnAssessment()

    @pytest.mark.asyncio
    async def test_invalid_answer_fails_open(self, mock_decide):
        mock_decide.side_effect = InvalidDecisionAnswer("bad shape")
        assessment = await evaluate_voice_turn("cho tôi hỏi giá nhà")
        assert assessment == VoiceTurnAssessment()

    @pytest.mark.asyncio
    async def test_unexpected_exception_fails_open(self, mock_decide):
        mock_decide.side_effect = RuntimeError("worker exploded")
        assessment = await evaluate_voice_turn("cho tôi hỏi giá nhà")
        assert assessment == VoiceTurnAssessment()

    @pytest.mark.asyncio
    async def test_missing_answer_keys_fail_open_per_field(
        self, mock_decide
    ):
        # Backend answered but only returned one key — treated as
        # uncertain for the missing fields, never an action.
        mock_decide.return_value = _result(
            {"should_respond": _noul(0.9)}
        )
        assessment = await evaluate_voice_turn("cho tôi hỏi giá nhà")
        assert assessment == VoiceTurnAssessment()
