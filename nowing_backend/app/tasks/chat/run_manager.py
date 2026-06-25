"""Background agent run lifecycle manager.

Manages detached asyncio tasks for persistent agent execution that survives
FE disconnect, browser refresh, and worker restart.

Single-worker constraint (M1): _active_runs is module-level dict.
With --workers N>1, cancel that lands on a different worker is a no-op.
Deployment MUST use UVICORN_WORKERS=1 (or sticky sessions via Redis — OOS).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import text

from app.db import ChatRun, ChatRunEvent, ChatRunStatus, shielded_async_session

if TYPE_CHECKING:
    from app.services.run_event_writer import RunEventWriter

log = logging.getLogger(__name__)

# Module-level strong refs — keys alive until task completes (M1)
_active_runs: dict[UUID, asyncio.Task] = {}
_cancel_events: dict[UUID, asyncio.Event] = {}

# Feature flag: when False, start_run and /runs/active return 503/empty (M3)
_RESUMABLE_RUNS_ENABLED = os.getenv("RESUMABLE_RUNS_ENABLED", "true").lower() == "true"


# ------------------------------------------------------------------
# Redis client (lazy singleton)
# ------------------------------------------------------------------

_redis_client = None


async def _get_redis():
    global _redis_client
    if _redis_client is None:
        import redis.asyncio as aioredis

        from app.celery_app import CELERY_BROKER_URL

        _redis_client = aioredis.from_url(CELERY_BROKER_URL, decode_responses=True)
    return _redis_client


# ------------------------------------------------------------------
# Status helpers
# ------------------------------------------------------------------

async def _mark_run_completed(run_id: UUID, final_message_id: int | None = None) -> None:
    async with shielded_async_session() as session:
        await session.execute(
            text(
                "UPDATE chat_runs SET status='completed', completed_at=NOW(), "
                "final_message_id=:msg_id WHERE id=:rid"
            ),
            {"rid": str(run_id), "msg_id": final_message_id},
        )
        await session.commit()
    log.info("run %s completed", run_id)


# Public alias for tests and external callers
complete_run = _mark_run_completed


async def _mark_run_failed(run_id: UUID, error: str) -> None:
    """Persist a generic failure marker. Full error goes to server log only — never DB.

    M3: raw exception strings may include API keys / prompt fragments / DB URLs.
    """
    log.error("run %s failed: %s", run_id, error[:2000], exc_info=False)
    redacted = "Run failed; see server logs for details."
    async with shielded_async_session() as session:
        await session.execute(
            text(
                "UPDATE chat_runs SET status='failed', completed_at=NOW(), "
                "error_message=:err WHERE id=:rid"
            ),
            {"rid": str(run_id), "err": redacted},
        )
        await session.commit()


async def _mark_run_cancelled(run_id: UUID) -> None:
    async with shielded_async_session() as session:
        await session.execute(
            text(
                "UPDATE chat_runs SET status='cancelled', completed_at=NOW() "
                "WHERE id=:rid"
            ),
            {"rid": str(run_id)},
        )
        await session.commit()
    log.info("run %s cancelled", run_id)


# ------------------------------------------------------------------
# start_run
# ------------------------------------------------------------------

async def start_run(
    thread_id: int,
    user_query: str,
    user_id: UUID,
    search_space_id: int,
    llm_config_id: int = -1,
    model_id: int | None = None,
    mentioned_document_ids: list[int] | None = None,
    mentioned_nowing_doc_ids: list[int] | None = None,
    disabled_tools: list[str] | None = None,
    needs_history_bootstrap: bool = False,
    thread_visibility=None,
    current_user_display_name: str | None = None,
) -> ChatRun:
    """Dispatch a detached agent execution task. Returns immediately (<300ms)."""
    if not _RESUMABLE_RUNS_ENABLED:
        raise HTTPException(503, "Resumable runs not enabled. Use /regenerate.")

    run_id = uuid4()
    session_id = f"{thread_id}-{run_id.hex[:8]}"
    langgraph_thread_id = f"run-{run_id}"

    run = ChatRun(
        id=run_id,
        thread_id=thread_id,
        created_by_id=user_id,
        session_id=session_id,
        langgraph_thread_id=langgraph_thread_id,
        user_query=user_query,
        llm_config_id=llm_config_id if llm_config_id > 0 else None,
        model_id=model_id,
        mentioned_document_ids=mentioned_document_ids,
        disabled_tools=disabled_tools,
        status=ChatRunStatus.RUNNING,
        started_at=datetime.now(UTC),
        last_heartbeat_at=datetime.now(UTC),
    )
    async with shielded_async_session() as session:
        session.add(run)
        await session.commit()
        await session.refresh(run)

    await _spawn_execution_task(
        run=run,
        user_query=user_query,
        search_space_id=search_space_id,
        llm_config_id=llm_config_id,
        model_id=model_id,
        mentioned_document_ids=mentioned_document_ids,
        mentioned_nowing_doc_ids=mentioned_nowing_doc_ids,
        disabled_tools=disabled_tools,
        needs_history_bootstrap=needs_history_bootstrap,
        thread_visibility=thread_visibility,
        current_user_display_name=current_user_display_name,
        checkpoint_id=None,
    )

    return run


async def _spawn_execution_task(
    run: ChatRun,
    user_query: str,
    search_space_id: int,
    llm_config_id: int,
    model_id: int | None,
    mentioned_document_ids: list[int] | None,
    mentioned_nowing_doc_ids: list[int] | None,
    disabled_tools: list[str] | None,
    needs_history_bootstrap: bool,
    thread_visibility,
    current_user_display_name: str | None,
    checkpoint_id: str | None,
) -> None:
    """Internal: create and track the detached asyncio task (C2: codebase pattern)."""
    from app.agents.new_chat.chat_deepagent import _stream_cancel_event_var, _stream_writer_var
    from app.services.run_event_writer import RunEventWriter
    from app.tasks.chat.stream_new_chat import stream_new_chat_detached

    run_id = run.id
    cancel_event = asyncio.Event()
    _cancel_events[run_id] = cancel_event

    async def _execute():
        redis = await _get_redis()
        writer = RunEventWriter(run_id, redis, shielded_async_session)
        writer_token = _stream_writer_var.set(writer.write)
        cancel_token = _stream_cancel_event_var.set(cancel_event)  # T13
        flush_task = asyncio.create_task(writer.run_flush_loop())
        final_message_id: int | None = None

        try:
            final_message_id = await stream_new_chat_detached(
                run_id=run_id,
                langgraph_thread_id=run.langgraph_thread_id,
                user_query=user_query,
                search_space_id=search_space_id,
                thread_id=run.thread_id,
                user_id=str(run.created_by_id),
                llm_config_id=llm_config_id,
                model_id=model_id,
                mentioned_document_ids=mentioned_document_ids,
                mentioned_nowing_doc_ids=mentioned_nowing_doc_ids,
                disabled_tools=disabled_tools,
                needs_history_bootstrap=needs_history_bootstrap,
                thread_visibility=thread_visibility,
                current_user_display_name=current_user_display_name,
                checkpoint_id=checkpoint_id,
                cancel_event=cancel_event,
                writer=writer,
            )
            # M4: if cooperative cancel was signalled, prefer cancelled status over completed
            if cancel_event.is_set():
                await _mark_run_cancelled(run_id)
            else:
                await _mark_run_completed(run_id, final_message_id)
        except asyncio.CancelledError:
            await _mark_run_cancelled(run_id)
            raise
        except Exception as exc:
            err = (str(exc) or repr(exc))[:8000]
            await _mark_run_failed(run_id, err)
        finally:
            _stream_writer_var.reset(writer_token)
            _stream_cancel_event_var.reset(cancel_token)  # T13
            await writer.stop()
            try:
                await flush_task
            except (asyncio.CancelledError, Exception):
                pass

    # M19: register task in _active_runs BEFORE starting it so cancel_run race within <1ms is safe
    task = asyncio.ensure_future(_execute())
    _active_runs[run_id] = task

    def _cleanup(t: asyncio.Task):
        _active_runs.pop(run_id, None)
        _cancel_events.pop(run_id, None)

    task.add_done_callback(_cleanup)
    log.info("spawned run %s (thread=%d, langgraph_thread=%s)", run_id, run.thread_id, run.langgraph_thread_id)


# ------------------------------------------------------------------
# cancel_run
# ------------------------------------------------------------------

async def cancel_run(run_id: UUID) -> bool:
    """Cooperative cancel → 2s grace → task.cancel(). Returns True if run was active."""
    event = _cancel_events.get(run_id)
    if event:
        event.set()

    task = _active_runs.get(run_id)
    if task and not task.done():
        # C1: drop shield — wait_for should be allowed to cancel the task on timeout.
        # On cooperative success the task finishes; on timeout we hard-cancel and swallow.
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        return True

    # Not in active dict — still update DB status if it's currently running
    async with shielded_async_session() as session:
        result = await session.execute(
            text(
                "UPDATE chat_runs SET status='cancelled', completed_at=NOW() "
                "WHERE id=:rid AND status='running' RETURNING id"
            ),
            {"rid": str(run_id)},
        )
        await session.commit()
        cancelled = bool(result.fetchone())

    # M12: publish orchestra-cancel so any live SSE tail sees a terminal event
    if cancelled:
        try:
            redis = await _get_redis()
            channel = f"nowing:run:{run_id}"
            await redis.publish(
                channel,
                json.dumps({
                    "event_type": "orchestra-cancel",
                    "payload": {"sessionId": str(run_id), "reason": "user_cancel"},
                }),
            )
        except Exception as exc:
            log.warning("orchestra-cancel publish failed for run %s: %s", run_id, exc)
    return cancelled


# ------------------------------------------------------------------
# resume_run
# ------------------------------------------------------------------

async def resume_run(
    run_id: UUID,
    search_space_id: int,
    thread_visibility=None,
    current_user_display_name: str | None = None,
) -> ChatRun:
    """Resume an abandoned run from the latest non-human-end LangGraph checkpoint (H7)."""
    async with shielded_async_session() as session:
        result = await session.execute(
            text("SELECT * FROM chat_runs WHERE id=:rid"),
            {"rid": str(run_id)},
        )
        row = result.mappings().fetchone()

    if not row:
        raise HTTPException(404, "Run not found")
    if row["status"] != ChatRunStatus.ABANDONED:
        raise HTTPException(409, "Only abandoned runs can be resumed")

    # Verify checkpoint is resumable (H7)
    try:
        checkpoint_id = await _find_resumable_checkpoint(row["langgraph_thread_id"])
    except CheckpointerUnavailableError as exc:
        raise HTTPException(503, detail="checkpointer_unavailable") from exc
    if checkpoint_id is None:
        raise HTTPException(409, detail="checkpoint_not_resumable")

    # Update status → running
    async with shielded_async_session() as session:
        await session.execute(
            text(
                "UPDATE chat_runs SET status='running', started_at=NOW(), "
                "last_heartbeat_at=NOW(), error_message=NULL WHERE id=:rid"
            ),
            {"rid": str(run_id)},
        )
        await session.commit()
        result2 = await session.execute(
            text("SELECT * FROM chat_runs WHERE id=:rid"),
            {"rid": str(run_id)},
        )
        updated_row = result2.mappings().fetchone()

    # Re-create ChatRun object for return
    run = ChatRun(
        id=run_id,
        thread_id=updated_row["thread_id"],
        created_by_id=updated_row["created_by_id"],
        session_id=updated_row["session_id"],
        langgraph_thread_id=updated_row["langgraph_thread_id"],
        user_query=updated_row["user_query"],
        llm_config_id=updated_row["llm_config_id"],
        model_id=updated_row["model_id"],
        mentioned_document_ids=updated_row["mentioned_document_ids"],
        disabled_tools=updated_row["disabled_tools"],
        status=ChatRunStatus.RUNNING,
        started_at=datetime.now(UTC),
        last_heartbeat_at=datetime.now(UTC),
    )
    run.id = run_id

    await _spawn_execution_task(
        run=run,
        user_query=updated_row["user_query"] or "",
        search_space_id=search_space_id,
        llm_config_id=updated_row["llm_config_id"] or -1,
        model_id=updated_row["model_id"],
        mentioned_document_ids=updated_row["mentioned_document_ids"],
        disabled_tools=updated_row["disabled_tools"],
        needs_history_bootstrap=False,
        thread_visibility=thread_visibility,
        current_user_display_name=current_user_display_name,
        checkpoint_id=checkpoint_id,
    )

    return run


class CheckpointerUnavailableError(RuntimeError):
    """Raised when the checkpointer backend is reachable but errored — distinguishable from
    a clean miss (no resumable checkpoint exists). Caller should treat as 503, not 409."""


async def _find_resumable_checkpoint(langgraph_thread_id: str) -> str | None:
    """Walk checkpoints newest-first; pick latest where last message is not HumanMessage (H7).

    Returns None on clean miss. Raises CheckpointerUnavailableError on infra failure
    so the caller can surface 503 instead of 409.
    """
    from langchain_core.messages import HumanMessage

    from app.agents.new_chat.checkpointer import get_checkpointer

    try:
        checkpointer = await get_checkpointer()
        config = {"configurable": {"thread_id": langgraph_thread_id}}
        async for checkpoint_tuple in checkpointer.alist(config):
            messages = (
                checkpoint_tuple.checkpoint.get("channel_values", {}).get("messages", [])
            )
            if not messages:
                continue
            last_msg = messages[-1]
            if not isinstance(last_msg, HumanMessage):
                return checkpoint_tuple.config["configurable"].get("checkpoint_id")
    except (ConnectionError, TimeoutError, OSError) as exc:
        log.error("checkpointer unavailable for %s: %s", langgraph_thread_id, exc, exc_info=True)
        raise CheckpointerUnavailableError(str(exc)) from exc
    except Exception as exc:
        log.warning("checkpoint lookup miss for %s: %s", langgraph_thread_id, exc, exc_info=True)
    return None


# ------------------------------------------------------------------
# mark_abandoned_runs_on_startup
# ------------------------------------------------------------------

async def mark_abandoned_runs_on_startup() -> int:
    """Mark all DB-running runs as abandoned. Called on lifespan startup (M2, M5)."""
    if os.getenv("UVICORN_RELOAD", "").lower() == "true":
        log.debug("mark_abandoned_runs_on_startup: skipped (UVICORN_RELOAD=true, M5)")
        return 0
    if not _RESUMABLE_RUNS_ENABLED:
        return 0

    try:
        async with shielded_async_session() as session:
            # T9/AC9: heartbeat fence — only abandon runs with stale/missing heartbeat.
            # Healthy runs on sibling workers update last_heartbeat_at every 30s.
            # Runs with a heartbeat < 90s ago are still alive; leave them running.
            result = await session.execute(
                text(
                    "UPDATE chat_runs SET status='abandoned' "
                    "WHERE status='running' "
                    "AND (last_heartbeat_at IS NULL "
                    "     OR last_heartbeat_at < NOW() - interval '90 seconds') "
                    "RETURNING id"
                )
            )
            await session.commit()
            count = result.rowcount
            if count:
                log.info("startup: marked %d orphaned runs as abandoned (heartbeat fence)", count)
            return count
    except Exception as exc:
        # M2: migration may not have applied yet on fresh deploy
        log.warning("mark_abandoned_runs_on_startup skipped (table not ready?): %s", exc)
        return 0
