"""Health probe for Messaging providers (Telegram, Discord, Slack)."""

from __future__ import annotations

import logging
import os
import time
from datetime import UTC, datetime

import httpx

from app.config import config
from app.services.health.probe_base import HealthProbe, HealthResult, HealthStatus

logger = logging.getLogger(__name__)


class MessagingHealthProbe(HealthProbe):
    """Probes messaging subsystem configuration and connectivity."""

    def __init__(self, provider: str = "telegram") -> None:
        self._provider = provider.lower()
        self._service_id = f"messaging/{self._provider}"
        self._service_name = f"{self._provider.title()} Gateway"
        self._display_group = "Messaging & Notifications"

    @property
    def service_id(self) -> str:
        return self._service_id

    @property
    def service_name(self) -> str:
        return self._service_name

    @property
    def category(self) -> str:
        return "messaging"

    @property
    def display_group(self) -> str:
        return self._display_group

    @property
    def interval_seconds(self) -> int:
        return 300  # 5 minutes

    async def _ping_telegram(self, token: str) -> tuple[HealthStatus, str | None]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            if resp.status_code == 200 and resp.json().get("ok"):
                return ("healthy", None)
            if resp.status_code in (401, 403):
                return ("degraded", "Telegram bot token rejected")
            if resp.status_code >= 500:
                return ("unavailable", f"Telegram API returned HTTP {resp.status_code}")
            return ("degraded", f"Telegram API returned HTTP {resp.status_code}")
        except Exception as exc:
            return ("unavailable", f"Telegram ping failed: {type(exc).__name__}: {exc}")

    async def _ping_slack(self, token: str) -> tuple[HealthStatus, str | None]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://slack.com/api/auth.test",
                    headers={"Authorization": f"Bearer {token}"},
                )
            data = resp.json()
            if data.get("ok"):
                return ("healthy", None)
            if data.get("error") in {"invalid_auth", "account_inactive"}:
                return ("degraded", f"Slack auth error: {data.get('error')}")
            return ("unavailable", f"Slack auth.test failed: {data.get('error')}")
        except Exception as exc:
            return ("unavailable", f"Slack ping failed: {type(exc).__name__}: {exc}")

    async def _ping_discord(self, token: str) -> tuple[HealthStatus, str | None]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://discord.com/api/v10/users/@me",
                    headers={"Authorization": f"Bot {token}"},
                )
            if resp.status_code == 200:
                return ("healthy", None)
            if resp.status_code in (401, 403):
                return ("degraded", f"Discord bot token rejected (HTTP {resp.status_code})")
            if resp.status_code >= 500:
                return ("unavailable", f"Discord API returned HTTP {resp.status_code}")
            return ("degraded", f"Discord API returned HTTP {resp.status_code}")
        except Exception as exc:
            return ("unavailable", f"Discord ping failed: {type(exc).__name__}: {exc}")

    async def probe(self) -> HealthResult:
        start = time.perf_counter()
        status: HealthStatus = "healthy"
        last_error: str | None = None
        suggested_action: str | None = None

        try:
            if self._provider == "telegram":
                bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or getattr(config, "TELEGRAM_BOT_TOKEN", None)
                if not bot_token:
                    status = "not_configured"
                    suggested_action = "Configure TELEGRAM_BOT_TOKEN in environment"
                else:
                    status, last_error = await self._ping_telegram(bot_token)
                    if status != "healthy":
                        suggested_action = "Verify Telegram bot token and network reachability"
            elif self._provider == "slack":
                slack_token = os.getenv("SLACK_BOT_TOKEN") or getattr(config, "SLACK_BOT_TOKEN", None)
                if not slack_token:
                    status = "not_configured"
                    suggested_action = "Configure SLACK_BOT_TOKEN in environment"
                else:
                    status, last_error = await self._ping_slack(slack_token)
                    if status != "healthy":
                        suggested_action = "Verify Slack bot token and workspace permissions"
            elif self._provider == "discord":
                discord_token = os.getenv("DISCORD_BOT_TOKEN") or getattr(config, "DISCORD_BOT_TOKEN", None)
                if not discord_token:
                    status = "not_configured"
                    suggested_action = "Configure DISCORD_BOT_TOKEN in environment"
                else:
                    status, last_error = await self._ping_discord(discord_token)
                    if status != "healthy":
                        suggested_action = "Verify Discord bot token and gateway permissions"
            else:
                status = "not_configured"
                suggested_action = f"Configure credentials for messaging provider {self._provider}"

            latency_ms = int((time.perf_counter() - start) * 1000)
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            status = "unavailable"
            last_error = f"Messaging probe error: {type(exc).__name__}"
            suggested_action = "Verify messaging provider configuration and network access"

        success_rate = 100.0 if status == "healthy" else (50.0 if status == "degraded" else 0.0)
        error_rate = 0.0 if status == "healthy" else (50.0 if status == "degraded" else 100.0)

        return HealthResult(
            service_id=self._service_id,
            service_name=self._service_name,
            category=self.category,
            display_group=self.display_group,
            status=status,
            latency_ms=latency_ms,
            last_error=last_error,
            suggested_action=suggested_action,
            error_rate_15m=error_rate,
            success_rate_15m=success_rate,
            metadata={"provider": self._provider},
            probed_at=datetime.now(UTC),
        )
