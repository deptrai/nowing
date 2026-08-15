"""Generate the REST door from the capability registry (05).

One typed ``POST`` per verb under ``/workspaces/{id}/scrapers/{platform}/{verb}``;
each runs the same thin adapter: authn -> workspace authz -> meter-gate -> executor
-> charge -> typed output. Every request is recorded to the ``runs`` table
(best-effort) and its id returned via the ``X-Run-Id`` header.

Runs can also be started in **async mode** (``?mode=async``): the POST inserts a
``running`` row, spawns the scrape as a background task, and returns ``202`` with
the run id. The client then tails ``GET .../runs/{run_id}/events`` (SSE) for live
progress and a terminal ``run.finished`` event, or cancels via
``POST .../runs/{run_id}/cancel``. Two ``GET`` routes expose the run history that
backs the Scraper-API logs UI.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.canonical.tenant_context import set_request_tenant_context
from app.capabilities.chainlens.research.schemas import ResearchOutput, Source
from app.capabilities.core import execute_with_context
from app.capabilities.core.access.rate_limit import enforce_capability_rate_limit
from app.capabilities.core.async_runner import (
    finalize_cancelled_run,
    record_and_publish_sync_run,
    record_and_publish_sync_run_error,
    start_async_run,
)
from app.capabilities.core.billing import (
    charge_capability,
    gate_capability,
    pricing_meters,
)
from app.capabilities.core.events import run_event_bus
from app.capabilities.core.progress import progress_scope
from app.capabilities.core.store import all_capabilities
from app.capabilities.core.types import Capability, CapabilityContext
from app.config import config
from app.db import Report, Run, async_session_maker, get_async_session
from app.exceptions import ExternalServiceError, NowingError
from app.services.chainlens.gap_fill import GapFillRequest, GapFillService
from app.services.web_crawl_credit_service import InsufficientCreditsError
from app.services.workspace_limits import workspace_limit_service
from app.users import get_auth_context
from app.utils.rbac import check_workspace_access

logger = logging.getLogger(__name__)

_HEARTBEAT_SEC = 10

# NFR-9 State B: only speed/balanced may run synchronously in chat.
_SYNC_CHAT_ALLOWED_MODES: frozenset[str] = frozenset({"speed", "balanced"})


def _is_sync_chat_mode_allowed(research_mode: str) -> bool:
    """Return True only when the research mode may block a chat turn.

    ``auto`` is never allowed because the engine may resolve it to ``quality``
    or deep modes. ``quality``, ``deep-research``, and ``deep-reasoning`` are
    async-only until cost/latency targets are ratified.
    """
    if research_mode == "auto":
        return False
    return research_mode in _SYNC_CHAT_ALLOWED_MODES


_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class PricingMeter(BaseModel):
    """One live per-item rate a verb charges on, e.g. 3500 micro-USD per place."""

    unit: str
    micros_per_unit: int


class CapabilitySummary(BaseModel):
    """A verb's identity + input/output JSON schemas + pricing, for the playground UI."""

    name: str
    description: str
    docs_url: str | None = None
    input_schema: dict
    output_schema: dict
    # Empty list = free (billing disabled or an unmetered verb).
    pricing: list[PricingMeter] = []


class RunSummary(BaseModel):
    """Metadata row for the runs list (output body + progress log omitted)."""

    id: str
    capability: str
    origin: str
    status: str
    item_count: int
    char_count: int
    duration_ms: int | None
    cost_micros: int | None
    error: str | None
    created_at: datetime


class RunDetail(RunSummary):
    """Full run including input, stored output, and the coarse progress log."""

    thread_id: str | None
    input: dict | None
    output_text: str | None
    progress: list[dict] | None


def _origin_for(auth: AuthContext) -> str:
    """Session callers are the in-app UI; PAT/system callers are the public API."""
    return "ui" if getattr(auth, "method", None) == "session" else "api"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


def build_capabilities_router(
    capabilities: list[Capability] | None = None,
) -> APIRouter:
    """Emit one typed route per verb (defaults to the whole registry) + run history."""
    router = APIRouter(tags=["scrapers"])
    caps = capabilities if capabilities is not None else all_capabilities()
    for capability in caps:
        _register_verb(router, capability)
    _register_capabilities_list(router, caps)
    _register_run_history(router)
    return router


