"""Sequencer scheduling helpers: Decree 91 curfew and anti-thundering herd jitter."""

from __future__ import annotations

import random
from datetime import UTC, datetime, time, timedelta

from app.services.sequencer.constants import VN_TZ

# Decree 91/2020/NĐ-CP (Story 37.2 / AC-4): outbound dispatch halts between
# 21:00 and 08:00 ICT. The send window is therefore 08:00 - 21:00 ICT.
CURFEW_START_MINUTE = 21 * 60  # 21:00 ICT — dispatch halt begins
CURFEW_END_MINUTE = 8 * 60  # 08:00 ICT — dispatch resumes

# Story 38.4: Decree 91 restricts unsolicited *telephone* solicitation to a
# tighter, split daily window than text/email dispatch: Mon-Fri only, two
# blocks with a protected lunch break in between. Minutes-from-midnight ICT.
VOICE_WINDOW_MORNING_START = 9 * 60  # 09:00 ICT
VOICE_WINDOW_MORNING_END = 11 * 60 + 30  # 11:30 ICT
VOICE_WINDOW_AFTERNOON_START = 13 * 60 + 30  # 13:30 ICT
VOICE_WINDOW_AFTERNOON_END = 17 * 60  # 17:00 ICT

# Monday=0 … Sunday=6. Telephone solicitation is banned at the weekend.
VOICE_ALLOWED_WEEKDAYS = frozenset({0, 1, 2, 3, 4})

# Fixed solar VN public holidays: (1, 1) Tết Dương, (4, 30) Giải phóng, (5, 1) Lao động, (9, 2) Quốc khánh.
# shortcut: static solar holidays only; lunar Tet needs a lunar calendar or per-year table, upgrade when voice volume justifies it
VN_SOLAR_PUBLIC_HOLIDAYS = frozenset({(1, 1), (4, 30), (5, 1), (9, 2)})

# Post-window dispatch time: 09:05 and 13:35 ICT (5 min after each block opens)
# so we never dial exactly on the boundary, plus the shared 0-1800s jitter.
_VOICE_MORNING_REOPEN = time(hour=9, minute=5)
_VOICE_AFTERNOON_REOPEN = time(hour=13, minute=35)

_JITTER_MAX_SECONDS = 1800


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


def is_voice_curfew(now: datetime | None = None) -> bool:
    """True when *outbound voice* dialing is prohibited by Decree 91.

    Unlike text/email, telephone solicitation is only permitted Mon-Fri
    09:00-11:30 and 13:30-17:00 ICT. Outside those windows — including the
    11:30-13:30 lunch break and the whole weekend — dialing is prohibited.

    Story 38.4. Shares VN_TZ normalisation with :func:`is_dispatch_curfew`.
    """
    if now is None:
        now = datetime.now(VN_TZ)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=UTC).astimezone(VN_TZ)
    else:
        now = now.astimezone(VN_TZ)

    if (now.month, now.day) in VN_SOLAR_PUBLIC_HOLIDAYS:
        return True

    if now.weekday() not in VOICE_ALLOWED_WEEKDAYS:
        return True

    minute = now.hour * 60 + now.minute
    in_morning = VOICE_WINDOW_MORNING_START <= minute <= VOICE_WINDOW_MORNING_END
    in_afternoon = VOICE_WINDOW_AFTERNOON_START <= minute <= VOICE_WINDOW_AFTERNOON_END
    return not (in_morning or in_afternoon)


def _next_voice_window(dt: datetime) -> datetime:
    """First dialable moment at or after *dt*, honouring the split window."""
    # Weekend: advance immediately to next working day morning.
    if dt.weekday() not in VOICE_ALLOWED_WEEKDAYS:
        candidate = dt.date() + timedelta(days=1)
        while candidate.weekday() not in VOICE_ALLOWED_WEEKDAYS:
            candidate += timedelta(days=1)
        return datetime.combine(candidate, _VOICE_MORNING_REOPEN, tzinfo=VN_TZ)

    minute = dt.hour * 60 + dt.minute

    # Working day, before the morning block opens.
    if minute < VOICE_WINDOW_MORNING_START:
        return datetime.combine(dt.date(), _VOICE_MORNING_REOPEN, tzinfo=VN_TZ)

    # Working day, inside the morning block, or in the protected lunch break.
    if minute <= VOICE_WINDOW_AFTERNOON_START:
        return datetime.combine(dt.date(), _VOICE_AFTERNOON_REOPEN, tzinfo=VN_TZ)

    # After the afternoon block closes — roll to the next working day.
    candidate = dt.date() + timedelta(days=1)
    while candidate.weekday() not in VOICE_ALLOWED_WEEKDAYS:
        candidate += timedelta(days=1)
    return datetime.combine(candidate, _VOICE_MORNING_REOPEN, tzinfo=VN_TZ)


def calculate_step_eta(
    delay_seconds: int,
    from_dt: datetime | None = None,
    channel: str = "email",
) -> datetime:
    """Calculate the next execution timestamp respecting the Decree 91 curfew.

    Args:
        delay_seconds: Delay to add to *from_dt* before applying the curfew.
        from_dt: Reference time; defaults to now. Naive values are read as UTC.
        channel: ``"email"`` (and other text channels) use the 08:00-21:00
            window. ``"voice"`` uses Decree 91's stricter split window —
            Mon-Fri 09:00-11:30 and 13:30-17:00 ICT (Story 38.4).

    Returns:
        The ETA, shifted forward plus jitter when it lands outside the
        window permitted for *channel*.
    """
    if from_dt is None:
        from_dt = datetime.now(VN_TZ)
    elif from_dt.tzinfo is None:
        from_dt = from_dt.replace(tzinfo=UTC).astimezone(VN_TZ)
    else:
        from_dt = from_dt.astimezone(VN_TZ)

    delay_seconds = max(delay_seconds, 0)
    target_dt = from_dt + timedelta(seconds=delay_seconds)

    if channel == "voice":
        if not is_voice_curfew(target_dt):
            return target_dt
        return _next_voice_window(target_dt) + timedelta(
            seconds=random.randint(0, _JITTER_MAX_SECONDS)
        )

    current_minute = target_dt.hour * 60 + target_dt.minute
    start_minute = CURFEW_END_MINUTE  # 08:00
    end_minute = CURFEW_START_MINUTE - 1  # last sendable minute: 20:59

    if start_minute <= current_minute <= end_minute:
        return target_dt

    jitter_seconds = random.randint(0, _JITTER_MAX_SECONDS)
    if current_minute < start_minute:
        next_send = datetime.combine(
            target_dt.date(), time(hour=8, minute=5), tzinfo=VN_TZ
        )
    else:
        next_day = target_dt.date() + timedelta(days=1)
        next_send = datetime.combine(next_day, time(hour=8, minute=5), tzinfo=VN_TZ)

    return next_send + timedelta(seconds=jitter_seconds)
