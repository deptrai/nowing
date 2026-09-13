"""Stage helpers for ``stream_new_chat`` (split from ``orchestrator.py``).

Each helper corresponds to a numbered block in the orchestrator docstring so
``stream_new_chat`` stays a slim composition layer. Frame-producing stages
are async generators so SSE ordering and flush timing are unchanged; terminal
error exits return a frame list the caller drains before returning.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import logging
import re
import time
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

import anyio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat.main_agent.middleware.busy_mutex import end_turn
from app.agents.chat.runtime.llm_config import AgentConfig as RuntimeAgentConfig
from app.auth.agent_chat import _resolve_agent_config
from app.config import config as app_config
from app.db import (
    AgentConfig as RegistryAgentConfig,
    Workspace,
)
from app.observability import otel as ot
from app.services.new_streaming_service import VercelStreamingService
from app.services.project_context_service import ProjectContextService
from app.tasks.chat.content_builder import AssistantContentBuilder
from app.tasks.chat.streaming.flows.new_chat.auto_pin import resolve_initial_auto_pin
from app.tasks.chat.streaming.flows.new_chat.chat_modes import (
    get_chat_mode_system_prompt,
    is_chat_mode_enabled,
    resolve_chat_mode,
)
from app.tasks.chat.streaming.flows.new_chat.initial_thinking_step import (
    build_initial_thinking_step,
    iter_initial_thinking_step_frame,
)
from app.tasks.chat.streaming.flows.new_chat.llm_capability import (
    check_image_input_capability,
)
from app.tasks.chat.streaming.flows.new_chat.persistence_spawn import (
    await_persist_task,
    spawn_persist_assistant_shell_task,
)
from app.tasks.chat.streaming.flows.new_chat.runtime_context import (
    build_new_chat_runtime_context,
)
from app.tasks.chat.streaming.flows.new_chat.title_gen import (
    spawn_title_task,
)
from app.tasks.chat.streaming.flows.shared.assistant_finalize import (
    finalize_assistant_message,
)
from app.tasks.chat.streaming.flows.shared.finally_cleanup import (
    close_session_and_clear_ai_responding,
)
from app.tasks.chat.streaming.flows.shared.first_frames import (
    iter_final_frames,
    iter_initial_frames,
)
from app.tasks.chat.streaming.flows.shared.llm_bundle import load_llm_bundle
from app.tasks.chat.streaming.flows.shared.premium_quota import (
    CreditReservation,
    needs_credit_quota,
    release_credit,
    reserve_credit,
)
from app.tasks.chat.streaming.shared.stream_result import StreamResult
from app.utils.perf import get_perf_logger

logger = logging.getLogger(__name__)
_perf_log = get_perf_logger()

# AC-18.4: runtime guard for admin-injected system instructions.
_MAX_INSTRUCTIONS_LEN = 8_000


class _AgentNotFoundError(Exception):
    """Raised when a requested agent_id cannot be resolved from the registry."""

    def __init__(self, message: str, error_code: str = "AGENT_NOT_FOUND") -> None:
        self.message = message
        self.error_code = error_code
        self.error_kind = "user_error"
        super().__init__(message)


def _clamp_agent_instructions(instructions: str | None) -> str | None:
    """Enforce AC-18.4 guards: max 8k chars and no Jinja-like markers.

    Only the documented ``{resolved_today}`` placeholder is allowed. Any other
    ``{`` or ``}`` characters are stripped to prevent secret interpolation.
    """
    if instructions is None:
        return None
    s = instructions[:_MAX_INSTRUCTIONS_LEN]
    # Escape literal braces except the documented placeholder.
    placeholder = "\x00resolved_today\x00"
    s = s.replace("{resolved_today}", placeholder)
    s = re.sub(r"[{}]", "", s)
    return s.replace(placeholder, "{resolved_today}")


async def _merge_registry_agent_config(
    session: AsyncSession,
    *,
    agent_config: RuntimeAgentConfig,
    agent_config_override: RegistryAgentConfig | None,
    client_id: str | None,
    agent_id: str | None,
    disabled_tools: list[str] | None = None,
) -> tuple[RuntimeAgentConfig, list[str] | None, list[str] | None]:
    """Load and merge the registry AgentConfig into the runtime config.

    If ``agent_config_override`` is provided it is used directly; otherwise the
    existing ``_resolve_agent_config`` helper is reused for fail-closed 404.
    Returns the merged runtime config plus the effective ``enabled_tools`` and
    ``disabled_tools`` lists for this turn.
    """
    registry = agent_config_override
    if registry is None and agent_id and client_id:
        try:
            registry = await _resolve_agent_config(session, client_id, agent_id)
        except HTTPException as exc:
            raise _AgentNotFoundError(exc.detail) from exc
    if agent_id and not registry:
        raise _AgentNotFoundError("agent not found or inactive")

    effective_enabled: list[str] | None = None
    effective_disabled: list[str] | None = (
        list(disabled_tools) if disabled_tools else None
    )

    if registry:
        # AC-18.4: AgentConfig.system_instructions is *prepended* to the default
        # system prompt; the additive prompt builder keeps the default body.
        if registry.system_instructions is not None:
            agent_config.system_instructions = _clamp_agent_instructions(
                registry.system_instructions
            )
        if registry.citations_enabled is not None:
            agent_config.citations_enabled = registry.citations_enabled
        if registry.model_name:
            agent_config.model_name = registry.model_name

        # Fail-closed: an explicit empty list means "no tools", while None or
        # a missing registry means "no restriction". This matches AD-30's
        # deny-by-default stance for new connectors.
        if registry.enabled_tools is not None:
            effective_enabled = list(registry.enabled_tools)
        if registry.disabled_tools is not None:
            if effective_disabled is None:
                effective_disabled = []
            effective_disabled.extend(registry.disabled_tools)

        logger.info(
            "agent-config merged for client_id=%s agent_id=%s "
            "instructions_len=%d enabled_tools=%s disabled_tools=%s",
            registry.client_id,
            registry.slug,
            len(agent_config.system_instructions or ""),
            effective_enabled,
            effective_disabled,
        )

    return agent_config, effective_enabled, effective_disabled


@dataclasses.dataclass
class _ResolvedModelConfig:
    """Outputs of Block 1 (validation / config) consumed by later stages.

    ``premium_reservation`` is populated even on error exits so the caller's
    ``finally`` can still release a successfully-reserved credit — matching
    the pre-split behaviour where the reservation was a function-scoped local.
    """

    premium_reservation: CreditReservation | None = None
    llm_config_id: int = -1
    llm: Any = None
    agent_config: RuntimeAgentConfig | None = None
    effective_enabled_tools: list[str] | None = None
    effective_disabled_tools: list[str] | None = None
    chat_mode: Any = None


async def _resolve_model_and_config(
    session: AsyncSession,
    *,
    chat_id: int,
    workspace_id: int,
    user_id: str | None,
    llm_config_id: int,
    requested_llm_config_id: int,
    requires_image_input: bool,
    user_image_data_urls: list[str] | None,
    llm: Any | None,
    agent_config: RuntimeAgentConfig | None,
    agent_config_override: RegistryAgentConfig | None,
    client_id: str | None,
    agent_id: str | None,
    disabled_tools: list[str] | None,
    platform_metadata: dict[str, Any] | None,
    chat_thread: Any,
    flow: str,
    request_id: str | None,
    emit_error: Any,
    streaming_service: VercelStreamingService,
) -> tuple[list[str] | None, _ResolvedModelConfig]:
    """Block 1: LLM config + capability + premium reserve + agent config merge.

    Returns ``(error_frames, result)`` when the turn must abort — the caller
    yields the frames verbatim (terminal error + done marker) and returns —
    or ``(None, result)`` on success. ``result.premium_reservation`` is set
    whenever a credit reservation was taken out, including on error exits.
    """
    premium_reservation: CreditReservation | None = None

    _t0 = time.perf_counter()
    pin_result = await resolve_initial_auto_pin(
        session,
        chat_id=chat_id,
        workspace_id=workspace_id,
        user_id=user_id,
        selected_llm_config_id=llm_config_id,
        requires_image_input=requires_image_input,
        requested_llm_config_id=requested_llm_config_id,
    )
    if pin_result.error is not None:
        message, error_code, error_kind = pin_result.error
        return [
            emit_error(message=message, error_kind=error_kind, error_code=error_code),
            streaming_service.format_done(),
        ], _ResolvedModelConfig(premium_reservation=premium_reservation)
    llm_config_id = pin_result.llm_config_id  # type: ignore[assignment]

    if llm is None or agent_config is None:
        llm, agent_config, llm_load_error = await load_llm_bundle(
            session, config_id=llm_config_id, workspace_id=workspace_id
        )
        if llm_load_error:
            return [
                emit_error(
                    message=llm_load_error,
                    error_kind="server_error",
                    error_code="SERVER_ERROR",
                ),
                streaming_service.format_done(),
            ], _ResolvedModelConfig(premium_reservation=premium_reservation)
        _perf_log.info(
            "[stream_new_chat] LLM config loaded in %.3fs (config_id=%s)",
            time.perf_counter() - _t0,
            llm_config_id,
        )

    capability_error = check_image_input_capability(
        user_image_data_urls=user_image_data_urls, agent_config=agent_config
    )
    if capability_error is not None:
        message, error_code = capability_error
        return [
            emit_error(
                message=message,
                error_kind="user_error",
                error_code=error_code,
            ),
            streaming_service.format_done(),
        ], _ResolvedModelConfig(premium_reservation=premium_reservation)

    if needs_credit_quota(agent_config, user_id):
        premium_reservation = await reserve_credit(
            agent_config=agent_config,
            user_id=user_id,  # type: ignore[arg-type]
        )
        if not premium_reservation.allowed:
            ot.add_event("quota.denied", {"quota.code": "PREMIUM_QUOTA_EXHAUSTED"})
            if requested_llm_config_id == 0:
                pin_fallback = await resolve_initial_auto_pin(
                    session,
                    chat_id=chat_id,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    selected_llm_config_id=0,
                    requires_image_input=requires_image_input,
                    requested_llm_config_id=requested_llm_config_id,
                    force_repin_free=True,
                )
                if pin_fallback.error is not None:
                    message, error_code, error_kind = pin_fallback.error
                    return [
                        emit_error(
                            message=message,
                            error_kind=error_kind,
                            error_code=error_code,
                        ),
                        streaming_service.format_done(),
                    ], _ResolvedModelConfig(premium_reservation=premium_reservation)
                llm_config_id = pin_fallback.llm_config_id  # type: ignore[assignment]
                ot.add_event(
                    "model.repin",
                    {
                        "repin.reason": "premium_quota_exhausted",
                        "repin.to_config_id": llm_config_id,
                    },
                )
                llm, agent_config, llm_load_error = await load_llm_bundle(
                    session,
                    config_id=llm_config_id,
                    workspace_id=workspace_id,
                )
                if llm_load_error:
                    return [
                        emit_error(
                            message=llm_load_error,
                            error_kind="server_error",
                            error_code="SERVER_ERROR",
                        ),
                        streaming_service.format_done(),
                    ], _ResolvedModelConfig(premium_reservation=premium_reservation)
                premium_reservation = None
                # Re-route to free fallback logged via the structured
                # stream-error logger so cost/analytics see the auto-switch.
                from app.tasks.chat.streaming.errors.classifier import (
                    log_chat_stream_error,
                )

                log_chat_stream_error(
                    flow=flow,
                    error_kind="premium_quota_exhausted",
                    error_code="PREMIUM_QUOTA_EXHAUSTED",
                    severity="info",
                    is_expected=True,
                    request_id=request_id,
                    thread_id=chat_id,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    message=(
                        "Premium quota exhausted on pinned model; "
                        "auto-fallback switched to a free model"
                    ),
                    extra={
                        "fallback_config_id": llm_config_id,
                        "auto_fallback": True,
                    },
                )
            else:
                return [
                    emit_error(
                        message=(
                            "Buy more credits to continue with this model, or "
                            "switch to a free model"
                        ),
                        error_kind="premium_quota_exhausted",
                        error_code="PREMIUM_QUOTA_EXHAUSTED",
                        severity="info",
                        is_expected=True,
                        extra={
                            "resolved_config_id": llm_config_id,
                            "auto_fallback": False,
                        },
                    ),
                    streaming_service.format_done(),
                ], _ResolvedModelConfig(premium_reservation=premium_reservation)

    # --- Block 1b: AgentConfig merge ---
    try:
        (
            agent_config,
            effective_enabled_tools,
            effective_disabled_tools,
        ) = await _merge_registry_agent_config(
            session,
            agent_config=agent_config,
            agent_config_override=agent_config_override,
            client_id=client_id,
            agent_id=agent_id,
            disabled_tools=disabled_tools,
        )
    except _AgentNotFoundError as exc:
        return [
            emit_error(
                message=exc.message,
                error_kind=exc.error_kind,
                error_code=exc.error_code,
            ),
            streaming_service.format_done(),
        ], _ResolvedModelConfig(premium_reservation=premium_reservation)

    if not llm:
        return [
            emit_error(
                message="Failed to create LLM instance",
                error_kind="server_error",
                error_code="SERVER_ERROR",
            ),
            streaming_service.format_done(),
        ], _ResolvedModelConfig(premium_reservation=premium_reservation)

    # --- Block 1c: Chat mode gating (Story 27.1a, AD-120) ---
    chat_mode = resolve_chat_mode(platform_metadata)
    if chat_mode.mode_id != "default":
        workspace = (
            (
                await session.execute(
                    select(Workspace).where(Workspace.id == workspace_id)
                )
            )
            .scalars()
            .first()
        )
        if not is_chat_mode_enabled(
            chat_mode, workspace=workspace, app_config=app_config
        ):
            return [
                emit_error(
                    message=chat_mode.error_message,
                    error_kind="user_error",
                    error_code=chat_mode.error_code,
                ),
                streaming_service.format_done(),
            ], _ResolvedModelConfig(premium_reservation=premium_reservation)

        if agent_config is None:
            return [
                emit_error(
                    message=f"Failed to create agent config for {chat_mode.label}",
                    error_kind="server_error",
                    error_code="SERVER_ERROR",
                ),
                streaming_service.format_done(),
            ], _ResolvedModelConfig(premium_reservation=premium_reservation)

        if chat_mode.enabled_tools is not None:
            effective_enabled_tools = list(chat_mode.enabled_tools)
        agent_config.system_instructions = get_chat_mode_system_prompt(
            chat_mode, agent_config.system_instructions
        )

    # --- Block 1d: Project context injection (Story 3.18) ---
    if chat_thread is not None and getattr(chat_thread, "project_id", None):
        (
            project,
            pinned_pairs,
        ) = await ProjectContextService.load_project_with_pinned_docs(
            session, chat_thread.project_id, workspace_id
        )
        if project:
            proj_ctx = ProjectContextService.build_project_context(
                project, pinned_pairs, llm=llm
            )
            if proj_ctx:
                base_instructions = agent_config.system_instructions or ""
                agent_config.system_instructions = (
                    f"{proj_ctx}\n\n{base_instructions}".strip()
                    if base_instructions
                    else proj_ctx
                )

    if agent_config.system_instructions:
        agent_config.system_instructions = _clamp_agent_instructions(
            agent_config.system_instructions
        )

    return None, _ResolvedModelConfig(
        llm_config_id=llm_config_id,
        llm=llm,
        agent_config=agent_config,
        premium_reservation=premium_reservation,
        effective_enabled_tools=effective_enabled_tools,
        effective_disabled_tools=effective_disabled_tools,
        chat_mode=chat_mode,
    )


@dataclasses.dataclass
class _PreStreamOutcome:
    """Outputs of Blocks 4-6 the stream loop and finalize stage consume."""

    abort: bool = False
    title_task: asyncio.Task | None = None
    initial_step_id: str | None = None
    initial_step_title: str = ""
    initial_step_items: list[str] | None = None
    runtime_context: Any = None


async def _emit_pre_stream_frames(
    *,
    out: _PreStreamOutcome,
    streaming_service: VercelStreamingService,
    stream_result: StreamResult,
    emit_error: Any,
    chat_id: int,
    user_id: str | None,
    user_query: str,
    user_image_data_urls: list[str] | None,
    platform_metadata: dict[str, Any] | None,
    persist_user_task: asyncio.Task[int | None] | None,
    background_tasks: set[asyncio.Task],
    llm: Any,
    agent_config: RuntimeAgentConfig,
    workspace_id: int,
    mentioned_document_ids: list[int] | None,
    accepted_folder_ids: list[int] | None,
    mentioned_folder_ids: list[int] | None,
    mentioned_connector_ids: list[int] | None,
    mentioned_connectors: list[dict[str, Any]] | None,
    request_id: str | None,
) -> AsyncGenerator[str, None]:
    """Blocks 4-6: first SSE frames, persistence join + message-id frames,
    initial thinking step, title task, runtime context.

    On a persistence failure the helper yields the terminal error + final
    frames, sets ``out.abort`` and returns; the caller must then return.
    """
    # --- Block 4: First SSE frames ---

    for sse in iter_initial_frames(streaming_service, turn_id=stream_result.turn_id):
        yield sse

    # --- Block 5: Persistence join + message-id frames ---

    user_message_id = await await_persist_task(
        persist_user_task,
        chat_id=chat_id,
        turn_id=stream_result.turn_id,
        log_label="persist_user_task",
    )
    if user_message_id is None:
        yield emit_error(
            message="We couldn't save your message. Please try again in a moment.",
            error_kind="server_error",
            error_code="MESSAGE_PERSIST_FAILED",
        )
        for sse in iter_final_frames(streaming_service):
            yield sse
        out.abort = True
        return

    # Emit canonical user message id BEFORE any LLM streaming so the FE
    # can rename its optimistic ``msg-user-XXX`` placeholder to
    # ``msg-{user_message_id}`` and unlock features gated on a real DB id
    # (comments, edit-from-this-message). See B4 in the
    # ``sse-based_message_id_handshake`` plan.
    yield streaming_service.format_data(
        "user-message-id",
        {"message_id": user_message_id, "turn_id": stream_result.turn_id},
    )

    # Spawned only after the user row is confirmed, so a user-persist
    # failure can't orphan an assistant shell on the same turn.
    persist_asst_task = spawn_persist_assistant_shell_task(
        chat_id=chat_id,
        user_id=user_id,
        turn_id=stream_result.turn_id,
        background_tasks=background_tasks,
        platform_metadata=platform_metadata,
    )
    assistant_message_id = await await_persist_task(
        persist_asst_task,
        chat_id=chat_id,
        turn_id=stream_result.turn_id,
        log_label="persist_asst_task",
    )
    if assistant_message_id is None:
        # Genuine DB failure — abort the turn rather than stream into a
        # void. The user row is already persisted so the legacy
        # ghost-thread gate isn't reopened.
        yield emit_error(
            message=("We couldn't initialize the assistant message. Please try again."),
            error_kind="server_error",
            error_code="MESSAGE_PERSIST_FAILED",
        )
        for sse in iter_final_frames(streaming_service):
            yield sse
        out.abort = True
        return

    yield streaming_service.format_data(
        "assistant-message-id",
        {"message_id": assistant_message_id, "turn_id": stream_result.turn_id},
    )

    stream_result.assistant_message_id = assistant_message_id
    stream_result.content_builder = AssistantContentBuilder()

    # --- Block 6: Initial thinking step + title task + runtime context ---

    initial_step = build_initial_thinking_step(
        user_query=user_query,
        user_image_data_urls=user_image_data_urls,
    )
    for sse in iter_initial_thinking_step_frame(
        initial_step,
        streaming_service=streaming_service,
        content_builder=stream_result.content_builder,
    ):
        yield sse

    out.initial_step_id = initial_step.step_id
    out.initial_step_title = initial_step.title
    out.initial_step_items = initial_step.items

    out.title_task = spawn_title_task(
        chat_id=chat_id,
        user_query=user_query,
        user_image_data_urls=user_image_data_urls,
        assistant_message_id=assistant_message_id,
        llm=llm,
        agent_config=agent_config,
    )

    out.runtime_context = build_new_chat_runtime_context(
        workspace_id=workspace_id,
        mentioned_document_ids=mentioned_document_ids,
        accepted_folder_ids=accepted_folder_ids,
        mentioned_folder_ids=mentioned_folder_ids,
        mentioned_connector_ids=mentioned_connector_ids,
        mentioned_connectors=mentioned_connectors,
        request_id=request_id,
        turn_id=stream_result.turn_id,
    )


async def _run_turn_cleanup(
    *,
    chat_id: int,
    workspace_id: int,
    user_id: str | None,
    session: Any,
    stream_result: StreamResult,
    accumulator: Any,
    premium_reservation: CreditReservation | None,
    busy_error_raised: bool,
    client_id: str | None,
    external_metadata: dict[str, Any] | None,
    run_id: UUID | None,
    platform_metadata: dict[str, Any] | None,
    research_thread_id: int | None,
) -> None:
    """Block 10: shielded finally-cleanup (premium release, session close,
    assistant finalize, sandbox persist, busy-mutex release).

    Shield the ENTIRE async cleanup from anyio cancel-scope cancellation.
    Starlette's BaseHTTPMiddleware uses anyio task groups; on client
    disconnect, it cancels the scope with level-triggered cancellation
    — every unshielded ``await`` would raise CancelledError immediately.
    Without this the very first ``await`` (session.rollback) would
    raise, ``except Exception`` wouldn't catch it (CancelledError is a
    BaseException), and the rest of cleanup — including session.close()
    — would never run.
    """
    with anyio.CancelScope(shield=True):
        # Authoritative fallback cleanup for lock/cancel state. Middleware
        # teardown can be skipped on some client-abort paths.
        end_turn(str(chat_id))

        if premium_reservation is not None and user_id:
            await release_credit(reservation=premium_reservation, user_id=user_id)

        await close_session_and_clear_ai_responding(session, chat_id)

        await finalize_assistant_message(
            stream_result=stream_result,
            chat_id=chat_id,
            workspace_id=workspace_id,
            user_id=user_id,
            accumulator=accumulator,
            log_prefix="stream_new_chat",
            client_id=client_id,
            external_metadata=external_metadata,
            run_id=run_id,
            platform_metadata=platform_metadata,
            research_thread_id=research_thread_id,
        )

    # Persist any sandbox-produced files to local storage so they remain
    # downloadable after the Daytona sandbox auto-deletes.
    if stream_result and stream_result.sandbox_files:
        with contextlib.suppress(Exception):
            from app.agents.chat.multi_agent_chat.shared.middleware.filesystem.sandbox import (
                is_sandbox_enabled,
                persist_and_delete_sandbox,
            )

            if is_sandbox_enabled():
                with anyio.CancelScope(shield=True):
                    await persist_and_delete_sandbox(
                        chat_id, stream_result.sandbox_files
                    )

    # ``aafter_agent`` doesn't fire on ``interrupt()`` or early bailout.
    # Skip on ``BusyError`` (caller never acquired the lock).
    if not busy_error_raised:
        with contextlib.suppress(Exception):
            end_turn(str(chat_id))
            _perf_log.info("[stream_new_chat] end_turn cleanup (chat_id=%s)", chat_id)
