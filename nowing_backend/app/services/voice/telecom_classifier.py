"""Telecom Signal Classifier, AMD & Dead-air Watchdog Engine (Story 38.5).

Protects unit economics and telephony reputation under Decree 91:
1. Answering Machine Detection (AMD): Detects voicemails and automated IVRs
   within the first 3 seconds of customer pickup via initial speech duration
   (> 1.8s) and carrier keyword spotting. Drops call with SIP BYE in <= 4s.
2. Dead-air Watchdog: Probes after 3.0s of silence following bot speech
   ("Alo anh/chị có nghe rõ em nói không ạ?"); hangs up decisively before 8.0s
   if customer remains silent for another 3.0s-3.5s.
3. In-flight Anti-Spam Circuit Breaker: Tracks short call (< 5s) and complaint
   rates per campaign in Redis. Auto-trips (pauses campaign) if short_call_rate
   > 0.40 or spam_rate > 0.06 after min 30 completed calls.

Constraints:
- Reuses Redis client from app.lead_intelligence.dnc.service.get_redis() — no new pools.
- Pure in-process logic on STT transcripts and timestamp durations.
- Fail-open when Redis is unavailable (circuit breaker ignores, call proceeds).
"""

from __future__ import annotations

import enum
import logging
import time
import unicodedata
from dataclasses import dataclass

from app.config.voice import (
    VOICE_AMD_INITIAL_SPEECH_DURATION_MAX,
    VOICE_CIRCUIT_BREAKER_MIN_CALLS,
    VOICE_CIRCUIT_BREAKER_SHORT_CALL_THRESHOLD,
    VOICE_CIRCUIT_BREAKER_SPAM_THRESHOLD,
    VOICE_DEAD_AIR_HANGUP_SECONDS,
    VOICE_DEAD_AIR_PROBE_PROMPT,
    VOICE_DEAD_AIR_PROBE_SECONDS,
)
from app.lead_intelligence.dnc.service import get_redis

logger = logging.getLogger(__name__)

# Keyphrases identifying carrier voicemails or automated answering systems
VOICEMAIL_KEYPHRASES = (
    "thuê bao quý khách",
    "thue bao quy khach",
    "hiện không liên lạc được",
    "hien khong lien lac duoc",
    "tạm thời không liên lạc được",
    "tam thoi khong lien lac duoc",
    "vui lòng để lại lời nhắn",
    "vui long de lai loi nhan",
    "để lại tin nhắn",
    "de lai tin nhan",
    "sau tiếng bíp",
    "sau tieng bip",
    "hộp thư thoại",
    "hop thu thoai",
    "tin nhắn thoại",
    "tin nhan thoai",
    "cuộc gọi lỡ",
    "cuoc goi lo",
    "voicemail",
    "mailbox",
    "leave a message",
    "after the tone",
    "is not available",
    "the number you have dialed",
    "please call back later",
)

IVR_KEYPHRASES = (
    "cảm ơn quý khách đã gọi đến",
    "cam on quy khach da goi den",
    "bấm phím",
    "bam phim",
    "để gặp nhân viên",
    "de gap nhan vien",
    "nhấn phím",
    "nhan phim",
    "tổng đài chăm sóc",
    "tong dai cham soc",
    "press one",
    "press 1",
)


class CallSignal(enum.StrEnum):
    """Classification result of the customer audio channel."""

    HUMAN = "HUMAN"
    MACHINE_VOICEMAIL = "MACHINE_VOICEMAIL"
    MACHINE_IVR = "MACHINE_IVR"
    DEAD_AIR = "DEAD_AIR"
    BUSY = "BUSY"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class AMDResult:
    """Outcome of Answering Machine Detection evaluation."""

    signal: CallSignal
    is_machine: bool
    reason: str
    confidence: float

    @classmethod
    def human(cls, reason: str = "Short conversational opening") -> AMDResult:
        return cls(
            signal=CallSignal.HUMAN,
            is_machine=False,
            reason=reason,
            confidence=0.95,
        )

    @classmethod
    def machine_voicemail(cls, reason: str, confidence: float = 0.98) -> AMDResult:
        return cls(
            signal=CallSignal.MACHINE_VOICEMAIL,
            is_machine=True,
            reason=reason,
            confidence=confidence,
        )

    @classmethod
    def machine_ivr(cls, reason: str, confidence: float = 0.96) -> AMDResult:
        return cls(
            signal=CallSignal.MACHINE_IVR,
            is_machine=True,
            reason=reason,
            confidence=confidence,
        )

    @classmethod
    def unresolved(cls) -> AMDResult:
        return cls(
            signal=CallSignal.UNRESOLVED,
            is_machine=False,
            reason="Insufficient signal to classify",
            confidence=0.5,
        )


