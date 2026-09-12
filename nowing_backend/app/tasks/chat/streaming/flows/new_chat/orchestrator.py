"""``stream_new_chat`` — public entry point for a fresh chat turn.

Slim composition layer over the per-concern modules in this folder and the
building blocks under ``flows/shared/``. Stage bodies live in ``_stages.py``;
each phase corresponds to a numbered block in the surrounding code so the
on-the-wire ordering stays explicit:

  1. Validation / config — auto-pin, LLM bundle, capability, premium reserve.
  2. Concurrent persistence + pre-stream setup — spawn DB writes, build the
     connector, fetch the checkpointer, build the agent.
  3. Input assembly — history bootstrap, mentions, nowing docs, reports.
  4. First SSE frames — message_start, start_step, turn-info, turn-status.
  5. Persistence join + message-id frames (ghost-thread protection).
  6. Initial thinking step + title task + runtime context.
  7. Stream loop with in-stream rate-limit recovery + mid-stream title emit.
  8. Finalize — premium debit, token-usage SSE, finish frames.
  9. Exception branch — classify, emit terminal error, finish frames.
 10. Finally — premium release, session close, assistant finalize, GC, span.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from collections.abc import AsyncGenerator
from functools import partial
from typing import Any, Literal
from uuid import UUID

from app.agents.chat.multi_agent_chat import create_multi_agent_chat_deep_agent
from app.agents.chat.multi_agent_chat.shared.filesystem_selection import (
    FilesystemMode,
    FilesystemSelection,
)
from app.agents.chat.runtime.llm_config import AgentConfig as RuntimeAgentConfig
from app.auth.context import AuthContext
from app.db import (
    AgentConfig as RegistryAgentConfig,
    ChatVisibility,
    NewChatThread,
    async_session_maker,
)
from app.observability import otel as ot
from app.services.new_streaming_service import VercelStreamingService
from app.tasks.chat.streaming.agent.builder import build_main_agent_for_thread
from app.tasks.chat.streaming.contract.file_contract import log_file_contract
from app.tasks.chat.streaming.errors.emitter import emit_stream_terminal_error
from app.tasks.chat.streaming.flows.new_chat._recovery import (
    _RateLimitRecoveryState,
    _recover_provider_rate_limit,
)
from app.tasks.chat.streaming.flows.new_chat._stages import (
    _MAX_INSTRUCTIONS_LEN,
    _AgentNotFoundError,
    _clamp_agent_instructions,
    _emit_pre_stream_frames,
    _merge_registry_agent_config,
    _PreStreamOutcome,
    _resolve_model_and_config,
    _run_turn_cleanup,
)
from app.tasks.chat.streaming.flows.new_chat.input_state import (
    build_new_chat_input_state,
)
from app.tasks.chat.streaming.flows.new_chat.persistence_spawn import (
    spawn_persist_user_task,
    spawn_set_ai_responding_bg,
)
from app.tasks.chat.streaming.flows.new_chat.title_gen import (
    await_pending_title_update,
    maybe_emit_title_update,
)
from app.tasks.chat.streaming.flows.shared.finalize_emit import (
    iter_suggested_actions_frame,
    iter_token_usage_frame,
)
from app.tasks.chat.streaming.flows.shared.finally_cleanup import (
    run_gc_pass,
)
from app.tasks.chat.streaming.flows.shared.first_frames import iter_final_frames
from app.tasks.chat.streaming.flows.shared.pre_stream_setup import (
    get_chat_checkpointer,
    setup_connector_service,
)
from app.tasks.chat.streaming.flows.shared.premium_quota import (
    CreditReservation,
    finalize_credit,
)
from app.tasks.chat.streaming.flows.shared.span import (
    close_chat_request_span,
    open_chat_request_span,
    set_agent_mode,
)
from app.tasks.chat.streaming.flows.shared.stream_loop import run_stream_loop
from app.tasks.chat.streaming.flows.shared.terminal_error import (
    handle_terminal_exception,
)
from app.tasks.chat.streaming.shared.stream_result import StreamResult
from app.tenant_context import set_request_tenant_context
from app.utils.perf import get_perf_logger, log_system_snapshot

logger = logging.getLogger(__name__)
_perf_log = get_perf_logger()

# Holds spawned background tasks (set_ai_responding, persist_user, persist_asst)
# so the GC doesn't drop them before they finish. Kept at module level so it
# survives across turns within one process.
_background_tasks: set[asyncio.Task] = set()

# Re-exported for ``resume_chat.orchestrator`` and tests that historically
# imported them from this module.
__all__ = [
    "_MAX_INSTRUCTIONS_LEN",
    "_AgentNotFoundError",
    "_clamp_agent_instructions",
    "_merge_registry_agent_config",
    "stream_new_chat",
]


async def stream_new_chat(
    user_query: str,
    workspace_id: int,
    chat_id: int,
    user_id: str | None = None,
    llm_config_id: int = -1,
    mentioned_document_ids: list[int] | None = None,
    mentioned_folder_ids: list[int] | None = None,
    mentioned_connector_ids: list[int] | None = None,
    mentioned_connectors: list[dict[str, Any]] | None = None,
    mentioned_documents: list[dict[str, Any]] | None = None,
    mentioned_thread_ids: list[int] | None = None,
    checkpoint_id: str | None = None,
    needs_history_bootstrap: bool = False,
    thread_visibility: ChatVisibility | None = None,
    current_user_display_name: str | None = None,
    disabled_tools: list[str] | None = None,
    filesystem_selection: FilesystemSelection | None = None,
    request_id: str | None = None,
    user_image_data_urls: list[str] | None = None,
    auth_context: AuthContext | None = None,
    client_id: str | None = None,
    agent_id: str | None = None,
    platform_metadata: dict[str, Any] | None = None,
    external_metadata: dict[str, Any] | None = None,
    run_id: UUID | None = None,
    llm: Any | None = None,
    agent_config: RuntimeAgentConfig | None = None,
    agent_config_override: RegistryAgentConfig | None = None,
    mode: Literal["speed", "balanced", "quality", "auto"] | None = None,
    flow: Literal["new", "regenerate"] = "new",
) -> AsyncGenerator[str, None]:
    """Stream a new chat turn using the Nowing deep agent.

    Uses the Vercel AI SDK Data Stream Protocol (SSE). ``chat_id`` is the
    LangGraph thread id (durable conversation memory via the checkpointer).
    Manages its own database session so cleanup runs even when Starlette
    cancels the task on client disconnect.
    """
    streaming_service = VercelStreamingService()
    stream_result = StreamResult()
    _t_total = time.perf_counter()
    fs_mode = filesystem_selection.mode.value if filesystem_selection else "cloud"
    fs_platform = (
        filesystem_selection.client_platform.value if filesystem_selection else "web"
    )
    stream_result.request_id = request_id
    stream_result.turn_id = f"{chat_id}:{int(time.time() * 1000)}"
    stream_result.filesystem_mode = fs_mode
    stream_result.client_platform = fs_platform

    chat_agent_mode = "unknown"
    chat_outcome = "success"
    chat_error_category: str | None = None
    chat_span_cm, chat_span = open_chat_request_span(
        chat_id=chat_id,
        workspace_id=workspace_id,
        flow=flow,
        request_id=request_id,
        turn_id=stream_result.turn_id,
        filesystem_mode=fs_mode,
        client_platform=fs_platform,
        agent_mode=chat_agent_mode,
    )
    log_file_contract("turn_start", stream_result)
    _perf_log.info(
        "[stream_new_chat] filesystem_mode=%s client_platform=%s",
        fs_mode,
        fs_platform,
    )
    log_system_snapshot("stream_new_chat_START")

    from app.services.token_tracking_service import start_turn

    accumulator = start_turn()

    premium_reservation: CreditReservation | None = None
    busy_error_raised = False

    emit_stream_error = partial(
        emit_stream_terminal_error,
        streaming_service=streaming_service,
        flow=flow,
        request_id=request_id,
        thread_id=chat_id,
        workspace_id=workspace_id,
        user_id=user_id,
    )

    _maybe_session = async_session_maker()
    if inspect.isawaitable(_maybe_session):
        session = await _maybe_session
    else:
        session = _maybe_session
    # Propagate tenant GUCs so any query inside the stream respects client RLS.
    await set_request_tenant_context(
        session,
        workspace_id=workspace_id,
        client_id=client_id,
        agent_id=agent_id,
    )

    # Load the chat thread once so downstream layers can scope memory recall
    # to the linked ResearchThread (Story 18.5 AC-3). Mirror the turn's
    # platform_metadata on the thread for last-turn context (P-METADATA-PERSIST).
    chat_thread = await session.get(NewChatThread, chat_id)
    if chat_thread is not None:
        # Story 27.1a: per-turn payload overrides thread-level metadata; if the
        # turn omits it (or sends an empty dict), fall back to the thread's
        # stored metadata so mode is not lost on regenerate/refresh.
        thread_metadata = getattr(chat_thread, "platform_metadata", None)
        if platform_metadata:
            chat_thread.platform_metadata = platform_metadata
        elif thread_metadata is not None:
            platform_metadata = thread_metadata
    research_thread_id = (
        chat_thread.research_thread_id if chat_thread is not None else None
    )

    # Declared at function scope so SSE-yield join points and the finally
    # clause see them on every exit path.
    persist_user_task: asyncio.Task[int | None] | None = None
    try:
        spawn_set_ai_responding_bg(
            chat_id=chat_id, user_id=user_id, background_tasks=_background_tasks
        )

        # --- Block 1: LLM config + capability ---

        requested_llm_config_id = llm_config_id
        requires_image_input = bool(user_image_data_urls)

        error_frames, resolved = await _resolve_model_and_config(
            session,
            chat_id=chat_id,
            workspace_id=workspace_id,
            user_id=user_id,
            llm_config_id=llm_config_id,
            requested_llm_config_id=requested_llm_config_id,
            requires_image_input=requires_image_input,
            user_image_data_urls=user_image_data_urls,
            llm=llm,
            agent_config=agent_config,
            agent_config_override=agent_config_override,
            client_id=client_id,
            agent_id=agent_id,
            disabled_tools=disabled_tools,
            platform_metadata=platform_metadata,
            chat_thread=chat_thread,
            flow=flow,
            request_id=request_id,
            emit_error=emit_stream_error,
            streaming_service=streaming_service,
        )
        premium_reservation = resolved.premium_reservation
        if error_frames is not None:
            for frame in error_frames:
                yield frame
            return
        llm_config_id = resolved.llm_config_id
        llm = resolved.llm
        agent_config = resolved.agent_config
        effective_enabled_tools = resolved.effective_enabled_tools
        effective_disabled_tools = resolved.effective_disabled_tools
        chat_mode = resolved.chat_mode

        # --- Block 2: Spawn concurrent persistence; build pre-stream setup ---

        persist_user_task = spawn_persist_user_task(
            chat_id=chat_id,
            user_id=user_id,
            turn_id=stream_result.turn_id,
            user_query=user_query,
            user_image_data_urls=user_image_data_urls,
            mentioned_documents=mentioned_documents,
            background_tasks=_background_tasks,
            platform_metadata=platform_metadata,
        )

        _t0 = time.perf_counter()
        connector_service = await setup_connector_service(
            session, workspace_id=workspace_id
        )
        _perf_log.info(
            "[stream_new_chat] Connector service in %.3fs",
            time.perf_counter() - _t0,
        )

        _t0 = time.perf_counter()
        checkpointer = await get_chat_checkpointer()
        _perf_log.info(
            "[stream_new_chat] Checkpointer ready in %.3fs", time.perf_counter() - _t0
        )

        visibility = thread_visibility or ChatVisibility.PRIVATE
        chat_agent_mode = "multi"
        set_agent_mode(chat_span, chat_agent_mode)

        _t0 = time.perf_counter()
        agent_factory = create_multi_agent_chat_deep_agent
        # Build the agent inline. Provider 429s surface through the in-stream
        # recovery loop below, which repins the thread to an eligible
        # alternative config and rebuilds the agent before the user sees any
        # output.
        agent = await build_main_agent_for_thread(
            agent_factory,
            llm=llm,
            workspace_id=workspace_id,
            db_session=session,
            connector_service=connector_service,
            checkpointer=checkpointer,
            user_id=user_id,
            thread_id=chat_id,
            agent_config=agent_config,
            thread_visibility=visibility,
            filesystem_selection=filesystem_selection,
            enabled_tools=effective_enabled_tools,
            disabled_tools=effective_disabled_tools,
            mentioned_document_ids=mentioned_document_ids,
            auth_context=auth_context,
            research_mode=mode,
            research_thread_id=research_thread_id,
            client_id=client_id,
        )
        _perf_log.info(
            "[stream_new_chat] Agent created in %.3fs", time.perf_counter() - _t0
        )

        # --- Block 3: Input assembly ---

        _t0 = time.perf_counter()
        assembled = await build_new_chat_input_state(
            session,
            chat_id=chat_id,
            workspace_id=workspace_id,
            user_query=user_query,
            user_image_data_urls=user_image_data_urls,
            mentioned_document_ids=mentioned_document_ids,
            mentioned_folder_ids=mentioned_folder_ids,
            mentioned_connectors=mentioned_connectors,
            mentioned_documents=mentioned_documents,
            mentioned_thread_ids=mentioned_thread_ids,
            requesting_user_id=user_id,
            needs_history_bootstrap=needs_history_bootstrap,
            thread_visibility=visibility,
            current_user_display_name=current_user_display_name,
            filesystem_mode=fs_mode,
            request_id=request_id,
            turn_id=stream_result.turn_id,
            client_id=client_id,
            agent_id=agent_id,
            platform_metadata=platform_metadata,
        )
        input_state = assembled.input_state
        accepted_folder_ids = assembled.accepted_folder_ids
        _perf_log.info(
            "[stream_new_chat] History bootstrap + doc/report queries in %.3fs",
            time.perf_counter() - _t0,
        )

        # All pre-streaming DB reads done. Commit to release the transaction
        # and its ACCESS SHARE locks so we don't block DDL (e.g. migrations)
        # for the entire LLM streaming duration. Tools that need DB access
        # during streaming start their own short-lived transactions (or use
        # isolated sessions).
        await session.commit()
        # Detach heavy ORM objects (documents with chunks, reports, etc.)
        # from the session identity map now that we've extracted what we
        # need. Without this they accumulate in memory for the entire
        # streaming duration (which can be several minutes).
        session.expunge_all()

        _perf_log.info(
            "[stream_new_chat] Total pre-stream setup in %.3fs (chat_id=%s)",
            time.perf_counter() - _t_total,
            chat_id,
        )

        configurable: dict[str, Any] = {
            "thread_id": str(chat_id),
            "request_id": request_id or "unknown",
            "turn_id": stream_result.turn_id,
        }
        if mode:
            configurable["research_mode"] = mode
        if checkpoint_id:
            configurable["checkpoint_id"] = checkpoint_id

        config = {
            "configurable": configurable,
            # Effectively uncapped, matching the agent-level ``with_config``
            # default in ``chat_deepagent.create_agent`` and the unbounded
            # ``while(true)`` in OpenCode's ``session/processor.ts``. Real
            # circuit-breakers live in middleware (``DoomLoopMiddleware``,
            # plus ``enable_tool_call_limit`` / ``enable_model_call_limit``).
            # The original 25 (and our previous 80 bump) hit users on
            # legitimate multi-tool plans.
            "recursion_limit": 10_000,
        }

        # Drop the heavy ORM objects + the container that holds them so they
        # aren't retained for the entire streaming duration. ``input_state``
        # already carries the langchain_messages list independently.
        del assembled

        # --- Blocks 4-6: first frames, persistence join, thinking step ---

        pre_stream = _PreStreamOutcome()
        async for sse in _emit_pre_stream_frames(
            out=pre_stream,
            streaming_service=streaming_service,
            stream_result=stream_result,
            emit_error=emit_stream_error,
            chat_id=chat_id,
            user_id=user_id,
            user_query=user_query,
            user_image_data_urls=user_image_data_urls,
            platform_metadata=platform_metadata,
            persist_user_task=persist_user_task,
            background_tasks=_background_tasks,
            llm=llm,
            agent_config=agent_config,
            workspace_id=workspace_id,
            mentioned_document_ids=mentioned_document_ids,
            accepted_folder_ids=accepted_folder_ids,
            mentioned_folder_ids=mentioned_folder_ids,
            mentioned_connector_ids=mentioned_connector_ids,
            mentioned_connectors=mentioned_connectors,
            request_id=request_id,
        ):
            yield sse
        if pre_stream.abort:
            return

        title_task = pre_stream.title_task
        title_emitted = False
        runtime_context = pre_stream.runtime_context

        # --- Block 7: Stream loop ---

        _t_stream_start = time.perf_counter()

        def _on_first_event() -> None:
            _perf_log.info(
                "[stream_new_chat] First agent event in %.3fs (time since stream start), "
                "%.3fs (total since request start) (chat_id=%s)",
                time.perf_counter() - _t_stream_start,
                time.perf_counter() - _t_total,
                chat_id,
            )

        recovery_state = _RateLimitRecoveryState(
            llm_config_id=llm_config_id,
            llm=llm,
            agent_config=agent_config,
            runtime_rate_limit_recovered=False,
            title_task=title_task,
            effective_enabled_tools=effective_enabled_tools,
            effective_disabled_tools=effective_disabled_tools,
        )
        _recover = partial(
            _recover_provider_rate_limit,
            state=recovery_state,
            session=session,
            requested_llm_config_id=requested_llm_config_id,
            requires_image_input=requires_image_input,
            chat_id=chat_id,
            workspace_id=workspace_id,
            user_id=user_id,
            agent_config_override=agent_config_override,
            client_id=client_id,
            agent_id=agent_id,
            disabled_tools=disabled_tools,
            chat_mode=chat_mode,
            chat_thread=chat_thread,
            agent_factory=agent_factory,
            connector_service=connector_service,
            checkpointer=checkpointer,
            visibility=visibility,
            filesystem_selection=filesystem_selection,
            mentioned_document_ids=mentioned_document_ids,
            auth_context=auth_context,
            research_thread_id=research_thread_id,
            flow=flow,
            request_id=request_id,
        )

        async for sse in run_stream_loop(
            agent=agent,
            streaming_service=streaming_service,
            config=config,
            input_data=input_state,
            stream_result=stream_result,
            step_prefix="thinking",
            initial_step_id=pre_stream.initial_step_id,
            initial_step_title=pre_stream.initial_step_title,
            initial_step_items=pre_stream.initial_step_items,
            fallback_commit_workspace_id=workspace_id,
            fallback_commit_created_by_id=user_id,
            fallback_commit_filesystem_mode=(
                filesystem_selection.mode
                if filesystem_selection
                else FilesystemMode.CLOUD
            ),
            fallback_commit_thread_id=chat_id,
            runtime_context=runtime_context,
            content_builder=stream_result.content_builder,
            recover=_recover,
            on_first_event=_on_first_event,
        ):
            yield sse
            # Inject the title update mid-stream as soon as the background
            # task finishes; gated so we emit at most once.
            async for title_sse in maybe_emit_title_update(
                title_task=title_task,
                title_emitted=title_emitted,
                chat_id=chat_id,
                accumulator=accumulator,
                streaming_service=streaming_service,
            ):
                yield title_sse
                title_emitted = True
            # Account for the case where the task completed but produced no
            # title — flip the flag anyway so we don't keep checking it.
            if title_task is not None and title_task.done() and not title_emitted:
                title_emitted = True

        # A successful in-stream recovery may have replaced/cancelled the
        # title task; pick up the current value from the recovery state.
        title_task = recovery_state.title_task

        _perf_log.info(
            "[stream_new_chat] Agent stream completed in %.3fs (chat_id=%s)",
            time.perf_counter() - _t_stream_start,
            chat_id,
        )
        log_system_snapshot("stream_new_chat_END")

        # --- Block 8: Finalize ---

        if stream_result.is_interrupted:
            ot.add_event("chat.interrupted", {"chat.flow": flow})
            if title_task is not None and not title_task.done():
                title_task.cancel()
            for sse in iter_token_usage_frame(
                streaming_service,
                accumulator=accumulator,
                log_label="interrupted new_chat",
            ):
                yield sse
            yield streaming_service.format_finish_step()
            yield streaming_service.format_finish()
            yield streaming_service.format_done()
            return

        async for title_sse in await_pending_title_update(
            title_task=title_task,
            title_emitted=title_emitted,
            chat_id=chat_id,
            accumulator=accumulator,
            streaming_service=streaming_service,
        ):
            yield title_sse

        # Finalize premium credit debit with the actual provider cost reported
        # by LiteLLM, summed across every call in the turn. Mirrors the
        # pre-cost behaviour of "premium turn → all calls count" so free
        # sub-agent calls during a premium turn still contribute to the bill
        # (they're $0 in practice anyway).
        if premium_reservation is not None and user_id:
            await finalize_credit(
                reservation=premium_reservation,
                user_id=user_id,
                accumulator=accumulator,
            )
            premium_reservation = None

        # Emit contextual suggested action pills (Story 21.11 / AC: 1, 4)
        assistant_text = "".join(
            p.get("text", "")
            for p in stream_result.content_builder.parts
            if p.get("type") == "text"
        )
        tool_names = [
            p.get("toolName", "")
            for p in stream_result.content_builder.parts
            if p.get("type") == "tool-call" and p.get("toolName")
        ]

        for sse in iter_suggested_actions_frame(
            streaming_service,
            user_query=user_query,
            assistant_text=assistant_text,
            tool_names=tool_names,
            payload_context=platform_metadata,
        ):
            yield sse

        for sse in iter_token_usage_frame(
            streaming_service, accumulator=accumulator, log_label="normal new_chat"
        ):
            yield sse

        for sse in iter_final_frames(streaming_service):
            yield sse

    except Exception as exc:
        frames, summary = handle_terminal_exception(
            exc,
            flow=flow,
            flow_label="chat",
            log_prefix="stream_new_chat",
            streaming_service=streaming_service,
            request_id=request_id,
            chat_id=chat_id,
            workspace_id=workspace_id,
            user_id=user_id,
            chat_span=chat_span,
        )
        if summary["busy_error_raised"]:
            busy_error_raised = True
        chat_outcome = summary["chat_outcome"]
        chat_error_category = summary["chat_error_category"]
        for sse in frames:
            yield sse

    finally:
        await _run_turn_cleanup(
            chat_id=chat_id,
            workspace_id=workspace_id,
            user_id=user_id,
            session=session,
            stream_result=stream_result,
            accumulator=accumulator,
            premium_reservation=premium_reservation,
            busy_error_raised=busy_error_raised,
            client_id=client_id,
            external_metadata=external_metadata,
            run_id=run_id,
            platform_metadata=platform_metadata,
            research_thread_id=research_thread_id,
        )

        # Break circular refs held by the agent graph, tools, and LLM
        # wrappers so the GC can reclaim them in a single pass.
        agent = llm = connector_service = None
        input_state = stream_result = None
        session = None

        run_gc_pass(log_prefix="stream_new_chat", chat_id=chat_id)
        close_chat_request_span(
            span_cm=chat_span_cm,
            span=chat_span,
            chat_outcome=chat_outcome,
            chat_agent_mode=chat_agent_mode,
            flow=flow,
            chat_error_category=chat_error_category,
            duration_seconds=time.perf_counter() - _t_total,
        )
