"""Factory-local helpers of ``build_task_tool_with_parent_config``, promoted to module level.

Closures that captured factory locals in the original ``task_tool.py`` take
them as explicit parameters here (``subagent_names``, ``resolve_subagent``,
``hint_providers``); call sites in :mod:`._factory` pass the same values the
closure would have captured.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from typing import Any

from langchain.tools import ToolRuntime
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables import Runnable
from langgraph.errors import GraphInterrupt
from langgraph.types import Command

from app.agents.chat.multi_agent_chat.constants import LEGACY_SUBAGENT_ALIASES
from app.agents.chat.multi_agent_chat.subagents.shared.invocation import (
    EXCLUDED_STATE_KEYS,
    subagent_invoke_config,
)
from app.agents.chat.multi_agent_chat.subagents.shared.spec import ContextHintProvider

from ..constants import (
    DEFAULT_SUBAGENT_BATCH_CONCURRENCY,
    DEFAULT_SUBAGENT_BILLABLE_THRESHOLD,
    MAX_SUBAGENT_BATCH_SIZE,
)
from ._helpers import SubagentInvokeTimeoutError, _ainvoke_with_timeout

logger = logging.getLogger(__name__)


def _canonical_subagent_type(subagent_type: str, subagent_names: set[str]) -> str:
    """Resolve a legacy connector subagent name to its consolidated route.

    Only rewrites when the requested name is unavailable but its alias is
    (checkpoint resume of a pre-consolidation ``task(...)`` call). Current
    routing never emits legacy names, so live traffic is untouched.
    """
    if subagent_type in subagent_names:
        return subagent_type
    alias = LEGACY_SUBAGENT_ALIASES.get(subagent_type)
    if alias is not None and alias in subagent_names:
        logger.info(
            "[hitl_route] aliasing legacy subagent %r -> %r",
            subagent_type,
            alias,
        )
        return alias
    return subagent_type


def _billable_call_update(subagent_type: str, runtime: ToolRuntime) -> dict[str, Any]:
    """Build the per-call ``billable_calls`` delta plus an optional soft-cap warning.

    Always emits ``{subagent_type: 1}`` (a reducer accumulates it); when this
    call would cross the threshold, also adds a soft ``messages`` entry so the
    orchestrator self-limits on its next step.
    """
    delta: dict[str, Any] = {"billable_calls": {subagent_type: 1}}
    threshold = DEFAULT_SUBAGENT_BILLABLE_THRESHOLD
    if threshold <= 0:
        return delta
    prior = runtime.state.get("billable_calls") or {}
    # Count int values only so a malformed checkpoint can't crash us.
    prior_total = sum(v for v in prior.values() if isinstance(v, int))
    new_total = prior_total + 1
    if prior_total < threshold <= new_total:
        warn = (
            f"[budget warning] This turn has dispatched {new_total} "
            f"subagent calls (soft cap = {threshold}). Wrap up the "
            "user's request with what you have rather than launching "
            "more specialists; surface a partial answer if needed."
        )
        delta["_billable_warn_text"] = warn
    return delta


def _attach_billable(cmd: Command, subagent_type: str, runtime: ToolRuntime) -> Command:
    """Merge the per-call billable counter (and warning) into ``cmd``."""
    delta = _billable_call_update(subagent_type, runtime)
    warn_text = delta.pop("_billable_warn_text", None)
    # Copy so we don't mutate state shared with other tool returns.
    update = dict(getattr(cmd, "update", {}) or {})
    for key, value in delta.items():
        update[key] = value
    if warn_text:
        existing_msgs = list(update.get("messages") or [])
        existing_msgs.append(
            ToolMessage(content=warn_text, tool_call_id=runtime.tool_call_id)
        )
        update["messages"] = existing_msgs
    return Command(update=update)


def _safe_message_text(msg: Any) -> str:
    """Pull text out of a BaseMessage without using the ``.text`` property.

    ``.text`` crashes when ``content`` is ``None`` (common for tool-call
    AIMessages), and ``getattr`` won't catch it, so read ``content`` directly.
    """
    try:
        content = getattr(msg, "content", None)
    except Exception:
        content = None
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                block_text = block.get("text") or block.get("content")
                if isinstance(block_text, str):
                    parts.append(block_text)
        return " ".join(parts)
    return str(content)


def _build_tool_trace(messages: list[Any]) -> list[dict[str, Any]]:
    """Compress the subagent's messages into a compact tool trace.

    Entries (``{tool, status, preview}``) ride on the ToolMessage's
    ``additional_kwargs["surf_tool_trace"]`` for UI/observability; the LLM
    never sees them.
    """
    trace: list[dict[str, Any]] = []
    for msg in messages:
        tool_name = getattr(msg, "name", None)
        tool_call_id_attr = getattr(msg, "tool_call_id", None)
        if not tool_name and not tool_call_id_attr:
            # Only ToolMessages carry either field.
            continue
        status = getattr(msg, "status", None) or "ok"
        preview = _safe_message_text(msg).strip().replace("\n", " ")
        if len(preview) > 120:
            preview = preview[:117] + "..."
        trace.append(
            {
                "tool": tool_name or "<unknown>",
                "status": status,
                "preview": preview,
            }
        )
    return trace


def _return_command_with_state_update(result: dict, tool_call_id: str) -> Command:
    if "messages" not in result:
        msg = (
            "CompiledSubAgent must return a state containing a 'messages' key. "
            "Custom StateGraphs used with CompiledSubAgent should include 'messages' "
            "in their state schema to communicate results back to the main agent."
        )
        raise ValueError(msg)

    state_update = {k: v for k, v in result.items() if k not in EXCLUDED_STATE_KEYS}
    messages = result["messages"]
    if not messages:
        msg = (
            "CompiledSubAgent returned an empty 'messages' list. "
            "Subagents must produce at least one message so the parent has "
            "output to forward back to the user."
        )
        raise ValueError(msg)
    message_text = _safe_message_text(messages[-1]).rstrip()
    # Trace is observability-only; never let a bad frame kill the turn.
    try:
        tool_trace = _build_tool_trace(messages)
    except Exception:
        logger.exception(
            "Failed to build tool_trace for subagent return; continuing without trace."
        )
        tool_trace = []
    tool_msg = ToolMessage(message_text, tool_call_id=tool_call_id)
    if tool_trace:
        # surf_ prefix avoids collision with provider keys (e.g. cache_control).
        tool_msg.additional_kwargs["surf_tool_trace"] = tool_trace
    return Command(
        update={
            **state_update,
            "messages": [tool_msg],
        }
    )


def _resolve_context_hint(
    subagent_type: str,
    description: str,
    runtime: ToolRuntime,
    hint_providers: dict[str, ContextHintProvider],
) -> str | None:
    """Run the per-subagent hint provider; swallow & log any exception."""
    provider = hint_providers.get(subagent_type)
    if provider is None:
        return None
    try:
        hint = provider(runtime.state, description)
    except Exception:
        logger.exception(
            "Context-hint provider for subagent %r raised; skipping hint.",
            subagent_type,
        )
        return None
    if not hint or not isinstance(hint, str):
        return None
    cleaned = hint.strip()
    return cleaned or None


def _forward_mention_pins(subagent_state: dict, runtime: ToolRuntime) -> None:
    """Carry the turn's ``@``-mention pins from main context into subagent state.

    Subagents are compiled without a ``context_schema`` and invoked without
    ``context=``, so ``runtime.context`` (which holds the ``@``-mentioned
    document/folder ids) does not reach them. The ``task`` tool runs in the
    main runtime, which *does* have the context, so we copy the pins into the
    forwarded state where ``search_knowledge_base`` reads them. Only set keys
    when present so we never clobber pins already on state (e.g. nested
    ``ask_knowledge_base`` re-entry).
    """
    ctx = getattr(runtime, "context", None)
    if ctx is None:
        return
    for state_key, ctx_attr in (
        ("mentioned_document_ids", "mentioned_document_ids"),
        ("mentioned_folder_ids", "mentioned_folder_ids"),
    ):
        value = getattr(ctx, ctx_attr, None)
        if value:
            subagent_state[state_key] = list(value)


def _validate_and_prepare_state(
    subagent_type: str,
    description: str,
    runtime: ToolRuntime,
    *,
    resolve_subagent: Callable[[str], Runnable],
    hint_providers: dict[str, ContextHintProvider],
) -> tuple[Runnable, dict]:
    subagent = resolve_subagent(subagent_type)
    subagent_state = {
        k: v for k, v in runtime.state.items() if k not in EXCLUDED_STATE_KEYS
    }
    _forward_mention_pins(subagent_state, runtime)
    hint = _resolve_context_hint(subagent_type, description, runtime, hint_providers)
    if hint:
        # Tagged block so the subagent prompt can pattern-match the section.
        payload = f"<context_hint>\n{hint}\n</context_hint>\n\n{description}"
    else:
        payload = description
    subagent_state["messages"] = [HumanMessage(content=payload)]
    return subagent, subagent_state


def _merge_batch_results(
    results: list[tuple[int, str, dict | str, dict | None]],
    runtime: ToolRuntime,
) -> Command:
    """Combine per-child results into one Command with an aggregate ToolMessage.

    ``results`` tuples are ``(task_index, subagent_type, payload_or_error,
    child_state_update)``; output blocks are sorted by index so the LLM can
    map them back to dispatch order, and each child contributes a
    ``billable_calls`` increment to match single-mode accounting.
    """
    results.sort(key=lambda r: r[0])
    merged_state: dict[str, Any] = {}
    billable_delta: dict[str, int] = {}
    message_blocks: list[str] = []
    batch_trace: list[dict[str, Any]] = []
    for task_index, subagent_type, payload, state_update in results:
        billable_delta[subagent_type] = billable_delta.get(subagent_type, 0) + 1
        if isinstance(payload, str):
            # Pre-flight error or per-task exception text.
            message_blocks.append(f"[task {task_index}] {payload}")
            batch_trace.append(
                {
                    "task_index": task_index,
                    "subagent_type": subagent_type,
                    "status": "error",
                    "tool_trace": [],
                }
            )
            continue
        messages = payload.get("messages") or []
        last_text = _safe_message_text(messages[-1]).rstrip() if messages else ""
        message_blocks.append(f"[task {task_index}] {last_text or '<empty>'}")
        try:
            child_trace = _build_tool_trace(messages)
        except Exception:
            logger.exception(
                "Failed to build tool_trace for batch task_index=%d; continuing.",
                task_index,
            )
            child_trace = []
        batch_trace.append(
            {
                "task_index": task_index,
                "subagent_type": subagent_type,
                "status": "ok",
                "tool_trace": child_trace,
            }
        )
        if state_update:
            # Later tasks win on scalar collisions; reducer-backed fields
            # accumulate at apply time.
            merged_state.update(state_update)
    aggregate = "\n\n".join(message_blocks)
    aggregate_msg = ToolMessage(content=aggregate, tool_call_id=runtime.tool_call_id)
    if batch_trace:
        aggregate_msg.additional_kwargs["surf_tool_trace"] = batch_trace
    update: dict[str, Any] = {
        **merged_state,
        "billable_calls": billable_delta,
        "messages": [aggregate_msg],
    }
    # Soft-cap warning: check the cumulative count after attribution.
    threshold = DEFAULT_SUBAGENT_BILLABLE_THRESHOLD
    if threshold > 0:
        prior = runtime.state.get("billable_calls") or {}
        prior_total = sum(v for v in prior.values() if isinstance(v, int))
        new_total = prior_total + sum(billable_delta.values())
        if prior_total < threshold <= new_total:
            update["messages"].append(
                ToolMessage(
                    content=(
                        f"[budget warning] This turn has dispatched "
                        f"{new_total} subagent calls (soft cap = "
                        f"{threshold}). Wrap up the user's request with "
                        "what you have rather than launching more "
                        "specialists; surface a partial answer if needed."
                    ),
                    tool_call_id=runtime.tool_call_id,
                )
            )
    return Command(update=update)


async def _ainvoke_one_batch_child(
    *,
    task_index: int,
    subagent_type: str,
    description: str,
    runtime: ToolRuntime,
    semaphore: asyncio.Semaphore,
    subagent_names: set[str],
    resolve_subagent: Callable[[str], Runnable],
    hint_providers: dict[str, ContextHintProvider],
) -> tuple[int, str, dict | str, dict | None]:
    """Run one child of a batched ``task`` call under the concurrency cap.

    Errors are returned as text (slot 2) so one child's failure doesn't abort
    the batch. A child's ``GraphInterrupt`` is a hard failure for that child:
    batched HITL is intentionally out of scope.
    """
    async with semaphore:
        subagent_type = _canonical_subagent_type(subagent_type, subagent_names)
        if subagent_type not in subagent_names:
            allowed_types = ", ".join([f"`{k}`" for k in subagent_names])
            return (
                task_index,
                subagent_type,
                (
                    f"Subagent {subagent_type!r} does not exist; "
                    f"allowed: {allowed_types}"
                ),
                None,
            )
        subagent, subagent_state = _validate_and_prepare_state(
            subagent_type,
            description,
            runtime,
            resolve_subagent=resolve_subagent,
            hint_providers=hint_providers,
        )
        sub_config = subagent_invoke_config(runtime)
        started_at = time.perf_counter()
        try:
            result = await _ainvoke_with_timeout(
                subagent.ainvoke(subagent_state, config=sub_config),
                subagent_type=subagent_type,
                started_at=started_at,
            )
        except SubagentInvokeTimeoutError as exc:
            logger.warning(
                "Batch child %d (%s) timed out after %.1fs",
                task_index,
                subagent_type,
                exc.elapsed_seconds,
            )
            return (task_index, subagent_type, str(exc), None)
        except GraphInterrupt:
            # Batched HITL unsupported; fail this child so the batch finishes.
            logger.warning(
                "Batch child %d (%s) raised GraphInterrupt; batched HITL "
                "is not supported. Re-dispatch this task as a single "
                "(non-batched) `task(...)` call to get the HITL prompt.",
                task_index,
                subagent_type,
            )
            return (
                task_index,
                subagent_type,
                (
                    f"Subagent {subagent_type!r} needs human approval. "
                    "Re-dispatch this task as a single (non-batched) "
                    "`task(...)` call so the approval card can be shown."
                ),
                None,
            )
        except Exception as exc:
            logger.exception(
                "Batch child %d (%s) raised: %s",
                task_index,
                subagent_type,
                exc,
            )
            return (
                task_index,
                subagent_type,
                f"Subagent {subagent_type!r} error: {exc}",
                None,
            )
        child_state_update = {
            k: v for k, v in result.items() if k not in EXCLUDED_STATE_KEYS
        }
        return (task_index, subagent_type, result, child_state_update)


def _coerce_batch_arg(tasks: Any) -> list[dict] | str:
    """Rescue common LLM malformations of the ``tasks`` argument.

    Recovers a JSON-encoded array string and a single dict (instead of a
    1-element array), logging a WARN. Unrecoverable shapes return a string
    the caller surfaces as the tool error.
    """
    if isinstance(tasks, list):
        return tasks
    if isinstance(tasks, dict):
        logger.warning(
            "task: `tasks` was a single dict; coercing to a 1-element list. "
            "Orchestrators should send `tasks=[{...}]` directly."
        )
        return [tasks]
    if isinstance(tasks, str):
        stripped = tasks.strip()
        if not stripped:
            return "tasks: argument is empty."
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            return (
                f"tasks: argument is a string but not valid JSON ({exc.msg}). "
                "Send a JSON array of `{description, subagent_type}` objects."
            )
        logger.warning(
            "task: `tasks` was a JSON-encoded string; parsed to %s. "
            "Orchestrators should send a JSON array directly.",
            type(parsed).__name__,
        )
        return _coerce_batch_arg(parsed)
    return (
        f"tasks: unsupported type {type(tasks).__name__}; expected an array "
        "of `{description, subagent_type}` objects."
    )


async def _adispatch_batch(
    tasks: list[dict],
    runtime: ToolRuntime,
    *,
    subagent_names: set[str],
    resolve_subagent: Callable[[str], Runnable],
    hint_providers: dict[str, ContextHintProvider],
) -> Command | str:
    """Fan out the ``tasks`` array (size- and concurrency-capped).

    Returns one Command; the LLM sees one ``[task <index>]``-prefixed block
    per child, in input order.
    """
    if not tasks:
        return "tasks: array is empty; nothing to dispatch."
    if len(tasks) > MAX_SUBAGENT_BATCH_SIZE:
        return (
            f"tasks: too many children ({len(tasks)}); "
            f"max is {MAX_SUBAGENT_BATCH_SIZE}. Split the batch."
        )
    normalized: list[tuple[int, str, str]] = []
    for idx, item in enumerate(tasks):
        if not isinstance(item, dict):
            return f"tasks[{idx}]: must be an object with description+subagent_type."
        description = item.get("description")
        subagent_type = item.get("subagent_type")
        if not isinstance(description, str) or not description.strip():
            return f"tasks[{idx}]: missing or empty 'description'."
        if not isinstance(subagent_type, str) or not subagent_type.strip():
            return f"tasks[{idx}]: missing or empty 'subagent_type'."
        normalized.append((idx, subagent_type.strip(), description))
    semaphore = asyncio.Semaphore(DEFAULT_SUBAGENT_BATCH_CONCURRENCY)
    coros = [
        _ainvoke_one_batch_child(
            task_index=idx,
            subagent_type=subagent_type,
            description=description,
            runtime=runtime,
            semaphore=semaphore,
            subagent_names=subagent_names,
            resolve_subagent=resolve_subagent,
            hint_providers=hint_providers,
        )
        for idx, subagent_type, description in normalized
    ]
    results = await asyncio.gather(*coros)
    return _merge_batch_results(list(results), runtime)