class AMDDetector:
    """Evaluates initial speech duration and transcripts to detect machines in <= 3s."""

    def __init__(
        self,
        *,
        max_initial_speech_duration: float = VOICE_AMD_INITIAL_SPEECH_DURATION_MAX,
    ) -> None:
        self.max_initial_speech_duration = max_initial_speech_duration
        self._initial_speech_start: float | None = None
        self._initial_speech_end: float | None = None
        self._evaluated: bool = False
        self._result: AMDResult = AMDResult.unresolved()

    @property
    def is_evaluated(self) -> bool:
        return self._evaluated

    @property
    def result(self) -> AMDResult:
        return self._result

    def on_speech_started(self, timestamp: float | None = None) -> None:
        """Mark start of first customer utterance."""
        if self._initial_speech_start is None:
            self._initial_speech_start = (
                timestamp if timestamp is not None else time.time()
            )

    def on_speech_ended(self, timestamp: float | None = None) -> None:
        """Mark end of first customer utterance."""
        if self._initial_speech_start is not None and self._initial_speech_end is None:
            self._initial_speech_end = (
                timestamp if timestamp is not None else time.time()
            )

    def evaluate(
        self,
        transcript: str | None = None,
        *,
        duration_seconds: float | None = None,
    ) -> AMDResult:
        """Classify opening utterance as HUMAN or MACHINE.

        Triggers:
        1. Transcript contains explicit voicemail / carrier greeting phrases.
        2. Transcript contains IVR navigation phrases.
        3. Initial monologue duration exceeds max_initial_speech_duration (> 1.8s)
           without natural pause (humans say 'Alo' in < 0.8s).
        """
        if self._evaluated:
            return self._result

        # Calculate duration if not explicitly passed
        dur = duration_seconds
        if dur is None and self._initial_speech_start is not None:
            end_t = self._initial_speech_end or time.time()
            dur = max(0.0, end_t - self._initial_speech_start)

        norm_text = ""
        if transcript and transcript.strip():
            norm_text = unicodedata.normalize("NFC", transcript).lower().strip()

        # 1. Carrier voicemail phrase match
        for phrase in VOICEMAIL_KEYPHRASES:
            if phrase in norm_text:
                self._evaluated = True
                self._result = AMDResult.machine_voicemail(
                    f"Voicemail keyphrase matched: {phrase!r}"
                )
                return self._result

        # 2. IVR phrase match
        for phrase in IVR_KEYPHRASES:
            if phrase in norm_text:
                self._evaluated = True
                self._result = AMDResult.machine_ivr(
                    f"IVR keyphrase matched: {phrase!r}"
                )
                return self._result

        # 3. Monologue duration threshold (> 1.8s unbroken opening speech)
        if dur is not None and dur >= self.max_initial_speech_duration:
            self._evaluated = True
            self._result = AMDResult.machine_voicemail(
                f"Opening monologue duration {dur:.2f}s exceeded threshold {self.max_initial_speech_duration}s"
            )
            return self._result

        # 4. Short human opening (< 1.2s with text, e.g. "Alo", "Nghe đây")
        if dur is not None and dur < self.max_initial_speech_duration and norm_text:
            self._evaluated = True
            self._result = AMDResult.human(
                f"Short opening response: {norm_text[:30]!r} ({dur:.2f}s)"
            )
            return self._result

        return AMDResult.unresolved()


