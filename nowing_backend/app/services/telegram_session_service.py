"""Telegram Session Mutex Lock & Cooldown Management Service (Story 22.2 / AC-3, AC-4, AD-2, AD-3)."""

from __future__ import annotations

import logging
import random
import time
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.db import ScraperPlatformAccount
    from app.services.scraper_platform_account_service import (
        ScraperPlatformAccountRotator,
    )

logger = logging.getLogger(__name__)

# Lua script to release lock only if the token matches (atomic safe release)
RELEASE_LOCK_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


def calculate_flood_wait_cooldown(flood_seconds: int | float) -> float:
    """Calculate anti-ban cooldown with randomized jitter (AD-3).

    Formula: now + N + uniform(2, 5) seconds.
    """
    jitter = random.uniform(2.0, 5.0)
    return time.time() + float(flood_seconds) + jitter


class TelegramSessionLock:
    """Distributed Redis Mutex Lock for Telegram MTProto userbot sessions (AD-2, AC-3).

    Key pattern: telegram:session:lock:{account_id}
    Prevents concurrent multi-worker session clashes on the same phone account.
    """

    def __init__(
        self,
        redis_client: Any,
        account_id: int,
        ttl_seconds: int = 120,
    ) -> None:
        self.redis_client = redis_client
        self.account_id = account_id
        self.ttl_seconds = ttl_seconds
        self.key = f"telegram:session:lock:{account_id}"
        self.token = uuid.uuid4().hex
        self._is_locked = False

    @property
    def is_locked(self) -> bool:
        return self._is_locked

    async def acquire(self) -> bool:
        """Acquire the distributed lock with NX (only if not exists) and EX (TTL)."""
        try:
            res = await self.redis_client.set(
                self.key,
                self.token,
                nx=True,
                ex=self.ttl_seconds,
            )
            self._is_locked = bool(res)
            return self._is_locked
        except Exception as exc:
            logger.warning(
                "Failed to acquire Telegram session lock %s: %s", self.key, exc
            )
            self._is_locked = False
            return False

    async def release(self) -> bool:
        """Safely release the lock only if token matches."""
        try:
            res = await self.redis_client.eval(
                RELEASE_LOCK_LUA,
                1,
                self.key,
                self.token,
            )
            self._is_locked = False
            return bool(res)
        except Exception as exc:
            logger.warning(
                "Failed to release Telegram session lock %s: %s", self.key, exc
            )
            self._is_locked = False
            return False

    async def __aenter__(self) -> TelegramSessionLock:
        await self.acquire()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.release()


class TelegramSessionService:
    """Orchestrates Telegram MTProto session rotation, health tracking, and FloodWait cooldowns."""

    def __init__(
        self,
        rotator: ScraperPlatformAccountRotator,
        redis_client: Any,
    ) -> None:
        self.rotator = rotator
        self.redis_client = redis_client

    def get_session_lock(
        self, account_id: int, ttl_seconds: int = 120
    ) -> TelegramSessionLock:
        """Create a TelegramSessionLock instance for given account_id."""
        return TelegramSessionLock(
            redis_client=self.redis_client,
            account_id=account_id,
            ttl_seconds=ttl_seconds,
        )

    async def handle_flood_wait(
        self, account: ScraperPlatformAccount, wait_seconds: int | float
    ) -> None:
        """Handle FloodWaitError by setting randomized cooldown and recording rate-limited status (AC-4, AD-3)."""
        cooldown_until = calculate_flood_wait_cooldown(wait_seconds)

        usage_state = getattr(account, "usage_state", None)
        if not isinstance(usage_state, dict):
            usage_state = {}
            account.usage_state = usage_state

        usage_state["banned_until"] = cooldown_until
        usage_state["consecutive_failures"] = (
            usage_state.get("consecutive_failures", 0) + 1
        )

        logger.warning(
            "Telegram account %s throttled by FloodWait (%ss). Cooldown until %s",
            account.id,
            wait_seconds,
            cooldown_until,
        )

        # Notify rotator to record failure with rate_limited error type
        await self.rotator.record_use(
            account,
            success=False,
            error_type="rate_limited",
        )