def _register_capabilities_list(
    router: APIRouter, capabilities: list[Capability]
) -> None:
    """Register the ``GET`` that lists verbs + their input schemas for the UI."""

    # Schemas are static; pricing is attached per request because rates are
    # read live from config (env retune + restart, no rebuild).
    base_summaries = [
        (
            CapabilitySummary(
                name=capability.name,
                description=capability.description,
                docs_url=capability.docs_url,
                input_schema=capability.input_schema.model_json_schema(),
                output_schema=capability.output_schema.model_json_schema(),
            ),
            capability.billing_unit,
        )
        for capability in capabilities
        if isinstance(capability.input_schema, type)
        and isinstance(capability.output_schema, type)
        and issubclass(capability.input_schema, BaseModel)
        and issubclass(capability.output_schema, BaseModel)
    ]

    async def list_capabilities(
        workspace_id: int,
        session: AsyncSession = Depends(get_async_session),
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[CapabilitySummary]:
        await check_workspace_access(session, auth, workspace_id)
        return [
            summary.model_copy(
                update={"pricing": [PricingMeter(**m) for m in pricing_meters(unit)]}
            )
            for summary, unit in base_summaries
        ]

    router.add_api_route(
        "/workspaces/{workspace_id}/scrapers/capabilities",
        list_capabilities,
        methods=["GET"],
        response_model=list[CapabilitySummary],
        name="scraper:list_capabilities",
    )


def _register_verb(router: APIRouter, capability: Capability) -> None:
    input_model = capability.input_schema
    output_model = capability.output_schema
    unit = capability.billing_unit
    executor = capability.executor
    name = capability.name
    platform, _, verb = name.partition(".")

    async def endpoint(
        workspace_id: int,
        payload: input_model,
        response: Response,
        session: AsyncSession = Depends(get_async_session),
        auth: AuthContext = Depends(get_auth_context),
        mode: str = Query(default="sync", pattern="^(sync|async)$"),
    ):
        await check_workspace_access(session, auth, workspace_id)

        # Enforce workspace run limit before meter-gate.
        await workspace_limit_service.check_run_limit(session, workspace_id)

        # State A/B: chainlens.research is async unless the sync chat-mode flag
        # is on AND the requested mode is in the allow-list (speed/balanced).
        # quality, deep-research, deep-reasoning, and auto remain async-only.
        if name == "chainlens.research" and not (
            config.DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED
            and _is_sync_chat_mode_allowed(payload.mode)
        ):
            mode = "async"

        sync_run_id = str(uuid.uuid4()) if name == "chainlens.research" else None
        ctx = CapabilityContext(
            session=session,
            workspace_id=workspace_id,
            run_id=sync_run_id,
        )
        try:
            await gate_capability(payload, unit, ctx)
        except InsufficientCreditsError as exc:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error_code": "insufficient_credits",
                    "message": str(exc),
                    "balance_micros": exc.balance_micros,
                    "required_micros": exc.required_micros,
                },
            ) from exc

        user_id = getattr(auth.user, "id", None)
        pat = getattr(auth, "pat", None)
        client_id = getattr(pat, "client_id", None) if pat is not None else None
        origin = _origin_for(auth)

        if mode == "async":
            run_id = await start_async_run(
                session=session,
                workspace_id=workspace_id,
                capability=capability,
                payload=payload,
                origin=origin,
                user_id=user_id,
                client_id=client_id,
            )
            if run_id is None:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Could not start run.",
                )
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={"run_id": f"run_{run_id}", "status": "running"},
                headers={"X-Run-Id": f"run_{run_id}"},
            )

        # Sync mode: block until done, persisting the coarse progress log.
        with progress_scope() as reporter:
            started = time.perf_counter()
            try:
                output = await execute_with_context(executor, payload=payload, ctx=ctx)
            except (NowingError, HTTPException) as exc:
                run_id = await record_and_publish_sync_run_error(
                    session=session,
                    workspace_id=workspace_id,
                    capability=name,
                    origin=origin,
                    payload=payload,
                    user_id=user_id,
                    client_id=client_id,
                    error=str(exc),
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    progress=reporter.coarse,
                    run_id=sync_run_id,
                )
                if run_id is not None:
                    response.headers["X-Run-Id"] = f"run_{run_id}"
                raise
            except Exception as exc:
                run_id = await record_and_publish_sync_run_error(
                    session=session,
                    workspace_id=workspace_id,
                    capability=name,
                    origin=origin,
                    payload=payload,
                    user_id=user_id,
                    client_id=client_id,
                    error=str(exc),
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    progress=reporter.coarse,
                    run_id=sync_run_id,
                )
                if run_id is not None:
                    response.headers["X-Run-Id"] = f"run_{run_id}"
                raise ExternalServiceError(
                    f"The '{name}' capability failed due to an upstream error.",
                    code="CAPABILITY_UPSTREAM_ERROR",
                ) from exc

            duration_ms = int((time.perf_counter() - started) * 1000)
            cost_micros = None
            try:
                cost_micros = await charge_capability(output, unit, ctx)
            except Exception:
                logger.exception("charge failed for sync run")

            # Story 20.2: trigger on-demand gap-fill indexing for research results.
            if name == "chainlens.research" and getattr(
                output, "gap_fill_needed", False
            ):
                try:
                    await GapFillService().request_sync_or_async(
                        GapFillRequest(
                            query=getattr(payload, "query", ""),
                            workspace_id=workspace_id,
                            domains=getattr(output, "suggested_domains", None) or [],
                            source="chainlens.research",
                            correlation_id=sync_run_id,
                        )
                    )
                except Exception:
                    logger.exception("gap-fill trigger failed for sync research run")

            run_id = await record_and_publish_sync_run(
                session=session,
                workspace_id=workspace_id,
                capability=name,
                origin=origin,
                payload=payload,
                output=output,
                user_id=user_id,
                client_id=client_id,
                duration_ms=duration_ms,
                cost_micros=cost_micros,
                progress=reporter.coarse,
                run_id=sync_run_id,
            )
        if run_id is not None:
            response.headers["X-Run-Id"] = f"run_{run_id}"
        return output

    router.add_api_route(
        f"/workspaces/{{workspace_id}}/scrapers/{platform}/{verb}",
        endpoint,
        methods=["POST"],
        response_model=output_model,
        name=f"scraper:{name}",
        dependencies=[Depends(enforce_capability_rate_limit)],
    )


