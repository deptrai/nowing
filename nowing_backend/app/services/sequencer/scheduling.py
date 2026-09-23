"""Sequencer scheduling helpers: Decree 91 curfew and anti-thundering herd jitter."""

from __future__ import annotations

import random
from datetime import UTC, datetime, time, timedelta

from app.services.sequencer.constants import VN_TZ

# Decree 91/2020/NĐ-CP (Story 37.2 / AC-4): outbound dispatch halts between
# 21:00 and 08:00 ICT. The send window is therefore 08:00 - 21:00 ICT.
CURFEW_START_MINUTE = 21 * 60  # 21:00 ICT — dispatch halt begins
CURFEW_END_MINUTE = 8 * 60  # 08:00 ICT — dispatch resumes


def is_dispatch_curfew(now: datetime | None = None) -> bool:
    """True when outbound message dispatch is halted by the 21:00-08:00 ICT curfew.

    Scope: this gate applies to unsolicited outbound marketing dispatch only.
    Two-way auto-replies responding to an inbound prospect message are EXEMPT —
    Decree 91/2020/NĐ-CP targets outbound advertising, not replies the
    prospect initiated. This is also the shared source of truth for the ZNS
    sending-window check in ``app.gateway.zalo.zns_client``.
    """
    if now is None:
        now = datetime.now(VN_TZ)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=UTC).astimezone(VN_TZ)
    else:
        now = now.astimezone(VN_TZ)
    minute = now.hour * 60 + now.minute
    return minute >= CURFEW_START_MINUTE or minute < CURFEW_END_MINUTE


def calculate_step_eta(delay_seconds: int, from_dt: datetime | None = None) -> datetime:
    """Calculate the next execution timestamp respecting the Decree 91 curfew (08:00 - 21:00 VN Time).

    If target timestamp falls outside the sending window:
    - Before 08:00 -> push to 08:05 today + random jitter (0-1800s).
    - At/after 21:00 -> push to 08:05 tomorrow + random jitter (0-1800s).
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
    start_minute = CURFEW_END_MINUTE  # 08:00
    end_minute = CURFEW_START_MINUTE - 1  # last sendable minute: 20:59

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
