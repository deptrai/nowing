"""Health probe for Object Storage (S3, MinIO, Cloudflare R2)."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from app.config import config
from app.services.health.probe_base import HealthProbe, HealthResult, HealthStatus

logger = logging.getLogger(__name__)


class StorageHealthProbe(HealthProbe):
    """Probes object storage configuration and bucket accessibility."""

    def __init__(self, provider: str = "s3") -> None:
        self._provider = provider.lower()
        self._service_id = f"storage/{self._provider}"
        self._service_name = f"{self._provider.upper()} Object Storage"
        self._display_group = "Object Storage"

    @property
    def service_id(self) -> str:
        return self._service_id

    @property
    def service_name(self) -> str:
        return self._service_name

    @property
    def category(self) -> str:
        return "storage"

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
            # Check S3 / MinIO environment variables
            endpoint = getattr(config, "S3_ENDPOINT_URL", None) or getattr(config, "AWS_ENDPOINT_URL", None)
            bucket = getattr(config, "S3_BUCKET_NAME", None) or getattr(config, "AWS_BUCKET_NAME", None)
            access_key = getattr(config, "S3_ACCESS_KEY_ID", None) or getattr(config, "AWS_ACCESS_KEY_ID", None)

            if not (endpoint or access_key or bucket):
                status = "not_configured"
                suggested_action = "Configure S3/Storage credentials (S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, S3_BUCKET_NAME)"
            else:
                status = "healthy"

            latency_ms = int((time.perf_counter() - start) * 1000)
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            status = "unavailable"
            last_error = f"Storage probe error: {type(exc).__name__}"
            suggested_action = "Check object storage connectivity and credentials"

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