class DeadAirState(enum.StrEnum):
    """State machine for the 2-phase dead-air detection loop."""

    IDLE = "IDLE"
    AWAITING_REPLY = "AWAITING_REPLY"  # Phase 1: bot finished speaking, waiting for customer
    PROBE_TRIGGERED = "PROBE_TRIGGERED"  # 3.0s elapsed: probe announcement playing
    AWAITING_PROBE_ACK = "AWAITING_PROBE_ACK"  # Phase 2: probe played, waiting for customer response
    DEAD_AIR_HANGUP = "DEAD_AIR_HANGUP"  # 6.5s-8.0s total: hang up decisively


class DeadAirWatchdog:
    """Manages 2-phase silence detection: probe at 3.0s, hangup before 8.0s."""

    def __init__(
        self,
        *,
        probe_seconds: float = VOICE_DEAD_AIR_PROBE_SECONDS,
        hangup_seconds: float = VOICE_DEAD_AIR_HANGUP_SECONDS,
        probe_prompt: str = VOICE_DEAD_AIR_PROBE_PROMPT,
    ) -> None:
        self.probe_seconds = probe_seconds
        self.hangup_seconds = hangup_seconds
        self.probe_prompt = probe_prompt
        self.state = DeadAirState.IDLE
        self._silence_start_time: float | None = None
        self._probe_triggered_at: float | None = None

    def on_bot_speech_stopped(self, timestamp: float | None = None) -> None:
        """Start silence timer when bot completes utterance."""
        now = timestamp if timestamp is not None else time.time()
        self.state = DeadAirState.AWAITING_REPLY
        self._silence_start_time = now
        self._probe_triggered_at = None

    def on_customer_speech_started(self) -> None:
        """Reset watchdog when customer speaks."""
        self.state = DeadAirState.IDLE
        self._silence_start_time = None
        self._probe_triggered_at = None

    def on_probe_dispatched(self, timestamp: float | None = None) -> None:
        """Transition from PROBE_TRIGGERED to AWAITING_PROBE_ACK."""
        now = timestamp if timestamp is not None else time.time()
        self.state = DeadAirState.AWAITING_PROBE_ACK
        self._probe_triggered_at = now

    def check_silence(self, timestamp: float | None = None) -> DeadAirState:
        """Evaluate elapsed silence and transition state machine.

        Returns:
            The current :class:`DeadAirState`.
            - If ``PROBE_TRIGGERED``: caller must emit ``probe_prompt``.
            - If ``DEAD_AIR_HANGUP``: caller must terminate call before 8.0s.
        """
        if self.state == DeadAirState.IDLE:
            return self.state

        now = timestamp if timestamp is not None else time.time()

        if self.state == DeadAirState.AWAITING_REPLY:
            if self._silence_start_time is None:
                return self.state
            elapsed = now - self._silence_start_time
            if elapsed >= self.probe_seconds:
                self.state = DeadAirState.PROBE_TRIGGERED
                logger.info(
                    "[DeadAir] 3.0s silence detected — triggering probe"
                )
                return self.state
            return self.state

        if self.state == DeadAirState.AWAITING_PROBE_ACK:
            # Total elapsed silence from beginning of dead-air episode
            total_elapsed = (
                now - self._silence_start_time
                if self._silence_start_time is not None
                else 0.0
            )
            if total_elapsed >= self.hangup_seconds:
                self.state = DeadAirState.DEAD_AIR_HANGUP
                logger.warning(
                    "[DeadAir] Total silence %.2fs reached hangup threshold %.2fs — dropping call",
                    total_elapsed,
                    self.hangup_seconds,
                )
                return self.state
            return self.state

        return self.state


@dataclass(frozen=True)
class CircuitBreakerStatus:
    """Metrics snapshot of outbound campaign health."""

    campaign_id: str | int
    total_calls: int
    short_calls: int
    spam_complaints: int
    short_call_rate: float
    spam_rate: float
    is_tripped: bool
    trip_reason: str | None = None


