"""Service for managing admin-supplied scraper platform credentials."""

from __future__ import annotations

import json
import logging
from http.cookies import SimpleCookie
from typing import Any

from sqlalchemy import select, update as sql_update
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import ScraperPlatformAccount, async_session_maker
from app.utils.oauth_security import TokenEncryption

logger = logging.getLogger(__name__)


def _get_token_encryption() -> TokenEncryption | None:
    if not config.SECRET_KEY:
        logger.warning("SECRET_KEY not set; scraper credentials cannot be encrypted")
        return None
    return TokenEncryption(config.SECRET_KEY)


def encrypt_credentials(credentials: dict[str, Any]) -> str:
    enc = _get_token_encryption()
    if enc is None:
        raise ValueError("SECRET_KEY must be set to store scraper credentials")
    return enc.encrypt_token(json.dumps(credentials, ensure_ascii=False))


def decrypt_credentials(encrypted: str | None) -> dict[str, Any] | None:
    if not encrypted:
        return None
    enc = _get_token_encryption()
    if enc is None:
        raise ValueError("SECRET_KEY must be set to decrypt scraper credentials")
    raw = enc.decrypt_token(encrypted)
    try:
        return json.loads(raw)
    except Exception as exc:
        raise ValueError("Stored scraper credentials are not valid JSON") from exc


def _parse_cookie_input(
    cookie_input: str | list[dict[str, Any]],
    domain: str | None = None,
) -> list[dict[str, Any]]:
    """Normalize cookies from a JSON array or a ``name=value; ...`` string."""
    if isinstance(cookie_input, list):
        return cookie_input
    text = cookie_input.strip()
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
    jar = SimpleCookie(text)
    return [
        {"name": key, "value": morsel.value, "domain": domain or "", "path": "/"}
        for key, morsel in jar.items()
    ]


def cookie_string_to_playwright(
    cookie_input: str | list[dict[str, Any]],
    domain: str,
) -> list[dict[str, Any]]:
    """Parse cookies into Playwright ``add_cookies`` format.

    Accepts either a JSON array (from browser extensions) or a
    ``name=value; ...`` string (legacy ``document.cookie`` format).
    """
    cookies = _parse_cookie_input(cookie_input, domain=domain)
    if cookies:
        return cookies
    # Fallback for legacy empty/whitespace strings.
    jar = SimpleCookie(str(cookie_input))
    return [
        {"name": key, "value": morsel.value, "domain": domain, "path": "/"}
        for key, morsel in jar.items()
    ]


def cookie_string_to_dict(cookie_input: str | list[dict[str, Any]]) -> dict[str, str]:
    """Parse cookies into a plain ``name -> value`` dict."""
    cookies = _parse_cookie_input(cookie_input)
    return {c["name"]: c.get("value", "") for c in cookies}


class ScraperPlatformAccountService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(self, platform: str | None = None) -> list[ScraperPlatformAccount]:
        stmt = select(ScraperPlatformAccount)
        if platform:
            stmt = stmt.where(ScraperPlatformAccount.platform == platform)
        result = await self.session.execute(
            stmt.order_by(ScraperPlatformAccount.created_at)
        )
        return list(result.scalars().all())

    async def get(self, account_id: int) -> ScraperPlatformAccount | None:
        return await self.session.get(ScraperPlatformAccount, account_id)

    async def get_default(self, platform: str) -> ScraperPlatformAccount | None:
        result = await self.session.execute(
            select(ScraperPlatformAccount)
            .where(
                ScraperPlatformAccount.platform == platform,
                ScraperPlatformAccount.is_enabled.is_(True),
                ScraperPlatformAccount.is_default.is_(True),
            )
            .order_by(ScraperPlatformAccount.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def get_default_credentials(self, platform: str) -> dict[str, Any] | None:
        account = await self.get_default(platform)
        if not account:
            return None
        return decrypt_credentials(account.encrypted_credentials)

    async def create(
        self,
        platform: str,
        label: str | None,
        is_enabled: bool,
        is_default: bool,
        credentials: dict[str, Any] | None,
    ) -> ScraperPlatformAccount:
        if is_default:
            await self._clear_default_for_platform(platform)
        account = ScraperPlatformAccount(
            platform=platform,
            label=label,
            is_enabled=is_enabled,
            is_default=is_default,
            encrypted_credentials=encrypt_credentials(credentials)
            if credentials
            else None,
        )
        self.session.add(account)
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def update(
        self,
        account: ScraperPlatformAccount,
        updates: dict[str, Any],
    ) -> ScraperPlatformAccount:
        label = updates.get("label")
        if label is not None or "label" in updates:
            account.label = label
        is_enabled = updates.get("is_enabled")
        if is_enabled is not None or "is_enabled" in updates:
            account.is_enabled = is_enabled
        is_default = updates.get("is_default")
        if is_default is not None or "is_default" in updates:
            if is_default:
                await self._clear_default_for_platform(account.platform)
            account.is_default = is_default
        credentials = updates.get("credentials")
        if credentials is not None or "credentials" in updates:
            account.encrypted_credentials = (
                encrypt_credentials(credentials) if credentials else None
            )
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def delete(self, account: ScraperPlatformAccount) -> None:
        await self.session.delete(account)
        await self.session.commit()

    async def _clear_default_for_platform(self, platform: str) -> None:
        await self.session.execute(
            sql_update(ScraperPlatformAccount)
            .where(
                ScraperPlatformAccount.platform == platform,
                ScraperPlatformAccount.is_default.is_(True),
            )
            .values(is_default=False)
        )


async def get_default_credentials(platform: str) -> dict[str, Any] | None:
    """Fetch the default enabled credentials for a platform without a pre-existing session."""
    try:
        async with async_session_maker() as session:
            return await ScraperPlatformAccountService(session).get_default_credentials(
                platform
            )
    except ProgrammingError as exc:
        logger.warning(
            "scraper_platform_accounts table not available for %s: %s", platform, exc
        )
        return None
