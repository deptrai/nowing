"""Anti-False-Interruption & Multi-tier Barge-in Engine (Story 38.3).

In-process barge-in engine operating on raw PCM16 audio buffers in Voice Agent Worker:
1. Echo Lockout: Ignores audio during the first 400ms after bot begins speaking.
2. Ducking: Drops bot gain by -14dB in <= 30ms upon customer speech detection (P >= 0.88).
3. Keyword Spotting (KWS): Recognizes Vietnamese backchannel fillers (< 280ms) and recovers
   gain to 0dB without interrupting bot speech.
4. Real Barge-in: Cancels LLM/TTS in < 50ms upon real customer barge-in and sends a 40ms
   SIP silence packet.

Constraints:
- In-process on raw PCM16 buffers — no independent audio microservice.
- Uses numpy for PCM16 sample math with clipping to int16 — no audioop (removed in Python 3.13).
- Fail-open when SEQUENCER_VOICE_ENABLED=false or configuration is missing.
"""

from __future__ import annotations

import enum
import logging
import re
import time
import unicodedata
from typing import Any

import numpy as np
from livekit import rtc

from app.config.voice import (
    SEQUENCER_VOICE_ENABLED,
    VOICE_BARGE_IN_BACKCHANNEL_WORDS,
    VOICE_BARGE_IN_DUCKING_DB,
    VOICE_BARGE_IN_DUCKING_RAMP_MS,
    VOICE_BARGE_IN_ECHO_LOCKOUT_MS,
    VOICE_BARGE_IN_INTERRUPT_DEADLINE_MS,
    VOICE_BARGE_IN_KWS_TIMEOUT_MS,
    VOICE_BARGE_IN_SILENCE_PACKET_MS,
    VOICE_BARGE_IN_SPEECH_PROB_THRESHOLD,
)

logger = logging.getLogger(__name__)

_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)


def remove_vietnamese_accents(text: str) -> str:
    """Strip Vietnamese diacritics and normalize character casing.

    Handles 'đ'/'Đ' explicitly as NFD decomposition does not split 'đ' into 'd'.
    """
    text = text.replace("đ", "d").replace("Đ", "D")
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _normalize_backchannel_text(text: str) -> str:
    """Lowercase + strip punctuation + collapse whitespace."""
    return " ".join(_PUNCT_RE.sub(" ", text.lower()).split())


def is_backchannel(text: str, backchannel_words: str | None = None) -> bool:
    """Return True if *text* matches a known backchannel / conversational filler.

    Matching is case-insensitive, ignores punctuation, and matches both
    accented and unaccented forms of the configured backchannel words.
    """
    if not text or not text.strip():
        return False

    raw_words_str = (
        backchannel_words
        if backchannel_words is not None
        else VOICE_BARGE_IN_BACKCHANNEL_WORDS
    )
    raw_words = [w.strip() for w in raw_words_str.split(",") if w.strip()]

    target_set: set[str] = set()
    for word in raw_words:
        norm = _normalize_backchannel_text(word)
        if norm:
            target_set.add(norm)
            target_set.add(remove_vietnamese_accents(norm))

    cleaned = _normalize_backchannel_text(text)
    cleaned_no_accents = remove_vietnamese_accents(cleaned)

    return cleaned in target_set or cleaned_no_accents in target_set


def apply_gain(frame: Any, gain_db: float) -> Any:
    """Multiply PCM16 samples by linear gain corresponding to *gain_db*.

    Clips values to [-32768, 32767] to prevent int16 overflow / wrapping.
    Gain of 0.0 dB is a strict no-op.
    Malformed frames (invalid sample rate, empty data) are skipped without error.
    """
    if abs(gain_db) < 1e-4:
        return frame

    factor = 10.0 ** (gain_db / 20.0)

    # Handle rtc.AudioFrame or objects with a .data buffer
    if hasattr(frame, "data"):
        try:
            sample_rate = getattr(frame, "sample_rate", 1)
            samples_per_channel = getattr(frame, "samples_per_channel", 1)
            if sample_rate <= 0 or samples_per_channel <= 0:
                return frame

            data_view = memoryview(frame.data)
            if len(data_view) == 0 or len(data_view) % 2 != 0:
                return frame

            arr = np.frombuffer(data_view, dtype=np.int16)
            scaled = np.clip(np.round(arr * factor), -32768, 32767).astype(np.int16)
            arr[:] = scaled
            return frame
        except Exception as exc:
            logger.warning("[barge_in] apply_gain failed on AudioFrame: %s", exc)
            return frame

    # Handle bytes / bytearray for testing without LiveKit AudioFrame
    if isinstance(frame, (bytes, bytearray)):
        if len(frame) == 0 or len(frame) % 2 != 0:
            return frame
        arr = np.frombuffer(frame, dtype=np.int16).copy()
        scaled = np.clip(np.round(arr * factor), -32768, 32767).astype(np.int16)
        return (
            scaled.tobytes()
            if isinstance(frame, bytes)
            else bytearray(scaled.tobytes())
        )

    # Handle np.ndarray directly
    if isinstance(frame, np.ndarray) and frame.dtype == np.int16:
        scaled = np.clip(np.round(frame * factor), -32768, 32767).astype(np.int16)
        frame[:] = scaled
        return frame

    return frame


