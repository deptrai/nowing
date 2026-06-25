"""
Streaming task for the new Nowing deep agent chat.

This module streams responses from the deep agent using the Vercel AI SDK
Data Stream Protocol (SSE format).

Supports loading LLM configurations from:
- YAML files (negative IDs for global configs)
- NewLLMConfig database table (positive IDs for user-created configs with prompt settings)
"""

import ast
import asyncio
import contextlib
import re
import gc
import json
import logging
import os
import re
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import anyio
from langchain_core.messages import HumanMessage
from sqlalchemy import func
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.agents.new_chat.chat_deepagent import (
    _rate_limit_state,
    _stream_writer_var,
    create_nowing_deep_agent,
)

# LangGraph step budget for the main agent. Under rate-limit pacing each step
# can take 10-60s (gate spacing + sub-agent retries), so 80 was insufficient for
# 6-agent comprehensive queries. Bump default to 200 and allow env override.
_AGENT_RECURSION_LIMIT = int(os.getenv("AGENT_RECURSION_LIMIT", "200"))
from app.agents.new_chat.checkpointer import get_checkpointer
from app.agents.new_chat.llm_config import (
    AgentConfig,
    create_chat_litellm_from_agent_config,
    create_chat_litellm_from_config,
    load_agent_config,
    load_llm_config_from_yaml,
)
from app.agents.new_chat.memory_extraction import (
    extract_and_save_memory,
    extract_and_save_team_memory,
)
from app.config import config as app_config
from app.db import (
    ChatVisibility,
    NewChatMessage,
    NewChatThread,
    Report,
    SearchSourceConnectorType,
    NowingDocsDocument,
    async_session_maker,
    shielded_async_session,
)
from app.prompts import TITLE_GENERATION_PROMPT_TEMPLATE
from app.services.chat_session_state_service import (
    clear_ai_responding,
    set_ai_responding,
)
from app.services.connector_service import ConnectorService
from app.services.citation_harvester import harvest_citations
from app.services.new_streaming_service import VercelStreamingService
from app.utils.content_utils import bootstrap_history_from_db
from app.utils.perf import get_perf_logger, log_system_snapshot, trim_native_heap

_perf_log = get_perf_logger()


async def _with_heartbeat(
    generator: AsyncGenerator[str, None],
    timeout: float = 15.0,
) -> AsyncGenerator[str, None]:
    """
    Wrap an async generator to yield SSE heartbeats if idle for timeout seconds.
    Uses a robust task-based approach to avoid cancelling the underlying generator
    iterator during idle periods.

    Story 11.7 T2 / round-2 review: cancellation safety. When the SSE consumer
    disconnects, Starlette cancels this generator. Two-phase cleanup:
      1. Cancel the in-flight `next_task` (which is awaiting the inner
         generator's next step) and let `CancelledError` propagate to its
         await point.
      2. Explicitly call `generator.aclose()`, which throws `GeneratorExit`
         into the inner generator at its latest await — this is the documented
         Python protocol for graceful generator cleanup. Inner generator's
         `try/finally` (DB sessions, LangGraph checkpoints, Redis pubsub) gets
         to release resources cleanly.
    Both cleanup steps are wrapped with `asyncio.shield` so an outer cancel
    of the heartbeat wrapper itself doesn't interrupt the inner cleanup mid-
    write. We absorb expected exceptions (`CancelledError`, `StopAsyncIteration`,
    `GeneratorExit`, plus `RuntimeError` from "generator already closed").
    """
    it = generator.__aiter__()
    # Use anext() if available (Python 3.10+), else it.__anext__()
    try:
        next_task = asyncio.create_task(anext(it))
    except NameError:
        next_task = asyncio.create_task(it.__anext__())

    try:
        while True:
            done, pending = await asyncio.wait(
                [next_task], timeout=timeout, return_when=asyncio.FIRST_COMPLETED
            )
            if next_task in done:
                try:
                    result = next_task.result()
                    yield result
                    try:
                        next_task = asyncio.create_task(anext(it))
                    except NameError:
                        next_task = asyncio.create_task(it.__anext__())
                except StopAsyncIteration:
                    break
            else:
                yield VercelStreamingService.format_heartbeat()
    finally:
        # Phase 1: cancel the in-flight next-step task. The shield prevents an
        # outer cancel of the heartbeat wrapper from racing this drain.
        if not next_task.done():
            next_task.cancel()
            with contextlib.suppress(
                asyncio.CancelledError, StopAsyncIteration, GeneratorExit
            ):
                await asyncio.shield(_drain(next_task))

        # Phase 2: call aclose() so the inner generator's `finally` blocks
        # run with a deterministic `GeneratorExit` rather than a half-applied
        # CancelledError. This is what releases DB sessions / LangGraph
        # checkpoint state / Redis pubsub subscriptions in the inner code
        # path. Suppress the standard cleanup exceptions; a misbehaving
        # generator that re-raises is logged but never propagated past the
        # wrapper boundary.
        try:
            await asyncio.shield(generator.aclose())
        except (asyncio.CancelledError, StopAsyncIteration, GeneratorExit, RuntimeError):
            pass
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "_with_heartbeat: inner generator raised during aclose(): %s", exc
            )


async def _drain(task: asyncio.Task) -> None:
    """Helper: await a task that's already been cancelled, swallow its result."""
    try:
        await task
    except (asyncio.CancelledError, StopAsyncIteration, GeneratorExit):
        pass


def format_mentioned_nowing_docs_as_context(
    documents: list[NowingDocsDocument],
) -> str:
    """Format mentioned Nowing documentation as context for the agent."""
    if not documents:
        return ""

    context_parts = ["<mentioned_nowing_docs>"]
    context_parts.append(
        "The user has explicitly mentioned the following Nowing documentation pages. "
        "These are official documentation about how to use Nowing and should be used to answer questions about the application. "
        "Use [citation:CHUNK_ID] format for citations (e.g., [citation:doc-123])."
    )

    for doc in documents:
        metadata_json = json.dumps({"source": doc.source}, ensure_ascii=False)

        context_parts.append("<document>")
        context_parts.append("<document_metadata>")
        context_parts.append(f"  <document_id>doc-{doc.id}</document_id>")
        context_parts.append("  <document_type>NOWING_DOCS</document_type>")
        context_parts.append(f"  <title><![CDATA[{doc.title}]]></title>")
        context_parts.append(f"  <url><![CDATA[{doc.source}]]></url>")
        context_parts.append(
            f"  <metadata_json><![CDATA[{metadata_json}]]></metadata_json>"
        )
        context_parts.append("</document_metadata>")
        context_parts.append("")
        context_parts.append("<document_content>")

        if hasattr(doc, "chunks") and doc.chunks:
            for chunk in doc.chunks:
                context_parts.append(
                    f"  <chunk id='doc-{chunk.id}'><![CDATA[{chunk.content}]]></chunk>"
                )
        else:
            context_parts.append(
                f"  <chunk id='doc-0'><![CDATA[{doc.content}]]></chunk>"
            )

        context_parts.append("</document_content>")
        context_parts.append("</document>")
        context_parts.append("")

    context_parts.append("</mentioned_nowing_docs>")

    return "\n".join(context_parts)


def extract_todos_from_deepagents(command_output) -> dict:
    """
    Extract todos from deepagents' TodoListMiddleware Command output.

    deepagents returns a Command object with:
    - Command.update['todos'] = [{'content': '...', 'status': '...'}]

    Returns the todos directly (no transformation needed - UI matches deepagents format).
    """
    todos_data = []
    if hasattr(command_output, "update"):
        # It's a Command object from deepagents
        update = command_output.update
        todos_data = update.get("todos", [])
    elif isinstance(command_output, dict):
        # Already a dict - check if it has todos directly or in update
        if "todos" in command_output:
            todos_data = command_output.get("todos", [])
        elif "update" in command_output and isinstance(command_output["update"], dict):
            todos_data = command_output["update"].get("todos", [])

    return {"todos": todos_data}


async def _extract_partial_analysis(agent: Any, config: dict[str, Any]) -> dict | None:
    """Read checkpointer state and format any completed sub-agent outputs as
    a graceful partial response.

    Used by the stream error handler when a rate-limit error kills synthesis
    but partial ToolMessages from completed sub-agents exist in state. Returns
    None if no completed work can be salvaged; caller falls back to a normal
    error yield.

    Returns:
        dict with keys `message` (markdown), `completed_count`, `errored_count`.
    """
    from langchain_core.messages import ToolMessage

    try:
        state = await agent.aget_state(config)
    except Exception:
        return None
    if not state or not getattr(state, "values", None):
        return None
    messages = state.values.get("messages", [])
    if not messages:
        return None

    # Map tool_call_id → args for prior task() tool_calls (AIMessage history)
    tool_calls_by_id: dict[str, dict] = {}
    for m in messages:
        tcs = getattr(m, "tool_calls", None)
        if tcs is None and isinstance(m, dict):
            tcs = m.get("tool_calls")
        if not tcs:
            continue
        for tc in tcs:
            tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
            tc_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
            tc_args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
            if tc_id and tc_name == "task":
                tool_calls_by_id[tc_id] = tc_args or {}

    completed: list[tuple[str, str]] = []
    errored: list[str] = []
    for m in messages:
        if not isinstance(m, ToolMessage):
            continue
        args = tool_calls_by_id.get(m.tool_call_id)
        if not args:
            continue
        agent_name = args.get("subagent_type", "unknown")
        content = m.content if isinstance(m.content, str) else str(m.content)
        if getattr(m, "status", None) == "error":
            errored.append(agent_name)
        else:
            completed.append((agent_name, content))

    if not completed and not errored:
        return None

    parts = [
        "⚠️ **Analysis limited by LLM provider rate limits** — "
        "below are the partial results collected so far:\n",
    ]
    for name, content in completed:
        snippet = content.strip()
        if len(snippet) > 2000:
            snippet = snippet[:2000] + "\n\n*(trimmed)*"
        parts.append(f"\n### ✅ {name}\n{snippet}\n")
    if errored:
        parts.append(
            f"\n### ❌ Incomplete\n"
            f"{', '.join(errored)} — provider rate limit exhausted.\n"
        )
    parts.append(
        "\n---\n*Retry your question in 1-2 minutes for a complete analysis.*"
    )

    return {
        "message": "".join(parts),
        "completed_count": len(completed),
        "errored_count": len(errored),
    }


@dataclass
class StreamResult:
    accumulated_text: str = ""
    is_interrupted: bool = False
    interrupt_value: dict[str, Any] | None = None
    sandbox_files: list[str] = field(default_factory=list)  # unused, kept for compat
    agent_called_update_memory: bool = False
    total_tokens_used: int = 0  # Accumulated across all LLM calls in the stream


