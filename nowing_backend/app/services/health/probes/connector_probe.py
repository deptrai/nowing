"""Health probe for SaaS connectors."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select

from app.db import async_session_maker
from app.models.connectors import Connection
from app.services.health.probe_base import HealthProbe, HealthResult, HealthStatus

logger = logging.getLogger(__name__)


class ConnectorHealthProbe(HealthProbe):
    """Probes SaaS connectors for connectivity and active configuration."""

    def __init__(
        self,
        connector_type: str,
        service_name: str | None = None,
        display_group: str = "SaaS Connectors",
    ) -> None:
        self._connector_type = connector_type
        self._service_id = f"connector/{connector_type}"
        self._service_name = service_name or connector_type.replace("_", " ").title()
        self._display_group = display_group

    @property
    def service_id(self) -> str:
        return self._service_id

    @property
    def service_name(self) -> str:
        return self._service_name

    @property
    def category(self) -> str:
        return "connector"

    @property
    def display_group(self) -> str:
        return self._display_group

    @property
    def interval_seconds(self) -> int:
        return 900  # 15 minutes

    async def probe(self) -> HealthResult:
        start = time.perf_counter()
        status: HealthStatus = "healthy"
        last_error: str | None = None
        suggested_action: str | None = None
        active_accounts = 0

        try:
            async with async_session_maker() as session:
                # Filter Connection by enabled == True and non-null credentials (api_key or extra configuration)
                query = select(func.count()).select_from(Connection).where(
                    and_(
                        Connection.provider == self._connector_type,
                        Connection.enabled.is_(True),
                        or_(
                            Connection.api_key.isnot(None),
                            Connection.extra.isnot(None),
                        ),
                    )
                )
                res = await session.execute(query)
                active_accounts = res.scalar() or 0

            latency_ms = int((time.perf_counter() - start) * 1000)
            if active_accounts == 0:
                status = "not_configured"
                suggested_action = f"Configure active credentials for {self._service_name}"
            else:
                status = "healthy"
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            status = "unavailable"
            last_error = f"Connector probe error: {type(exc).__name__}"
            suggested_action = f"Check database connectivity and credentials for {self._service_name}"

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
            metadata={"connector_type": self._connector_type, "active_accounts": active_accounts},
            probed_at=datetime.now(UTC),
        )