def create_silence_frame(
    duration_ms: int = 40,
    sample_rate: int = 48000,
    num_channels: int = 1,
) -> rtc.AudioFrame:
    """Create a 40ms silence AudioFrame for SIP barge-in (default 48000Hz telephony standard)."""
    samples = int(sample_rate * duration_ms / 1000)
    frame = rtc.AudioFrame.create(
        sample_rate=sample_rate,
        num_channels=num_channels,
        samples_per_channel=samples,
    )
    frame.data.cast("B")[:] = b"\x00" * frame.data.nbytes
    return frame


class DuckingController:
    """Calculates linear gain envelope over time for ducking and recovery.

    Transitions from 0.0 dB down to *ducking_db* over *ramp_ms* linearly in dB.
    """

    def __init__(
        self,
        ramp_ms: int = VOICE_BARGE_IN_DUCKING_RAMP_MS,
        ducking_db: float = VOICE_BARGE_IN_DUCKING_DB,
    ) -> None:
        self.ramp_ms = max(1, ramp_ms)
        # Enforce non-positive gain — ducking must attenuate, never amplify.
        self.ducking_db = -abs(float(ducking_db))
        self._is_ducking: bool = False
        self._is_recovering: bool = False
        self._start_time: float | None = None
        self._start_gain_db: float = 0.0
        self._target_gain_db: float = 0.0
        self._current_gain_db: float = 0.0

    def start_ducking(self, timestamp: float | None = None) -> None:
        """Start ducking gain envelope towards *ducking_db*."""
        now = timestamp if timestamp is not None else time.time()
        self._is_ducking = True
        self._is_recovering = False
        self._start_time = now
        self._start_gain_db = self._current_gain_db
        self._target_gain_db = self.ducking_db

    def recover(self, timestamp: float | None = None, immediate: bool = True) -> None:
        """Recover gain back to 0.0 dB."""
        self._is_ducking = False
        if immediate:
            self._is_recovering = False
            self._current_gain_db = 0.0
            self._start_gain_db = 0.0
            self._target_gain_db = 0.0
            self._start_time = None
        else:
            now = timestamp if timestamp is not None else time.time()
            self._is_recovering = True
            self._start_time = now
            self._start_gain_db = self._current_gain_db
            self._target_gain_db = 0.0

    def get_gain_db(self, timestamp: float | None = None) -> float:
        """Return current gain in dB at *timestamp*."""
        if not self._is_ducking and not self._is_recovering:
            self._current_gain_db = 0.0
            return 0.0

        if self._start_time is None:
            return self._target_gain_db if self._is_ducking else 0.0

        now = timestamp if timestamp is not None else time.time()
        elapsed_ms = (now - self._start_time) * 1000.0

        if elapsed_ms <= 0:
            return self._start_gain_db

        if elapsed_ms >= self.ramp_ms:
            self._current_gain_db = self._target_gain_db
            return self._current_gain_db

        progress = elapsed_ms / float(self.ramp_ms)
        self._current_gain_db = self._start_gain_db + progress * (
            self._target_gain_db - self._start_gain_db
        )
        return self._current_gain_db

    def get_gain_linear(self, timestamp: float | None = None) -> float:
        """Return linear gain multiplier at *timestamp*."""
        db = self.get_gain_db(timestamp)
        return 10.0 ** (db / 20.0)


class BargeInState(enum.StrEnum):
    """4-state machine for multi-tier barge-in engine."""

    IDLE = "IDLE"
    ECHO_LOCKOUT = "ECHO_LOCKOUT"
    DUCKING = "DUCKING"
    INTERRUPTED = "INTERRUPTED"