async def _stream_agent_events(
    agent: Any,
    config: dict[str, Any],
    input_data: Any,
    streaming_service: VercelStreamingService,
    result: StreamResult,
    step_prefix: str = "thinking",
    initial_step_id: str | None = None,
    initial_step_title: str = "",
    initial_step_items: list[str] | None = None,
    user_query: str = "",
) -> AsyncGenerator[str, None]:
    """Shared async generator that streams and formats astream_events from the agent.

    Yields SSE-formatted strings. After exhausting, inspect the ``result``
    object for accumulated_text and interrupt state.

    Args:
        agent: The compiled LangGraph agent.
        config: LangGraph config dict (must include configurable.thread_id).
        input_data: The input to pass to agent.astream_events (dict or Command).
        streaming_service: VercelStreamingService instance for formatting events.
        result: Mutable StreamResult populated with accumulated_text / interrupt info.
        step_prefix: Prefix for thinking step IDs (e.g. "thinking" or "thinking-resume").
        initial_step_id: If set, the helper inherits an already-active thinking step.
        initial_step_title: Title of the inherited thinking step.
        initial_step_items: Items of the inherited thinking step.

    Yields:
        SSE-formatted strings for each event.
    """
    accumulated_text = ""
    current_text_id: str | None = None
    thinking_step_counter = 1 if initial_step_id else 0
    tool_step_ids: dict[str, str] = {}
    completed_step_ids: set[str] = set()
    last_active_step_id: str | None = initial_step_id
    last_active_step_title: str = initial_step_title
    last_active_step_items: list[str] = initial_step_items or []
    just_finished_tool: bool = False
    active_tool_depth: int = 0  # Track nesting: >0 means we're inside a tool
    called_update_memory: bool = False
    _tool_inputs_by_run_id: dict[str, Any] = {}
    _token_meta_emitted: bool = False

    # AC13: writer queue for orchestra events emitted from contexts that can't
    # call dispatch_custom_event (rate bucket, monkey-patched LiteLLM gates).
    # Drained on every event yield + at the end of the stream.
    _orchestra_writer_queue: list[str] = []
    _session_id = str(config.get("configurable", {}).get("thread_id", ""))

    # AC1: bare-type events (orchestra-spawn/done/fail/cancel/complete/update) emit
    # at root level; data-* events (orchestra-narration/source-fetched/etc.) emit
    # under format_data. Writer routes by event_type prefix.
    _BARE_TYPE_EVENTS = frozenset(
        ("orchestra-spawn", "orchestra-update", "orchestra-done", "orchestra-fail",
         "orchestra-cancel", "orchestra-complete")
    )

    def _orchestra_writer(event_type: str, data: dict[str, Any]) -> None:
        # Stamp sessionId server-side if BE didn't provide one.
        if "sessionId" not in data:
            data = {**data, "sessionId": _session_id}
        if event_type in _BARE_TYPE_EVENTS:
            _orchestra_writer_queue.append(
                streaming_service._format_sse({"type": event_type, "data": data})
            )
        else:
            _orchestra_writer_queue.append(streaming_service.format_data(event_type, data))

    _writer_token = _stream_writer_var.set(_orchestra_writer)

    async def _drain_writer_queue() -> AsyncGenerator[str, None]:
        """Drain queued orchestra events one-by-one as SSE chunks."""
        while _orchestra_writer_queue:
            yield _orchestra_writer_queue.pop(0)

    def _release_writer() -> None:
        """V2-P1: idempotent reset, called from both happy + exception paths."""
        try:
            _stream_writer_var.reset(_writer_token)
        except (ValueError, LookupError):
            # Already reset, or token from different context — best effort.
            pass

    def next_thinking_step_id() -> str:
        nonlocal thinking_step_counter
        thinking_step_counter += 1
        return f"{step_prefix}-{thinking_step_counter}"

    def complete_current_step() -> str | None:
        nonlocal last_active_step_id
        if last_active_step_id and last_active_step_id not in completed_step_ids:
            completed_step_ids.add(last_active_step_id)
            event = streaming_service.format_thinking_step(
                step_id=last_active_step_id,
                title=last_active_step_title,
                status="completed",
                items=last_active_step_items if last_active_step_items else None,
            )
            last_active_step_id = None
            return event
        return None

    # V2-P1: try/finally guarantees writer ContextVar is reset even when
    # astream_events raises (rate-limit, cancellation, OOM). Without this,
    # the next stream in the same asyncio task inherits a stale closure.
    _stream_failed = False
    try:
      async for event in agent.astream_events(input_data, config=config, version="v2"):
        # Drain any writer-queued orchestra events first (rate-gate-wait, etc).
        while _orchestra_writer_queue:
            yield _orchestra_writer_queue.pop(0)

        event_type = event.get("event", "")

        if event_type == "on_chat_model_stream":
            if active_tool_depth > 0:
                continue  # Suppress inner-tool LLM tokens from leaking into chat
            if "nowing:internal" in event.get("tags", []):
                continue  # Suppress middleware-internal LLM tokens (e.g. KB search classification)
            chunk = event.get("data", {}).get("chunk")
            if chunk and hasattr(chunk, "content"):
                content = chunk.content
                if content and isinstance(content, str):
                    if current_text_id is None:
                        completion_event = complete_current_step()
                        if completion_event:
                            yield completion_event
                        if just_finished_tool:
                            last_active_step_id = None
                            last_active_step_title = ""
                            last_active_step_items = []
                            just_finished_tool = False
                        current_text_id = streaming_service.generate_text_id()
                        yield streaming_service.format_text_start(current_text_id)
                    yield streaming_service.format_text_delta(current_text_id, content)
                    accumulated_text += content

        elif event_type == "on_tool_start":
            active_tool_depth += 1
            tool_name = event.get("name", "unknown_tool")
            run_id = event.get("run_id", "")
            tool_input = event.get("data", {}).get("input", {})

            if current_text_id is not None:
                yield streaming_service.format_text_end(current_text_id)
                current_text_id = None

            if last_active_step_title != "Synthesizing response":
                completion_event = complete_current_step()
                if completion_event:
                    yield completion_event

            just_finished_tool = False
            tool_step_id = next_thinking_step_id()
            tool_step_ids[run_id] = tool_step_id
            last_active_step_id = tool_step_id

            # Capture input for tools we need to correlate at on_tool_end
            if tool_name == "get_coingecko_token_info" and isinstance(tool_input, dict):
                _tool_inputs_by_run_id[run_id] = tool_input

            if tool_name == "ls":
                ls_path = (
                    tool_input.get("path", "/")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                last_active_step_title = "Listing files"
                last_active_step_items = [ls_path]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Listing files",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "read_file":
                fp = (
                    tool_input.get("file_path", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                display_fp = fp if len(fp) <= 80 else "…" + fp[-77:]
                last_active_step_title = "Reading file"
                last_active_step_items = [display_fp]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Reading file",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "write_file":
                fp = (
                    tool_input.get("file_path", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                display_fp = fp if len(fp) <= 80 else "…" + fp[-77:]
                last_active_step_title = "Writing file"
                last_active_step_items = [display_fp]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Writing file",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "edit_file":
                fp = (
                    tool_input.get("file_path", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                display_fp = fp if len(fp) <= 80 else "…" + fp[-77:]
                last_active_step_title = "Editing file"
                last_active_step_items = [display_fp]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Editing file",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "glob":
                pat = (
                    tool_input.get("pattern", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                base_path = (
                    tool_input.get("path", "/") if isinstance(tool_input, dict) else "/"
                )
                last_active_step_title = "Searching files"
                last_active_step_items = [f"{pat} in {base_path}"]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Searching files",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "grep":
                pat = (
                    tool_input.get("pattern", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                grep_path = (
                    tool_input.get("path", "") if isinstance(tool_input, dict) else ""
                )
                display_pat = pat[:60] + ("…" if len(pat) > 60 else "")
                last_active_step_title = "Searching content"
                last_active_step_items = [
                    f'"{display_pat}"' + (f" in {grep_path}" if grep_path else "")
                ]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Searching content",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "save_document":
                doc_title = (
                    tool_input.get("title", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                display_title = doc_title[:60] + ("…" if len(doc_title) > 60 else "")
                last_active_step_title = "Saving document"
                last_active_step_items = [display_title]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Saving document",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "generate_image":
                prompt = (
                    tool_input.get("prompt", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                last_active_step_title = "Generating image"
                last_active_step_items = [
                    f"Prompt: {prompt[:80]}{'...' if len(prompt) > 80 else ''}"
                ]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Generating image",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "scrape_webpage":
                url = (
                    tool_input.get("url", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                last_active_step_title = "Scraping webpage"
                last_active_step_items = [
                    f"URL: {url[:80]}{'...' if len(url) > 80 else ''}"
                ]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Scraping webpage",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "generate_podcast":
                podcast_title = (
                    tool_input.get("podcast_title", "Nowing Podcast")
                    if isinstance(tool_input, dict)
                    else "Nowing Podcast"
                )
                content_len = len(
                    tool_input.get("source_content", "")
                    if isinstance(tool_input, dict)
                    else ""
                )
                last_active_step_title = "Generating podcast"
                last_active_step_items = [
                    f"Title: {podcast_title}",
                    f"Content: {content_len:,} characters",
                    "Preparing audio generation...",
                ]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Generating podcast",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "generate_report":
                report_topic = (
                    tool_input.get("topic", "Report")
                    if isinstance(tool_input, dict)
                    else "Report"
                )
                is_revision = bool(
                    isinstance(tool_input, dict) and tool_input.get("parent_report_id")
                )
                step_title = "Revising report" if is_revision else "Generating report"
                last_active_step_title = step_title
                last_active_step_items = [
                    f"Topic: {report_topic}",
                    "Analyzing source content...",
                ]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title=step_title,
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "chainlens_deep_research":
                raw_query = (
                    tool_input.get("query")
                    if isinstance(tool_input, dict)
                    else None
                )
                query = raw_query if isinstance(raw_query, str) else ""
                query_preview = query[:80] + ("…" if len(query) > 80 else "")
                last_active_step_title = "Deep researching"
                last_active_step_items = (
                    [f"Query: {query_preview}"] if query_preview else []
                )
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Deep researching",
                    status="in_progress",
                    items=last_active_step_items,
                )
            elif tool_name == "execute":
                cmd = (
                    tool_input.get("command", "")
                    if isinstance(tool_input, dict)
                    else str(tool_input)
                )
                display_cmd = cmd[:80] + ("…" if len(cmd) > 80 else "")
                last_active_step_title = "Running command"
                last_active_step_items = [f"$ {display_cmd}"]
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title="Running command",
                    status="in_progress",
                    items=last_active_step_items,
                )
            else:
                last_active_step_title = f"Using {tool_name.replace('_', ' ')}"
                last_active_step_items = []
                yield streaming_service.format_thinking_step(
                    step_id=tool_step_id,
                    title=last_active_step_title,
                    status="in_progress",
                )

            tool_call_id = (
                f"call_{run_id[:32]}"
                if run_id
                else streaming_service.generate_tool_call_id()
            )
            yield streaming_service.format_tool_input_start(tool_call_id, tool_name)
            # Sanitize tool_input: strip runtime-injected non-serializable
            # values (e.g. LangChain ToolRuntime) before sending over SSE.
            if isinstance(tool_input, dict):
                _safe_input: dict[str, Any] = {}
                for _k, _v in tool_input.items():
                    try:
                        json.dumps(_v)
                        _safe_input[_k] = _v
                    except (TypeError, ValueError, OverflowError):
                        pass
            else:
                _safe_input = {"input": tool_input}
            yield streaming_service.format_tool_input_available(
                tool_call_id,
                tool_name,
                _safe_input,
            )

        elif event_type == "on_tool_end":
            active_tool_depth = max(0, active_tool_depth - 1)
            run_id = event.get("run_id", "")
            tool_name = event.get("name", "unknown_tool")
            raw_output = event.get("data", {}).get("output", "")

            if tool_name == "update_memory":
                called_update_memory = True

            if hasattr(raw_output, "content"):
                content = raw_output.content
                if isinstance(content, str):
                    try:
                        tool_output = json.loads(content)
                    except (json.JSONDecodeError, TypeError):
                        tool_output = {"result": content}
                elif isinstance(content, dict):
                    tool_output = content
                else:
                    tool_output = {"result": str(content)}
            elif isinstance(raw_output, dict):
                tool_output = raw_output
            else:
                tool_output = {"result": str(raw_output) if raw_output else "completed"}

            tool_call_id = f"call_{run_id[:32]}" if run_id else "call_unknown"
            original_step_id = tool_step_ids.get(
                run_id, f"{step_prefix}-unknown-{run_id[:8]}"
            )
            completed_step_ids.add(original_step_id)

            if tool_name == "read_file":
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Reading file",
                    status="completed",
                    items=last_active_step_items,
                )
            elif tool_name == "write_file":
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Writing file",
                    status="completed",
                    items=last_active_step_items,
                )
            elif tool_name == "edit_file":
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Editing file",
                    status="completed",
                    items=last_active_step_items,
                )
            elif tool_name == "glob":
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Searching files",
                    status="completed",
                    items=last_active_step_items,
                )
            elif tool_name == "grep":
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Searching content",
                    status="completed",
                    items=last_active_step_items,
                )
            elif tool_name == "save_document":
                result_str = (
                    tool_output.get("result", "")
                    if isinstance(tool_output, dict)
                    else str(tool_output)
                )
                is_error = "Error" in result_str
                completed_items = [
                    *last_active_step_items,
                    result_str[:80] if is_error else "Saved to knowledge base",
                ]
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Saving document",
                    status="completed",
                    items=completed_items,
                )
            elif tool_name == "generate_image":
                if isinstance(tool_output, dict) and not tool_output.get("error"):
                    completed_items = [
                        *last_active_step_items,
                        "Image generated successfully",
                    ]
                else:
                    error_msg = (
                        tool_output.get("error", "Generation failed")
                        if isinstance(tool_output, dict)
                        else "Generation failed"
                    )
                    completed_items = [*last_active_step_items, f"Error: {error_msg}"]
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Generating image",
                    status="completed",
                    items=completed_items,
                )
            elif tool_name == "scrape_webpage":
                if isinstance(tool_output, dict):
                    title = tool_output.get("title", "Webpage")
                    word_count = tool_output.get("word_count", 0)
                    has_error = "error" in tool_output
                    if has_error:
                        completed_items = [
                            *last_active_step_items,
                            f"Error: {tool_output.get('error', 'Failed to scrape')[:50]}",
                        ]
                    else:
                        completed_items = [
                            *last_active_step_items,
                            f"Title: {title[:50]}{'...' if len(title) > 50 else ''}",
                            f"Extracted: {word_count:,} words",
                        ]
                else:
                    completed_items = [*last_active_step_items, "Content extracted"]
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Scraping webpage",
                    status="completed",
                    items=completed_items,
                )
            elif tool_name == "generate_podcast":
                podcast_status = (
                    tool_output.get("status", "unknown")
                    if isinstance(tool_output, dict)
                    else "unknown"
                )
                podcast_title = (
                    tool_output.get("title", "Podcast")
                    if isinstance(tool_output, dict)
                    else "Podcast"
                )
                if podcast_status == "processing":
                    completed_items = [
                        f"Title: {podcast_title}",
                        "Audio generation started",
                        "Processing in background...",
                    ]
                elif podcast_status == "already_generating":
                    completed_items = [
                        f"Title: {podcast_title}",
                        "Podcast already in progress",
                        "Please wait for it to complete",
                    ]
                elif podcast_status == "error":
                    error_msg = (
                        tool_output.get("error", "Unknown error")
                        if isinstance(tool_output, dict)
                        else "Unknown error"
                    )
                    completed_items = [
                        f"Title: {podcast_title}",
                        f"Error: {error_msg[:50]}",
                    ]
                else:
                    completed_items = last_active_step_items
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Generating podcast",
                    status="completed",
                    items=completed_items,
                )
            elif tool_name == "generate_video_presentation":
                vp_status = (
                    tool_output.get("status", "unknown")
                    if isinstance(tool_output, dict)
                    else "unknown"
                )
                vp_title = (
                    tool_output.get("title", "Presentation")
                    if isinstance(tool_output, dict)
                    else "Presentation"
                )
                if vp_status in ("pending", "generating"):
                    completed_items = [
                        f"Title: {vp_title}",
                        "Presentation generation started",
                        "Processing in background...",
                    ]
                elif vp_status == "failed":
                    error_msg = (
                        tool_output.get("error", "Unknown error")
                        if isinstance(tool_output, dict)
                        else "Unknown error"
                    )
                    completed_items = [
                        f"Title: {vp_title}",
                        f"Error: {error_msg[:50]}",
                    ]
                else:
                    completed_items = last_active_step_items
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Generating video presentation",
                    status="completed",
                    items=completed_items,
                )
            elif tool_name == "generate_report":
                report_status = (
                    tool_output.get("status", "unknown")
                    if isinstance(tool_output, dict)
                    else "unknown"
                )
                report_title = (
                    tool_output.get("title", "Report")
                    if isinstance(tool_output, dict)
                    else "Report"
                )
                word_count = (
                    tool_output.get("word_count", 0)
                    if isinstance(tool_output, dict)
                    else 0
                )
                is_revision = (
                    tool_output.get("is_revision", False)
                    if isinstance(tool_output, dict)
                    else False
                )
                step_title = "Revising report" if is_revision else "Generating report"

                if report_status == "ready":
                    completed_items = [
                        f"Topic: {report_title}",
                        f"{word_count:,} words",
                        "Report ready",
                    ]
                elif report_status == "failed":
                    error_msg = (
                        tool_output.get("error", "Unknown error")
                        if isinstance(tool_output, dict)
                        else "Unknown error"
                    )
                    completed_items = [
                        f"Topic: {report_title}",
                        f"Error: {error_msg[:50]}",
                    ]
                else:
                    completed_items = last_active_step_items

                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title=step_title,
                    status="completed",
                    items=completed_items,
                )
            elif tool_name == "chainlens_deep_research":
                # Use pre-parsed tool_output (handles ToolMessage.content JSON string)
                # CRITICAL: title stays "Deep researching" for BOTH success and fallback
                # (FR25 silent fallback — user never sees "fallback" or vendor name)
                sources_count = 0
                if isinstance(tool_output, dict):
                    sources_list = tool_output.get("sources", [])
                    if isinstance(sources_list, list):
                        sources_count = len(sources_list)
                completion_items = (
                    [f"Sources found: {sources_count}"]
                    if sources_count > 0
                    else ["Research completed"]
                )
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Deep researching",
                    status="completed",
                    items=completion_items,
                )
                last_active_step_title = "Deep researching"
                last_active_step_items = completion_items
            elif tool_name == "execute":
                raw_text = (
                    tool_output.get("result", "")
                    if isinstance(tool_output, dict)
                    else str(tool_output)
                )
                m = re.match(r"^Exit code:\s*(\d+)", raw_text)
                exit_code_val = int(m.group(1)) if m else None
                if exit_code_val is not None and exit_code_val == 0:
                    completed_items = [
                        *last_active_step_items,
                        "Completed successfully",
                    ]
                elif exit_code_val is not None:
                    completed_items = [
                        *last_active_step_items,
                        f"Exit code: {exit_code_val}",
                    ]
                else:
                    completed_items = [*last_active_step_items, "Finished"]
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Running command",
                    status="completed",
                    items=completed_items,
                )
            elif tool_name == "get_coingecko_token_info":
                token_symbol = (
                    tool_output.get("symbol", "").upper()
                    if isinstance(tool_output, dict)
                    else ""
                )
                token_name = (
                    tool_output.get("name", "")
                    if isinstance(tool_output, dict)
                    else ""
                )
                saved_input = _tool_inputs_by_run_id.pop(run_id, {})
                coingecko_id = (
                    saved_input.get("coin_id", "")
                    if isinstance(saved_input, dict)
                    else ""
                )
                completed_items = [token_name or token_symbol or "Token info fetched"]
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Fetching token info",
                    status="completed",
                    items=completed_items,
                )
                if token_symbol and not _token_meta_emitted:
                    _token_meta_emitted = True
                    yield streaming_service.format_data(
                        "token-meta",
                        {
                            "token_symbol": token_symbol,
                            "token_name": token_name,
                            "coingecko_id": coingecko_id,
                        },
                    )
            elif tool_name == "ls":
                if isinstance(tool_output, dict):
                    ls_output = tool_output.get("result", "")
                elif isinstance(tool_output, str):
                    ls_output = tool_output
                else:
                    ls_output = str(tool_output) if tool_output else ""
                file_names: list[str] = []
                if ls_output:
                    paths: list[str] = []
                    try:
                        parsed = ast.literal_eval(ls_output)
                        if isinstance(parsed, list):
                            paths = [str(p) for p in parsed]
                    except (ValueError, SyntaxError):
                        paths = [
                            line.strip()
                            for line in ls_output.strip().split("\n")
                            if line.strip()
                        ]
                    for p in paths:
                        name = p.rstrip("/").split("/")[-1]
                        if name and len(name) <= 40:
                            file_names.append(name)
                        elif name:
                            file_names.append(name[:37] + "...")
                if file_names:
                    if len(file_names) <= 5:
                        completed_items = [f"[{name}]" for name in file_names]
                    else:
                        completed_items = [f"[{name}]" for name in file_names[:4]]
                        completed_items.append(f"(+{len(file_names) - 4} more)")
                else:
                    completed_items = ["No files found"]
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title="Listing files",
                    status="completed",
                    items=completed_items,
                )
            else:
                yield streaming_service.format_thinking_step(
                    step_id=original_step_id,
                    title=f"Using {tool_name.replace('_', ' ')}",
                    status="completed",
                    items=last_active_step_items,
                )

            just_finished_tool = True
            last_active_step_id = None
            last_active_step_title = ""
            last_active_step_items = []

            if tool_name == "generate_podcast":
                yield streaming_service.format_tool_output_available(
                    tool_call_id,
                    tool_output
                    if isinstance(tool_output, dict)
                    else {"result": tool_output},
                )
                if (
                    isinstance(tool_output, dict)
                    and tool_output.get("status") == "success"
                ):
                    yield streaming_service.format_terminal_info(
                        f"Podcast generated successfully: {tool_output.get('title', 'Podcast')}",
                        "success",
                    )
                else:
                    error_msg = (
                        tool_output.get("error", "Unknown error")
                        if isinstance(tool_output, dict)
                        else "Unknown error"
                    )
                    yield streaming_service.format_terminal_info(
                        f"Podcast generation failed: {error_msg}",
                        "error",
                    )
            elif tool_name == "generate_video_presentation":
                yield streaming_service.format_tool_output_available(
                    tool_call_id,
                    tool_output
                    if isinstance(tool_output, dict)
                    else {"result": tool_output},
                )
                if (
                    isinstance(tool_output, dict)
                    and tool_output.get("status") == "pending"
                ):
                    yield streaming_service.format_terminal_info(
                        f"Video presentation queued: {tool_output.get('title', 'Presentation')}",
                        "success",
                    )
                elif (
                    isinstance(tool_output, dict)
                    and tool_output.get("status") == "failed"
                ):
                    error_msg = (
                        tool_output.get("error", "Unknown error")
                        if isinstance(tool_output, dict)
                        else "Unknown error"
                    )
                    yield streaming_service.format_terminal_info(
                        f"Presentation generation failed: {error_msg}",
                        "error",
                    )
            elif tool_name == "generate_image":
                yield streaming_service.format_tool_output_available(
                    tool_call_id,
                    tool_output
                    if isinstance(tool_output, dict)
                    else {"result": tool_output},
                )
                if isinstance(tool_output, dict):
                    if tool_output.get("error"):
                        yield streaming_service.format_terminal_info(
                            f"Image generation failed: {tool_output['error'][:60]}",
                            "error",
                        )
                    else:
                        yield streaming_service.format_terminal_info(
                            "Image generated successfully",
                            "success",
                        )
            elif tool_name == "scrape_webpage":
                if isinstance(tool_output, dict):
                    display_output = {
                        k: v for k, v in tool_output.items() if k != "content"
                    }
                    if "content" in tool_output:
                        content = tool_output.get("content", "")
                        display_output["content_preview"] = (
                            content[:500] + "..." if len(content) > 500 else content
                        )
                    yield streaming_service.format_tool_output_available(
                        tool_call_id,
                        display_output,
                    )
                else:
                    yield streaming_service.format_tool_output_available(
                        tool_call_id,
                        {"result": tool_output},
                    )
                if isinstance(tool_output, dict) and "error" not in tool_output:
                    title = tool_output.get("title", "Webpage")
                    word_count = tool_output.get("word_count", 0)
                    yield streaming_service.format_terminal_info(
                        f"Scraped: {title[:40]}{'...' if len(title) > 40 else ''} ({word_count:,} words)",
                        "success",
                    )
                else:
                    error_msg = (
                        tool_output.get("error", "Failed to scrape")
                        if isinstance(tool_output, dict)
                        else "Failed to scrape"
                    )
                    yield streaming_service.format_terminal_info(
                        f"Scrape failed: {error_msg}",
                        "error",
                    )
            elif tool_name == "generate_report":
                # Stream the full report result so frontend can render the ReportCard
                yield streaming_service.format_tool_output_available(
                    tool_call_id,
                    tool_output
                    if isinstance(tool_output, dict)
                    else {"result": tool_output},
                )
                # Send appropriate terminal message based on status
                if (
                    isinstance(tool_output, dict)
                    and tool_output.get("status") == "ready"
                ):
                    word_count = tool_output.get("word_count", 0)
                    yield streaming_service.format_terminal_info(
                        f"Report generated: {tool_output.get('title', 'Report')} ({word_count:,} words)",
                        "success",
                    )
                else:
                    error_msg = (
                        tool_output.get("error", "Unknown error")
                        if isinstance(tool_output, dict)
                        else "Unknown error"
                    )
                    yield streaming_service.format_terminal_info(
                        f"Report generation failed: {error_msg}",
                        "error",
                    )
            elif tool_name in (
                "create_notion_page",
                "update_notion_page",
                "delete_notion_page",
                "create_linear_issue",
                "update_linear_issue",
                "delete_linear_issue",
                "create_google_drive_file",
                "delete_google_drive_file",
                "create_onedrive_file",
                "delete_onedrive_file",
                "create_dropbox_file",
                "delete_dropbox_file",
                "create_gmail_draft",
                "update_gmail_draft",
                "send_gmail_email",
                "trash_gmail_email",
                "create_calendar_event",
                "update_calendar_event",
                "delete_calendar_event",
                "create_jira_issue",
                "update_jira_issue",
                "delete_jira_issue",
                "create_confluence_page",
                "update_confluence_page",
                "delete_confluence_page",
            ):
                yield streaming_service.format_tool_output_available(
                    tool_call_id,
                    tool_output
                    if isinstance(tool_output, dict)
                    else {"result": tool_output},
                )
            elif tool_name == "execute":
                raw_text = (
                    tool_output.get("result", "")
                    if isinstance(tool_output, dict)
                    else str(tool_output)
                )
                exit_code: int | None = None
                output_text = raw_text
                m = re.match(r"^Exit code:\s*(\d+)", raw_text)
                if m:
                    exit_code = int(m.group(1))
                    om = re.search(r"\nOutput:\n([\s\S]*)", raw_text)
                    output_text = om.group(1) if om else ""
                thread_id_str = config.get("configurable", {}).get("thread_id", "")

                for sf_match in re.finditer(
                    r"^SANDBOX_FILE:\s*(.+)$", output_text, re.MULTILINE
                ):
                    fpath = sf_match.group(1).strip()
                    if fpath and fpath not in result.sandbox_files:
                        result.sandbox_files.append(fpath)

                yield streaming_service.format_tool_output_available(
                    tool_call_id,
                    {
                        "exit_code": exit_code,
                        "output": output_text,
                        "thread_id": thread_id_str,
                    },
                )
            elif tool_name == "web_search":
                xml = (
                    tool_output.get("result", str(tool_output))
                    if isinstance(tool_output, dict)
                    else str(tool_output)
                )
                citations: dict[str, dict[str, str]] = {}
                for m in re.finditer(
                    r"<title><!\[CDATA\[(.*?)\]\]></title>\s*<url><!\[CDATA\[(.*?)\]\]></url>",
                    xml,
                ):
                    title, url = m.group(1).strip(), m.group(2).strip()
                    if url.startswith("http") and url not in citations:
                        citations[url] = {"title": title}
                for m in re.finditer(
                    r"<chunk\s+id='([^']*)'><!\[CDATA\[([\s\S]*?)\]\]></chunk>",
                    xml,
                ):
                    chunk_url, content = m.group(1).strip(), m.group(2).strip()
                    if (
                        chunk_url.startswith("http")
                        and chunk_url in citations
                        and content
                    ):
                        citations[chunk_url]["snippet"] = (
                            content[:200] + "…" if len(content) > 200 else content
                        )
                yield streaming_service.format_tool_output_available(
                    tool_call_id,
                    {"status": "completed", "citations": citations},
                )
            else:
                yield streaming_service.format_tool_output_available(
                    tool_call_id,
                    {"status": "completed", "result_length": len(str(tool_output))},
                )
                yield streaming_service.format_terminal_info(
                    f"Tool {tool_name} completed", "success"
                )

        elif event_type == "on_custom_event" and event.get("name") == "report_progress":
            # Live progress updates from inside the generate_report tool
            data = event.get("data", {})
            message = data.get("message", "")
            if message and last_active_step_id:
                phase = data.get("phase", "")
                # Always keep the "Topic: ..." line
                topic_items = [
                    item for item in last_active_step_items if item.startswith("Topic:")
                ]

                if phase in ("revising_section", "adding_section"):
                    # During section-level ops: keep plan summary + show current op
                    plan_items = [
                        item
                        for item in last_active_step_items
                        if item.startswith("Topic:")
                        or item.startswith("Modifying ")
                        or item.startswith("Adding ")
                        or item.startswith("Removing ")
                    ]
                    # Only keep plan_items that don't end with "..." (not progress lines)
                    plan_items = [
                        item for item in plan_items if not item.endswith("...")
                    ]
                    last_active_step_items = [*plan_items, message]
                else:
                    # Phase transitions: replace everything after topic
                    last_active_step_items = [*topic_items, message]

                yield streaming_service.format_thinking_step(
                    step_id=last_active_step_id,
                    title=last_active_step_title,
                    status="in_progress",
                    items=last_active_step_items,
                )

        elif (
            event_type == "on_custom_event" and event.get("name") == "document_created"
        ):
            data = event.get("data", {})
            if data.get("id"):
                yield streaming_service.format_data(
                    "documents-updated",
                    {
                        "action": "created",
                        "document": data,
                    },
                )

        elif (
            event_type == "on_custom_event" and event.get("name") == "research_status"
        ):
            # Forward neutral status events from chainlens_deep_research tool to FE.
            # Defensive: payload may be None or non-dict if tool misbehaves.
            # FR25 defense-in-depth: scrub any vendor/fallback hints before forwarding
            # so user never sees "Chainlens" / "fallback" even if tool leaks upstream.
            raw_payload = event.get("data")
            payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
            _BANNED_TOKENS = ("chainlens", "fallback")
            sanitized: dict[str, Any] = {}
            for _k, _v in payload.items():
                if isinstance(_v, str) and any(
                    _b in _v.lower() for _b in _BANNED_TOKENS
                ):
                    # Drop fields that leak vendor name or fallback intent.
                    continue
                sanitized[_k] = _v
            yield streaming_service.format_data("research-status", sanitized)

        elif event_type == "on_custom_event" and event.get("name") == "orchestra_spawn":
            data = event.get("data", {})
            session_id = str(config.get("configurable", {}).get("thread_id", ""))
            yield streaming_service.format_orchestra_spawn(
                session_id=session_id,
                agent_id=data.get("agentId", ""),
                agent_name=data.get("agentName", ""),
                agent_type=data.get("agentType", ""),
            )

        elif event_type == "on_custom_event" and event.get("name") == "orchestra_done":
            data = event.get("data", {})
            session_id = str(config.get("configurable", {}).get("thread_id", ""))
            yield streaming_service.format_orchestra_done(
                session_id=session_id,
                agent_id=data.get("agentId", ""),
                citation_ids=data.get("citationIds") or [],
            )

        elif event_type == "on_custom_event" and event.get("name") == "orchestra_fail":
            data = event.get("data", {})
            session_id = str(config.get("configurable", {}).get("thread_id", ""))
            yield streaming_service.format_orchestra_fail(
                session_id=session_id,
                agent_id=data.get("agentId", ""),
                error_code=data.get("errorCode", "unknown"),
                error_message=data.get("errorMessage", ""),
            )

        elif event_type == "on_custom_event" and event.get("name") == "orchestra_narration":
            data = event.get("data", {})
            session_id = str(config.get("configurable", {}).get("thread_id", ""))
            agent_name = data.get("agentName", "")
            yield streaming_service.format_orchestra_narration(
                session_id=session_id,
                agent_id=agent_name,
                text=data.get("text", ""),
                tone=data.get("tone", "fetching"),
            )

        elif event_type == "on_custom_event" and event.get("name") == "orchestra_source_fetched":
            data = event.get("data", {})
            session_id = str(config.get("configurable", {}).get("thread_id", ""))
            agent_name = data.get("agentName", "")
            source = data.get("source", {})
            yield streaming_service.format_orchestra_source_fetched(
                session_id=session_id,
                agent_id=agent_name,
                domain=source.get("domain", ""),
                favicon=source.get("favicon", ""),
                url=source.get("url", ""),
                data_type=source.get("dataType", ""),
            )

        elif event_type == "on_custom_event" and event.get("name") == "orchestra_rate_gate_wait":
            data = event.get("data", {})
            session_id = str(config.get("configurable", {}).get("thread_id", ""))
            wait_secs = data.get("waitSeconds", 0.0)
            reason = data.get("reason", "min_interval")
            yield streaming_service.format_orchestra_rate_gate_wait(
                session_id=session_id,
                wait_seconds=wait_secs,
                reason=reason,
            )

        elif event_type == "on_custom_event" and event.get("name") == "orchestra_fact_captured":
            data = event.get("data", {})
            session_id = str(config.get("configurable", {}).get("thread_id", ""))
            yield streaming_service.format_orchestra_fact_captured(
                session_id=session_id,
                agent_id=data.get("agentId") or data.get("agentName", ""),
                fact_summary=data.get("factSummary", ""),
                value=data.get("value"),
                unit=data.get("unit"),
            )

        elif event_type == "on_custom_event" and event.get("name") == "orchestra_llm_call":
            data = event.get("data", {})
            session_id = str(config.get("configurable", {}).get("thread_id", ""))
            yield streaming_service.format_orchestra_llm_call(
                session_id=session_id,
                agent_id=data.get("agentId") or data.get("agentName", ""),
            )

        elif event_type == "on_custom_event" and event.get("name") == "orchestra_model_attribution":
            data = event.get("data", {})
            session_id = str(config.get("configurable", {}).get("thread_id", ""))
            yield streaming_service.format_orchestra_model_attribution(
                session_id=session_id,
                agent_id=data.get("agentId") or data.get("agentName", ""),
                model=data.get("model", ""),
                provider=data.get("provider", ""),
                tier=data.get("tier"),
            )

        elif event_type == "on_custom_event" and event.get("name") in ("smart_money_flow", "smart-money-flow"):
            # Two name forms accepted by design:
            # - "smart_money_flow" (underscore) — LangChain dispatch_custom_event constraint
            # - "smart-money-flow" (hyphen) — canonical SSE event type (matches FE handler)
            # Both originate from chat_deepagent._emit_orchestra_event(...).
            data = event.get("data") or {}
            if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
                data = data["data"]
            if not isinstance(data, dict):
                continue
            yield streaming_service.format_data(
                "smart-money-flow",
                {
                    "nodes": data.get("nodes", []),
                    "links": data.get("links", []),
                    "net_flow_amount": data.get("net_flow_amount", 0.0),
                    "currency": data.get("currency", "USD"),
                    "source_domain": data.get("source_domain"),
                    "cohort_summary": data.get("cohort_summary"),
                },
            )

        elif event_type == "on_custom_event" and event.get("name") == "data_agent_result":
            # Fallback path when _orchestra_writer ContextVar isn't set (nested LangGraph
            # invocation boundaries). Mirror the writer's routing: bare-type events go
            # via _format_sse, data-* via format_data which auto-prefixes "data-".
            # Prefer payload-supplied sessionId (when set by caller for nested runs)
            # over outer config.thread_id, so events route to the correct session.
            data = event.get("data", {})
            session_id = str(
                data.get("sessionId")
                or config.get("configurable", {}).get("thread_id", "")
            )
            yield streaming_service.format_data(
                "agent-result",
                {
                    "sessionId": session_id,
                    "agentId": data.get("agentId", ""),
                    "resultText": data.get("resultText", ""),
                    "resultLength": data.get("resultLength", 0),
                    "truncated": data.get("truncated", False),
                },
            )

        elif event_type == "on_chat_model_end":
            # Accumulate token counts for quota tracking (cloud mode)
            output = event.get("data", {}).get("output")
            if output is not None:
                usage = None
                if hasattr(output, "usage_metadata") and output.usage_metadata is not None:
                    usage = output.usage_metadata
                elif hasattr(output, "response_metadata") and output.response_metadata is not None:
                    rm = output.response_metadata or {}
                    usage = rm.get("usage") or rm.get("token_usage") or rm.get("usage_metadata")

                if isinstance(usage, dict):
                    total = (
                        usage.get("total_tokens")
                        or (usage.get("input_tokens", 0) + usage.get("output_tokens", 0))
                        or (usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0))
                    )
                    result.total_tokens_used += total or 0
                elif usage is not None and hasattr(usage, "total_tokens"):
                    result.total_tokens_used += getattr(usage, "total_tokens", 0) or 0

        elif event_type in ("on_chain_end", "on_agent_end"):
            if current_text_id is not None:
                yield streaming_service.format_text_end(current_text_id)
                current_text_id = None

    except BaseException:
        # Mark for finally + re-raise. Any queued events are still drained
        # below in the finally clause so partial state is visible to the user.
        _stream_failed = True
        raise
    finally:
        # V2-P1: drain remaining queue + release ContextVar regardless of
        # whether astream_events completed normally or raised.
        while _orchestra_writer_queue:
            yield _orchestra_writer_queue.pop(0)
        _release_writer()
    # End of writer-protected region.

    # Emit citation_map BEFORE text-end so FE has it when rendering final text
    if "[[cite:" in accumulated_text:
        citation_map = harvest_citations(accumulated_text)
        if citation_map:
            yield streaming_service.format_data("citation-map", {"citation_map": citation_map})

    # Parse and emit follow-up questions emitted by LLM in synthesis directive
    # Format: <!--follow-ups-start-->[...]<!--follow-ups-end-->
    # (HTML comment — invisible in renderer; sentinel-delimited so questions
    # may safely contain `]`, `<`, or `>` without truncating the JSON capture.)
    # Legacy format `<!--follow-ups:[...]-->` is also supported for back-compat
    # but uses a greedy capture between the colon and the final `]-->`.
    _follow_ups_match = re.search(
        r"<!--follow-ups-start-->\s*(\[.*\])\s*<!--follow-ups-end-->",
        accumulated_text,
        re.DOTALL,
    )
    if not _follow_ups_match:
        _follow_ups_match = re.search(
            r"<!--follow-ups:(\[.*\])-->", accumulated_text, re.DOTALL
        )
    if _follow_ups_match:
        try:
            follow_ups = json.loads(_follow_ups_match.group(1))
            if isinstance(follow_ups, list) and follow_ups:
                yield streaming_service.format_data("follow-ups", {"follow_ups": follow_ups})
        except (json.JSONDecodeError, ValueError):
            pass
        # Strip comment(s) from stored text
        accumulated_text = (
            accumulated_text[: _follow_ups_match.start()]
            + accumulated_text[_follow_ups_match.end() :]
        ).rstrip()

    # Detect crypto report sentinel and emit report-type event
    if "<!-- crypto-report-v2 -->" in accumulated_text:
        yield streaming_service.format_data(
            "report-type", {"report_type": "comprehensive_crypto"}
        )
        # Emit token-meta if not already emitted by tool handler
        if not _token_meta_emitted:
            _sym_match = re.search(
                r"—\s*([A-Z]{2,12})\s+Token[^(]*\(([^)]+)\)", accumulated_text
            )
            if _sym_match:
                yield streaming_service.format_data(
                    "token-meta",
                    {
                        "token_symbol": _sym_match.group(1),
                        "token_name": _sym_match.group(2),
                        "coingecko_id": "",
                    },
                )
            elif user_query:
                _q_match = re.search(r"\b([A-Z]{2,12})\b", user_query)
                if _q_match:
                    yield streaming_service.format_data(
                        "token-meta",
                        {
                            "token_symbol": _q_match.group(1),
                            "token_name": "",
                            "coingecko_id": "",
                        },
                    )

    if current_text_id is not None:
        yield streaming_service.format_text_end(current_text_id)

    completion_event = complete_current_step()
    if completion_event:
        yield completion_event

    result.accumulated_text = accumulated_text
    result.agent_called_update_memory = called_update_memory

    state = await agent.aget_state(config)
    is_interrupted = state.tasks and any(task.interrupts for task in state.tasks)
    if is_interrupted:
        result.is_interrupted = True
        result.interrupt_value = state.tasks[0].interrupts[0].value
        yield streaming_service.format_interrupt_request(result.interrupt_value)


