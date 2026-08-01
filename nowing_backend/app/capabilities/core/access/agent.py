"""Generate the agent door from the capability registry (05).

One LangChain tool per verb; each runs the same thin adapter as the REST door
(``access/rest.py``): meter-gate -> executor -> charge. Every run is recorded to
the ``runs`` table (best-effort). Outputs that fit under ``RUN_OUTPUT_CHAR_CAP``
are returned inline; larger ones are stored and the model gets a char-budgeted
preview plus a ``run_<id>`` reference it can page with ``read_run``/``search_run``.
Those two read tools are appended to the tool list so every capability-using
subagent can follow a truncation reference without extra wiring.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import HTTPException
from langchain_core.tools import BaseTool, StructuredTool

from app.auth.context import AuthContext
from app.capabilities.core import execute_with_context
from app.capabilities.core.async_runner import start_async_run
from app.capabilities.core.billing import charge_capability, gate_capability
from app.capabilities.core.progress import progress_scope
from app.capabilities.core.runs import (
    RUN_OUTPUT_CHAR_CAP,
    record_run,
    serialize_output,
)
from app.capabilities.core.store import all_capabilities
from app.capabilities.core.types import Capability, CapabilityContext
from app.config import config
from app.db import async_session_maker
from app.exceptions import ExternalServiceError, ForbiddenError
from app.services.memory.run_enqueue import (
    enqueue_run_memory_extraction_after_commit,
)
from app.services.web_crawl_credit_service import InsufficientCreditsError
from app.utils.rbac import check_workspace_access

logger = logging.getLogger(__name__)


def build_capability_tools(
    *,
    workspace_id: int,
    capabilities: list[Capability] | None = None,
    user_id: Any | None = None,
    auth_context: AuthContext | None = None,
) -> list[BaseTool]:
    """Emit one tool per verb (defaults to the whole registry), plus the run readers.

    ``user_id`` is the active chat principal, threaded through to ``record_run`` so
    an agent-origin run carries a creator (Story 3.13, D4/T4). Without it every
    agent run is authorless, and memory extraction can only skip it as
    ``missing_creator`` — the run is still recorded either way. It stays optional
    because the caller resolves it from the subagent dependency dict, where it can
    legitimately be absent (e.g. an unauthenticated internal invocation).

    ``auth_context`` is used to re-validate workspace access before executing the
    tool, mirroring the REST door's trust-boundary check.
    """
    caps = capabilities if capabilities is not None else all_capabilities()
    tools = [
        _capability_tool(cap, workspace_id, user_id=user_id, auth_context=auth_context)
        for cap in caps
    ]
    # Deferred import: the reader lives in the agents package (which imports from
    # here), so importing it lazily avoids an import-time cycle.
    from app.agents.chat.multi_agent_chat.subagents.shared.run_reader import (
        build_run_reader_tools,
    )

    tools.extend(build_run_reader_tools(workspace_id=workspace_id))
    return tools


def _current_thread_id() -> str | None:
    """Best-effort ``configurable.thread_id`` from the active LangGraph config."""
    try:
        from langgraph.config import get_config

        cfg = get_config()
        tid = (cfg.get("configurable") or {}).get("thread_id")
        return str(tid) if tid is not None else None
    except Exception:
        return None


async def _verify_workspace_access(
    session: Any, workspace_id: int, auth_context: AuthContext
) -> None:
    """Re-validate workspace access before creating a ``CapabilityContext``.

    This is the same trust-boundary check the REST door runs via
    ``check_workspace_access``. ``HTTPException`` is remapped to a controlled
    ``ForbiddenError`` so the agent tool never raises an unhandled 500.
    """
    try:
        await check_workspace_access(session, auth_context, workspace_id)
    except HTTPException as exc:
        message = (
            str(exc.detail) if exc.detail is not None else "Workspace access denied."
        )
        raise ForbiddenError(message) from exc


def _capability_tool(
    capability: Capability,
    workspace_id: int,
    *,
    user_id: Any | None = None,
    auth_context: AuthContext | None = None,
) -> BaseTool:
    input_model = capability.input_schema
    unit = capability.billing_unit
    executor = capability.executor
    name = capability.name

    async def _run(**kwargs: object) -> dict | str:
        payload = input_model(**kwargs)
        input_dump = payload.model_dump(exclude_none=True)
        thread_id = _current_thread_id()

        # State A/B: deep research is always async in chat unless the sync
        # chat-mode feature flag is on. The agent submits the run and returns
        # the run id so the chat turn can finish without blocking on ChainLens.
        if (
            name == "chainlens.research"
            and not config.DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED
        ):
            async with async_session_maker() as session:
                if auth_context is not None:
                    await _verify_workspace_access(session, workspace_id, auth_context)
                ctx = CapabilityContext(session=session, workspace_id=workspace_id)
                try:
                    await gate_capability(payload, unit, ctx)
                except InsufficientCreditsError as exc:
                    return str(exc)
                run_id = await start_async_run(
                    session=session,
                    workspace_id=workspace_id,
                    capability=capability,
                    payload=payload,
                    origin="agent",
                    user_id=user_id,
                    thread_id=thread_id,
                )
            if run_id is None:
                raise ExternalServiceError(
                    "Could not start deep research run.",
                    code="CAPABILITY_START_ERROR",
                )
            return {
                "run_id": f"run_{run_id}",
                "status": "running",
                "message": "Deep research started. The result will stream via the run events endpoint.",
            }

        # A buffer-only reporter: coarse progress lands in ``runs.progress`` and,
        # because we're inside a LangGraph tool call, ``emit_progress`` also fires
        # ``scraper_progress`` custom events that surface on the chat thinking step.
        with progress_scope() as reporter:
            async with async_session_maker() as session:
                if auth_context is not None:
                    await _verify_workspace_access(session, workspace_id, auth_context)
                ctx = CapabilityContext(session=session, workspace_id=workspace_id)
                try:
                    await gate_capability(payload, unit, ctx)
                except InsufficientCreditsError as exc:
                    return str(exc)

                started = time.perf_counter()
                try:
                    output = await execute_with_context(
                        executor, payload=payload, ctx=ctx
                    )
                except Exception as exc:
                    duration_ms = int((time.perf_counter() - started) * 1000)
                    async with async_session_maker() as rec_session:
                        await record_run(
                            rec_session,
                            workspace_id=workspace_id,
                            capability=name,
                            origin="agent",
                            status="error",
                            input=input_dump,
                            user_id=user_id,
                            error=str(exc),
                            thread_id=thread_id,
                            duration_ms=duration_ms,
                            progress=reporter.coarse,
                        )
                    raise

                duration_ms = int((time.perf_counter() - started) * 1000)
                cost_micros = None
                try:
                    cost_micros = await charge_capability(output, unit, ctx)
                except Exception:
                    logger.exception("charge failed for agent run %s", name)

            serialized = serialize_output(output)
            async with async_session_maker() as rec_session:
                run_id = await record_run(
                    rec_session,
                    workspace_id=workspace_id,
                    capability=name,
                    origin="agent",
                    status="success",
                    serialized=serialized,
                    input=input_dump,
                    user_id=user_id,
                    thread_id=thread_id,
                    duration_ms=duration_ms,
                    cost_micros=cost_micros,
                    progress=reporter.coarse,
                )

            # T4/D1: the recorder owns its own session and has committed by the
            # time it returns a run id, so the row the task will load is already
            # visible to another connection. Never raises (AC-5).
            enqueue_run_memory_extraction_after_commit(run_id)

        if serialized.char_count <= RUN_OUTPUT_CHAR_CAP:
            dump = output.model_dump(exclude_none=True)
            if "next_action" in dump:
                dump.setdefault("next_step", dump["next_action"])
            if run_id is not None:
                dump["run_id"] = f"run_{run_id}"
            return dump

        return _build_preview(serialized, run_id)

    return StructuredTool.from_function(
        coroutine=_run,
        name=name.replace(".", "_"),
        description=capability.description,
        args_schema=input_model,
    )


def _build_preview(serialized, run_id: str | None) -> str:
    """Char-budgeted preview: whole JSONL items until the cap is spent."""
    lines = serialized.text.split("\n")
    preview_lines: list[str] = []
    used = 0
    for line in lines:
        cost = len(line) + 1
        if used + cost > RUN_OUTPUT_CHAR_CAP:
            break
        preview_lines.append(line)
        used += cost

    if not preview_lines and lines:
        # A single item larger than the cap: show a clipped head so the model
        # still sees the shape and can page/search for the rest.
        preview_lines = [lines[0][:RUN_OUTPUT_CHAR_CAP]]

    shown = len(preview_lines)
    preview = "\n".join(preview_lines)

    if run_id is None:
        return (
            f"{preview}\n\n...Showing {shown} of {serialized.item_count} items "
            f"({serialized.char_count} chars). Full output unavailable (storage error)."
        )
    return (
        f"{preview}\n\n...Showing {shown} of {serialized.item_count} items "
        f"({serialized.char_count} chars). Full run stored as run_{run_id}. Use "
        f"read_run('run_{run_id}', offset, limit) or search_run('run_{run_id}', "
        "pattern) to inspect the rest."
    )
