"""Health probe for core infrastructure (PostgreSQL, Redis, Celery, Caddy, Zero Cache)."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import text

from app.config import config
from app.db import engine
from app.redis_client import get_redis_client
from app.services.admin_telemetry_service import AdminTelemetryService
from app.services.health.probe_base import HealthProbe, HealthResult, HealthStatus

logger = logging.getLogger(__name__)


class InfrastructureHealthProbe(HealthProbe):
    """Probes a core infrastructure service component."""

    def __init__(self, component: str) -> None:
        self._component = component.lower()
        self._service_id = f"infra/{self._component}"
        self._service_name = {
            "postgres": "PostgreSQL Database",
            "redis": "Redis Cache & Broker",
            "celery": "Celery Background Workers",
            "caddy": "Caddy Reverse Proxy",
            "zero": "Zero Cache Sync Engine",
        }.get(self._component, f"Infra: {self._component.title()}")

    @property
    def service_id(self) -> str:
        return self._service_id

    @property
    def service_name(self) -> str:
        return self._service_name

    @property
    def category(self) -> str:
        return "infra"

    @property
    def display_group(self) -> str:
        return "Core Infrastructure"

    @property
    def interval_seconds(self) -> int:
        return 30  # 30 seconds

    async def probe(self) -> HealthResult:
        start = time.perf_counter()
        status: HealthStatus = "healthy"
        last_error: str | None = None
        suggested_action: str | None = None
        latency_ms: int | None = None
        metadata: dict[str, Any] = {"component": self._component}

        try:
            if self._component == "postgres":
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                latency_ms = int((time.perf_counter() - start) * 1000)
                if latency_ms > 1000:
                    status = "degraded"
                    suggested_action = "Check database load and connection pool capacity"

            elif self._component == "redis":
                client = await get_redis_client()
                await client.ping()
                latency_ms = int((time.perf_counter() - start) * 1000)
                if latency_ms > 500:
                    status = "degraded"
                    suggested_action = "Inspect Redis memory usage and latency metrics"

            elif self._component == "celery":
                telemetry_service = AdminTelemetryService(session=None)  # type: ignore[arg-type]
                stats = await telemetry_service.get_celery_queue_stats()
                latency_ms = int((time.perf_counter() - start) * 1000)
                if stats.get("status") == "unavailable" or stats.get("active_workers", 0) == 0:
                    status = "unavailable"
                    last_error = "No active Celery workers found"
                    suggested_action = "Restart Celery worker daemon and inspect queue health"
                else:
                    status = "healthy"
                metadata["active_workers"] = stats.get("active_workers", 0)
                metadata["queues"] = stats.get("queues", [])

            elif self._component == "caddy":
                caddy_url = getattr(config, "CADDY_ADMIN_URL", "http://localhost:2019/metrics")
                try:
                    async with httpx.AsyncClient(timeout=2.0) as client:
                        resp = await client.get(caddy_url)
                        latency_ms = int((time.perf_counter() - start) * 1000)
                        if resp.status_code >= 400:
                            status = "degraded"
                            last_error = f"Caddy returned HTTP {resp.status_code}"
                            suggested_action = "Inspect Caddy reverse proxy logs"
                        else:
                            status = "healthy"
                except Exception as exc:
                    latency_ms = int((time.perf_counter() - start) * 1000)
                    status = "unavailable"
                    last_error = f"Caddy connect failure: {type(exc).__name__}"
                    suggested_action = "Verify Caddy service is running and admin API is accessible"

            elif self._component == "zero":
                zero_url = getattr(config, "ZERO_CACHE_KEEPALIVE_URL", "http://localhost:4848/keepalive")
                try:
                    async with httpx.AsyncClient(timeout=2.0) as client:
                        resp = await client.get(zero_url)
                        latency_ms = int((time.perf_counter() - start) * 1000)
                        if resp.status_code >= 400:
                            status = "degraded"
                            last_error = f"Zero Cache returned HTTP {resp.status_code}"
                            suggested_action = "Inspect Zero Cache service status"
                        else:
                            status = "healthy"
                except Exception as exc:
                    latency_ms = int((time.perf_counter() - start) * 1000)
                    status = "unavailable"
                    last_error = f"Zero Cache connect failure: {type(exc).__name__}"
                    suggested_action = "Check Zero Cache sync engine process"

            else:
                latency_ms = int((time.perf_counter() - start) * 1000)
                status = "not_configured"
                suggested_action = f"Configure infrastructure probe for {self._component}"

        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            status = "unavailable"
            last_error = f"Infra probe error: {type(exc).__name__}"
            suggested_action = f"Inspect logs and configuration for infra/{self._component}"

        success_rate = 100.0 if status in {"healthy", "degraded"} else 0.0
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
            metadata=metadata,
            probed_at=datetime.now(UTC),
        )