async def stream_new_chat(
    user_query: str,
    search_space_id: int,
    chat_id: int,
    user_id: str | None = None,
    llm_config_id: int = -1,
    mentioned_document_ids: list[int] | None = None,
    mentioned_nowing_doc_ids: list[int] | None = None,
    checkpoint_id: str | None = None,
    needs_history_bootstrap: bool = False,
    thread_visibility: ChatVisibility | None = None,
    current_user_display_name: str | None = None,
    disabled_tools: list[str] | None = None,
    langgraph_thread_id_override: str | None = None,
    heartbeat_timeout: float | None = 15.0,
) -> AsyncGenerator[str, None]:
    """
    Stream chat responses with optional heartbeat.
    """
    gen = _stream_new_chat_inner(
        user_query=user_query,
        search_space_id=search_space_id,
        chat_id=chat_id,
        user_id=user_id,
        llm_config_id=llm_config_id,
        mentioned_document_ids=mentioned_document_ids,
        mentioned_nowing_doc_ids=mentioned_nowing_doc_ids,
        checkpoint_id=checkpoint_id,
        needs_history_bootstrap=needs_history_bootstrap,
        thread_visibility=thread_visibility,
        current_user_display_name=current_user_display_name,
        disabled_tools=disabled_tools,
        langgraph_thread_id_override=langgraph_thread_id_override,
    )
    if heartbeat_timeout is not None:
        async for chunk in _with_heartbeat(gen, timeout=heartbeat_timeout):
            yield chunk
    else:
        async for chunk in gen:
            yield chunk


