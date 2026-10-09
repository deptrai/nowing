"""Unit tests for Sequencer voice curfew scheduling (Story 38.4 / Decree 91).

Voice dispatch is bound to a stricter split window than email/text:
Mon-Fri only, 09:00-11:30 and 13:30-17:00 ICT, with the 11:30-13:30 lunch
break protected and weekends entirely banned.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.services.sequencer.constants import VN_TZ
from app.services.sequencer.scheduling import (
    calculate_step_eta,
    is_voice_curfew,
)

pytestmark = pytest.mark.unit


def _ict(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=VN_TZ)


class TestIsVoiceCurfew:
    """Decree 91 calling-window predicate."""

    @pytest.mark.parametrize(
        "moment",
        [
            _ict(2026, 10, 5, 9, 0),  # Mon 09:00 — open
            _ict(2026, 10, 5, 11, 30),  # Mon 11:30 — last morning minute
            _ict(2026, 10, 5, 13, 30),  # Mon 13:30 — afternoon opens
            _ict(2026, 10, 5, 17, 0),  # Mon 17:00 — last afternoon minute
        ],
    )
    def test_inside_window_is_not_curfew(self, moment: datetime) -> None:
        assert is_voice_curfew(moment) is False

    @pytest.mark.parametrize(
        "moment",
        [
            _ict(2026, 10, 5, 8, 59),  # before morning opens
            _ict(2026, 10, 5, 11, 31),  # just past morning close
            _ict(2026, 10, 5, 12, 15),  # protected lunch break
            _ict(2026, 10, 5, 13, 29),  # just before afternoon opens
            _ict(2026, 10, 5, 17, 1),  # just past afternoon close
            _ict(2026, 10, 5, 22, 0),  # evening
            _ict(2026, 10, 5, 3, 0),  # middle of the night
        ],
    )
    def test_outside_window_is_curfew(self, moment: datetime) -> None:
        assert is_voice_curfew(moment) is True

    @pytest.mark.parametrize(
        "moment",
        [
            _ict(2026, 10, 10, 10, 0),  # Saturday
            _ict(2026, 10, 11, 10, 0),  # Sunday
        ],
    )
    def test_weekend_is_always_curfew(self, moment: datetime) -> None:
        assert is_voice_curfew(moment) is True

    @pytest.mark.parametrize(
        "moment",
        [
            _ict(2026, 1, 1, 10, 0),  # Tết Dương lịch (Thursday)
            _ict(2026, 4, 30, 10, 0),  # Giải phóng (Thursday)
            _ict(2026, 5, 1, 10, 0),  # Lao động (Friday)
            _ict(2026, 9, 2, 10, 0),  # Quốc khánh (Wednesday)
        ],
    )
    def test_solar_public_holidays_are_always_curfew(self, moment: datetime) -> None:
        assert is_voice_curfew(moment) is True

    def test_naive_datetime_treated_as_utc(self) -> None:
        naive = datetime(2026, 10, 5, 2, 0)  # 09:00 ICT when read as UTC
        assert is_voice_curfew(naive) is False


class TestCalculateStepEtaVoice:
    """Voice ETA must land inside a legal calling window."""

    def test_inside_window_passes_through_unchanged(self) -> None:
        from_dt = _ict(2026, 10, 5, 10, 0)
        assert calculate_step_eta(0, from_dt, channel="voice") == from_dt

    def test_before_morning_opens_pushes_to_0905(self) -> None:
        from_dt = _ict(2026, 10, 5, 6, 30)
        eta = calculate_step_eta(0, from_dt, channel="voice")
        assert eta.date() == from_dt.date()
        assert eta.hour == 9
        assert 5 <= eta.minute <= 35  # 09:05 + up to 30 min jitter

    def test_lunch_break_pushes_to_1335(self) -> None:
        from_dt = _ict(2026, 10, 5, 12, 15)
        eta = calculate_step_eta(0, from_dt, channel="voice")
        # 13:35 + up to 30 min jitter — can land in hour 13 or 14
        assert eta.date() == from_dt.date()
        assert eta.hour in (13, 14)
        assert is_voice_curfew(eta) is False

    def test_after_afternoon_rolls_to_next_working_day(self) -> None:
        friday_evening = _ict(2026, 10, 9, 18, 0)  # Friday
        eta = calculate_step_eta(0, friday_evening, channel="voice")
        # Weekend is banned, so the next dialable day is Monday.
        assert eta.date() == datetime(2026, 10, 12).date()
        assert eta.hour == 9

    def test_saturday_rolls_to_monday(self) -> None:
        saturday = _ict(2026, 10, 10, 10, 0)
        eta = calculate_step_eta(0, saturday, channel="voice")
        assert eta.date() == datetime(2026, 10, 12).date()
        assert eta.hour == 9

    def test_sunday_rolls_to_monday(self) -> None:
        sunday = _ict(2026, 10, 11, 10, 0)
        eta = calculate_step_eta(0, sunday, channel="voice")
        assert eta.date() == datetime(2026, 10, 12).date()
        assert eta.hour == 9

    def test_delay_can_push_into_curfew(self) -> None:
        # 16:50 + 30min delay = 17:20 -> outside 17:00 afternoon window
        # Pushes to Tuesday morning (weekday 1)
        from_dt = _ict(2026, 10, 5, 16, 50)
        eta = calculate_step_eta(1800, from_dt, channel="voice")
        assert eta.weekday() == 1  # Tuesday
        assert (eta.hour, eta.minute) >= (9, 5)

    def test_result_always_legal(self) -> None:
        """Property check: whatever the input, the returned ETA is dialable."""
        for hour in range(0, 24):
            for minute in (0, 15, 30, 45):
                from_dt = _ict(2026, 10, 5, hour, minute)
                eta = calculate_step_eta(0, from_dt, channel="voice")
                assert is_voice_curfew(eta) is False, (
                    f"ETA {eta} is inside a curfew window"
                )


class TestCalculateStepEtaEmailUnchanged:
    """The existing email window must not regress."""

    def test_email_window_unchanged_at_10am(self) -> None:
        from_dt = _ict(2026, 10, 5, 10, 0)
        assert calculate_step_eta(0, from_dt) == from_dt

    def test_email_still_blocked_after_21(self) -> None:
        from_dt = _ict(2026, 10, 5, 22, 0)
        eta = calculate_step_eta(0, from_dt)
        assert eta.hour == 8 and eta.minute >= 5

    def test_voice_is_stricter_than_email(self) -> None:
        """12:00 is fine for email but illegal for voice."""
        from_dt = _ict(2026, 10, 5, 12, 0)
        assert calculate_step_eta(0, from_dt) == from_dt
        assert calculate_step_eta(0, from_dt, channel="voice") != from_dt
