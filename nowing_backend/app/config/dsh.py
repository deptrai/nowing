"""Config domain: dsh."""

from __future__ import annotations

import os

from app.config._helpers import (
    _env_float,
    _env_int,
)

# DSH worker sidecar (Story 26.2)
DSH_WORKER_PAT = os.getenv("DSH_WORKER_PAT", "")
DSH_WORKER_SECRET = os.getenv("DSH_WORKER_SECRET", "")
DSH_INTERNAL_BASE_URL = os.getenv("DSH_INTERNAL_BASE_URL", "http://localhost:8000")
DSH_HEARTBEAT_INTERVAL_SECONDS = int(
    os.getenv("DSH_HEARTBEAT_INTERVAL_SECONDS", str(30))
)
DSH_LOCK_TTL_SECONDS = int(os.getenv("DSH_LOCK_TTL_SECONDS", str(120)))
DSH_XAUTOCLAIM_MIN_IDLE_MS = int(
    os.getenv("DSH_XAUTOCLAIM_MIN_IDLE_MS", str(60 * 1000))
)
DSH_MAX_RETRIES = int(os.getenv("DSH_MAX_RETRIES", str(3)))
DSH_STREAM_TASKS = os.getenv("DSH_STREAM_TASKS", "nowing:dsh:tasks")
DSH_STREAM_DLQ = os.getenv("DSH_STREAM_DLQ", "nowing:dsh:dlq")
DSH_CONSUMER_GROUP = os.getenv("DSH_CONSUMER_GROUP", "dsh_workers")
DSH_REDIS_BLOCK_MS = int(os.getenv("DSH_REDIS_BLOCK_MS", str(5000)))
DSH_SYNC_TIMEOUT_SECONDS = int(os.getenv("DSH_SYNC_TIMEOUT_SECONDS", str(60)))
DSH_MAX_PAYLOAD_BYTES = int(
    os.getenv("DSH_MAX_PAYLOAD_BYTES", str(10 * 1024 * 1024))
)
DSH_EXECUTOR_ENGINE = os.getenv("DSH_EXECUTOR_ENGINE", "legacy")

# DSH Telegram Interactive Checkpoint & Auto-Refund (Story 26.6)
DSH_TELEGRAM_FIT_SCORE_THRESHOLD = max(
    0, _env_int("DSH_TELEGRAM_FIT_SCORE_THRESHOLD", 80)
)
_raw_refund_cap_pct = _env_float("DSH_TELEGRAM_REFUND_CAP_PCT", 0.15)
if not (0.0 <= _raw_refund_cap_pct <= 1.0):
    raise ValueError(
        f"DSH_TELEGRAM_REFUND_CAP_PCT must be in [0, 1], got {_raw_refund_cap_pct}"
    )
DSH_TELEGRAM_REFUND_CAP_PCT = _raw_refund_cap_pct
DSH_TELEGRAM_REFUND_WINDOW_HOURS = max(
    0, _env_int("DSH_TELEGRAM_REFUND_WINDOW_HOURS", 24)
)
DSH_TELEGRAM_MAX_LEADS_PER_MISSION = max(
    0, _env_int("DSH_TELEGRAM_MAX_LEADS_PER_MISSION", 1)
)
DSH_TELEGRAM_CALLBACK_RATE_LIMIT_PER_MINUTE = max(
    0, _env_int("DSH_TELEGRAM_CALLBACK_RATE_LIMIT_PER_MINUTE", 60)
)

# Scheduled DSH mission tick interval (Story 6.10)
SCHEDULED_DSH_MISSION_TICK_SECONDS = int(
    os.getenv("SCHEDULED_DSH_MISSION_TICK_SECONDS", "60")
)



__all__ = [
    'DSH_CONSUMER_GROUP',
    'DSH_EXECUTOR_ENGINE',
    'DSH_HEARTBEAT_INTERVAL_SECONDS',
    'DSH_INTERNAL_BASE_URL',
    'DSH_LOCK_TTL_SECONDS',
    'DSH_MAX_PAYLOAD_BYTES',
    'DSH_MAX_RETRIES',
    'DSH_REDIS_BLOCK_MS',
    'DSH_STREAM_DLQ',
    'DSH_STREAM_TASKS',
    'DSH_SYNC_TIMEOUT_SECONDS',
    'DSH_TELEGRAM_CALLBACK_RATE_LIMIT_PER_MINUTE',
    'DSH_TELEGRAM_FIT_SCORE_THRESHOLD',
    'DSH_TELEGRAM_MAX_LEADS_PER_MISSION',
    'DSH_TELEGRAM_REFUND_CAP_PCT',
    'DSH_TELEGRAM_REFUND_WINDOW_HOURS',
    'DSH_WORKER_PAT',
    'DSH_WORKER_SECRET',
    'DSH_XAUTOCLAIM_MIN_IDLE_MS',
    'SCHEDULED_DSH_MISSION_TICK_SECONDS',
    '_raw_refund_cap_pct',
]