async def stream_resume_chat(
    chat_id: int,
    search_space_id: int,
    decisions: list[dict],
    user_id: str | None = None,
    llm_config_id: int = -1,
    thread_visibility: ChatVisibility | None = None,
    heartbeat_timeout: float | None = 15.0,
) -> AsyncGenerator[str, None]:
    """
    Resume chat responses with optional heartbeat.
    """
    gen = _stream_resume_chat_inner(
        chat_id=chat_id,
        search_space_id=search_space_id,
        decisions=decisions,
        user_id=user_id,
        llm_config_id=llm_config_id,
        thread_visibility=thread_visibility,
    )
    if heartbeat_timeout is not None:
        async for chunk in _with_heartbeat(gen, timeout=heartbeat_timeout):
            yield chunk
    else:
        async for chunk in gen:
            yield chunk


async def _stream_new_chat_inner(
    user_query: str,
    search_space_id: int,
    chat_id: int,
    user_id: str | None = None,
    llm_config_id: int = -1,
    mentioned_document_ids: list[int] | None = None,
    mentioned_nowing_doc_ids: list[int] | None = None,
    checkpoint_id: str | None = None,
    needs_history_bootstrap: bool = False,
    thread_visibility: ChatVisibility | None = None,
    current_user_display_name: str | None = None,
    disabled_tools: list[str] | None = None,
    langgraph_thread_id_override: str | None = None,  # C1: detached runs use run-{uuid} for checkpoint isolation
) -> AsyncGenerator[str, None]:
    """
    Inner implementation of stream_new_chat.
    """
    streaming_service = VercelStreamingService()
    stream_result = StreamResult()
    _t_total = time.perf_counter()
    log_system_snapshot("stream_new_chat_START")

    session = async_session_maker()
    try:
        # Mark AI as responding to this user for live collaboration
        if user_id:
            await set_ai_responding(session, chat_id, UUID(user_id))
        # Load LLM config - supports both YAML (negative IDs) and database (positive IDs)
        agent_config: AgentConfig | None = None

        _t0 = time.perf_counter()
        if llm_config_id >= 0:
            # Positive ID: Load from NewLLMConfig database table
            agent_config = await load_agent_config(
                session=session,
                config_id=llm_config_id,
                search_space_id=search_space_id,
            )
            if not agent_config:
                yield streaming_service.format_error(
                    f"Failed to load NewLLMConfig with id {llm_config_id}"
                )
                yield streaming_service.format_done()
                return

            # Create ChatLiteLLM from AgentConfig
            llm = create_chat_litellm_from_agent_config(agent_config)
        else:
            # Negative ID: Load from YAML (global configs)
            llm_config = load_llm_config_from_yaml(llm_config_id=llm_config_id)
            if not llm_config:
                yield streaming_service.format_error(
                    f"Failed to load LLM config with id {llm_config_id}"
                )
                yield streaming_service.format_done()
                return

            # Create ChatLiteLLM from YAML config dict
            llm = create_chat_litellm_from_config(llm_config)
            # Create AgentConfig from YAML for consistency (uses defaults for prompt settings)
            agent_config = AgentConfig.from_yaml_config(llm_config)
        _perf_log.info(
            "[stream_new_chat] LLM config loaded in %.3fs (config_id=%s)",
            time.perf_counter() - _t0,
            llm_config_id,
        )

        if not llm:
            yield streaming_service.format_error("Failed to create LLM instance")
            yield streaming_service.format_done()
            return

        # Create connector service
        _t0 = time.perf_counter()
        connector_service = ConnectorService(session, search_space_id=search_space_id)

        firecrawl_api_key = None
        webcrawler_connector = await connector_service.get_connector_by_type(
            SearchSourceConnectorType.WEBCRAWLER_CONNECTOR, search_space_id
        )
        if webcrawler_connector and webcrawler_connector.config:
            firecrawl_api_key = webcrawler_connector.config.get("FIRECRAWL_API_KEY")
        _perf_log.info(
            "[stream_new_chat] Connector service + firecrawl key in %.3fs",
            time.perf_counter() - _t0,
        )

        # Get the PostgreSQL checkpointer for persistent conversation memory
        _t0 = time.perf_counter()
        checkpointer = await get_checkpointer()
        _perf_log.info(
            "[stream_new_chat] Checkpointer ready in %.3fs", time.perf_counter() - _t0
        )

        visibility = thread_visibility or ChatVisibility.PRIVATE
        _t0 = time.perf_counter()
        agent = await create_nowing_deep_agent(
            llm=llm,
            search_space_id=search_space_id,
            db_session=session,
            connector_service=connector_service,
            checkpointer=checkpointer,
            user_id=user_id,
            thread_id=chat_id,
            agent_config=agent_config,
            firecrawl_api_key=firecrawl_api_key,
            thread_visibility=visibility,
            disabled_tools=disabled_tools,
            mentioned_document_ids=mentioned_document_ids,
        )
        _perf_log.info(
            "[stream_new_chat] Agent created in %.3fs", time.perf_counter() - _t0
        )

        # Build input with message history
        langchain_messages = []

        _t0 = time.perf_counter()
        # Bootstrap history for cloned chats (no LangGraph checkpoint exists yet)
        if needs_history_bootstrap:
            langchain_messages = await bootstrap_history_from_db(
                session, chat_id, thread_visibility=visibility
            )

            thread_result = await session.execute(
                select(NewChatThread).filter(NewChatThread.id == chat_id)
            )
            thread = thread_result.scalars().first()
            if thread:
                thread.needs_history_bootstrap = False
                await session.commit()

        # Mentioned KB documents are now handled by KnowledgeBaseSearchMiddleware
        # which merges them into the scoped filesystem with full document
        # structure. Only Nowing docs and report context are inlined here.

        # Fetch mentioned Nowing docs if any
        mentioned_nowing_docs: list[NowingDocsDocument] = []
        if mentioned_nowing_doc_ids:
            result = await session.execute(
                select(NowingDocsDocument)
                .options(selectinload(NowingDocsDocument.chunks))
                .filter(
                    NowingDocsDocument.id.in_(mentioned_nowing_doc_ids),
                )
            )
            mentioned_nowing_docs = list(result.scalars().all())

        # Fetch the most recent report(s) in this thread so the LLM can
        # easily find report_id for versioning decisions, instead of
        # having to dig through conversation history.
        recent_reports_result = await session.execute(
            select(Report)
            .filter(
                Report.thread_id == chat_id,
                Report.content.isnot(None),  # exclude failed reports
            )
            .order_by(Report.id.desc())
            .limit(3)
        )
        recent_reports = list(recent_reports_result.scalars().all())

        # Format the user query with context (Nowing docs + reports only)
        final_query = user_query
        context_parts = []

        if mentioned_nowing_docs:
            context_parts.append(
                format_mentioned_nowing_docs_as_context(mentioned_nowing_docs)
            )

        # Surface report IDs prominently so the LLM doesn't have to
        # retrieve them from old tool responses in conversation history.
        if recent_reports:
            report_lines = []
            for r in recent_reports:
                report_lines.append(
                    f'  - report_id={r.id}, title="{r.title}", '
                    f'style="{r.report_style or "detailed"}"'
                )
            reports_listing = "\n".join(report_lines)
            context_parts.append(
                "<report_context>\n"
                "Previously generated reports in this conversation:\n"
                f"{reports_listing}\n\n"
                "If the user wants to MODIFY, REVISE, UPDATE, or ADD to one of "
                "these reports, set parent_report_id to the relevant report_id above.\n"
                "If the user wants a completely NEW report on a different topic, "
                "leave parent_report_id unset.\n"
                "</report_context>"
            )

        if context_parts:
            context = "\n\n".join(context_parts)
            final_query = f"{context}\n\n<user_query>{user_query}</user_query>"

        if visibility == ChatVisibility.SEARCH_SPACE and current_user_display_name:
            final_query = f"**[{current_user_display_name}]:** {final_query}"

        # if messages:
        #     # Convert frontend messages to LangChain format
        #     for msg in messages:
        #         if msg.role == "user":
        #             langchain_messages.append(HumanMessage(content=msg.content))
        #         elif msg.role == "assistant":
        #             langchain_messages.append(AIMessage(content=msg.content))
        # else:
        # Fallback: just use the current user query with attachment context
        langchain_messages.append(HumanMessage(content=final_query))

        input_state = {
            # Lets not pass this message atm because we are using the checkpointer to manage the conversation history
            # We will use this to simulate group chat functionality in the future
            "messages": langchain_messages,
            "search_space_id": search_space_id,
        }

        _perf_log.info(
            "[stream_new_chat] History bootstrap + doc/report queries in %.3fs",
            time.perf_counter() - _t0,
        )

        # All pre-streaming DB reads are done.  Commit to release the
        # transaction and its ACCESS SHARE locks so we don't block DDL
        # (e.g. migrations) for the entire duration of LLM streaming.
        # Tools that need DB access during streaming will start their own
        # short-lived transactions (or use isolated sessions).
        await session.commit()

        # Detach heavy ORM objects (documents with chunks, reports, etc.)
        # from the session identity map now that we've extracted the data
        # we need.  This prevents them from accumulating in memory for the
        # entire duration of LLM streaming (which can be several minutes).
        session.expunge_all()

        _perf_log.info(
            "[stream_new_chat] Total pre-stream setup in %.3fs (chat_id=%s)",
            time.perf_counter() - _t_total,
            chat_id,
        )

        # Configure LangGraph with thread_id for memory
        # C1: detached runs use langgraph_thread_id_override ("run-{uuid}") for checkpoint isolation
        configurable = {"thread_id": langgraph_thread_id_override or str(chat_id)}
        if checkpoint_id:
            configurable["checkpoint_id"] = checkpoint_id

        config = {
            "configurable": configurable,
            "recursion_limit": _AGENT_RECURSION_LIMIT,  # env AGENT_RECURSION_LIMIT (default 200) — bumped from 80 to accommodate pacing
        }

        # Start the message stream
        yield streaming_service.format_message_start()
        yield streaming_service.format_start_step()

        # Initial thinking step - analyzing the request
        if mentioned_nowing_docs:
            initial_title = "Analyzing referenced content"
            action_verb = "Analyzing"
        else:
            initial_title = "Understanding your request"
            action_verb = "Processing"

        processing_parts = []
        query_text = user_query[:80] + ("..." if len(user_query) > 80 else "")
        processing_parts.append(query_text)

        if mentioned_nowing_docs:
            doc_names = []
            for doc in mentioned_nowing_docs:
                title = doc.title
                if len(title) > 30:
                    title = title[:27] + "..."
                doc_names.append(title)
            if len(doc_names) == 1:
                processing_parts.append(f"[{doc_names[0]}]")
            else:
                processing_parts.append(f"[{len(doc_names)} docs]")

        initial_items = [f"{action_verb}: {' '.join(processing_parts)}"]
        initial_step_id = "thinking-1"

        yield streaming_service.format_thinking_step(
            step_id=initial_step_id,
            title=initial_title,
            status="in_progress",
            items=initial_items,
        )

        # These ORM objects (with eagerly-loaded chunks) can be very large.
        # They're only needed to build context strings already copied into
        # final_query / langchain_messages — release them before streaming.
        del mentioned_nowing_docs, recent_reports
        del langchain_messages, final_query

        # Check if this is the first assistant response so we can generate
        # a title in parallel with the agent stream (better UX than waiting
        # until after the full response).
        assistant_count_result = await session.execute(
            select(func.count(NewChatMessage.id)).filter(
                NewChatMessage.thread_id == chat_id,
                NewChatMessage.role == "assistant",
            )
        )
        is_first_response = (assistant_count_result.scalar() or 0) == 0

        title_task: asyncio.Task[str | None] | None = None
        if is_first_response:

            async def _generate_title() -> str | None:
                try:
                    title_chain = TITLE_GENERATION_PROMPT_TEMPLATE | llm
                    title_result = await title_chain.ainvoke(
                        {"user_query": user_query[:500]}
                    )
                    if title_result and hasattr(title_result, "content"):
                        raw_title = title_result.content.strip()
                        if raw_title and len(raw_title) <= 100:
                            return raw_title.strip("\"'")
                except Exception:
                    pass
                return None

            title_task = asyncio.create_task(_generate_title())

        title_emitted = False

        _t_stream_start = time.perf_counter()
        _first_event_logged = False
        async for sse in _stream_agent_events(
            agent=agent,
            config=config,
            input_data=input_state,
            streaming_service=streaming_service,
            result=stream_result,
            step_prefix="thinking",
            initial_step_id=initial_step_id,
            initial_step_title=initial_title,
            initial_step_items=initial_items,
            user_query=user_query,
        ):
            if not _first_event_logged:
                _perf_log.info(
                    "[stream_new_chat] First agent event in %.3fs (time since stream start), "
                    "%.3fs (total since request start) (chat_id=%s)",
                    time.perf_counter() - _t_stream_start,
                    time.perf_counter() - _t_total,
                    chat_id,
                )
                _first_event_logged = True
            yield sse

            # Inject title update mid-stream as soon as the background task finishes
            if title_task is not None and title_task.done() and not title_emitted:
                generated_title = title_task.result()
                if generated_title:
                    async with shielded_async_session() as title_session:
                        title_thread_result = await title_session.execute(
                            select(NewChatThread).filter(NewChatThread.id == chat_id)
                        )
                        title_thread = title_thread_result.scalars().first()
                        if title_thread:
                            title_thread.title = generated_title
                            await title_session.commit()
                    yield streaming_service.format_thread_title_update(
                        chat_id, generated_title
                    )
                title_emitted = True

        _perf_log.info(
            "[stream_new_chat] Agent stream completed in %.3fs (chat_id=%s)",
            time.perf_counter() - _t_stream_start,
            chat_id,
        )
        log_system_snapshot("stream_new_chat_END")

        if stream_result.is_interrupted:
            if title_task is not None and not title_task.done():
                title_task.cancel()
            yield streaming_service.format_finish_step()
            yield streaming_service.format_finish()
            yield streaming_service.format_done()
            return

        # If the title task didn't finish during streaming, await it now
        if title_task is not None and not title_emitted:
            generated_title = await title_task
            if generated_title:
                async with shielded_async_session() as title_session:
                    title_thread_result = await title_session.execute(
                        select(NewChatThread).filter(NewChatThread.id == chat_id)
                    )
                    title_thread = title_thread_result.scalars().first()
                    if title_thread:
                        title_thread.title = generated_title
                        await title_session.commit()
                yield streaming_service.format_thread_title_update(
                    chat_id, generated_title
                )

        # Fire background memory extraction if the agent didn't handle it.
        # Shared threads write to team memory; private threads write to user memory.
        if not stream_result.agent_called_update_memory:
            if visibility == ChatVisibility.SEARCH_SPACE:
                asyncio.create_task(
                    extract_and_save_team_memory(
                        user_message=user_query,
                        search_space_id=search_space_id,
                        llm=llm,
                        author_display_name=current_user_display_name,
                    )
                )
            elif user_id:
                asyncio.create_task(
                    extract_and_save_memory(
                        user_message=user_query,
                        user_id=user_id,
                        llm=llm,
                    )
                )

        # Cloud mode: deduct consumed tokens from the user's monthly quota
        if app_config.is_cloud() and user_id and stream_result.total_tokens_used > 0:
            try:
                async with shielded_async_session() as quota_session:
                    from app.services.token_quota_service import TokenQuotaService

                    quota_service = TokenQuotaService(quota_session)
                    new_total = await quota_service.update_token_usage(
                        user_id, stream_result.total_tokens_used, allow_exceed=True
                    )
                    _, effective_limit = await quota_service.get_token_usage(user_id)
                    yield streaming_service.format_data(
                        "token-usage",
                        {
                            "tokens_this_request": stream_result.total_tokens_used,
                            "tokens_used_total": new_total,
                            "monthly_limit": effective_limit,
                            "tokens_remaining": max(0, effective_limit - new_total),
                        },
                    )
            except Exception as quota_err:
                # Non-fatal — log and continue; usage was already streamed
                logging.getLogger(__name__).warning(
                    "[stream_new_chat] Failed to record token usage: %s", quota_err
                )

        # Finish the step and message
        yield streaming_service.format_finish_step()
        yield streaming_service.format_finish()
        yield streaming_service.format_done()

    except Exception as e:
        # Handle any errors
        import traceback

        error_str = str(e)
        is_rate_limit = (
            "rate limit" in error_str.lower()
            or "429" in error_str
            or type(e).__name__ == "RateLimitError"
        )
        if is_rate_limit:
            _rate_limit_state.mark_rate_limited()
            logging.getLogger(__name__).warning(
                "[stream_new_chat] rate_limit caught — future comprehensive queries will spawn sequentially"
            )
            # Try to salvage partial sub-agent work from checkpointer so user
            # never sees "Sorry, there was an error" when real results exist.
            try:
                partial = await _extract_partial_analysis(agent, config)
            except Exception as extract_err:
                logging.getLogger(__name__).warning(
                    "[stream_new_chat] partial extraction failed: %s", extract_err
                )
                partial = None
            if partial:
                logging.getLogger(__name__).warning(
                    "[stream_new_chat] yielding partial analysis: %d completed, %d errored",
                    partial["completed_count"], partial["errored_count"],
                )
                import uuid as _uuid
                _tid = _uuid.uuid4().hex[:12]
                yield streaming_service.format_text_start(_tid)
                yield streaming_service.format_text_delta(_tid, partial["message"])
                yield streaming_service.format_text_end(_tid)
                yield streaming_service.format_finish_step()
                yield streaming_service.format_finish()
                yield streaming_service.format_done()
                return

        error_message = f"Error during chat: {e!s}"
        print(f"[stream_new_chat] {error_message}")
        print(f"[stream_new_chat] Exception type: {type(e).__name__}")
        print(f"[stream_new_chat] Traceback:\n{traceback.format_exc()}")

        yield streaming_service.format_error(error_message)
        yield streaming_service.format_finish_step()
        yield streaming_service.format_finish()
        yield streaming_service.format_done()

    finally:
        # Shield the ENTIRE async cleanup from anyio cancel-scope
        # cancellation.  Starlette's BaseHTTPMiddleware uses anyio task
        # groups; on client disconnect, it cancels the scope with
        # level-triggered cancellation — every unshielded `await` inside
        # the cancelled scope raises CancelledError immediately.  Without
        # this shield the very first `await` (session.rollback) would
        # raise CancelledError, `except Exception` wouldn't catch it
        # (CancelledError is a BaseException), and the rest of the
        # finally block — including session.close() — would never run.
        with anyio.CancelScope(shield=True):
            try:
                await session.rollback()
                await clear_ai_responding(session, chat_id)
            except Exception:
                try:
                    async with shielded_async_session() as fresh_session:
                        await clear_ai_responding(fresh_session, chat_id)
                except Exception:
                    logging.getLogger(__name__).warning(
                        "Failed to clear AI responding state for thread %s", chat_id
                    )

            with contextlib.suppress(Exception):
                session.expunge_all()

            with contextlib.suppress(Exception):
                await session.close()

        # Break circular refs held by the agent graph, tools, and LLM
        # wrappers so the GC can reclaim them in a single pass.
        agent = llm = connector_service = None
        input_state = stream_result = None
        session = None

        collected = gc.collect(0) + gc.collect(1) + gc.collect(2)
        if collected:
            _perf_log.info(
                "[stream_new_chat] gc.collect() reclaimed %d objects (chat_id=%s)",
                collected,
                chat_id,
            )
        trim_native_heap()
        log_system_snapshot("stream_new_chat_END")


