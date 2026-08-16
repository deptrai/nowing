"""Service for managing admin-supplied scraper platform credentials."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
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

    async def list_enabled(self, platform: str) -> list[ScraperPlatformAccount]:
        """Return enabled accounts for a platform, ordered by last use."""
        result = await self.session.execute(
            select(ScraperPlatformAccount)
            .where(
                ScraperPlatformAccount.platform == platform,
                ScraperPlatformAccount.is_enabled.is_(True),
            )
            .order_by(ScraperPlatformAccount.last_used_at.asc().nulls_first())
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

    async def update_usage(
        self,
        account: ScraperPlatformAccount,
        *,
        last_used_at: datetime | None = None,
        usage_state: dict[str, Any] | None = None,
    ) -> None:
        """Persist rate-limit / cooldown state without touching credentials."""
        values: dict[str, Any] = {}
        if last_used_at is not None:
            values["last_used_at"] = last_used_at
        if usage_state is not None:
            values["usage_state"] = usage_state
        if not values:
            return
        await self.session.execute(
            sql_update(ScraperPlatformAccount)
            .where(ScraperPlatformAccount.id == account.id)
            .values(**values)
        )
        await self.session.commit()
        if last_used_at is not None:
            account.last_used_at = last_used_at
        if usage_state is not None:
            account.usage_state = usage_state

    async def _clear_default_for_platform(self, platform: str) -> None:
        await self.session.execute(
            sql_update(ScraperPlatformAccount)
            .where(
                ScraperPlatformAccount.platform == platform,
                ScraperPlatformAccount.is_default.is_(True),
            )
            .values(is_default=False)
        )


@dataclass
class RateLimit:
    """Sliding-window token-bucket rate limit for a single scraper account."""

    requests_per_minute: float = 5.0
    burst: int = 2
    cooldown_seconds: float = 300.0
    max_consecutive_failures: int = 3


class ScraperPlatformAccountRotator:
    """Rotate through enabled platform accounts with token-bucket rate limits.

    Accounts are selected by available tokens and recency of use.  Failed or
    rate-limited accounts are put on cooldown so a scrape does not keep
    hammering a restricted cookie.
    """

    def __init__(
        self,
        service: ScraperPlatformAccountService,
        platform: str,
        limit: RateLimit | None = None,
    ):
        self.service = service
        self.platform = platform
        self.limit = limit or RateLimit()
        self._accounts: list[ScraperPlatformAccount] | None = None
        self._state: dict[int, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def _load(self) -> list[ScraperPlatformAccount]:
        if self._accounts is None:
            accounts = await self.service.list_enabled(self.platform)
            self._accounts = accounts
            for account in accounts:
                self._state[account.id] = dict(account.usage_state or {})
        return self._accounts

    def _is_banned(self, account: ScraperPlatformAccount, now: float) -> bool:
        banned_until = self._state.get(account.id, {}).get("banned_until")
        return bool(banned_until and banned_until > now)

    def _tokens(self, account: ScraperPlatformAccount, now: float) -> float:
        state = self._state.get(account.id, {})
        burst = float(self.limit.burst)
        tokens = float(state.get("tokens", burst))
        last_refill = state.get("last_refill") or now
        refill_rate = self.limit.requests_per_minute / 60.0
        return min(burst, tokens + (now - last_refill) * refill_rate)

    def _choose(self, now: float) -> ScraperPlatformAccount | None:
        accounts = self._accounts or []
        available = [a for a in accounts if not self._is_banned(a, now)]
        if not available:
            return None
        available.sort(
            key=lambda a: (-self._tokens(a, now), a.last_used_at is not None, a.id)
        )
        for account in available:
            if self._tokens(account, now) >= 1.0:
                return account
        return None

    async def get_credentials(
        self,
        *,
        wait: bool = True,
        timeout: float = 60.0,
    ) -> tuple[ScraperPlatformAccount | None, dict[str, Any] | None]:
        """Return the next usable (account, credentials) pair.

        If ``wait`` is true, blocks until an account has a token or a cooldown
        expires, up to ``timeout`` seconds.
        """
        async with self._lock:
            await self._load()
            now = time.time()
            deadline = now + timeout
            while True:
                account = self._choose(now)
                if account is not None:
                    return await self._checkout(account, now)

                if not wait or now >= deadline:
                    return None, None

                # Compute the soonest moment an account becomes usable again.
                next_times: list[float] = []
                for a in self._accounts or []:
                    if self._is_banned(a, now):
                        banned = self._state[a.id].get("banned_until", now)
                        next_times.append(banned)
                    else:
                        tokens = self._tokens(a, now)
                        if tokens < 1.0:
                            refill_rate = self.limit.requests_per_minute / 60.0
                            next_in = (1.0 - tokens) / refill_rate
                            next_times.append(now + next_in)

                if not next_times:
                    return None, None

                sleep_for = min(max(0.0, min(next_times) - now), 5.0)
                if sleep_for <= 0:
                    sleep_for = 0.1
                if sleep_for > deadline - now:
                    sleep_for = max(0.0, deadline - now)

                await asyncio.sleep(sleep_for)
                now = time.time()

    async def _checkout(
        self, account: ScraperPlatformAccount, now: float
    ) -> tuple[ScraperPlatformAccount, dict[str, Any] | None]:
        state = self._state[account.id]
        tokens = self._tokens(account, now) - 1.0
        state["tokens"] = tokens
        state["last_refill"] = now
        account.last_used_at = datetime.now(UTC)
        account.usage_state = state
        await self.service.update_usage(
            account,
            last_used_at=account.last_used_at,
            usage_state=state,
        )
        credentials = decrypt_credentials(account.encrypted_credentials)
        return account, credentials

    async def record_use(
        self,
        account: ScraperPlatformAccount,
        *,
        success: bool,
        error_type: str | None = None,
        custom_cooldown_until: float | None = None,
    ) -> None:
        """Update rate-limit state after a request completes."""
        async with self._lock:
            state = self._state.get(account.id, {})
            now = time.time()
            if not success:
                state["consecutive_failures"] = state.get("consecutive_failures", 0) + 1
                if custom_cooldown_until is not None:
                    state["banned_until"] = float(custom_cooldown_until)
                    logger.warning(
                        "Scraper account %s rate limited with custom cooldown until %s (%.0fs)",
                        account.id,
                        state["banned_until"],
                        state["banned_until"] - now,
                    )
                elif error_type == "restricted":
                    state["banned_until"] = now + (self.limit.cooldown_seconds * 2)
                    logger.warning(
                        "Scraper account %s marked restricted; cooldown %.0fs",
                        account.id,
                        state["banned_until"] - now,
                    )
                elif error_type == "rate_limited":
                    state["banned_until"] = now + self.limit.cooldown_seconds
                    logger.warning(
                        "Scraper account %s rate limited; cooldown %.0fs",
                        account.id,
                        state["banned_until"] - now,
                    )
                if (
                    state.get("consecutive_failures", 0)
                    >= self.limit.max_consecutive_failures
                ):
                    if custom_cooldown_until is None:
                        state["banned_until"] = now + self.limit.cooldown_seconds
                    state["consecutive_failures"] = 0
                    logger.warning(
                        "Scraper account %s hit max consecutive failures; cooldown %.0fs",
                        account.id,
                        state["banned_until"] - now,
                    )
            else:
                state["consecutive_failures"] = 0
            account.usage_state = state
            await self.service.update_usage(account, usage_state=state)


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
