"""Health probe for SaaS connectors."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import and_, func, or_, select

from app.db import async_session_maker
from app.models.connectors import Connection
from app.services.health.probe_base import HealthProbe, HealthResult, HealthStatus

logger = logging.getLogger(__name__)

# Limit concurrent DB sessions opened by connector probes to avoid pool exhaustion.
_CONNECTOR_DB_SESSION_SEMAPHORE = asyncio.Semaphore(5)


_CONNECTOR_HEALTH_PING: dict[str, tuple[str, str, dict[str, Any] | None]] = {
    "google_drive": ("GET", "https://www.googleapis.com/drive/v3/about", None),
    "google_gmail": ("GET", "https://gmail.googleapis.com/gmail/v1/users/me/profile", None),
    "google_calendar": ("GET", "https://www.googleapis.com/calendar/v3/users/me/calendarList", None),
    "google_sheets": ("GET", "https://sheets.googleapis.com/v4/spreadsheets", None),
    "slack": ("GET", "https://slack.com/api/auth.test", None),
    "discord": ("GET", "https://discord.com/api/v10/users/@me", None),
    "jira": ("GET", "/rest/api/2/myself", None),
    "confluence": ("GET", "/rest/api/space", None),
    "notion": ("POST", "https://api.notion.com/v1/search", {"query": ""}),
    "airtable": ("GET", "https://api.airtable.com/v0/meta/bases", None),
    "linear": ("POST", "https://api.linear.app/graphql", {"query": "{ viewer { id } }"}),
    "github": ("GET", "https://api.github.com/user", None),
    "dropbox": ("POST", "https://api.dropboxapi.com/2/users/get_current_account", None),
    "clickup": ("GET", "https://api.clickup.com/api/v2/team", None),
}


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

    async def _ping_upstream(self, connection: Connection) -> tuple[HealthStatus, str | None]:
        """Run a lightweight upstream ping using the stored connector credentials."""
        ping = _CONNECTOR_HEALTH_PING.get(self._connector_type)
        if not ping:
            # Unknown connector type: mark healthy if DB has a credential row
            return ("healthy", None)

        method, url, body = ping
        headers: dict[str, str] = {}
        token = connection.api_key or ""

        if self._connector_type in {
            "google_drive",
            "google_gmail",
            "google_calendar",
            "google_sheets",
        }:
            headers["Authorization"] = f"Bearer {token}"
        elif self._connector_type in {"slack", "github", "airtable", "clickup"}:
            headers["Authorization"] = f"Bearer {token}"
        elif self._connector_type == "discord":
            headers["Authorization"] = f"Bot {token}"
        elif self._connector_type == "notion":
            headers["Authorization"] = f"Bearer {token}"
            headers["Notion-Version"] = "2022-06-28"
        elif self._connector_type == "linear":
            headers["Authorization"] = token
        elif self._connector_type == "dropbox":
            headers["Authorization"] = f"Bearer {token}"
        elif self._connector_type in {"jira", "confluence"}:
            # Jira/Confluence often use Basic auth or OAuth; try bearer first if long token
            if token and token.startswith("ey"):
                headers["Authorization"] = f"Bearer {token}"
            else:
                # Basic auth with api_key as token and user from extra
                user = (connection.extra or {}).get("username") or "admin"
                from base64 import b64encode

                creds = b64encode(f"{user}:{token}".encode()).decode()
                headers["Authorization"] = f"Basic {creds}"

        if url.startswith("/"):
            base = connection.base_url or (connection.extra or {}).get("base_url")
            if not base:
                return ("not_configured", "No base_url configured for Jira/Confluence connector")
            url = base.rstrip("/") + url

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                if method == "GET":
                    resp = await client.get(url, headers=headers)
                else:
                    resp = await client.post(url, headers=headers, json=body)

            if resp.status_code in (200, 202, 204):
                return ("healthy", None)
            if resp.status_code in (401, 403):
                return ("degraded", f"HTTP {resp.status_code} - credentials rejected or expired")
            if resp.status_code == 429:
                return ("degraded", f"HTTP {resp.status_code} - rate limited")
            if resp.status_code >= 500:
                return ("unavailable", f"HTTP {resp.status_code} - upstream error")
            return ("degraded", f"HTTP {resp.status_code} - unexpected response")
        except Exception as exc:
            return ("unavailable", f"Upstream ping failed: {type(exc).__name__}: {exc}")

    async def probe(self) -> HealthResult:
        start = time.perf_counter()
        status: HealthStatus = "healthy"
        last_error: str | None = None
        suggested_action: str | None = None
        active_accounts = 0
        latest_connection: Connection | None = None

        try:
            async with _CONNECTOR_DB_SESSION_SEMAPHORE:
                async with async_session_maker() as session:
                    query = select(Connection).where(
                        and_(
                            Connection.provider == self._connector_type,
                            Connection.enabled.is_(True),
                            or_(
                                Connection.api_key.isnot(None),
                                Connection.extra.isnot(None),
                            ),
                        )
                    ).order_by(Connection.created_at.desc()).limit(1)
                    res = await session.execute(query)
                    latest_connection = res.scalar_one_or_none()

                    count_query = select(func.count()).select_from(Connection).where(
                        and_(
                            Connection.provider == self._connector_type,
                            Connection.enabled.is_(True),
                            or_(
                                Connection.api_key.isnot(None),
                                Connection.extra.isnot(None),
                            ),
                        )
                    )
                    count_res = await session.execute(count_query)
                    active_accounts = count_res.scalar() or 0

            latency_ms = int((time.perf_counter() - start) * 1000)
            if active_accounts == 0:
                status = "not_configured"
                suggested_action = f"Configure active credentials for {self._service_name}"
            elif latest_connection is not None:
                upstream_status, upstream_error = await self._ping_upstream(latest_connection)
                status = upstream_status
                last_error = upstream_error
                if status == "degraded":
                    suggested_action = f"Refresh credentials or inspect {self._service_name} rate limits"
                elif status == "unavailable":
                    suggested_action = f"Check {self._service_name} service status and credentials"
                else:
                    suggested_action = None
            else:
                status = "healthy"
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            status = "unavailable"
            last_error = f"Connector probe error: {type(exc).__name__}"
            suggested_action = f"Check database connectivity and credentials for {self._service_name}"

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
            metadata={"connector_type": self._connector_type, "active_accounts": active_accounts},
            probed_at=datetime.now(UTC),
        )
