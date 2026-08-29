"""Config domain: memory."""

from __future__ import annotations

import os

from app.config._helpers import (
    _env_choice,
    _env_float,
    _env_int,
)

# Memory auto-extraction defaults.
MEMORY_AUTO_EXTRACT_ENABLED = (
    os.getenv("MEMORY_AUTO_EXTRACT_ENABLED", "true").strip().lower() == "true"
)
MEMORY_AUTO_EXTRACT_CONFIDENCE = max(
    0.0, min(1.0, _env_float("MEMORY_AUTO_EXTRACT_CONFIDENCE", 0.7))
)
MEMORY_AUTO_EXTRACT_MAX_ITEMS = max(1, _env_int("MEMORY_AUTO_EXTRACT_MAX_ITEMS", 3))

# Memory auto-extraction cost controls (Story 8.7 / AR-6 / RS-1).
# The budget cap and rate-limit default to disabled/no-op so enabling
# auto-extract introduces no new gating until an operator opts in. The
# wallet pre-check is the only always-on gate, but note what it is: an
# ELIGIBILITY gate (skip optional background work for an owner who cannot
# pay for their foreground work), NOT a spend meter for extraction. Per
# AD-8 the wallet-debit surface is ETL pages / premium model calls /
# deep-research; memory extraction is deliberately excluded, and
# usage_type="memory_create" is Story 8.9's observability record, not a
# debit. The bounds that actually apply to extraction spend are
# MEMORY_AUTO_EXTRACT_ENABLED (kill-switch, Story 8.8) and the opt-in
# budget cap below. See app.services.memory.extract_budget.
#
# Clamped to >= 1: 0 would disable the always-on gate entirely. Use 1 to
# mean "only block a fully empty wallet".
MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS = max(
    1, _env_int("MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS", 100)
)
# Per-workspace spend ceiling (micro-USD) for memory_create TokenUsage over
# the current MEMORY_AUTO_EXTRACT_BUDGET_WINDOW. 0 = disabled (no gating).
# Ships at 0 on purpose: AD-8's 2026-07-25 amendment forbids fixing a cost
# figure before story 8-7 + FR-37 produce measured numbers.
# Clamped to >= 0: negative values are treated as disabled, but we normalise
# them to 0 to match the documented "0 = disabled" convention.
MEMORY_AUTO_EXTRACT_BUDGET_MICROS = max(
    0, _env_int("MEMORY_AUTO_EXTRACT_BUDGET_MICROS", 0)
)
# Rolling budget window; "day" is a rolling 24h lookback (not a calendar-day
# cliff) to avoid a midnight reset that lets a burst through right after
# rollover. "month" is a flat 30-day lookback, not a calendar month.
MEMORY_AUTO_EXTRACT_BUDGET_WINDOW = _env_choice(
    "MEMORY_AUTO_EXTRACT_BUDGET_WINDOW", "day", ("day", "week", "month")
)
# Max extractions per workspace per MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS.
# 0 = disabled (no throttling). Clamped to >= 0 for the same reason as
# MEMORY_AUTO_EXTRACT_BUDGET_MICROS.
MEMORY_AUTO_EXTRACT_RATE_MAX = max(0, _env_int("MEMORY_AUTO_EXTRACT_RATE_MAX", 0))
# Clamped to >= 1: Redis EXPIRE with a non-positive TTL deletes the key, so
# 0 would make every increment self-destruct and silently void the limit.
MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS = max(
    1, _env_int("MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS", 3600)
)

# News entity extraction defaults and cost controls (Story 14.2a)
NEWS_ENTITY_EXTRACTION_ENABLED = (
    os.getenv("NEWS_ENTITY_EXTRACTION_ENABLED", "true").strip().lower() == "true"
)
NEWS_ENTITY_EXTRACTION_CONFIDENCE = max(
    0.0, min(1.0, _env_float("NEWS_ENTITY_EXTRACTION_CONFIDENCE", 0.6))
)
NEWS_ENTITY_EXTRACTION_MIN_RESERVE_MICROS = max(
    0, _env_int("NEWS_ENTITY_EXTRACTION_MIN_RESERVE_MICROS", 0)
)
NEWS_ENTITY_EXTRACTION_BUDGET_MICROS = max(
    0, _env_int("NEWS_ENTITY_EXTRACTION_BUDGET_MICROS", 0)
)
NEWS_ENTITY_EXTRACTION_BUDGET_WINDOW = _env_choice(
    "NEWS_ENTITY_EXTRACTION_BUDGET_WINDOW", "day", ("day", "week", "month")
)
NEWS_ENTITY_EXTRACTION_RATE_MAX = max(
    0, _env_int("NEWS_ENTITY_EXTRACTION_RATE_MAX", 0)
)
NEWS_ENTITY_EXTRACTION_RATE_WINDOW_SECONDS = max(
    1, _env_int("NEWS_ENTITY_EXTRACTION_RATE_WINDOW_SECONDS", 3600)
)

NOWING_PUBLIC_URL = os.getenv("NOWING_PUBLIC_URL")
NEXT_FRONTEND_URL = os.getenv("NEXT_FRONTEND_URL") or NOWING_PUBLIC_URL


__all__ = ['MEMORY_AUTO_EXTRACT_BUDGET_MICROS', 'MEMORY_AUTO_EXTRACT_BUDGET_WINDOW', 'MEMORY_AUTO_EXTRACT_CONFIDENCE', 'MEMORY_AUTO_EXTRACT_ENABLED', 'MEMORY_AUTO_EXTRACT_MAX_ITEMS', 'MEMORY_AUTO_EXTRACT_MIN_RESERVE_MICROS', 'MEMORY_AUTO_EXTRACT_RATE_MAX', 'MEMORY_AUTO_EXTRACT_RATE_WINDOW_SECONDS', 'NEWS_ENTITY_EXTRACTION_BUDGET_MICROS', 'NEWS_ENTITY_EXTRACTION_BUDGET_WINDOW', 'NEWS_ENTITY_EXTRACTION_CONFIDENCE', 'NEWS_ENTITY_EXTRACTION_ENABLED', 'NEWS_ENTITY_EXTRACTION_MIN_RESERVE_MICROS', 'NEWS_ENTITY_EXTRACTION_RATE_MAX', 'NEWS_ENTITY_EXTRACTION_RATE_WINDOW_SECONDS', 'NEXT_FRONTEND_URL', 'NOWING_PUBLIC_URL']
