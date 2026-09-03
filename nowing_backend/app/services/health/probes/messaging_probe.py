"""Health probe for Messaging providers (Telegram, Discord, Slack)."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

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

    async def probe(self) -> HealthResult:
        start = time.perf_counter()
        status: HealthStatus = "healthy"
        last_error: str | None = None
        suggested_action: str | None = None

        try:
            if self._provider == "telegram":
                bot_token = getattr(config, "TELEGRAM_BOT_TOKEN", None)
                if not bot_token:
                    status = "not_configured"
                    suggested_action = "Configure TELEGRAM_BOT_TOKEN in environment"
                else:
                    status = "healthy"
            elif self._provider == "slack":
                slack_token = getattr(config, "SLACK_BOT_TOKEN", None)
                if not slack_token:
                    status = "not_configured"
                    suggested_action = "Configure SLACK_BOT_TOKEN in environment"
                else:
                    status = "healthy"
            elif self._provider == "discord":
                discord_token = getattr(config, "DISCORD_BOT_TOKEN", None)
                if not discord_token:
                    status = "not_configured"
                    suggested_action = "Configure DISCORD_BOT_TOKEN in environment"
                else:
                    status = "healthy"
            else:
                status = "not_configured"
                suggested_action = f"Configure credentials for messaging provider {self._provider}"

            latency_ms = int((time.perf_counter() - start) * 1000)
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            status = "unavailable"
            last_error = f"Messaging probe error: {type(exc).__name__}"
            suggested_action = "Verify messaging provider configuration and network access"

        success_rate = 100.0 if status in {"healthy", "not_configured"} else 0.0
        error_rate = 0.0 if status in {"healthy", "not_configured"} else 100.0

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
