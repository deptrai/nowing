"""Unit tests for ScraperPlatformAccountService and Rotator."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.services.scraper_platform_account_service import (
    RateLimit,
    ScraperPlatformAccountRotator,
    ScraperPlatformAccountService,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _mock_decrypt(mocker):
    mocker.patch(
        "app.services.scraper_platform_account_service.decrypt_credentials",
        return_value={"cookies": "a=1"},
    )


@pytest.fixture
def fake_account(mocker):
    return mocker.Mock(
        id=1,
        usage_state={},
        last_used_at=None,
        encrypted_credentials="enc",
    )


@pytest.mark.asyncio
async def test_rotator_picks_least_recent_account(mocker, fake_account):
    service = mocker.AsyncMock(spec=ScraperPlatformAccountService)
    used_account = mocker.Mock(
        id=2,
        usage_state={},
        last_used_at=datetime.now(UTC),
        encrypted_credentials="enc",
    )
    service.list_enabled.return_value = [used_account, fake_account]

    rotator = ScraperPlatformAccountRotator(
        service, "batdongsan", RateLimit(requests_per_minute=60.0, burst=2)
    )
    account, credentials = await rotator.get_credentials(wait=False, timeout=0)

    assert account is fake_account
    assert credentials == {"cookies": "a=1"}


@pytest.mark.asyncio
async def test_rotator_rate_limit_blocks_excess_requests(mocker, fake_account):
    service = mocker.AsyncMock(spec=ScraperPlatformAccountService)
    service.list_enabled.return_value = [fake_account]

    rotator = ScraperPlatformAccountRotator(
        service, "batdongsan", RateLimit(requests_per_minute=60.0, burst=1)
    )

    first, _ = await rotator.get_credentials(wait=False, timeout=0)
    assert first is fake_account

    second, _ = await rotator.get_credentials(wait=False, timeout=0)
    assert second is None


@pytest.mark.asyncio
async def test_rotator_records_restricted_cooldown(mocker, fake_account):
    service = mocker.AsyncMock(spec=ScraperPlatformAccountService)
    service.list_enabled.return_value = [fake_account]

    rotator = ScraperPlatformAccountRotator(
        service, "batdongsan", RateLimit(cooldown_seconds=60.0)
    )

    account, _ = await rotator.get_credentials(wait=False, timeout=0)
    await rotator.record_use(account, success=False, error_type="restricted")

    assert fake_account.usage_state["banned_until"] > 0
    assert fake_account.usage_state["consecutive_failures"] == 1

    next_account, _ = await rotator.get_credentials(wait=False, timeout=0)
    assert next_account is None


@pytest.mark.asyncio
async def test_rotator_records_rate_limited_cooldown(mocker, fake_account):
    service = mocker.AsyncMock(spec=ScraperPlatformAccountService)
    service.list_enabled.return_value = [fake_account]

    rotator = ScraperPlatformAccountRotator(
        service, "batdongsan", RateLimit(cooldown_seconds=30.0)
    )

    account, _ = await rotator.get_credentials(wait=False, timeout=0)
    await rotator.record_use(account, success=False, error_type="rate_limited")

    assert fake_account.usage_state["banned_until"] > 0


@pytest.mark.asyncio
async def test_rotator_resets_consecutive_failures_on_success(mocker, fake_account):
    service = mocker.AsyncMock(spec=ScraperPlatformAccountService)
    service.list_enabled.return_value = [fake_account]

    rotator = ScraperPlatformAccountRotator(
        service, "batdongsan", RateLimit(max_consecutive_failures=2)
    )

    account, _ = await rotator.get_credentials(wait=False, timeout=0)
    await rotator.record_use(account, success=False, error_type="other")
    await rotator.record_use(account, success=True)

    assert fake_account.usage_state.get("consecutive_failures", 0) == 0