def _parse_run_uuid(run_id: str) -> uuid.UUID:
    raw = run_id[len("run_") :] if run_id.startswith("run_") else run_id
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found."
        ) from exc


async def _load_run(
    session: AsyncSession, workspace_id: int, parsed_id: uuid.UUID
) -> Run:
    # AC-18.8: set workspace/run GUCs before the RLS-protected Run lookup.
    await set_request_tenant_context(
        session, workspace_id=workspace_id, run_id=str(parsed_id)
    )
    row = (
        await session.execute(
            select(Run).where(Run.id == parsed_id, Run.workspace_id == workspace_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found."
        )
    return row


def _register_run_history(router: APIRouter) -> None:
    """Register the run list/detail + live-events + cancel routes."""

    async def list_runs(
        workspace_id: int,
        session: AsyncSession = Depends(get_async_session),
        auth: AuthContext = Depends(get_auth_context),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        capability: str | None = Query(default=None),
        run_status: str | None = Query(default=None, alias="status"),
    ) -> list[RunSummary]:
        await check_workspace_access(session, auth, workspace_id)
        # AC-18.8: set workspace GUC so the RLS-protected run list succeeds.
        await set_request_tenant_context(session, workspace_id=workspace_id)
        stmt = select(Run).where(Run.workspace_id == workspace_id)
        if capability:
            stmt = stmt.where(Run.capability == capability)
        if run_status:
            stmt = stmt.where(Run.status == run_status)
        stmt = stmt.order_by(Run.created_at.desc()).limit(limit).offset(offset)
        rows = (await session.execute(stmt)).scalars().all()
        return [_to_summary(row) for row in rows]

    async def get_run(
        workspace_id: int,
        run_id: str,
        session: AsyncSession = Depends(get_async_session),
        auth: AuthContext = Depends(get_auth_context),
    ) -> RunDetail:
        await check_workspace_access(session, auth, workspace_id)
        parsed_id = _parse_run_uuid(run_id)
        row = await _load_run(session, workspace_id, parsed_id)
        return _to_detail(row)

    async def stream_run_events(
        workspace_id: int,
        run_id: str,
        session: AsyncSession = Depends(get_async_session),
        auth: AuthContext = Depends(get_auth_context),
    ):
        """SSE tail of a run's progress: replay buffered events, then live.

        Note: the request ``session`` must not be used inside the generator (it
        is torn down once the response starts streaming) — the generator opens
        its own session for the terminal snapshot.
        """
        await check_workspace_access(session, auth, workspace_id)
        parsed_id = _parse_run_uuid(run_id)
        await _load_run(session, workspace_id, parsed_id)  # authz + 404
        raw = str(parsed_id)

        async def gen():
            queue = run_event_bus.subscribe(raw)
            try:
                replayed = list(run_event_bus.replay(raw))
                for event in replayed:
                    yield _sse(event)
                if any(e.get("type") == "run.finished" for e in replayed):
                    return
                # If the run is already terminal (finished before we attached,
                # a sync run, or a run owned by another worker), snapshot it and
                # close. Otherwise wait for the live event stream.
                async with async_session_maker() as snap_session:
                    # AC-18.8: set tenant GUCs for the snapshot Run read.
                    await set_request_tenant_context(
                        snap_session,
                        workspace_id=workspace_id,
                        run_id=str(parsed_id),
                    )
                    row = (
                        await snap_session.execute(
                            select(Run).where(
                                Run.id == parsed_id,
                                Run.workspace_id == workspace_id,
                            )
                        )
                    ).scalar_one_or_none()
                if row and row.status in {"success", "error", "cancelled"}:
                    yield _sse(
                        {
                            "type": "run.finished",
                            "run_id": f"run_{raw}",
                            "status": row.status,
                            "item_count": row.item_count,
                            "error": row.error,
                            "ts": _now_ms(),
                        }
                    )
                    return
                while True:
                    try:
                        event = await asyncio.wait_for(
                            queue.get(), timeout=_HEARTBEAT_SEC
                        )
                    except TimeoutError:
                        yield _sse({"type": "run.heartbeat", "ts": _now_ms()})
                        continue
                    yield _sse(event)
                    if event.get("type") == "run.finished":
                        return
            finally:
                run_event_bus.unsubscribe(raw, queue)

        return StreamingResponse(
            gen(), media_type="text/event-stream", headers=_SSE_HEADERS
        )

    async def cancel_run(
        workspace_id: int,
        run_id: str,
        session: AsyncSession = Depends(get_async_session),
        auth: AuthContext = Depends(get_auth_context),
    ):
        await check_workspace_access(session, auth, workspace_id)
        parsed_id = _parse_run_uuid(run_id)
        row = await _load_run(session, workspace_id, parsed_id)
        if row.status != "running":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Run is not in progress.",
            )
        raw = str(parsed_id)
        task = run_event_bus.get_task(raw)
        if task is not None and not task.done():
            task.cancel()
        # No output produced -> nothing charged. ponytail: any pre-cancel captcha
        # attempts go unbilled; upgrade path is charging from progress counters.
        await finalize_cancelled_run(raw)
        return JSONResponse(content={"run_id": f"run_{raw}", "status": "cancelled"})

    router.add_api_route(
        "/workspaces/{workspace_id}/scrapers/runs",
        list_runs,
        methods=["GET"],
        response_model=list[RunSummary],
        name="scraper:list_runs",
    )
    router.add_api_route(
        "/workspaces/{workspace_id}/scrapers/runs/{run_id}",
        get_run,
        methods=["GET"],
        response_model=RunDetail,
        name="scraper:get_run",
    )
    router.add_api_route(
        "/workspaces/{workspace_id}/scrapers/runs/{run_id}/events",
        stream_run_events,
        methods=["GET"],
        name="scraper:stream_run_events",
    )
    router.add_api_route(
        "/workspaces/{workspace_id}/scrapers/runs/{run_id}/cancel",
        cancel_run,
        methods=["POST"],
        name="scraper:cancel_run",
    )

    async def create_deliverable(
        workspace_id: int,
        run_id: str,
        session: AsyncSession = Depends(get_async_session),
        auth: AuthContext = Depends(get_auth_context),
    ):
        """Materialize a finished deep-research run as a Report deliverable."""
        await check_workspace_access(session, auth, workspace_id)
        parsed_id = _parse_run_uuid(run_id)
        row = await _load_run(session, workspace_id, parsed_id)
        if row.capability != "chainlens.research":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Run is not a deep research run.",
            )
        if row.status != "success" or not row.output_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Run has no deliverable output.",
            )
        lines = row.output_text.splitlines()
        if not lines:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Run output is empty.",
            )
        first_line = lines[0]
        try:
            output = ResearchOutput.model_validate_json(first_line)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Run output is not valid deliverable JSON.",
            ) from exc
        except Exception:
            logger.exception("Failed to parse run %s output as ResearchOutput", run_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not parse run output.",
            ) from None

        query = (row.input or {}).get("query", "Deep Research")
        sources_md = _sources_to_markdown(output.sources)
        content = f"{output.answer}\n\n{sources_md}"
        existing = (
            await session.execute(
                select(Report)
                .with_for_update(of=Report)
                .where(
                    Report.report_metadata["run_id"].as_string() == f"run_{row.id}",
                    Report.workspace_id == workspace_id,
                )
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Deliverable already exists for this run.",
            )
        report_thread_id: int | None = None
        if row.thread_id is not None:
            try:
                report_thread_id = int(row.thread_id)
            except (TypeError, ValueError):
                logger.warning(
                    "Run %s thread_id %r cannot be converted to an integer for the report",
                    run_id,
                    row.thread_id,
                )
        report_cost_micros = output.cost_micros or row.cost_micros or 0
        report = Report(
            workspace_id=workspace_id,
            thread_id=report_thread_id,
            title=query[:500],
            content=content,
            content_type="markdown",
            report_style="deep_research",
            report_metadata={
                "run_id": f"run_{row.id}",
                "thread_id": row.thread_id,
                "resolved_mode": output.resolved_mode,
                "cost_micros": report_cost_micros,
            },
        )
        session.add(report)
        await session.commit()
        await session.refresh(report)
        if report.report_group_id is None:
            report.report_group_id = report.id
            await session.commit()
            await session.refresh(report)
        return JSONResponse(
            content={
                "report_id": report.id,
                "report_group_id": report.report_group_id or report.id,
                "run_id": f"run_{row.id}",
            }
        )

    router.add_api_route(
        "/workspaces/{workspace_id}/scrapers/runs/{run_id}/deliverable",
        create_deliverable,
        methods=["POST"],
        name="scraper:create_deliverable",
    )


def _sources_to_markdown(sources: list[Source]) -> str:
    """Format a list of sources as a simple markdown list."""
    if not sources:
        return "_No sources available._"
    lines = []
    for i, source in enumerate(sources, start=1):
        title = source.title or source.url
        lines.append(f"{i}. [{title}]({source.url})")
    return "\n".join(lines)


def _to_summary(row: Run) -> RunSummary:
    return RunSummary(
        id=f"run_{row.id}",
        capability=row.capability,
        origin=row.origin,
        status=row.status,
        item_count=row.item_count,
        char_count=row.char_count,
        duration_ms=row.duration_ms,
        cost_micros=row.cost_micros,
        error=row.error,
        created_at=row.created_at,
    )


def _to_detail(row: Run) -> RunDetail:
    return RunDetail(
        **_to_summary(row).model_dump(),
        thread_id=row.thread_id,
        input=row.input,
        output_text=row.output_text,
        progress=row.progress,
    )
