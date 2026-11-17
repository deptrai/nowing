"""Unit tests for Anti-False-Interruption & Multi-tier Barge-in Engine (Story 38.3).

Hermetic tests covering:
- Echo lockout: audio within 400ms ignored, gain remains 0dB
- Ducking envelope: reaches -14dB in <= 30ms linearly
- Filler recovery: backchannel ("ừ", "dạ", "vâng") restores 0dB in < 280ms
- Real barge-in: non-filler speech triggers INTERRUPTED in < 50ms
- PCM16 gain math: numpy scaling, int16 clipping, 0dB no-op
- Malformed frames: empty / invalid sample rate handled gracefully without crash
- Fail-open: disabled engine remains in IDLE with 0dB gain
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import numpy as np
import pytest
from livekit import rtc
from livekit.agents import stt

from app.services.voice.barge_in import (
    BargeInEngine,
    BargeInState,
    DuckingController,
    apply_gain,
    create_silence_frame,
    is_backchannel,
    remove_vietnamese_accents,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pcm16_frame(
    samples: list[int] | np.ndarray,
    sample_rate: int = 24000,
    num_channels: int = 1,
) -> rtc.AudioFrame:
    """Create an rtc.AudioFrame with the specified PCM16 samples."""
    arr = np.array(samples, dtype=np.int16)
    frame = rtc.AudioFrame.create(
        sample_rate=sample_rate,
        num_channels=num_channels,
        samples_per_channel=len(arr) // num_channels,
    )
    frame.data.cast("B")[:] = arr.tobytes()
    return frame


def _make_speech_event(
    event_type: stt.SpeechEventType,
    text: str = "",
    confidence: float = 0.95,
) -> stt.SpeechEvent:
    """Create a mock SpeechEvent."""
    return stt.SpeechEvent(
        type=event_type,
        alternatives=[stt.SpeechData(text=text, language="vi", confidence=confidence)],
    )


# ---------------------------------------------------------------------------
# Test Echo Lockout
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEchoLockout:
    """Echo lockout must ignore customer sound during the first 400ms."""

    def test_echo_lockout_ignores_speech_within_400ms(self):
        """Audio arriving within 400ms after bot start is ignored."""
        engine = BargeInEngine(
            echo_lockout_ms=400,
            ducking_db=-14.0,
            speech_prob_threshold=0.88,
            enabled=True,
        )
        t0 = 1000.0
        engine.on_bot_speech_started(timestamp=t0)
        assert engine.state == BargeInState.ECHO_LOCKOUT
        assert engine.current_gain_db(timestamp=t0) == 0.0

        # Customer makes noise at 150ms and 350ms (both < 400ms)
        state_150 = engine.on_speech_detected(probability=0.99, timestamp=t0 + 0.15)
        assert state_150 == BargeInState.ECHO_LOCKOUT
        assert engine.current_gain_db(timestamp=t0 + 0.15) == 0.0

        state_350 = engine.on_speech_detected(probability=0.99, timestamp=t0 + 0.35)
        assert state_350 == BargeInState.ECHO_LOCKOUT
        assert engine.current_gain_db(timestamp=t0 + 0.35) == 0.0

    def test_speech_after_echo_lockout_triggers_ducking(self):
        """Speech arriving after 400ms with P >= 0.88 enters DUCKING."""
        engine = BargeInEngine(
            echo_lockout_ms=400,
            ducking_db=-14.0,
            speech_prob_threshold=0.88,
            enabled=True,
        )
        t0 = 1000.0
        engine.on_bot_speech_started(timestamp=t0)

        # Customer speaks at 450ms (> 400ms) with P = 0.92
        state = engine.on_speech_detected(probability=0.92, timestamp=t0 + 0.45)
        assert state == BargeInState.DUCKING
        assert engine.state == BargeInState.DUCKING

    def test_speech_with_low_probability_after_lockout_ignored(self):
        """Speech arriving after 400ms with P < 0.88 is ignored."""
        engine = BargeInEngine(
            echo_lockout_ms=400,
            speech_prob_threshold=0.88,
            enabled=True,
        )
        t0 = 1000.0
        engine.on_bot_speech_started(timestamp=t0)

        # Customer noise with P = 0.60 (below threshold 0.88)
        state = engine.on_speech_detected(probability=0.60, timestamp=t0 + 0.45)
        assert state == BargeInState.ECHO_LOCKOUT
        assert engine.current_gain_db(timestamp=t0 + 0.45) == 0.0


# ---------------------------------------------------------------------------
# Test Ducking Controller
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDuckingController:
    """Ducking gain envelope drops to -14dB in <= 30ms linearly."""

    def test_linear_ramp_timing(self):
        """Gain ramps from 0dB to -14dB over 30ms."""
        ctrl = DuckingController(ramp_ms=30, ducking_db=-14.0)
        t0 = 100.0
        assert ctrl.get_gain_db(timestamp=t0) == 0.0

        ctrl.start_ducking(timestamp=t0)

        # At t0 (0ms): 0dB
        assert ctrl.get_gain_db(timestamp=t0) == 0.0

        # At 15ms (halfway): -7dB
        gain_15ms = ctrl.get_gain_db(timestamp=t0 + 0.015)
        assert pytest.approx(gain_15ms, abs=0.1) == -7.0

        # At 30ms: -14dB
        gain_30ms = ctrl.get_gain_db(timestamp=t0 + 0.030)
        assert pytest.approx(gain_30ms, abs=0.1) == -14.0

        # Beyond 30ms: stays clamped at -14dB
        gain_50ms = ctrl.get_gain_db(timestamp=t0 + 0.050)
        assert pytest.approx(gain_50ms, abs=0.1) == -14.0

    def test_linear_amplitude_conversion(self):
        """Linear gain multiplier matches 10^(dB/20)."""
        ctrl = DuckingController(ramp_ms=30, ducking_db=-14.0)
        t0 = 100.0
        ctrl.start_ducking(timestamp=t0)

        # At 30ms: -14dB -> 10^(-14/20) ~ 0.1995
        expected_linear = 10.0 ** (-14.0 / 20.0)
        actual_linear = ctrl.get_gain_linear(timestamp=t0 + 0.030)
        assert pytest.approx(actual_linear, rel=1e-3) == expected_linear

    def test_recovery_restores_0db(self):
        """Calling recover restores gain to 0dB."""
        ctrl = DuckingController(ramp_ms=30, ducking_db=-14.0)
        t0 = 100.0
        ctrl.start_ducking(timestamp=t0)
        assert pytest.approx(ctrl.get_gain_db(timestamp=t0 + 0.030), abs=0.1) == -14.0

        ctrl.recover(immediate=True)
        assert ctrl.get_gain_db() == 0.0
        assert ctrl.get_gain_linear() == 1.0


# ---------------------------------------------------------------------------
# Test Keyword Spotting & Filler Recovery
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestKeywordSpottingFillerRecovery:
    """Backchannel fillers (< 280ms) restore gain to 0dB without interrupting."""

    @pytest.mark.parametrize(
        "filler_word",
        ["ừ", "dạ", "vâng", "ờ", "ừm", "dạ rồi", "ok", "okay", "mm"],
    )
    def test_known_backchannel_words_matched(self, filler_word: str):
        """All default backchannel words are recognized by is_backchannel."""
        assert is_backchannel(filler_word) is True

    @pytest.mark.parametrize(
        "variation",
        ["Ừ", "DẠ", "VÂNG", "da", "u", "vang", "da roi", "OK", "OKAY", "  dạ...  "],
    )
    def test_accent_and_case_insensitive_matching(self, variation: str):
        """Matching is case-insensitive, punctuation-insensitive, and accent-free."""
        assert is_backchannel(variation) is True

    def test_non_backchannel_words_not_matched(self):
        """Real conversational content is not misclassified as backchannel."""
        assert is_backchannel("tôi bận rồi") is False
        assert is_backchannel("khoan đã") is False
        assert is_backchannel("dừng lại") is False
        assert is_backchannel("cho tôi gặp người thật") is False
        assert is_backchannel("") is False

    def test_filler_recognized_under_280ms_recovers_to_0db(self):
        """Backchannel recognized in < 280ms recovers gain to 0dB and state IDLE."""
        engine = BargeInEngine(
            echo_lockout_ms=400,
            ducking_db=-14.0,
            ducking_ramp_ms=30,
            kws_timeout_ms=280,
            enabled=True,
        )
        t0 = 1000.0
        engine.on_bot_speech_started(timestamp=t0)

        # Customer speaks at 500ms (> 400ms lockout)
        engine.on_speech_detected(probability=0.95, timestamp=t0 + 0.50)
        assert engine.state == BargeInState.DUCKING

        # Filler "dạ" arrives at 650ms (elapsed 150ms < 280ms)
        state = engine.on_transcript(text="dạ", timestamp=t0 + 0.65)
        assert state == BargeInState.IDLE
        assert engine.state == BargeInState.IDLE
        assert engine.current_gain_db() == 0.0

    def test_filler_recognized_after_280ms_triggers_interrupted(self):
        """Backchannel arriving after 280ms timeout is treated as real barge-in."""
        engine = BargeInEngine(
            echo_lockout_ms=400,
            ducking_db=-14.0,
            kws_timeout_ms=280,
            enabled=True,
        )
        t0 = 1000.0
        engine.on_bot_speech_started(timestamp=t0)

        # Customer speaks at 500ms
        engine.on_speech_detected(probability=0.95, timestamp=t0 + 0.50)
        assert engine.state == BargeInState.DUCKING

        # Word arrives at 820ms (elapsed 320ms > 280ms)
        state = engine.on_transcript(text="dạ", timestamp=t0 + 0.82)
        assert state == BargeInState.INTERRUPTED
        assert engine.state == BargeInState.INTERRUPTED


# ---------------------------------------------------------------------------
# Test Real Barge-In
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRealBargeIn:
    """Real customer speech cancels LLM/TTS in < 50ms."""

    def test_real_speech_transcript_triggers_interrupted(self):
        """Non-filler speech triggers INTERRUPTED immediately."""
        engine = BargeInEngine(
            echo_lockout_ms=400,
            ducking_db=-14.0,
            enabled=True,
        )
        t0 = 1000.0
        engine.on_bot_speech_started(timestamp=t0)
        engine.on_speech_detected(probability=0.95, timestamp=t0 + 0.50)

        # Real speech arrives: "tôi bận rồi"
        state = engine.on_transcript(text="tôi bận rồi", timestamp=t0 + 0.55)
        assert state == BargeInState.INTERRUPTED

    def test_preflight_transcript_triggers_interrupted_under_50ms(self):
        """PREFLIGHT_TRANSCRIPT event transitions to INTERRUPTED in < 50ms."""
        engine = BargeInEngine(
            echo_lockout_ms=400,
            ducking_db=-14.0,
            enabled=True,
        )
        t0 = 1000.0
        engine.on_bot_speech_started(timestamp=t0)
        engine.on_speech_detected(probability=0.95, timestamp=t0 + 0.50)

        ev = _make_speech_event(
            stt.SpeechEventType.PREFLIGHT_TRANSCRIPT,
            text="khoan đã em ơi",
        )

        start = time.perf_counter()
        state = engine.on_speech_event(ev, timestamp=t0 + 0.52)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert state == BargeInState.INTERRUPTED
        assert elapsed_ms < 50.0

    def test_kws_timeout_check_triggers_interrupted(self):
        """Speech exceeding 280ms without filler confirmation becomes INTERRUPTED."""
        engine = BargeInEngine(
            echo_lockout_ms=400,
            kws_timeout_ms=280,
            enabled=True,
        )
        t0 = 1000.0
        engine.on_bot_speech_started(timestamp=t0)
        engine.on_speech_detected(probability=0.95, timestamp=t0 + 0.50)
        assert engine.state == BargeInState.DUCKING

        # At 200ms elapsed: not timed out yet
        assert engine.check_timeouts(timestamp=t0 + 0.70) == BargeInState.DUCKING

        # At 300ms elapsed (> 280ms): times out to INTERRUPTED
        assert engine.check_timeouts(timestamp=t0 + 0.80) == BargeInState.INTERRUPTED


# ---------------------------------------------------------------------------
# Test PCM16 Audio Gain & Frame Math
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPCM16GainMathAndClipping:
    """PCM16 numpy gain math, clipping, and frame robustness."""

    def test_apply_gain_zero_db_is_noop(self):
        """gain 0.0 dB returns original frame unchanged."""
        samples = [1000, -2000, 3000, -4000]
        frame = _make_pcm16_frame(samples)
        result = apply_gain(frame, gain_db=0.0)
        assert result is frame

        res_samples = np.frombuffer(frame.data, dtype=np.int16).tolist()
        assert res_samples == samples

    def test_apply_gain_ducking_minus_14db(self):
        """-14dB gain reduces amplitude by ~0.1995."""
        samples = [10000, -10000, 20000, -20000]
        frame = _make_pcm16_frame(samples)
        factor = 10.0 ** (-14.0 / 20.0)  # ~0.199526

        apply_gain(frame, gain_db=-14.0)
        result_samples = np.frombuffer(frame.data, dtype=np.int16)

        expected = np.clip(np.round(np.array(samples) * factor), -32768, 32767).astype(np.int16)
        np.testing.assert_array_equal(result_samples, expected)

    def test_gain_clipping_does_not_wrap_int16(self):
        """High positive gain does not wrap around int16 boundaries."""
        samples = [25000, -25000, 30000, -30000]
        frame = _make_pcm16_frame(samples)

        # +12dB is roughly 4x gain — would overflow int16 without clipping
        apply_gain(frame, gain_db=12.0)
        result = np.frombuffer(frame.data, dtype=np.int16)

        assert np.all(result >= -32768)
        assert np.all(result <= 32767)
        assert result[0] == 32767
        assert result[1] == -32768
        assert result[2] == 32767
        assert result[3] == -32768

    def test_malformed_empty_frame_ignored_without_exception(self):
        """Empty frame data does not raise exception."""
        mock_frame = MagicMock()
        mock_frame.data = memoryview(b"")
        mock_frame.sample_rate = 24000
        mock_frame.samples_per_channel = 0

        res = apply_gain(mock_frame, gain_db=-14.0)
        assert res is mock_frame

    def test_malformed_invalid_sample_rate_ignored_without_exception(self):
        """AudioFrame with sample_rate <= 0 is skipped without error."""
        mock_frame = MagicMock()
        mock_frame.data = memoryview(b"\x00\x00")
        mock_frame.sample_rate = 0
        mock_frame.samples_per_channel = 1

        res = apply_gain(mock_frame, gain_db=-14.0)
        assert res is mock_frame

    def test_create_silence_frame_properties(self):
        """create_silence_frame creates 40ms silence AudioFrame."""
        frame = create_silence_frame(duration_ms=40, sample_rate=24000, num_channels=1)
        assert frame.sample_rate == 24000
        assert frame.num_channels == 1
        assert frame.samples_per_channel == 960  # 24000 * 0.040
        assert pytest.approx(frame.duration, abs=1e-3) == 0.04

        # Verify all bytes are 0
        data_bytes = bytes(frame.data)
        assert all(b == 0 for b in data_bytes)


# ---------------------------------------------------------------------------
# Test Fail-Open & Disabled State
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFailOpenAndDisabled:
    """When disabled or misconfigured, engine fails open to IDLE."""

    def test_disabled_engine_remains_idle(self):
        """When enabled=False, engine ignores all inputs and stays IDLE."""
        engine = BargeInEngine(enabled=False)
        assert engine.enabled is False
        assert engine.state == BargeInState.IDLE
        assert engine.current_gain_db() == 0.0

        engine.on_bot_speech_started()
        assert engine.state == BargeInState.IDLE

        state = engine.on_speech_detected(1.0)
        assert state == BargeInState.IDLE

        state = engine.on_transcript("tôi bận rồi")
        assert state == BargeInState.IDLE

        frame = _make_pcm16_frame([1000, 2000])
        res = engine.apply_gain(frame)
        assert res is frame

    def test_bot_speech_stopped_resets_state_and_gain(self):
        """on_bot_speech_stopped resets state to IDLE and gain to 0dB."""
        engine = BargeInEngine(
            echo_lockout_ms=400,
            ducking_db=-14.0,
            enabled=True,
        )
        t0 = 1000.0
        engine.on_bot_speech_started(timestamp=t0)
        engine.on_speech_detected(probability=0.95, timestamp=t0 + 0.50)
        assert engine.state == BargeInState.DUCKING

        engine.on_bot_speech_stopped()
        assert engine.state == BargeInState.IDLE
        assert engine.current_gain_db() == 0.0


# ---------------------------------------------------------------------------
# Test Vietnamese Accent Removal
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestVietnameseAccentRemoval:
    """remove_vietnamese_accents strips diacritics including đ/Đ."""

    def test_remove_vietnamese_accents(self):
        assert remove_vietnamese_accents("ừ") == "u"
        assert remove_vietnamese_accents("dạ") == "da"
        assert remove_vietnamese_accents("vâng") == "vang"
        assert remove_vietnamese_accents("ờ") == "o"
        assert remove_vietnamese_accents("được") == "duoc"
        assert remove_vietnamese_accents("Đồng Ý") == "Dong Y"