class AntiSpamCircuitBreaker:
    """Monitors campaign short calls (< 5s) and spam complaints to auto-pause campaigns."""

    def __init__(
        self,
        *,
        min_calls: int = VOICE_CIRCUIT_BREAKER_MIN_CALLS,
        short_call_threshold: float = VOICE_CIRCUIT_BREAKER_SHORT_CALL_THRESHOLD,
        spam_threshold: float = VOICE_CIRCUIT_BREAKER_SPAM_THRESHOLD,
    ) -> None:
        self.min_calls = min_calls
        self.short_call_threshold = short_call_threshold
        self.spam_threshold = spam_threshold

    @staticmethod
    def _metrics_key(campaign_id: str | int) -> str:
        return f"voice:campaign:metrics:{campaign_id}"

    async def record_call_outcome(
        self,
        campaign_id: str | int,
        duration_seconds: float,
        *,
        is_spam_complaint: bool = False,
    ) -> CircuitBreakerStatus:
        """Record completed call duration and evaluate circuit breaker health.

        Short call definition: duration < 5.0 seconds.
        Increments Redis hash counters atomically.
        """
        redis_client = get_redis()
        key = self._metrics_key(campaign_id)

        is_short = 1 if duration_seconds < 5.0 else 0
        complaint = 1 if is_spam_complaint else 0

        total = 0
        short = 0
        spam = 0

        if redis_client is not None:
            try:
                pipe = redis_client.pipeline()
                pipe.hincrby(key, "total_calls", 1)
                if is_short:
                    pipe.hincrby(key, "short_calls", 1)
                else:
                    pipe.hsetnx(key, "short_calls", 0)
                if complaint:
                    pipe.hincrby(key, "spam_complaints", 1)
                else:
                    pipe.hsetnx(key, "spam_complaints", 0)
                # Keep metrics alive for 7 days
                pipe.expire(key, 604800)
                res = await pipe.execute()
                total = int(res[0])
                # Fetch full hash
                metrics = await redis_client.hgetall(key)
                short = int(metrics.get("short_calls", 0))
                spam = int(metrics.get("spam_complaints", 0))
            except Exception as exc:
                logger.warning(
                    "[CircuitBreaker] Redis failure recording metrics for campaign %s: %s",
                    campaign_id,
                    exc,
                )
                return CircuitBreakerStatus(
                    campaign_id=campaign_id,
                    total_calls=1,
                    short_calls=is_short,
                    spam_complaints=complaint,
                    short_call_rate=float(is_short),
                    spam_rate=float(complaint),
                    is_tripped=False,
                )
        else:
            total = 1
            short = is_short
            spam = complaint

        short_rate = (short / total) if total > 0 else 0.0
        spam_rate = (spam / total) if total > 0 else 0.0

        is_tripped = False
        trip_reason: str | None = None

        if total >= self.min_calls:
            if short_rate > self.short_call_threshold:
                is_tripped = True
                trip_reason = (
                    f"Short call rate ({short_rate:.1%}) exceeded "
                    f"threshold ({self.short_call_threshold:.1%}) after {total} calls"
                )
            elif spam_rate > self.spam_threshold:
                is_tripped = True
                trip_reason = (
                    f"Spam complaint rate ({spam_rate:.1%}) exceeded "
                    f"threshold ({self.spam_threshold:.1%}) after {total} calls"
                )

        if is_tripped:
            logger.error(
                "[CircuitBreaker] TRIP campaign=%s: %s", campaign_id, trip_reason
            )

        return CircuitBreakerStatus(
            campaign_id=campaign_id,
            total_calls=total,
            short_calls=short,
            spam_complaints=spam,
            short_call_rate=short_rate,
            spam_rate=spam_rate,
            is_tripped=is_tripped,
            trip_reason=trip_reason,
        )

    async def reset(self, campaign_id: str | int) -> None:
        """Reset campaign metrics in Redis upon manual operator review."""
        redis_client = get_redis()
        if redis_client is not None:
            try:
                await redis_client.delete(self._metrics_key(campaign_id))
            except Exception as exc:
                logger.warning(
                    "[CircuitBreaker] Failed to reset metrics for campaign %s: %s",
                    campaign_id,
                    exc,
                )