async def _stream_resume_chat_inner(
    chat_id: int,
    search_space_id: int,
    decisions: list[dict],
    user_id: str | None = None,
    llm_config_id: int = -1,
    thread_visibility: ChatVisibility | None = None,
) -> AsyncGenerator[str, None]:
    """
    Inner implementation of stream_resume_chat.
    """
    streaming_service = VercelStreamingService()
    stream_result = StreamResult()
    _t_total = time.perf_counter()

    session = async_session_maker()
    try:
        if user_id:
            await set_ai_responding(session, chat_id, UUID(user_id))

        agent_config: AgentConfig | None = None
        _t0 = time.perf_counter()
        if llm_config_id >= 0:
            agent_config = await load_agent_config(
                session=session,
                config_id=llm_config_id,
                search_space_id=search_space_id,
            )
            if not agent_config:
                yield streaming_service.format_error(
                    f"Failed to load NewLLMConfig with id {llm_config_id}"
                )
                yield streaming_service.format_done()
                return
            llm = create_chat_litellm_from_agent_config(agent_config)
        else:
            llm_config = load_llm_config_from_yaml(llm_config_id=llm_config_id)
            if not llm_config:
                yield streaming_service.format_error(
                    f"Failed to load LLM config with id {llm_config_id}"
                )
                yield streaming_service.format_done()
                return
            llm = create_chat_litellm_from_config(llm_config)
            agent_config = AgentConfig.from_yaml_config(llm_config)
        _perf_log.info(
            "[stream_resume] LLM config loaded in %.3fs", time.perf_counter() - _t0
        )

        if not llm:
            yield streaming_service.format_error("Failed to create LLM instance")
            yield streaming_service.format_done()
            return

        _t0 = time.perf_counter()
        connector_service = ConnectorService(session, search_space_id=search_space_id)

        firecrawl_api_key = None
        webcrawler_connector = await connector_service.get_connector_by_type(
            SearchSourceConnectorType.WEBCRAWLER_CONNECTOR, search_space_id
        )
        if webcrawler_connector and webcrawler_connector.config:
            firecrawl_api_key = webcrawler_connector.config.get("FIRECRAWL_API_KEY")
        _perf_log.info(
            "[stream_resume] Connector service + firecrawl key in %.3fs",
            time.perf_counter() - _t0,
        )

        _t0 = time.perf_counter()
        checkpointer = await get_checkpointer()
        _perf_log.info(
            "[stream_resume] Checkpointer ready in %.3fs", time.perf_counter() - _t0
        )

        visibility = thread_visibility or ChatVisibility.PRIVATE

        _t0 = time.perf_counter()
        agent = await create_nowing_deep_agent(
            llm=llm,
            search_space_id=search_space_id,
            db_session=session,
            connector_service=connector_service,
            checkpointer=checkpointer,
            user_id=user_id,
            thread_id=chat_id,
            agent_config=agent_config,
            firecrawl_api_key=firecrawl_api_key,
            thread_visibility=visibility,
        )
        _perf_log.info(
            "[stream_resume] Agent created in %.3fs", time.perf_counter() - _t0
        )

        # Release the transaction before streaming (same rationale as stream_new_chat).
        await session.commit()
        session.expunge_all()

        _perf_log.info(
            "[stream_resume] Total pre-stream setup in %.3fs (chat_id=%s)",
            time.perf_counter() - _t_total,
            chat_id,
        )

        from langgraph.types import Command

        config = {
            "configurable": {"thread_id": str(chat_id)},
            "recursion_limit": _AGENT_RECURSION_LIMIT,
        }

        yield streaming_service.format_message_start()
        yield streaming_service.format_start_step()

        _t_stream_start = time.perf_counter()
        _first_event_logged = False
        async for sse in _stream_agent_events(
            agent=agent,
            config=config,
            input_data=Command(resume={"decisions": decisions}),
            streaming_service=streaming_service,
            result=stream_result,
            step_prefix="thinking-resume",
            user_query=user_query,
        ):
            if not _first_event_logged:
                _perf_log.info(
                    "[stream_resume] First agent event in %.3fs (stream), %.3fs (total) (chat_id=%s)",
                    time.perf_counter() - _t_stream_start,
                    time.perf_counter() - _t_total,
                    chat_id,
                )
                _first_event_logged = True
            yield sse
        _perf_log.info(
            "[stream_resume] Agent stream completed in %.3fs (chat_id=%s)",
            time.perf_counter() - _t_stream_start,
            chat_id,
        )
        if stream_result.is_interrupted:
            yield streaming_service.format_finish_step()
            yield streaming_service.format_finish()
            yield streaming_service.format_done()
            return

        yield streaming_service.format_finish_step()
        # Cloud mode: deduct consumed tokens from the user's monthly quota
        if app_config.is_cloud() and user_id and stream_result.total_tokens_used > 0:
            try:
                async with shielded_async_session() as quota_session:
                    from app.services.token_quota_service import TokenQuotaService

                    quota_service = TokenQuotaService(quota_session)
                    new_total = await quota_service.update_token_usage(
                        user_id, stream_result.total_tokens_used, allow_exceed=True
                    )
                    _, effective_limit = await quota_service.get_token_usage(user_id)
                    yield streaming_service.format_data(
                        "token-usage",
                        {
                            "tokens_this_request": stream_result.total_tokens_used,
                            "tokens_used_total": new_total,
                            "monthly_limit": effective_limit,
                            "tokens_remaining": max(0, effective_limit - new_total),
                        },
                    )
            except Exception as quota_err:
                # Non-fatal — log and continue; usage was already streamed
                logging.getLogger(__name__).warning(
                    "[stream_resume_chat] Failed to record token usage: %s", quota_err
                )

        yield streaming_service.format_finish()
        yield streaming_service.format_done()

    except Exception as e:
        import traceback

        error_str = str(e)
        is_rate_limit = (
            "rate limit" in error_str.lower()
            or "429" in error_str
            or type(e).__name__ == "RateLimitError"
        )
        if is_rate_limit:
            _rate_limit_state.mark_rate_limited()
            logging.getLogger(__name__).warning(
                "[stream_resume_chat] rate_limit caught — future comprehensive queries will spawn sequentially"
            )
            try:
                partial = await _extract_partial_analysis(agent, config)
            except Exception as extract_err:
                logging.getLogger(__name__).warning(
                    "[stream_resume_chat] partial extraction failed: %s", extract_err
                )
                partial = None
            if partial:
                logging.getLogger(__name__).warning(
                    "[stream_resume_chat] yielding partial analysis: %d completed, %d errored",
                    partial["completed_count"], partial["errored_count"],
                )
                import uuid as _uuid
                _tid = _uuid.uuid4().hex[:12]
                yield streaming_service.format_text_start(_tid)
                yield streaming_service.format_text_delta(_tid, partial["message"])
                yield streaming_service.format_text_end(_tid)
                yield streaming_service.format_finish_step()
                yield streaming_service.format_finish()
                yield streaming_service.format_done()
                return

        error_message = f"Error during resume: {e!s}"
        print(f"[stream_resume_chat] {error_message}")
        print(f"[stream_resume_chat] Traceback:\n{traceback.format_exc()}")
        yield streaming_service.format_error(error_message)
        yield streaming_service.format_finish_step()
        yield streaming_service.format_finish()
        yield streaming_service.format_done()

    finally:
        with anyio.CancelScope(shield=True):
            try:
                await session.rollback()
                await clear_ai_responding(session, chat_id)
            except Exception:
                try:
                    async with shielded_async_session() as fresh_session:
                        await clear_ai_responding(fresh_session, chat_id)
                except Exception:
                    logging.getLogger(__name__).warning(
                        "Failed to clear AI responding state for thread %s", chat_id
                    )

            with contextlib.suppress(Exception):
                session.expunge_all()

            with contextlib.suppress(Exception):
                await session.close()

        agent = llm = connector_service = None
        stream_result = None
        session = None

        collected = gc.collect(0) + gc.collect(1) + gc.collect(2)
        if collected:
            _perf_log.info(
                "[stream_resume] gc.collect() reclaimed %d objects (chat_id=%s)",
                collected,
                chat_id,
            )
        trim_native_heap()
        log_system_snapshot("stream_resume_chat_END")


