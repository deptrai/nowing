"""Config domain: telephony & voice AI SDR infrastructure."""

from __future__ import annotations

import os

# LiveKit Media Server & SIP Gateway Configuration
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "http://localhost:7880")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")


def _safe_int_env(key: str, default: int) -> int:
    """Parse an integer env var, falling back to *default* on bad input."""
    try:
        return int(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default


def _positive_int_env(key: str, default: int) -> int:
    """Parse a strictly-positive integer env var, clamped to *default* when <= 0."""
    value = _safe_int_env(key, default)
    return value if value > 0 else default


def _safe_float_env(key: str, default: float) -> float:
    """Parse a float env var, clamped to [0.0, 1.0], falling back to *default* on invalid input."""
    val = os.getenv(key)
    if val is None or not val.strip():
        return default
    try:
        v = float(val.strip())
        return max(0.0, min(1.0, v))
    except (ValueError, TypeError):
        return default


# SIP Signaling & Gateway Parameters
SIP_OUTBOUND_GATEWAY_HOST = os.getenv("SIP_OUTBOUND_GATEWAY_HOST", "127.0.0.1")
SIP_OUTBOUND_GATEWAY_PORT = _safe_int_env("SIP_OUTBOUND_GATEWAY_PORT", 5060)
SIP_GATEWAY_SIP_URI = os.getenv(
    "SIP_GATEWAY_SIP_URI",
    f"sip:{SIP_OUTBOUND_GATEWAY_HOST}:{SIP_OUTBOUND_GATEWAY_PORT}",
)

# Telephony Defaults & Constraints (Invariant AD-122)
SIP_DEFAULT_TRUNK_ID = os.getenv("SIP_DEFAULT_TRUNK_ID", "")
SIP_ROOM_PREFIX = os.getenv("SIP_ROOM_PREFIX", "call_")
SIP_CALL_MAX_DURATION_SECONDS = _positive_int_env("SIP_CALL_MAX_DURATION_SECONDS", 180)
SIP_RINGING_TIMEOUT_SECONDS = _positive_int_env("SIP_RINGING_TIMEOUT_SECONDS", 30)

# Voice Channel Feature Flag
SEQUENCER_VOICE_ENABLED = (
    os.getenv("SEQUENCER_VOICE_ENABLED", "false").strip().lower()
    in ("true", "1", "t", "yes")
)


# Voice Agent Worker Pool (Story 38.2)
VOICE_WORKER_PROCESSES = _positive_int_env("VOICE_WORKER_PROCESSES", 8)
VOICE_MAX_CALLS_PER_WORKER = _positive_int_env("VOICE_MAX_CALLS_PER_WORKER", 12)

# Silero VAD tuning (Invariant: 180-220ms end-of-utterance detection)
VOICE_VAD_MIN_SILENCE_MS = _positive_int_env("VOICE_VAD_MIN_SILENCE_MS", 180)
VOICE_VAD_SPEECH_THRESHOLD = _safe_float_env("VOICE_VAD_SPEECH_THRESHOLD", 0.5)


def _safe_float_unbounded_env(key: str, default: float) -> float:
    """Parse a float env var without clamping to [0, 1]."""
    val = os.getenv(key)
    if val is None or not val.strip():
        return default
    try:
        return float(val.strip())
    except (ValueError, TypeError):
        return default


# Barge-in Engine Configuration (Story 38.3)
VOICE_BARGE_IN_ECHO_LOCKOUT_MS = _positive_int_env("VOICE_BARGE_IN_ECHO_LOCKOUT_MS", 400)
VOICE_BARGE_IN_DUCKING_DB = _safe_float_unbounded_env("VOICE_BARGE_IN_DUCKING_DB", -14.0)
VOICE_BARGE_IN_DUCKING_RAMP_MS = _positive_int_env("VOICE_BARGE_IN_DUCKING_RAMP_MS", 30)
VOICE_BARGE_IN_KWS_TIMEOUT_MS = _positive_int_env("VOICE_BARGE_IN_KWS_TIMEOUT_MS", 280)
VOICE_BARGE_IN_SILENCE_PACKET_MS = _positive_int_env("VOICE_BARGE_IN_SILENCE_PACKET_MS", 40)
VOICE_BARGE_IN_INTERRUPT_DEADLINE_MS = _positive_int_env(
    "VOICE_BARGE_IN_INTERRUPT_DEADLINE_MS", 50
)
VOICE_BARGE_IN_SPEECH_PROB_THRESHOLD = _safe_float_env(
    "VOICE_BARGE_IN_SPEECH_PROB_THRESHOLD", 0.88
)
VOICE_BARGE_IN_BACKCHANNEL_WORDS = os.getenv(
    "VOICE_BARGE_IN_BACKCHANNEL_WORDS",
    "ừ,dạ,vâng,ờ,ừm,dạ rồi,dạ vâng,vâng ạ,ok,okay,mm",
)

# Compliance & Pre-call Deposit (Story 38.4)
# 7,500,000 micros = 7,500 VND = 3-minute buffer at 2,500 VND/min
VOICE_PRECALL_SOFT_LOCK_MICROS = _positive_int_env(
    "VOICE_PRECALL_SOFT_LOCK_MICROS", 7_500_000
)
# Decree 91: caller must be informed that the call is being recorded in the first 3 seconds
VOICE_COMPLIANCE_RECORDING_DISCLOSURE_ENABLED = os.getenv(
    "VOICE_COMPLIANCE_RECORDING_DISCLOSURE_ENABLED", "true"
).strip().lower() in {"1", "true", "yes", "on"}
VOICE_RECORDING_DISCLOSURE_TEXT = os.getenv(
    "VOICE_RECORDING_DISCLOSURE_TEXT",
    "Cuộc gọi này được ghi âm để nâng cao chất lượng dịch vụ.",
)
# Hard call ceiling: 175s - 180s hangup (Nghị định 91 unit-economics protection)
VOICE_CALL_HARD_CEILING_SECONDS = _positive_int_env(
    "VOICE_CALL_HARD_CEILING_SECONDS", 180
)

# AMD & Dead-air Watchdog (Story 38.5)
# Initial monologue duration above this threshold (seconds) classifies as machine
VOICE_AMD_INITIAL_SPEECH_DURATION_MAX = _safe_float_env(
    "VOICE_AMD_INITIAL_SPEECH_DURATION_MAX", 1.8
)
# Dead-air: probe after this many seconds of customer silence
VOICE_DEAD_AIR_PROBE_SECONDS = _safe_float_env("VOICE_DEAD_AIR_PROBE_SECONDS", 3.0)
# Total silence (from bot speech end) before decisive hangup (before 8.0s)
VOICE_DEAD_AIR_HANGUP_SECONDS = _safe_float_env("VOICE_DEAD_AIR_HANGUP_SECONDS", 6.5)
VOICE_DEAD_AIR_PROBE_PROMPT = os.getenv(
    "VOICE_DEAD_AIR_PROBE_PROMPT",
    "Alo anh/chị có nghe rõ em nói không ạ?",
)

# Anti-Spam Circuit Breaker (Story 38.5)
VOICE_CIRCUIT_BREAKER_MIN_CALLS = _positive_int_env(
    "VOICE_CIRCUIT_BREAKER_MIN_CALLS", 30
)
VOICE_CIRCUIT_BREAKER_SHORT_CALL_THRESHOLD = _safe_float_env(
    "VOICE_CIRCUIT_BREAKER_SHORT_CALL_THRESHOLD", 0.40
)
VOICE_CIRCUIT_BREAKER_SPAM_THRESHOLD = _safe_float_env(
    "VOICE_CIRCUIT_BREAKER_SPAM_THRESHOLD", 0.06
)

# Filler audio directory (pre-loaded to RAM at worker startup)
VOICE_FILLER_DIR = os.path.normpath(
    os.getenv(
        "VOICE_FILLER_DIR",
        os.path.join(os.path.dirname(__file__), "..", "assets", "voice", "fillers"),
    )
)

# Provider selection
VOICE_LLM_PROVIDER = os.getenv("VOICE_LLM_PROVIDER", "anthropic")
VOICE_STT_PROVIDER = os.getenv("VOICE_STT_PROVIDER", "deepgram")
VOICE_TTS_PROVIDER = os.getenv("VOICE_TTS_PROVIDER", "openai")

# External provider keys (leave empty for local fallback)
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

__all__ = [
    "ANTHROPIC_API_KEY",
    "DEEPGRAM_API_KEY",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "LIVEKIT_URL",
    "OPENAI_API_KEY",
    "SEQUENCER_VOICE_ENABLED",
    "SIP_CALL_MAX_DURATION_SECONDS",
    "SIP_DEFAULT_TRUNK_ID",
    "SIP_GATEWAY_SIP_URI",
    "SIP_OUTBOUND_GATEWAY_HOST",
    "SIP_OUTBOUND_GATEWAY_PORT",
    "SIP_RINGING_TIMEOUT_SECONDS",
    "SIP_ROOM_PREFIX",
    "VOICE_AMD_INITIAL_SPEECH_DURATION_MAX",
    "VOICE_BARGE_IN_BACKCHANNEL_WORDS",
    "VOICE_BARGE_IN_DUCKING_DB",
    "VOICE_BARGE_IN_DUCKING_RAMP_MS",
    "VOICE_BARGE_IN_ECHO_LOCKOUT_MS",
    "VOICE_BARGE_IN_INTERRUPT_DEADLINE_MS",
    "VOICE_BARGE_IN_KWS_TIMEOUT_MS",
    "VOICE_BARGE_IN_SILENCE_PACKET_MS",
    "VOICE_BARGE_IN_SPEECH_PROB_THRESHOLD",
    "VOICE_CALL_HARD_CEILING_SECONDS",
    "VOICE_CIRCUIT_BREAKER_MIN_CALLS",
    "VOICE_CIRCUIT_BREAKER_SHORT_CALL_THRESHOLD",
    "VOICE_CIRCUIT_BREAKER_SPAM_THRESHOLD",
    "VOICE_COMPLIANCE_RECORDING_DISCLOSURE_ENABLED",
    "VOICE_DEAD_AIR_HANGUP_SECONDS",
    "VOICE_DEAD_AIR_PROBE_PROMPT",
    "VOICE_DEAD_AIR_PROBE_SECONDS",
    "VOICE_FILLER_DIR",
    "VOICE_LLM_PROVIDER",
    "VOICE_MAX_CALLS_PER_WORKER",
    "VOICE_PRECALL_SOFT_LOCK_MICROS",
    "VOICE_RECORDING_DISCLOSURE_TEXT",
    "VOICE_STT_PROVIDER",
    "VOICE_TTS_PROVIDER",
    "VOICE_VAD_MIN_SILENCE_MS",
    "VOICE_VAD_SPEECH_THRESHOLD",
    "VOICE_WORKER_PROCESSES",
]
