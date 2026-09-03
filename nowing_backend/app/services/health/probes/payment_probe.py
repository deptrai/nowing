"""Health probe for Payment gateways (Stripe, etc.)."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from app.config import config
from app.services.health.probe_base import HealthProbe, HealthResult, HealthStatus

logger = logging.getLogger(__name__)


class PaymentHealthProbe(HealthProbe):
    """Probes payment gateway configuration and read-only reachability."""

    def __init__(self, provider: str = "stripe") -> None:
        self._provider = provider.lower()
        self._service_id = f"payment/{self._provider}"
        self._service_name = f"{self._provider.title()} Billing Gateway"
        self._display_group = "Billing & Payments"

    @property
    def service_id(self) -> str:
        return self._service_id

    @property
    def service_name(self) -> str:
        return self._service_name

    @property
    def category(self) -> str:
        return "payment"

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
            if self._provider == "stripe":
                api_key = getattr(config, "STRIPE_SECRET_KEY", None) or getattr(config, "STRIPE_API_KEY", None)
                if not api_key:
                    status = "not_configured"
                    suggested_action = "Configure STRIPE_SECRET_KEY in environment"
                else:
                    status = "healthy"
            else:
                status = "not_configured"
                suggested_action = f"Configure credentials for payment provider {self._provider}"

            latency_ms = int((time.perf_counter() - start) * 1000)
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            status = "unavailable"
            last_error = f"Payment probe error: {type(exc).__name__}"
            suggested_action = "Inspect payment gateway configuration and keys"

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
