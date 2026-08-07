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

import json
import logging
import time
from typing import Any

from fastapi import HTTPException
from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command

from app.agents.chat.multi_agent_chat.shared.citations import load_registry
from app.auth.context import AuthContext
from app.capabilities.core import execute_with_context
from app.capabilities.core.access.rate_limit import (
    _KEY_PREFIX,
    _WINDOW_SECONDS,
    CAPABILITY_RATE_LIMIT_PER_MINUTE,
    _aincr,
)
from app.capabilities.core.access.run_citation import attach_run_citation
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
from app.exceptions import ExternalServiceError, ForbiddenError, NowingError
from app.services.memory.run_enqueue import (
    enqueue_run_memory_extraction_after_commit,
)
from app.services.token_tracking_service import add_current_turn_tool_cost
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


def _current_research_mode() -> str | None:
    """Best-effort ``configurable.research_mode`` from the active LangGraph config."""
    try:
        from langgraph.config import get_config

        cfg = get_config()
        return (cfg.get("configurable") or {}).get("research_mode")
    except Exception:
        return None


# NFR-9 State B: only speed/balanced may run synchronously in chat.
# quality, deep-research, deep-reasoning, and auto (which may resolve to those)
# are async-only until cost/latency targets are ratified.
_SYNC_CHAT_ALLOWED_MODES: frozenset[str] = frozenset({"speed", "balanced"})


def _is_sync_chat_mode_allowed(mode: str | None) -> bool:
    """Return True only when the given research mode may block a chat turn.

    ``None`` falls through to the default (``balanced``), which is allowed only
    while the feature flag is on. ``auto`` is never allowed in chat because the
    engine may resolve it to ``quality`` or deep modes.
    """
    if mode == "auto":
        return False
    if mode is None:
        mode = config.DEFAULT_RESEARCH_MODE
    return mode in _SYNC_CHAT_ALLOWED_MODES


async def _check_rate_limit(workspace_id: int) -> None:
    """Enforce the same per-workspace per-minute capability cap as the REST door.

    Unlike the REST dependency this does not raise HTTPException; it reuses the
    InsufficientCreditsError handler so the agent tool returns a string error.
    The underlying counter is off-loaded to a thread so the streaming event loop
    is not blocked by the sync Redis client or the in-memory lock.
    """
    count = await _aincr(f"{_KEY_PREFIX}:{workspace_id}", _WINDOW_SECONDS)
    if count > CAPABILITY_RATE_LIMIT_PER_MINUTE:
        raise InsufficientCreditsError(
            "Rate limit exceeded for this workspace. Try again shortly."
        )


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

    async def _run(runtime: ToolRuntime | None = None, **kwargs: object) -> dict | str | Command:
        # ponytail: thread the chat request's explicit research mode through to
        # chainlens.research so benchmark/user mode selections are honored.
        if name == "chainlens.research":
            research_mode = _current_research_mode()
            if research_mode:
                kwargs = {**kwargs, "mode": research_mode}
        payload = input_model(**kwargs)
        input_dump = payload.model_dump(exclude_none=True)
        thread_id = _current_thread_id()

        # NFR-9 State A vs State B for deep research in chat.
        #
        # State A (launch default): DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED is False.
        # chainlens.research is always async in chat. The agent submits the run
        # via start_async_run and returns a run_id so the chat turn can finish
        # without blocking on ChainLens. State A is required because the GTM
        # review shows ChainLens balanced p95 (44.3s) exceeds the 30s target for
        # a synchronous chat response.
        #
        # State B (opt-in): DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED is True AND the
        # requested mode is in the allow-list (speed/balanced). quality,
        # deep-research, deep-reasoning, and auto remain async-only in chat.
        if name == "chainlens.research" and not (
            config.DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED
            and _is_sync_chat_mode_allowed(research_mode)
        ):
            async with async_session_maker() as session:
                ctx = CapabilityContext(session=session, workspace_id=workspace_id)
                try:
                    if auth_context is not None:
                        await _verify_workspace_access(
                            session, workspace_id, auth_context
                        )
                    await _check_rate_limit(workspace_id)
                    await gate_capability(payload, unit, ctx)
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
                except ForbiddenError:
                    raise
                except InsufficientCreditsError as exc:
                    return str(exc)
                except NowingError as exc:
                    return f"Capability failed: {exc}"
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
                ctx = CapabilityContext(session=session, workspace_id=workspace_id)
                try:
                    if auth_context is not None:
                        await _verify_workspace_access(
                            session, workspace_id, auth_context
                        )
                    await _check_rate_limit(workspace_id)
                    await gate_capability(payload, unit, ctx)
                except ForbiddenError:
                    raise
                except InsufficientCreditsError as exc:
                    return str(exc)
                except NowingError as exc:
                    return f"Capability failed: {exc}"

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
                    if cost_micros:
                        # ponytail: include deep-research/tool cost in the chat
                        # turn's token-usage SSE so the benchmark sees the full cost.
                        add_current_turn_tool_cost(
                            cost_micros=cost_micros,
                            call_kind=name,
                        )
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

        if run_id is None:
            # Storage failed; fall back to the legacy return shape with no citation.
            if serialized.char_count <= RUN_OUTPUT_CHAR_CAP:
                dump = output.model_dump(exclude_none=True)
                if "next_action" in dump:
                    dump.setdefault("next_step", dump["next_action"])
                return dump
            return _build_preview(serialized, run_id)

        run_external_id = f"run_{run_id}"
        if serialized.char_count <= RUN_OUTPUT_CHAR_CAP:
            dump = output.model_dump(exclude_none=True)
            if "next_action" in dump:
                dump.setdefault("next_step", dump["next_action"])
            dump["run_id"] = run_external_id
        else:
            dump = None

        # Unit tests and direct ainvoke call paths do not supply a ToolRuntime.
        # Return the structured output directly so the tool is usable outside
        # a LangGraph ToolNode; citation rendering is reserved for the runtime.
        if runtime is None:
            if dump is not None:
                return dump
            return _build_preview(serialized, run_id)

        content = json.dumps(dump, ensure_ascii=False) if dump is not None else _build_preview(serialized, run_id)

        registry = load_registry(getattr(runtime, "state", None))
        _, label = attach_run_citation(
            registry,
            run_external_id=run_external_id,
            capability=name,
        )

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=content + label,
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
                "citation_registry": registry,
            }
        )

    _run.__annotations__["runtime"] = ToolRuntime

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