class BargeInEngine:
    """Multi-tier barge-in state machine and audio gain engine.

    States:
    - IDLE: Bot is not speaking, or bot speaking normally at 0dB.
    - ECHO_LOCKOUT: Bot speaking; incoming audio during first 400ms ignored.
    - DUCKING: Customer speech detected after echo lockout; gain dropped to -14dB in <= 30ms.
    - INTERRUPTED: Confirmed real barge-in; LLM/TTS cancelled in < 50ms, 40ms silence sent.
    """

    def __init__(
        self,
        *,
        echo_lockout_ms: int | None = None,
        ducking_db: float | None = None,
        ducking_ramp_ms: int | None = None,
        kws_timeout_ms: int | None = None,
        silence_packet_ms: int | None = None,
        interrupt_deadline_ms: int | None = None,
        speech_prob_threshold: float | None = None,
        backchannel_words: str | None = None,
        enabled: bool | None = None,
    ) -> None:
        self.enabled = (
            enabled if enabled is not None else SEQUENCER_VOICE_ENABLED
        )
        self.echo_lockout_ms = (
            echo_lockout_ms
            if echo_lockout_ms is not None
            else VOICE_BARGE_IN_ECHO_LOCKOUT_MS
        )
        self.ducking_db = (
            ducking_db if ducking_db is not None else VOICE_BARGE_IN_DUCKING_DB
        )
        self.ducking_ramp_ms = (
            ducking_ramp_ms
            if ducking_ramp_ms is not None
            else VOICE_BARGE_IN_DUCKING_RAMP_MS
        )
        self.kws_timeout_ms = (
            kws_timeout_ms
            if kws_timeout_ms is not None
            else VOICE_BARGE_IN_KWS_TIMEOUT_MS
        )
        self.silence_packet_ms = (
            silence_packet_ms
            if silence_packet_ms is not None
            else VOICE_BARGE_IN_SILENCE_PACKET_MS
        )
        self.interrupt_deadline_ms = (
            interrupt_deadline_ms
            if interrupt_deadline_ms is not None
            else VOICE_BARGE_IN_INTERRUPT_DEADLINE_MS
        )
        self.speech_prob_threshold = (
            speech_prob_threshold
            if speech_prob_threshold is not None
            else VOICE_BARGE_IN_SPEECH_PROB_THRESHOLD
        )
        self.backchannel_words = (
            backchannel_words
            if backchannel_words is not None
            else VOICE_BARGE_IN_BACKCHANNEL_WORDS
        )

        self.state: BargeInState = BargeInState.IDLE
        self.ducking_controller = DuckingController(
            ramp_ms=self.ducking_ramp_ms,
            ducking_db=self.ducking_db,
        )

        self._bot_speaking: bool = False
        self._bot_speaking_started_at: float = 0.0
        self._ducking_started_at: float = 0.0
        self._last_speech_detected_at: float = 0.0

    # ------------------------------------------------------------------
    # Lifecycle & Audio Timing
    # ------------------------------------------------------------------

    def on_bot_speech_started(self, timestamp: float | None = None) -> None:
        """Signal that the bot started playing audio frames."""
        if not self.enabled:
            return
        now = timestamp if timestamp is not None else time.time()
        self._bot_speaking = True
        self._bot_speaking_started_at = now
        self.state = BargeInState.ECHO_LOCKOUT
        self.ducking_controller.recover(now, immediate=True)

    def on_bot_speech_stopped(self) -> None:
        """Signal that the bot finished speaking."""
        self._bot_speaking = False
        self.state = BargeInState.IDLE
        self.ducking_controller.recover(immediate=True)

    # ------------------------------------------------------------------
    # Speech Detection & Transcript Events
    # ------------------------------------------------------------------

    def on_speech_detected(
        self, probability: float, timestamp: float | None = None
    ) -> BargeInState:
        """Handle incoming VAD speech probability.

        - If bot is not speaking: return current state.
        - If within echo lockout (400ms): ignore completely.
        - If probability >= threshold: transition to DUCKING and ramp gain to -14dB.
        """
        if not self.enabled or not self._bot_speaking:
            return self.state

        now = timestamp if timestamp is not None else time.time()
        elapsed_since_bot_start_ms = (now - self._bot_speaking_started_at) * 1000.0

        # Echo lockout: ignore audio during the first echo_lockout_ms
        if elapsed_since_bot_start_ms < self.echo_lockout_ms:
            return self.state

        if probability >= self.speech_prob_threshold:
            self._last_speech_detected_at = now
            if self.state in (BargeInState.ECHO_LOCKOUT, BargeInState.IDLE):
                self.state = BargeInState.DUCKING
                self._ducking_started_at = now
                self.ducking_controller.start_ducking(now)

        return self.state

    def on_transcript(
        self,
        text: str,
        is_preflight: bool = False,
        timestamp: float | None = None,
    ) -> BargeInState:
        """Evaluate an incoming speech transcript (interim or preflight).

        - Echo lockout active: ignore transcript.
        - In DUCKING or ECHO_LOCKOUT:
          - If matches backchannel in < kws_timeout_ms: recover to 0dB, state IDLE.
          - If non-filler speech content: transition to INTERRUPTED.
        """
        if not self.enabled or not self._bot_speaking:
            return self.state

        now = timestamp if timestamp is not None else time.time()
        elapsed_since_bot_start_ms = (now - self._bot_speaking_started_at) * 1000.0

        if elapsed_since_bot_start_ms < self.echo_lockout_ms:
            return self.state

        if self.state in (BargeInState.DUCKING, BargeInState.ECHO_LOCKOUT):
            elapsed_kws_ms = (
                (now - self._ducking_started_at) * 1000.0
                if self._ducking_started_at > 0
                else 0.0
            )
            if is_backchannel(text, self.backchannel_words):
                if elapsed_kws_ms <= self.kws_timeout_ms:
                    # Filler recovery — restore gain and keep talking
                    self.state = BargeInState.IDLE
                    self.ducking_controller.recover(now, immediate=True)
                    return self.state
                else:
                    # Backchannel recognition took too long (> 280ms) -> real barge-in
                    self.state = BargeInState.INTERRUPTED
                    return self.state
            elif text.strip():
                # Real speech detected — interrupt bot
                self.state = BargeInState.INTERRUPTED
                return self.state

        return self.state

    def on_speech_event(
        self, ev: Any, timestamp: float | None = None
    ) -> BargeInState:
        """Handle a livekit.agents.stt.SpeechEvent object."""
        if not self.enabled or not self._bot_speaking:
            return self.state

        now = timestamp if timestamp is not None else time.time()

        # Check event type name (avoiding rigid class identity if mocked)
        ev_type = getattr(ev, "type", None)
        type_str = str(getattr(ev_type, "name", ev_type))

        if type_str == "START_OF_SPEECH":
            return self.on_speech_detected(1.0, now)

        if type_str in ("PREFLIGHT_TRANSCRIPT", "INTERIM_TRANSCRIPT"):
            alts = getattr(ev, "alternatives", None)
            text = alts[0].text if alts and hasattr(alts[0], "text") else ""
            confidence = (
                getattr(alts[0], "confidence", 1.0)
                if alts and hasattr(alts[0], "confidence")
                else 1.0
            )

            # Ensure speech detection triggered if confidence is sufficient
            if self.state in (BargeInState.IDLE, BargeInState.ECHO_LOCKOUT):
                self.on_speech_detected(
                    confidence if confidence > 0 else 1.0, now
                )

            return self.on_transcript(
                text=text,
                is_preflight=(type_str == "PREFLIGHT_TRANSCRIPT"),
                timestamp=now,
            )

        return self.state

    def check_timeouts(self, timestamp: float | None = None) -> BargeInState:
        """Check if KWS timeout has elapsed while ducking without filler match."""
        if not self.enabled or self.state != BargeInState.DUCKING:
            return self.state

        now = timestamp if timestamp is not None else time.time()
        elapsed_kws_ms = (now - self._ducking_started_at) * 1000.0

        if elapsed_kws_ms > self.kws_timeout_ms:
            # Customer kept speaking without a backchannel confirmation -> real barge-in
            self.state = BargeInState.INTERRUPTED

        return self.state

    # ------------------------------------------------------------------
    # Gain Application
    # ------------------------------------------------------------------

    def current_gain_db(self, timestamp: float | None = None) -> float:
        """Return the current gain in dB to apply to outgoing audio."""
        if not self.enabled:
            return 0.0

        if self.state == BargeInState.DUCKING:
            return self.ducking_controller.get_gain_db(timestamp)

        return 0.0

    def current_gain_linear(self, timestamp: float | None = None) -> float:
        """Return the current linear gain factor."""
        db = self.current_gain_db(timestamp)
        return 10.0 ** (db / 20.0)

    def apply_gain(self, frame: Any, timestamp: float | None = None) -> Any:
        """Apply current engine gain to *frame*."""
        gain_db = self.current_gain_db(timestamp)
        return apply_gain(frame, gain_db)
