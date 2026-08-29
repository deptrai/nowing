"""Config domain: database."""

from __future__ import annotations

import os

from app.config._helpers import (
    _env_int,
)

# Database
DATABASE_URL = os.getenv("DATABASE_URL")

# Multi-channel sequencer outbound channels feature gate (AD-41 / Story 24.7)
SEQUENCER_OUTBOUND_CHANNELS: str = os.getenv("SEQUENCER_OUTBOUND_CHANNELS", "email")
SEQUENCE_EMAIL_COST_MICROS: int = _env_int("SEQUENCE_EMAIL_COST_MICROS", 500)
SEQUENCE_ZNS_COST_MICROS: int = _env_int("SEQUENCE_ZNS_COST_MICROS", 300)
SEQUENCE_TELEGRAM_COST_MICROS: int = _env_int("SEQUENCE_TELEGRAM_COST_MICROS", 0)
SEQUENCE_ZNS_MAX_RESCHEDULE_HOURS: int = _env_int(
    "SEQUENCE_ZNS_MAX_RESCHEDULE_HOURS", 24
)
AD_41_REACTIVATED: bool = os.getenv("AD_41_REACTIVATED", "FALSE").upper() == "TRUE"

# When TRUE (default) the app ensures extensions/tables/indexes exist on
# startup. Set FALSE in environments where schema is owned exclusively by
# Alembic migrations to skip all boot-time DDL.
DB_BOOTSTRAP_ON_STARTUP = (
    os.getenv("DB_BOOTSTRAP_ON_STARTUP", "TRUE").upper() == "TRUE"
)
# Per-session lock_timeout (ms) applied to boot-time DDL so a contended
# CREATE INDEX / CREATE TABLE fails fast instead of hanging the FastAPI
# lifespan forever behind another transaction's lock.
DB_DDL_LOCK_TIMEOUT_MS = int(os.getenv("DB_DDL_LOCK_TIMEOUT_MS", "5000"))
# Global idle_in_transaction_session_timeout (ms) applied to every pooled
# connection so an abandoned "idle in transaction" session can't wedge the
# database indefinitely. 0 disables. Only applied to asyncpg connections.
DB_IDLE_IN_TX_TIMEOUT_MS = int(os.getenv("DB_IDLE_IN_TX_TIMEOUT_MS", "900000"))
# Same protection for the separate Celery worker engine, where long-running
# ingestion/podcast/video tasks live. Kept higher than the web default so a
# legitimate per-document embed window is never reaped: if a task hasn't
# touched the DB in 60 min it's treated as orphaned and dropped. 0 disables.
DB_CELERY_IDLE_IN_TX_TIMEOUT_MS = int(
    os.getenv("DB_CELERY_IDLE_IN_TX_TIMEOUT_MS", "3600000")
)



__all__ = ['AD_41_REACTIVATED', 'DATABASE_URL', 'DB_BOOTSTRAP_ON_STARTUP', 'DB_CELERY_IDLE_IN_TX_TIMEOUT_MS', 'DB_DDL_LOCK_TIMEOUT_MS', 'DB_IDLE_IN_TX_TIMEOUT_MS', 'SEQUENCER_OUTBOUND_CHANNELS', 'SEQUENCE_EMAIL_COST_MICROS', 'SEQUENCE_TELEGRAM_COST_MICROS', 'SEQUENCE_ZNS_COST_MICROS', 'SEQUENCE_ZNS_MAX_RESCHEDULE_HOURS']
