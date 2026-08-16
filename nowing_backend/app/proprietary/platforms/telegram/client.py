"""In-memory Telethon MTProto Client Wrapper with SOCKS5 Proxy Routing (Story 22.2 / AC-2, AD-1)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from telethon import TelegramClient
from telethon.sessions import StringSession

from app.proprietary.platforms.telegram.entity_extractor import TelegramEntityExtractor
from app.proprietary.platforms.telegram.models import TelegramChannelMessage
from app.proprietary.platforms.telegram.schemas import ExtractedEntities

logger = logging.getLogger(__name__)


def parse_proxy_url(proxy_url: str | None) -> dict[str, Any] | None:
    """Parse proxy URL (e.g. socks5h://user:pass@host:port) into Telethon / python-socks proxy dict.

    Supports socks5, socks5h, socks4, http, https schemes.
    """
    if not proxy_url or not proxy_url.strip():
        return None

    parsed = urlparse(proxy_url.strip())
    scheme = (parsed.scheme or "socks5").lower()

    # Map scheme to proxy type
    proxy_type = "socks5"
    rdns = True
    if scheme in ("socks5h", "socks5"):
        proxy_type = "socks5"
        rdns = True
    elif scheme in ("socks4a", "socks4"):
        proxy_type = "socks4"
        rdns = True
    elif scheme in ("http", "https"):
        proxy_type = "http"
        rdns = False

    config: dict[str, Any] = {
        "proxy_type": proxy_type,
        "addr": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 1080,
        "username": parsed.username or None,
        "password": parsed.password or None,
        "rdns": rdns,
    }
    return config


class TelethonScraperClient:
    """Ephemeral in-memory Telethon client wrapper using StringSession (AD-1).

    Ensures ZERO .session or sqlite database artifacts are created on container disk.
    Supports SOCKS5 proxy routing (AC-2) and clean async context manager lifecycle.
    """

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session_string: str,
        proxy: dict[str, Any] | None = None,
    ) -> None:
        self.api_id = int(api_id)
        self.api_hash = str(api_hash)
        self.session_string = str(session_string)
        self.proxy = proxy
        self.is_in_memory_only = True
        self._raw_client: TelegramClient | None = None
        self._is_connected = False
        self._extractor = TelegramEntityExtractor()

    @classmethod
    def from_credentials(cls, credentials: dict[str, Any]) -> TelethonScraperClient:
        """Instantiate TelethonScraperClient from decrypted credential dictionary."""
        api_id = int(credentials["api_id"])
        api_hash = str(credentials["api_hash"])
        session_string = str(credentials.get("session_string", ""))

        proxy_config = None
        if credentials.get("proxy_url"):
            proxy_config = parse_proxy_url(credentials["proxy_url"])
        elif "proxy" in credentials and isinstance(credentials["proxy"], dict):
            proxy_config = credentials["proxy"]

        return cls(
            api_id=api_id,
            api_hash=api_hash,
            session_string=session_string,
            proxy=proxy_config,
        )

    @property
    def is_connected(self) -> bool:
        """Check if client is currently connected and authorized."""
        if self._raw_client is not None:
            try:
                return bool(self._raw_client.is_connected())
            except Exception:
                pass
        return self._is_connected

    async def connect(self) -> None:
        """Connect to Telegram MTProto servers using StringSession in memory."""
        if self._raw_client is None:
            self._raw_client = TelegramClient(
                StringSession(self.session_string),
                self.api_id,
                self.api_hash,
                proxy=self.proxy,
            )

        if not self._raw_client.is_connected():
            await self._raw_client.connect()
            self._is_connected = True

    async def disconnect(self) -> None:
        """Disconnect and cleanup in-memory resources."""
        if self._raw_client is not None and self._raw_client.is_connected():
            await self._raw_client.disconnect()
        self._is_connected = False
        self._raw_client = None

    async def __aenter__(self) -> TelethonScraperClient:
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.disconnect()

    async def get_channel_entity(self, channel: str) -> Any:
        """Resolve a public or private channel/group entity."""
        if not self.is_connected:
            await self.connect()
        assert self._raw_client is not None
        return await self._raw_client.get_entity(channel)

    async def get_channel_messages(
        self, channel: str, limit: int = 20
    ) -> list[TelegramChannelMessage]:
        """Fetch latest messages from a channel and parse into TelegramChannelMessage domain models."""
        if not self.is_connected:
            await self.connect()
        assert self._raw_client is not None

        messages: list[TelegramChannelMessage] = []
        raw_messages = self._raw_client.iter_messages(channel, limit=limit)

        # iter_messages can be an async iterator or list in test mocks
        if hasattr(raw_messages, "__aiter__"):
            async for raw_msg in raw_messages:
                msg = self._convert_message(raw_msg, channel)
                if msg is not None:
                    messages.append(msg)
        else:
            for raw_msg in raw_messages:
                msg = self._convert_message(raw_msg, channel)
                if msg is not None:
                    messages.append(msg)

        return messages

    def _convert_message(
        self, raw_msg: Any, channel_username: str
    ) -> TelegramChannelMessage | None:
        """Convert Telethon Message object to TelegramChannelMessage."""
        if raw_msg is None:
            return None

        text = getattr(raw_msg, "message", None) or getattr(raw_msg, "text", "") or ""
        msg_id = int(getattr(raw_msg, "id", 0))
        if not msg_id:
            return None

        # Published date
        raw_date = getattr(raw_msg, "date", None)
        published_at = raw_date if isinstance(raw_date, datetime) else datetime.now(UTC)

        # Views & stats
        views = int(getattr(raw_msg, "views", 0) or 0)
        forwards = int(getattr(raw_msg, "forwards", 0) or 0)
        has_media = bool(getattr(raw_msg, "media", False))

        # Author name
        author_name = None
        sender = getattr(raw_msg, "sender", None)
        if sender:
            first = getattr(sender, "first_name", "") or ""
            last = getattr(sender, "last_name", "") or ""
            author_name = f"{first} {last}".strip() or getattr(sender, "username", None)

        # Entities extraction
        entities: ExtractedEntities = self._extractor.extract(text)

        return TelegramChannelMessage(
            message_id=msg_id,
            channel_username=str(channel_username).lstrip("@"),
            text=text,
            published_at=published_at,
            views=views,
            forwards=forwards,
            replies_count=0,
            has_media=has_media,
            author_name=author_name,
            intent_tag=entities.intent_tag,
            entities=entities,
        )
