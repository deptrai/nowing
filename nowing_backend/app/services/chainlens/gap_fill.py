"""Nowing -> chainlens-research gap-fill adapter (Story 20.2).

The service calls ``POST /v1/gap-fill`` to ask chainlens-research to index
missing data on demand.  It supports both synchronous (chat-blocking) and
asynchronous (``?mode=async``) execution.  In the async path it creates a local
``runs`` row and streams progress/terminal events through the shared
``run_event_bus`` so clients can tail the same SSE endpoint used by the
scraper-api.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.capabilities.core.events import run_event_bus
from app.capabilities.core.progress import emit_progress, progress_scope
from app.capabilities.core.runs import create_pending_run, finalize_run
from app.config import config
from app.db import async_session_maker

from .auth import ChainLensServiceAuth

logger = logging.getLogger(__name__)


class GapFillRequest(BaseModel):
    """Body of ``POST /v1/gap-fill``."""

    model_config = ConfigDict(populate_by_name=True)

    query: str = Field(..., min_length=1, max_length=500)
    workspace_id: int = Field(..., gt=0, alias="workspaceId")
    domains: list[str] | None = Field(default=None, max_length=50)
    source: str | None = Field(default=None)
    priority: str | None = Field(default=None)
    mode: Literal["sync", "async"] = Field(default="sync")
    correlation_id: str | None = Field(default=None, alias="correlationId")

    @field_validator("query", mode="before")
    @classmethod
    def _strip_query(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class GapFillResponse(BaseModel):
    """Result of a ``GapFillService`` call."""

    model_config = ConfigDict(populate_by_name=True)

    run_id: str | None = Field(default=None, alias="runId")
    status: str = Field(default="pending")
    message: str | None = Field(default=None)
    cost_dollars: float | None = Field(default=None, alias="costDollars")
    cost_breakdown: dict[str, Any] | None = Field(default=None, alias="costBreakdown")
    suggested_domains: list[str] = Field(default_factory=list, alias="suggestedDomains")

    @property
    def billable_units(self) -> int:
        """Compatibility with the async runner's charge gate."""
        return 0


