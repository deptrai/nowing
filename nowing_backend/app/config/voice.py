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
    "VOICE_FILLER_DIR",
    "VOICE_LLM_PROVIDER",
    "VOICE_MAX_CALLS_PER_WORKER",
    "VOICE_STT_PROVIDER",
    "VOICE_TTS_PROVIDER",
    "VOICE_VAD_MIN_SILENCE_MS",
    "VOICE_VAD_SPEECH_THRESHOLD",
    "VOICE_WORKER_PROCESSES",
]
