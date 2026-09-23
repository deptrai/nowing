"""In-stream provider-429 recovery for ``stream_new_chat`` (Block 7).

Split from ``_stages.py``: the ``recover`` callback handed to
``run_stream_loop`` repins the thread to an eligible alternative config,
reloads the LLM bundle, re-applies registry/chat-mode/project config, and
rebuilds the agent before the user sees any output.
"""

from __future__ import annotations

import asyncio
import dataclasses
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat.shared.filesystem_selection import (
    FilesystemSelection,
)
from app.agents.chat.runtime.llm_config import AgentConfig as RuntimeAgentConfig
from app.auth.context import AuthContext
from app.db import (
    AgentConfig as RegistryAgentConfig,
    ChatVisibility,
)
from app.services.project_context_service import ProjectContextService
from app.tasks.chat.streaming.agent.builder import build_main_agent_for_thread
from app.tasks.chat.streaming.flows.new_chat._stages import (
    _clamp_agent_instructions,
    _merge_registry_agent_config,
)
from app.tasks.chat.streaming.flows.new_chat.chat_modes import (
    get_chat_mode_system_prompt,
)
from app.tasks.chat.streaming.flows.shared.llm_bundle import load_llm_bundle
from app.tasks.chat.streaming.flows.shared.rate_limit_recovery import (
    can_recover_provider_rate_limit,
    log_rate_limit_recovered,
    reroute_to_next_auto_pin,
)
from app.utils.perf import get_perf_logger

_perf_log = get_perf_logger()


@dataclasses.dataclass
class _RateLimitRecoveryState:
    """Mutable turn fields a successful in-stream recovery rewrites."""

    llm_config_id: int
    llm: Any
    agent_config: RuntimeAgentConfig | None
    runtime_rate_limit_recovered: bool
    title_task: asyncio.Task | None
    effective_enabled_tools: list[str] | None
    effective_disabled_tools: list[str] | None


async def _recover_provider_rate_limit(
    exc: BaseException,
    first_event_seen: bool,
    *,
    state: _RateLimitRecoveryState,
    session: AsyncSession,
    requested_llm_config_id: int,
    requires_image_input: bool,
    chat_id: int,
    workspace_id: int,
    user_id: str | None,
    agent_config_override: RegistryAgentConfig | None,
    client_id: str | None,
    agent_id: str | None,
    disabled_tools: list[str] | None,
    chat_mode: Any,
    chat_thread: Any,
    agent_factory: Any,
    connector_service: Any,
    checkpointer: Any,
    visibility: ChatVisibility,
    filesystem_selection: FilesystemSelection | None,
    mentioned_document_ids: list[int] | None,
    auth_context: AuthContext | None,
    research_thread_id: int | None,
    flow: str,
    request_id: str | None,
) -> Any | None:
    """In-stream provider-429 recovery (Block 7 ``recover`` callback).

    Repins the thread to an eligible alternative config, reloads the LLM
    bundle, re-applies registry/chat-mode/project config, and rebuilds the
    agent before the user sees any output. Returns the rebuilt agent, or
    ``None`` to re-raise the original exception.
    """
    if not can_recover_provider_rate_limit(
        exc,
        first_event_seen=first_event_seen,
        runtime_rate_limit_recovered=state.runtime_rate_limit_recovered,
        requested_llm_config_id=requested_llm_config_id,
        current_llm_config_id=state.llm_config_id,
    ):
        return None
    state.runtime_rate_limit_recovered = True
    previous_config_id = state.llm_config_id
    state.llm_config_id = await reroute_to_next_auto_pin(
        session,
        chat_id=chat_id,
        workspace_id=workspace_id,
        user_id=user_id,
        current_llm_config_id=state.llm_config_id,
        requires_image_input=requires_image_input,
    )
    new_llm, new_agent_config, llm_load_err = await load_llm_bundle(
        session, config_id=state.llm_config_id, workspace_id=workspace_id
    )
    if llm_load_err:
        # Re-raise the original so the terminal-error path classifies
        # it correctly (don't swallow as "config load error").
        return None
    state.llm = new_llm
    state.agent_config = new_agent_config

    # Re-apply the registry AgentConfig to the new LLM bundle so
    # custom system instructions/tool allowlists survive the repin.
    (
        state.agent_config,
        state.effective_enabled_tools,
        state.effective_disabled_tools,
    ) = await _merge_registry_agent_config(
        session,
        agent_config=state.agent_config,
        agent_config_override=agent_config_override,
        client_id=client_id,
        agent_id=agent_id,
        disabled_tools=disabled_tools,
    )

    # Re-apply the active chat-mode allowlist (and prompt) so a
    # web-builder/presentation-studio thread is not downgraded to the
    # registry's default tool set after a runtime rate-limit recovery.
    if chat_mode.mode_id != "default":
        if chat_mode.enabled_tools is not None:
            state.effective_enabled_tools = list(chat_mode.enabled_tools)
        state.agent_config.system_instructions = get_chat_mode_system_prompt(
            chat_mode, state.agent_config.system_instructions
        )

    # Re-apply project context if linked (Story 3.18)
    if chat_thread is not None and getattr(chat_thread, "project_id", None):
        (
            project,
            pinned_pairs,
        ) = await ProjectContextService.load_project_with_pinned_docs(
            session, chat_thread.project_id, workspace_id
        )
        if project:
            proj_ctx = ProjectContextService.build_project_context(
                project, pinned_pairs, llm=state.llm
            )
            if proj_ctx:
                base_instructions = state.agent_config.system_instructions or ""
                state.agent_config.system_instructions = (
                    f"{proj_ctx}\n\n{base_instructions}".strip()
                    if base_instructions
                    else proj_ctx
                )

    if state.agent_config.system_instructions:
        state.agent_config.system_instructions = _clamp_agent_instructions(
            state.agent_config.system_instructions
        )

    # Title gen used the initial llm object. After a runtime repin we
    # keep the stream focused on response recovery and skip title gen
    # for this turn.
    if state.title_task is not None and not state.title_task.done():
        state.title_task.cancel()
    state.title_task = None

    _t_rebuild = time.perf_counter()
    new_agent = await build_main_agent_for_thread(
        agent_factory,
        llm=state.llm,
        workspace_id=workspace_id,
        db_session=session,
        connector_service=connector_service,
        checkpointer=checkpointer,
        user_id=user_id,
        thread_id=chat_id,
        agent_config=state.agent_config,
        thread_visibility=visibility,
        filesystem_selection=filesystem_selection,
        enabled_tools=state.effective_enabled_tools,
        disabled_tools=state.effective_disabled_tools,
        mentioned_document_ids=mentioned_document_ids,
        auth_context=auth_context,
        research_thread_id=research_thread_id,
        client_id=client_id,
    )
    _perf_log.info(
        "[stream_new_chat] Runtime rate-limit recovery repinned "
        "config_id=%s -> %s and rebuilt agent in %.3fs",
        previous_config_id,
        state.llm_config_id,
        time.perf_counter() - _t_rebuild,
    )
    log_rate_limit_recovered(
        flow=flow,
        request_id=request_id,
        chat_id=chat_id,
        workspace_id=workspace_id,
        user_id=user_id,
        previous_config_id=previous_config_id,
        new_config_id=state.llm_config_id,
    )
    return new_agent
