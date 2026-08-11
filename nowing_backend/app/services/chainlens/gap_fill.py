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
import contextlib
import logging
import time
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.capabilities.core.billing import _resolve_workspace_owner, _to_nonneg_int
from app.capabilities.core.events import run_event_bus
from app.capabilities.core.progress import emit_progress, progress_scope
from app.capabilities.core.runs import create_pending_run, finalize_run
from app.config import config
from app.db import async_session_maker
from app.services.token_tracking_service import UsageType, record_token_usage
from app.services.wallet_credit import apply_debit, check_balance

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

    async def request(
        self,
        payload: GapFillRequest,
        *,
        run_id: str | None = None,
    ) -> GapFillResponse:
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

        logger.info(
            "Calling chainlens-research gap-fill (mode=%s, workspace=%s)",
            payload.mode,
            payload.workspace_id,
        )
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout(), follow_redirects=True
            ) as client:
                response: httpx.Response | None = None
                for attempt in range(2):
                    headers = auth.get_outbound_headers(
                        payload.workspace_id,
                        correlation_id=payload.correlation_id,
                        content_type="application/json",
                    )
                    response = await client.post(url, json=body, headers=headers)
                    if response.status_code == 401 and attempt == 0:
                        rotated = auth.rotate(
                            workspace_id=payload.workspace_id, reason="401_response"
                        )
                        if rotated:
                            continue
                    break
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

        if response is None:
            return GapFillResponse(
                status="unreachable",
                message="No response from chainlens-research gap-fill endpoint.",
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
        parsed = self._parse_response(data, response.status_code)
        await self._record_gap_fill_cost(payload, parsed, run_id)
        return parsed

    async def start_async(self, payload: GapFillRequest) -> GapFillResponse:
        """Start a local async gap-fill run and return its ``run_id`` immediately."""
        run_id, _ = await self._create_and_start_worker(payload)
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

        The sync request is handled by a local background worker so the same
        upstream call continues.  This avoids starting a second upstream request
        on timeout.
        """
        if payload.mode == "async":
            return await self.start_async(payload)

        run_id, task = await self._create_and_start_worker(payload)
        try:
            response = await asyncio.wait_for(task, timeout=sync_timeout_seconds)
            return response
        except TimeoutError:
            logger.info(
                "Gap-fill exceeded %ss for workspace %s; returning local run_id %s",
                sync_timeout_seconds,
                payload.workspace_id,
                run_id,
            )
            return GapFillResponse(
                run_id=f"run_{run_id}",
                status="running",
                message=(
                    "Gap-fill is taking longer than expected; "
                    "result will stream via the run events endpoint."
                ),
            )

    async def _create_and_start_worker(
        self, payload: GapFillRequest
    ) -> tuple[str, asyncio.Task[GapFillResponse]]:
        run_input = payload.model_dump(
            exclude={"mode"}, exclude_none=True, by_alias=True
        )
        run_id: str | None = None
        # ``runs.origin`` is capped at 16 characters.
        origin = (payload.source or "agent")[:16]
        async with async_session_maker() as session:
            run_id = await create_pending_run(
                session,
                workspace_id=payload.workspace_id,
                capability="chainlens.gap_fill",
                origin=origin,
                input=run_input,
            )

        if run_id is None:
            raise RuntimeError("Could not create a pending gap-fill run")

        task: asyncio.Task[GapFillResponse] = asyncio.create_task(
            self._async_worker(payload, run_id)
        )
        task.add_done_callback(self._on_task_done)
        self._background_tasks.append(task)
        return run_id, task

    def _on_task_done(self, task: asyncio.Task) -> None:
        with contextlib.suppress(ValueError):
            self._background_tasks.remove(task)
        with contextlib.suppress(asyncio.CancelledError, Exception):
            task.result()

    async def _async_worker(
        self, payload: GapFillRequest, run_id: str
    ) -> GapFillResponse:
        """Background task for an async or sync-via-local-run gap-fill."""
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
                response = await self.request(payload, run_id=run_id)
                final_status = (
                    "success"
                    if response.status in {"complete", "accepted"}
                    else response.status
                )
                emit_progress(
                    "gap_fill_complete",
                    message=f"Gap-fill finished with status {response.status}",
                )
            except asyncio.CancelledError:
                final_status = "cancelled"
                final_error = "Gap-fill run was cancelled"
                raise
            except Exception as exc:  # pragma: no cover - worker safety net
                logger.exception("Async gap-fill worker failed for run %s", run_id)
                final_status = "error"
                final_error = str(exc)

        if response is not None:
            response.run_id = f"run_{run_id}"

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

        return response or GapFillResponse(
            run_id=f"run_{run_id}",
            status=final_status,
            message=final_error,
        )

    async def _record_gap_fill_cost(
        self,
        payload: GapFillRequest,
        response: GapFillResponse,
        run_id: str | None,
    ) -> None:
        """Record gap-fill/scraper TokenUsage rows and debit the workspace once."""
        if response.cost_breakdown:
            gap_fill_micros = _to_nonneg_int(
                response.cost_breakdown.get("gap_fill_micros")
                or response.cost_breakdown.get("gapFillCostMicros")
            ) or 0
            scraper_micros = _to_nonneg_int(
                response.cost_breakdown.get("scraper_micros")
                or response.cost_breakdown.get("scraperCostMicros")
            ) or 0
            scraper_id = (
                response.cost_breakdown.get("scraper_id")
                or response.cost_breakdown.get("scraperId")
            )
        elif response.cost_dollars is not None and response.cost_dollars > 0:
            total_micros = ChainLensServiceAuth.cost_dollars_to_micros(
                response.cost_dollars
            )
            gap_fill_micros = total_micros
            scraper_micros = 0
            scraper_id = None
        else:
            return

        total_micros = gap_fill_micros + scraper_micros
        if total_micros <= 0:
            return

        owner_user_id = None
        async with async_session_maker() as session:
            owner_user_id = await _resolve_workspace_owner(
                session, payload.workspace_id
            )
            if owner_user_id is None:
                logger.warning(
                    "No workspace owner for gap-fill cost recording: %s",
                    payload.workspace_id,
                )
                return

            try:
                await check_balance(session, owner_user_id, total_micros)
                await apply_debit(session, owner_user_id, total_micros)
            except Exception:
                logger.exception("Failed to debit gap-fill cost for run %s", run_id)
                return

            common_details = {
                "source": payload.source,
                "scraper_id": scraper_id,
                "cost_dollars": response.cost_dollars,
                "cost_breakdown": response.cost_breakdown,
            }
            if gap_fill_micros > 0:
                await record_token_usage(
                    session,
                    usage_type=UsageType.CHAINLENS_GAP_FILL.value,
                    workspace_id=payload.workspace_id,
                    user_id=owner_user_id,
                    cost_micros=gap_fill_micros,
                    call_details={**common_details, "operation": "gap_fill"},
                    run_id=run_id,
                )
            if scraper_micros > 0:
                await record_token_usage(
                    session,
                    usage_type=UsageType.CHAINLENS_INGEST.value,
                    workspace_id=payload.workspace_id,
                    user_id=owner_user_id,
                    cost_micros=scraper_micros,
                    call_details={**common_details, "operation": "scraper"},
                    run_id=run_id,
                )
            await session.commit()