class GapFillService:
    """Service-to-service caller for ``chainlens-research`` gap-fill."""

    def __init__(self, config_obj: Any | None = None) -> None:
        self.config = config_obj if config_obj is not None else config
        self._background_tasks: list[asyncio.Task] = []

    def _url(self, mode: Literal["sync", "async"]) -> str:
        base = getattr(self.config, "CHAINLENS_API_URL", "http://localhost:3001")
        url = f"{base.rstrip('/')}/v1/gap-fill"
        if mode == "async":
            url = f"{url}?mode=async"
        return url

    def _timeout(self) -> float:
        return float(getattr(self.config, "CHAINLENS_REQUEST_TIMEOUT_SECONDS", 300.0))

    def _parse_response(
        self, data: dict[str, Any], status_code: int
    ) -> GapFillResponse:
        if status_code in (200, 202):
            status = "accepted" if status_code == 202 else "complete"
        else:
            status = "failed"
        return GapFillResponse(
            run_id=data.get("runId") or data.get("run_id"),
            status=status,
            message=data.get("message"),
            cost_dollars=data.get("costDollars") or data.get("cost_dollars"),
            cost_breakdown=data.get("costBreakdown") or data.get("cost_breakdown"),
            suggested_domains=data.get("suggestedDomains")
            or data.get("suggested_domains")
            or [],
        )

    async def request(self, payload: GapFillRequest) -> GapFillResponse:
        """Call ``POST /v1/gap-fill`` and return a typed response.

        For ``mode="async"`` the request includes the ``?mode=async`` query
        parameter and expects a ``202 Accepted`` with a ``runId``.
        """
        auth = ChainLensServiceAuth(config_obj=self.config)
        if not auth.configured:
            return GapFillResponse(
                status="service_auth_unavailable",
                message="ChainLens service token not configured",
            )

        body = payload.model_dump(
            exclude={"mode"},
            exclude_none=True,
            by_alias=True,
        )
        url = self._url(payload.mode)
        headers = auth.get_outbound_headers(
            payload.workspace_id,
            correlation_id=payload.correlation_id,
            content_type="application/json",
        )

        logger.info(
            "Calling chainlens-research gap-fill (mode=%s, workspace=%s)",
            payload.mode,
            payload.workspace_id,
        )
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout(), follow_redirects=True
            ) as client:
                response = await client.post(url, json=body, headers=headers)
        except httpx.TimeoutException:
            logger.warning(
                "Gap-fill request timed out for workspace %s", payload.workspace_id
            )
            return GapFillResponse(
                status="timeout",
                message="Gap-fill request timed out; try the async door.",
            )
        except httpx.RequestError as exc:
            logger.warning(
                "Gap-fill request failed for workspace %s: %s",
                payload.workspace_id,
                exc,
            )
            return GapFillResponse(
                status="unreachable",
                message="Could not reach chainlens-research gap-fill endpoint.",
            )

        if response.status_code == 401:
            return GapFillResponse(
                status="auth_failed", message="ChainLens service token rejected"
            )
        if response.status_code == 429:
            return GapFillResponse(
                status="rate_limited",
                message="ChainLens gap-fill rate limited; try again later",
            )
        if response.status_code >= 500:
            return GapFillResponse(
                status="upstream_error",
                message="ChainLens gap-fill returned an upstream error",
            )
        if response.status_code >= 400:
            return GapFillResponse(
                status="client_error",
                message=f"ChainLens gap-fill client error ({response.status_code})",
            )

        try:
            data = response.json() if response.content else {}
        except Exception:
            data = {}
        return self._parse_response(data, response.status_code)

    async def start_async(self, payload: GapFillRequest) -> GapFillResponse:
        """Start a local async gap-fill run and return its ``run_id`` immediately."""
        run_input = payload.model_dump(
            exclude={"mode"}, exclude_none=True, by_alias=True
        )
        run_id: str | None = None
        async with async_session_maker() as session:
            run_id = await create_pending_run(
                session,
                workspace_id=payload.workspace_id,
                capability="chainlens.gap_fill",
                origin="agent",
                input=run_input,
            )

        if run_id is None:
            return GapFillResponse(
                status="error",
                message="Could not create a pending gap-fill run",
            )

        task_payload = payload.model_copy(update={"mode": "async"})
        task = asyncio.create_task(self._async_worker(task_payload, run_id))
        self._background_tasks.append(task)
        return GapFillResponse(
            run_id=f"run_{run_id}",
            status="running",
            message="Gap-fill started; result will stream via the run events endpoint.",
        )

    async def request_sync_or_async(
        self,
        payload: GapFillRequest,
        *,
        sync_timeout_seconds: float = 60.0,
    ) -> GapFillResponse:
        """Try a sync gap-fill; if it takes longer than ``sync_timeout_seconds``,
        fall back to the local async door and return a ``run_id``.

        ponytail: This starts a fresh async request on timeout.  The cancelled
        sync request may still be running upstream; in a high-traffic deployment
        the caller should prefer ``start_async`` directly for known-long runs.
        """
        if payload.mode == "async":
            return await self.start_async(payload)

        sync_payload = payload.model_copy(update={"mode": "sync"})
        try:
            return await asyncio.wait_for(
                self.request(sync_payload), timeout=sync_timeout_seconds
            )
        except TimeoutError:
            logger.info(
                "Gap-fill exceeded %ss for workspace %s; switching to async",
                sync_timeout_seconds,
                payload.workspace_id,
            )
            return await self.start_async(payload)

    async def _async_worker(self, payload: GapFillRequest, run_id: str) -> None:
        """Background task for an async gap-fill run."""
        started = time.perf_counter()
        final_status = "error"
        final_error: str | None = None
        response: GapFillResponse | None = None

        with progress_scope(run_id=run_id, bus=run_event_bus) as _reporter:
            run_event_bus.publish(
                run_id,
                {
                    "type": "run.started",
                    "run_id": f"run_{run_id}",
                    "capability": "chainlens.gap_fill",
                    "ts": int(time.time() * 1000),
                },
            )
            try:
                response = await self.request(payload)
                final_status = (
                    "success"
                    if response.status in {"complete", "accepted"}
                    else response.status
                )
                emit_progress(
                    "gap_fill_complete",
                    message=f"Gap-fill finished with status {response.status}",
                )
            except Exception as exc:  # pragma: no cover - worker safety net
                logger.exception("Async gap-fill worker failed for run %s", run_id)
                final_status = "error"
                final_error = str(exc)

        duration_ms = int((time.perf_counter() - started) * 1000)
        async with async_session_maker() as session:
            await finalize_run(
                session,
                run_id=run_id,
                status=final_status,
                error=final_error,
                duration_ms=duration_ms,
            )

        run_event_bus.publish(
            run_id,
            {
                "type": "run.finished",
                "run_id": f"run_{run_id}",
                "status": final_status,
                "ts": int(time.time() * 1000),
            },
        )
