"""Shared async-run lifecycle for capability invocations.

This module is the single place that starts, executes, and finalizes a
background run. Both the REST async door and the agent tool door call
:func:`start_async_run` so the agent door never imports from the REST module.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid as _uuid
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.core import execute_with_context
from app.capabilities.core.billing import charge_capability
from app.capabilities.core.events import run_event_bus
from app.capabilities.core.progress import progress_scope
from app.capabilities.core.runs import (
    SerializedOutput,
    create_pending_run,
    finalize_run,
    record_run,
    serialize_output,
)
from app.capabilities.core.types import Capability, CapabilityContext
from app.db import async_session_maker
from app.exceptions import NowingError
from app.services.memory.run_enqueue import (
    enqueue_run_memory_extraction_after_commit,
)

logger = logging.getLogger(__name__)


def _now_ms() -> int:
    return int(time.time() * 1000)


async def start_async_run(
    *,
    session: AsyncSession,
    workspace_id: int,
    capability: Capability,
    payload: BaseModel,
    origin: str,
    user_id: Any | None = None,
    thread_id: str | None = None,
) -> str | None:
    """Insert a ``running`` row and spawn the background scrape.

    Returns the bare run id (without the ``run_`` prefix) or ``None`` if the
    pending run could not be created.
    """
    input_dump = payload.model_dump(exclude_none=True)
    run_id = await create_pending_run(
        session,
        workspace_id=workspace_id,
        capability=capability.name,
        origin=origin,
        input=input_dump,
        user_id=user_id,
        thread_id=thread_id,
    )
    if run_id is None:
        return None

    unit = capability.billing_unit
    executor = capability.executor
    task = asyncio.create_task(
        _execute_async_run(
            run_id=run_id,
            workspace_id=workspace_id,
            capability=capability.name,
            unit=unit,
            executor=executor,
            payload=payload,
        )
    )
    run_event_bus.register_task(run_id, task)
    task.add_done_callback(lambda t: _log_task_result(run_id, t))
    return run_id


async def _execute_async_run(
    *,
    run_id: str,
    workspace_id: int,
    capability: str,
    unit,
    executor,
    payload: BaseModel,
) -> None:
    """Run a scrape in the background: stream progress, charge, finalize the row.

    Owns its own DB sessions (the request session is long gone). Cancellation is
    finalized by the cancel endpoint, so here we simply let ``CancelledError``
    propagate. Every other failure finalizes the row as ``error`` and emits a
    terminal event so subscribers unblock.
    """
    prefixed = f"run_{run_id}"
    started = time.perf_counter()
    final_status = "error"
    final_error: str | None = None
    serialized: SerializedOutput | None = None
    duration_ms: int | None = None
    cost_micros: int | None = None

    with progress_scope(run_id=run_id, bus=run_event_bus) as reporter:
        run_event_bus.publish(
            run_id,
            {
                "type": "run.started",
                "run_id": prefixed,
                "capability": capability,
                "ts": _now_ms(),
            },
        )
        output = None
        ctx: CapabilityContext | None = None
        try:
            async with async_session_maker() as session:
                ctx = CapabilityContext(
                    session=session, workspace_id=workspace_id, run_id=run_id
                )
                output = await execute_with_context(executor, payload=payload, ctx=ctx)
                duration_ms = int((time.perf_counter() - started) * 1000)
                try:
                    if output.billable_units > 0:
                        cost_micros = await charge_capability(output, unit, ctx)
                except Exception:
                    logger.exception("charge failed for async run %s", run_id)

                serialized = serialize_output(output)
                final_status = "success"
        except asyncio.CancelledError:
            raise
        except (NowingError, HTTPException) as exc:
            final_status = "error"
            final_error = str(exc)
        except Exception:
            logger.exception("async run %s failed with an upstream error", run_id)
            final_status = "error"
            final_error = (
                f"The '{capability}' capability failed due to an upstream error."
            )

    await _finalize_async(
        run_id,
        status=final_status,
        serialized=serialized,
        error=final_error,
        started=started,
        duration_ms=duration_ms,
        cost_micros=cost_micros,
        progress=reporter.coarse,
    )


async def _finalize_async(
    run_id: str,
    *,
    status: str,
    serialized: SerializedOutput | None = None,
    error: str | None = None,
    started: float | None = None,
    duration_ms: int | None = None,
    cost_micros: int | None = None,
    progress: list[dict] | None = None,
) -> None:
    if duration_ms is None and started is not None:
        duration_ms = int((time.perf_counter() - started) * 1000)
    async with async_session_maker() as session:
        finalized = await finalize_run(
            session,
            run_id=run_id,
            status=status,
            serialized=serialized,
            error=error,
            duration_ms=duration_ms,
            cost_micros=cost_micros,
            progress=progress,
        )

    # Story 3.13 (T4/D1): the async door's single completion point, so all three
    # `_finalize_async` call sites are covered here rather than individually.
    # Gated on `finalized` because `finalize_run` is best-effort: a run whose
    # terminal status never committed is still `running` to any other
    # connection, and enqueueing on it would hand the task a row the service
    # correctly refuses to extract from. `status` is filtered inside the seam, so
    # the error/cancel paths through here never enqueue.
    if finalized:
        enqueue_run_memory_extraction_after_commit(run_id, status=status)
        await _publish_finished(run_id, status, serialized=serialized, error=error)
    else:
        logger.warning("run %s not finalized; skipping run.finished publish", run_id)


async def _notify_terminal(run_id: str, status: str) -> None:
    """Best-effort inbox notification when a deep-research run reaches a terminal status.

    Falls back to the workspace owner when the run has no recorded user_id.
    """
    try:
        from app.db import Run, Workspace
        from app.notifications.service.facade import NotificationService

        async with async_session_maker() as notify_session:
            run = await notify_session.get(Run, _uuid.UUID(run_id))
            if run is None or run.capability != "chainlens.research":
                return

            user_id = run.user_id
            if user_id is None:
                workspace = await notify_session.get(Workspace, run.workspace_id)
                if workspace is not None:
                    user_id = workspace.user_id
            if user_id is None:
                return

            if isinstance(user_id, str):
                user_id = _uuid.UUID(user_id)

            title_map = {
                "success": "Deep research complete",
                "error": "Deep research failed",
                "cancelled": "Deep research cancelled",
            }
            title = title_map.get(status, f"Deep research {status}")
            message = (
                f"Your deep research run run_{run_id} finished with status: {status}."
            )
            await NotificationService.create_notification(
                session=notify_session,
                user_id=user_id,
                notification_type="deep_research_complete",
                title=title,
                message=message,
                workspace_id=run.workspace_id,
                notification_metadata={
                    "run_id": f"run_{run_id}",
                    "status": status,
                    "capability": run.capability,
                },
            )
    except Exception:
        logger.exception("failed to create terminal notification for run %s", run_id)


async def _publish_finished(
    run_id: str,
    status: str,
    *,
    serialized: SerializedOutput | None = None,
    error: str | None = None,
) -> None:
    """Emit the terminal event to subscribers, notify the user, and drop bus state."""
    event: dict[str, Any] = {
        "type": "run.finished",
        "run_id": f"run_{run_id}",
        "status": status,
        "ts": _now_ms(),
    }
    if serialized is not None:
        event["item_count"] = serialized.item_count
    if error is not None:
        event["error"] = error
    run_event_bus.publish(run_id, event)
    await _notify_terminal(run_id, status)
    run_event_bus.close(run_id)


def _log_task_result(run_id: str, task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("async run %s task crashed: %r", run_id, exc)


async def record_and_publish_sync_run(
    *,
    session: AsyncSession,
    workspace_id: int,
    capability: str,
    origin: str,
    payload: BaseModel,
    output: BaseModel,
    user_id: Any | None = None,
    thread_id: str | None = None,
    duration_ms: int | None = None,
    cost_micros: int | None = None,
    progress: list[dict] | None = None,
) -> str | None:
    """Record a synchronous capability run and return its id (best-effort).

    Shared by the REST sync door and the agent sync door so both produce the
    same ``runs`` row.
    """
    input_dump = payload.model_dump(exclude_none=True)
    serialized = serialize_output(output)
    run_id = await record_run(
        session,
        workspace_id=workspace_id,
        capability=capability,
        origin=origin,
        status="success",
        serialized=serialized,
        input=input_dump,
        user_id=user_id,
        thread_id=thread_id,
        duration_ms=duration_ms,
        cost_micros=cost_micros,
        progress=progress,
    )
    if run_id is not None:
        # Story 3.13 (T4/D1): the sync door also enqueues memory extraction at
        # a single point after the row is durable.
        enqueue_run_memory_extraction_after_commit(run_id)
        await _publish_finished(
            run_id, "success", serialized=serialized, error=None
        )
    return run_id


async def record_and_publish_sync_run_error(
    *,
    session: AsyncSession,
    workspace_id: int,
    capability: str,
    origin: str,
    payload: BaseModel,
    user_id: Any | None = None,
    thread_id: str | None = None,
    error: str,
    duration_ms: int | None = None,
    progress: list[dict] | None = None,
) -> str | None:
    """Record a failed synchronous run and return its id (best-effort)."""
    input_dump = payload.model_dump(exclude_none=True)
    run_id = await record_run(
        session,
        workspace_id=workspace_id,
        capability=capability,
        origin=origin,
        status="error",
        input=input_dump,
        user_id=user_id,
        thread_id=thread_id,
        error=error,
        duration_ms=duration_ms,
        progress=progress,
    )
    if run_id is not None:
        await _publish_finished(run_id, "error", error=error)
    return run_id


async def finalize_cancelled_run(
    run_id: str,
    error: str = "Cancelled by user",
) -> bool:
    """Finalize a running run as cancelled and publish the terminal event.

    Called from the cancel endpoint. The background task is cancelled locally if
    it lives in this process; cross-replica cancellation relies on the run
    reaching a terminal state through other means.
    """
    async with async_session_maker() as cancel_session:
        finalized = await finalize_run(
            cancel_session,
            run_id=run_id,
            status="cancelled",
            error=error,
        )
    await _publish_finished(run_id, "cancelled", error=error)
    return finalized
