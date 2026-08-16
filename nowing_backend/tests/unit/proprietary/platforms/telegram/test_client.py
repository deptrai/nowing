"""Unit tests for Telethon MTProto Client Wrapper (Story 22.2 / AC-2, AD-1)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [
    pytest.mark.unit,
]


def test_telethon_scraper_client_init_from_string_session() -> None:
    """Test TelethonScraperClient initializes with StringSession without disk .session files (AD-1)."""
    from app.proprietary.platforms.telegram.client import TelethonScraperClient

    credentials = {
        "api_id": 123456,
        "api_hash": "abcdef0123456789abcdef0123456789",
        "session_string": "1BJWap1wBu8...",
    }

    client = TelethonScraperClient.from_credentials(credentials)
    assert client.api_id == 123456
    assert client.api_hash == "abcdef0123456789abcdef0123456789"
    assert client.session_string == "1BJWap1wBu8..."
    assert getattr(client, "is_in_memory_only", True) is True


def test_telethon_scraper_client_socks5_proxy_parsing() -> None:
    """Test parsing socks5h:// proxy url into Telethon proxy dict (AC-2)."""
    from app.proprietary.platforms.telegram.client import (
        TelethonScraperClient,
        parse_proxy_url,
    )

    proxy_url = "socks5h://user:pass123@192.168.1.100:1080"
    proxy_config = parse_proxy_url(proxy_url)

    assert proxy_config is not None
    assert proxy_config["proxy_type"] in ("socks5", 2)
    assert proxy_config["addr"] == "192.168.1.100"
    assert proxy_config["port"] == 1080
    assert proxy_config["username"] == "user"
    assert proxy_config["password"] == "pass123"
    assert proxy_config["rdns"] is True

    credentials = {
        "api_id": 123456,
        "api_hash": "abcdef0123456789",
        "session_string": "1BJWap1wBu8...",
        "proxy_url": proxy_url,
    }
    client = TelethonScraperClient.from_credentials(credentials)
    assert client.proxy == proxy_config


@pytest.mark.asyncio
async def test_telethon_scraper_client_context_manager_lifecycle(mocker) -> None:
    """Test async context manager connects and disconnects gracefully in memory."""
    from app.proprietary.platforms.telegram.client import TelethonScraperClient

    credentials = {
        "api_id": 123456,
        "api_hash": "abcdef0123456789",
        "session_string": "1BJWap1wBu8...",
    }

    mock_raw_client = MagicMock()
    mock_raw_client.connect = AsyncMock()
    mock_raw_client.disconnect = AsyncMock()
    mock_raw_client.is_connected = MagicMock(side_effect=[False, True, True, True])

    with (
        patch("app.proprietary.platforms.telegram.client.StringSession"),
        patch(
            "app.proprietary.platforms.telegram.client.TelegramClient",
            return_value=mock_raw_client,
        ),
    ):
        client = TelethonScraperClient.from_credentials(credentials)
        async with client:
            mock_raw_client.connect.assert_awaited_once()
            assert client.is_connected is True

        mock_raw_client.disconnect.assert_awaited_once()
        assert client.is_connected is False


@pytest.mark.asyncio
async def test_telethon_scraper_client_fetch_messages(mocker) -> None:
    """Test fetching messages converts Telethon entities to TelegramChannelMessage domain models."""
    from app.proprietary.platforms.telegram.client import TelethonScraperClient
    from app.proprietary.platforms.telegram.models import TelegramChannelMessage

    credentials = {
        "api_id": 123456,
        "api_hash": "abcdef0123456789",
        "session_string": "1BJWap1wBu8...",
    }

    mock_msg = MagicMock()
    mock_msg.id = 5001
    mock_msg.message = "Bán biệt thự Ciputra 200m2 giá 35 tỷ. SĐT 0912345678"
    mock_msg.views = 1200
    mock_msg.date = MagicMock()
    mock_msg.date.isoformat.return_value = "2026-08-16T12:00:00+00:00"
    mock_msg.media = True
    mock_msg.sender = MagicMock()
    mock_msg.sender.first_name = "Ciputra"
    mock_msg.sender.last_name = "Broker"

    client = TelethonScraperClient.from_credentials(credentials)
    client._raw_client = MagicMock()
    client._raw_client.iter_messages = MagicMock(return_value=[mock_msg])
    client._is_connected = True

    messages = await client.get_channel_messages("ciputrahanoi", limit=10)
    assert len(messages) == 1
    assert isinstance(messages[0], TelegramChannelMessage)
    assert messages[0].message_id == 5001
    assert "Ciputra" in messages[0].text
    assert messages[0].views == 1200
    assert "0912345678" in messages[0].entities.phone_numbers


@pytest.mark.asyncio
async def test_telethon_scraper_client_flood_wait_error_handling() -> None:
    """Test FloodWaitError from Telethon is preserved and propagated with wait seconds (AC-4)."""
    from telethon.errors import FloodWaitError

    from app.proprietary.platforms.telegram.client import TelethonScraperClient

    credentials = {
        "api_id": 123456,
        "api_hash": "abcdef0123456789",
        "session_string": "1BJWap1wBu8...",
    }

    client = TelethonScraperClient.from_credentials(credentials)
    client._raw_client = MagicMock()
    client._raw_client.get_entity = AsyncMock(
        side_effect=FloodWaitError(request=None, capture=45)
    )
    client._is_connected = True

    with pytest.raises(FloodWaitError) as exc_info:
        await client.get_channel_entity("private_channel_xyz")

    assert exc_info.value.seconds == 45
