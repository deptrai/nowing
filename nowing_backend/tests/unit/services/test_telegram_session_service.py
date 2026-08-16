"""Unit tests for Telegram Session Lock & Rotator Service (Story 22.2 / AC-3, AC-4, AD-2, AD-3)."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = [
    pytest.mark.unit,
]


@pytest.mark.asyncio
async def test_telegram_session_lock_acquire_success() -> None:
    """Test acquiring Redis mutex lock on telegram session (AC-3, AD-2)."""
    from app.services.telegram_session_service import TelegramSessionLock

    redis_mock = MagicMock()
    redis_mock.set = AsyncMock(return_value=True)

    lock = TelegramSessionLock(redis_client=redis_mock, account_id=42, ttl_seconds=120)
    acquired = await lock.acquire()

    assert acquired is True
    redis_mock.set.assert_awaited_once()
    call_args = redis_mock.set.await_args
    assert call_args[0][0] == "telegram:session:lock:42"
    assert call_args[1].get("nx") is True
    assert call_args[1].get("ex") == 120


@pytest.mark.asyncio
async def test_telegram_session_lock_conflict_fails() -> None:
    """Test lock acquisition fails when already acquired by another worker (AC-3)."""
    from app.services.telegram_session_service import (
        TelegramSessionLock,
        TelegramSessionLockError,
    )

    redis_mock = MagicMock()
    redis_mock.set = AsyncMock(return_value=None)

    lock = TelegramSessionLock(redis_client=redis_mock, account_id=42, ttl_seconds=120)
    acquired = await lock.acquire()

    assert acquired is False

    with pytest.raises(TelegramSessionLockError):
        async with lock:
            pass


@pytest.mark.asyncio
async def test_telegram_session_lock_release_safe() -> None:
    """Test safe release of Redis mutex lock (AC-3)."""
    from app.services.telegram_session_service import TelegramSessionLock

    redis_mock = MagicMock()
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.eval = AsyncMock(return_value=1)

    lock = TelegramSessionLock(redis_client=redis_mock, account_id=42, ttl_seconds=120)
    await lock.acquire()
    released = await lock.release()

    assert released is True
    redis_mock.eval.assert_awaited_once()


@pytest.mark.asyncio
async def test_telegram_session_lock_context_manager() -> None:
    """Test async context manager for automatic lock acquisition and release."""
    from app.services.telegram_session_service import TelegramSessionLock

    redis_mock = MagicMock()
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.eval = AsyncMock(return_value=1)

    lock = TelegramSessionLock(redis_client=redis_mock, account_id=10, ttl_seconds=120)
    async with lock:
        assert lock.is_locked is True

    assert lock.is_locked is False


def test_calculate_flood_wait_cooldown_with_jitter() -> None:
    """Test FloodWait cooldown calculation includes 2-5 seconds jitter (AC-4, AD-3)."""
    from app.services.telegram_session_service import calculate_flood_wait_cooldown

    before_ts = time.time()
    banned_until = calculate_flood_wait_cooldown(flood_seconds=60)
    after_ts = time.time()

    min_expected = before_ts + 60 + 2.0
    max_expected = after_ts + 60 + 5.0

    assert min_expected <= banned_until <= max_expected

    # Test safe clamping for negative / zero values
    safe_cooldown = calculate_flood_wait_cooldown(flood_seconds=-10)
    assert safe_cooldown >= before_ts + 5.0 + 2.0


@pytest.mark.asyncio
async def test_telegram_rotator_rotates_on_flood_wait(mocker) -> None:
    """Test rotator marks throttled account with cooldown and rotates to alternate account (AC-4)."""
    from app.services.scraper_platform_account_service import (
        RateLimit,
        ScraperPlatformAccountRotator,
        ScraperPlatformAccountService,
    )
    from app.services.telegram_session_service import TelegramSessionService

    mocker.patch(
        "app.services.scraper_platform_account_service.decrypt_credentials",
        return_value={"api_id": 123, "api_hash": "abc", "session_string": "xyz"},
    )

    service = mocker.AsyncMock(spec=ScraperPlatformAccountService)
    acc1 = mocker.Mock(
        id=1, usage_state={}, last_used_at=None, encrypted_credentials="enc1"
    )
    acc2 = mocker.Mock(
        id=2, usage_state={}, last_used_at=None, encrypted_credentials="enc2"
    )
    service.list_enabled.return_value = [acc1, acc2]

    rotator = ScraperPlatformAccountRotator(service, "telegram", RateLimit())
    telegram_session_svc = TelegramSessionService(
        rotator=rotator, redis_client=MagicMock()
    )

    # Simulate flood wait error on account 1 for 30s
    now = time.time()
    await telegram_session_svc.handle_flood_wait(acc1, wait_seconds=30)
    # Check that custom cooldown (30s + 2-5s) was recorded rather than default 300s
    assert now + 32.0 <= acc1.usage_state["banned_until"] <= now + 36.0

    # Next credential fetch should return account 2
    next_acc, _creds = await rotator.get_credentials(wait=False, timeout=0)
    assert next_acc is acc2
