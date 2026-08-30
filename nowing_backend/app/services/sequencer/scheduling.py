"""Sequencer scheduling helpers: quiet hours and anti-thundering herd jitter."""

from __future__ import annotations

import random
from datetime import UTC, datetime, time, timedelta

from app.services.sequencer.constants import VN_TZ


def calculate_step_eta(delay_seconds: int, from_dt: datetime | None = None) -> datetime:
    """Calculate the next execution timestamp respecting Vietnam quiet hours (08:00 - 21:30 VN Time).

    If target timestamp falls outside the sending window:
    - Before 08:00 -> push to 08:05 today + random jitter (0-1800s).
    - After 21:30 -> push to 08:05 tomorrow + random jitter (0-1800s).
    """
    if from_dt is None:
        from_dt = datetime.now(VN_TZ)
    elif from_dt.tzinfo is None:
        from_dt = from_dt.replace(tzinfo=UTC).astimezone(VN_TZ)
    else:
        from_dt = from_dt.astimezone(VN_TZ)

    delay_seconds = max(delay_seconds, 0)
    target_dt = from_dt + timedelta(seconds=delay_seconds)
    current_minute = target_dt.hour * 60 + target_dt.minute
    start_minute = 8 * 60  # 08:00
    end_minute = 21 * 60 + 30  # 21:30

    if start_minute <= current_minute <= end_minute:
        return target_dt

    jitter_seconds = random.randint(0, 1800)
    if current_minute < start_minute:
        next_send = datetime.combine(
            target_dt.date(), time(hour=8, minute=5), tzinfo=VN_TZ
        )
    else:
        next_day = target_dt.date() + timedelta(days=1)
        next_send = datetime.combine(next_day, time(hour=8, minute=5), tzinfo=VN_TZ)

    return next_send + timedelta(seconds=jitter_seconds)
