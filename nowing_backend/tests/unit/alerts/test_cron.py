"""Unit tests for alert cron helpers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.alerts.engine.cron import (
    InvalidCronError,
    compute_next_fire_at,
    cron_for_schedule,
    derive_cron,
)

pytestmark = pytest.mark.unit


def test_cron_for_schedule():
    assert cron_for_schedule("none") is None
    assert cron_for_schedule("daily") == "0 0 * * *"
    assert cron_for_schedule("weekly") == "0 0 * * 1"
    assert cron_for_schedule("unknown") is None


def test_derive_cron_valid():
    assert derive_cron("daily", "UTC") == "0 0 * * *"
    assert derive_cron("weekly", "Asia/Ho_Chi_Minh") == "0 0 * * 1"
    assert derive_cron("none", "UTC") is None


def test_derive_cron_invalid_timezone():
    with pytest.raises(InvalidCronError):
        derive_cron("daily", "Mars/Phobos")


def test_compute_next_fire_at_daily():
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    nxt = compute_next_fire_at("0 0 * * *", "UTC", after=now)
    assert nxt == datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC)