_VERCEL_PREFIX_RE = re.compile(r'^[0-9a-z]:"')


def _extract_sse_event_type(sse_chunk: str) -> str:
    """Extract event_type from SSE string for RunEventWriter classification.

    Handles:
    - `data: {"type": "orchestra-spawn", "data": {...}}\n\n` → "orchestra-spawn"
    - `data: 0:"text"\n` (Vercel text-delta) → "text-delta"
    - `data: [DONE]\n\n` → "done"
    - Other/parse failures → "sse-raw"
    """
    stripped = sse_chunk.strip()
    if not stripped.startswith("data:"):
        return "sse-raw"
    payload_str = stripped[5:].strip()  # drop "data: "
    if payload_str.startswith("[DONE]"):
        return "done"
    # Try JSON first (most events are structured)
    try:
        import json as _json
        parsed = _json.loads(payload_str)
        if isinstance(parsed, dict) and "type" in parsed:
            return parsed["type"]
    except Exception:
        pass
    # Vercel text delta strict: `0:"text"`, `g:"text"`, etc. — single hex/letter + ':"' prefix
    if _VERCEL_PREFIX_RE.match(payload_str):
        return "text-delta"
    return "sse-raw"


def _parse_vercel_envelope(sse_chunk: str) -> dict | None:
    """Parse SSE chunk into structured payload dict for JSONB storage.

    Returns structured dict suitable for RunEventWriter.write(), or None to skip.
    Format contract:
      - JSON events: returns full envelope {"type": ..., "data": ...}
      - text-delta:  returns {"type": "text-delta", "_vercel": raw_payload_str}
      - [DONE] / unparseable: returns None (skipped, not persisted)
    """
    stripped = sse_chunk.strip()
    if not stripped.startswith("data:"):
        return None
    payload_str = stripped[5:].strip()
    if payload_str.startswith("[DONE]"):
        return None
    try:
        parsed = json.loads(payload_str)
        if isinstance(parsed, dict) and "type" in parsed:
            return parsed
    except Exception:
        pass
    if _VERCEL_PREFIX_RE.match(payload_str):
        return {"type": "text-delta", "_vercel": payload_str}
    return None


