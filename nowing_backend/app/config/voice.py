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

__all__ = [
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "LIVEKIT_URL",
    "SEQUENCER_VOICE_ENABLED",
    "SIP_CALL_MAX_DURATION_SECONDS",
    "SIP_DEFAULT_TRUNK_ID",
    "SIP_GATEWAY_SIP_URI",
    "SIP_OUTBOUND_GATEWAY_HOST",
    "SIP_OUTBOUND_GATEWAY_PORT",
    "SIP_RINGING_TIMEOUT_SECONDS",
    "SIP_ROOM_PREFIX",
]