async def stream_new_chat_detached(
    run_id,
    langgraph_thread_id: str,
    user_query: str,
    search_space_id: int,
    thread_id: int,
    user_id: str | None = None,
    llm_config_id: int = -1,
    model_id: int | None = None,
    mentioned_document_ids: list[int] | None = None,
    mentioned_nowing_doc_ids: list[int] | None = None,
    disabled_tools: list[str] | None = None,
    needs_history_bootstrap: bool = False,
    thread_visibility=None,
    current_user_display_name: str | None = None,
    checkpoint_id: str | None = None,
    cancel_event=None,
    writer=None,
) -> int | None:
    """Detached agent execution: drains stream_new_chat → writes events to RunEventWriter.

    Does NOT yield SSE strings. All events go to writer (DB + Redis pubsub).
    Uses langgraph_thread_id (not thread_id) for LangGraph checkpoint isolation (C1).
    Cooperative cancel via cancel_event.is_set() between generator chunks.
    Returns final_message_id (int) captured from data-message-id event, or None.
    """
    if writer is None:
        raise ValueError("writer must be provided for detached execution")

    # Cancel-check wrapper: check cancel_event between every yielded chunk
    async def _consume_with_cancel() -> int | None:
        final_message_id: int | None = None
        gen = stream_new_chat(
            user_query=user_query,
            search_space_id=search_space_id,
            chat_id=thread_id,  # integer DB thread id for all DB lookups
            user_id=user_id,
            llm_config_id=llm_config_id,
            mentioned_document_ids=mentioned_document_ids,
            mentioned_nowing_doc_ids=mentioned_nowing_doc_ids,
            checkpoint_id=checkpoint_id,
            needs_history_bootstrap=needs_history_bootstrap,
            thread_visibility=thread_visibility,
            current_user_display_name=current_user_display_name,
            disabled_tools=disabled_tools,
            langgraph_thread_id_override=langgraph_thread_id,  # C1: isolated checkpoint
            heartbeat_timeout=None,  # Detached runs don't need SSE heartbeats
        )
        async for chunk in gen:
            if cancel_event is not None and cancel_event.is_set():
                # Cooperative cancel — emit cancel event then break (M17: bounded aclose)
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(gen.aclose(), timeout=2.0)
                writer.write("orchestra-cancel", {"sessionId": langgraph_thread_id, "reason": "user_cancel"})
                raise asyncio.CancelledError("run cancelled by user")
            parsed = _parse_vercel_envelope(chunk)
            if parsed is None:
                await asyncio.sleep(0)
                continue
            event_type = parsed.get("type", "sse-raw")
            # T12: capture final_message_id from data-message-id event
            if event_type == "data-message-id":
                msg_id_val = (parsed.get("data") or {}).get("id")
                if isinstance(msg_id_val, int):
                    final_message_id = msg_id_val
            writer.write(event_type, parsed)
            # M18: yield to event loop so flush_task can drain queue and avoid back-pressure
            await asyncio.sleep(0)
        return final_message_id

    return await _consume_with_cancel()
