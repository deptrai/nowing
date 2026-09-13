"""Build the ``task`` tool that invokes subagents with HITL bridging.

The tool's body is the only place where the parent and the subagent meet at
runtime: it reads the parent's stashed resume value, decides whether to send
fresh state or a targeted ``Command(resume=...)`` to the subagent, then
re-raises any new pending interrupt back to the parent.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Annotated, Any

from deepagents.middleware.subagents import TASK_TOOL_DESCRIPTION
from langchain.tools import BaseTool, ToolRuntime
from langchain_core.runnables import Runnable
from langchain_core.tools import StructuredTool
from langgraph.errors import GraphInterrupt
from langgraph.types import Command

from app.agents.chat.multi_agent_chat.subagents.shared.invocation import (
    subagent_invoke_config,
)
from app.agents.chat.multi_agent_chat.subagents.shared.spec import (
    SURF_CONTEXT_HINT_PROVIDER_KEY,
    ContextHintProvider,
)
from app.observability import metrics as ot_metrics, otel as ot
from app.utils.perf import get_perf_logger

from ..config import (
    consume_nowing_resume,
    drain_parent_null_resume,
    has_nowing_resume,
)
from ..constants import (
    DEFAULT_SUBAGENT_BATCH_CONCURRENCY,
    MAX_SUBAGENT_BATCH_SIZE,
)
from ..resume import (
    build_resume_command,
    fan_out_decisions_to_match,
    get_first_pending_subagent_interrupt,
    hitlrequest_action_count,
)
from ..spawn_paused import is_spawn_paused
from ._factory_helpers import (
    _adispatch_batch,
    _attach_billable,
    _canonical_subagent_type,
    _coerce_batch_arg,
    _return_command_with_state_update,
    _validate_and_prepare_state,
)
from ._helpers import (
    SubagentInvokeTimeoutError,
    _ainvoke_with_timeout,
    _reraise_stamped_subagent_interrupt,
    _synthesize_timeout_command,
)

logger = logging.getLogger(__name__)
_perf_log = get_perf_logger()


def build_task_tool_with_parent_config(
    subagents: list[dict[str, Any]],
    task_description: str | None = None,
    *,
    workspace_id: int | None = None,
    resolve_subagent: Callable[[str], Runnable] | None = None,
) -> BaseTool:
    """Upstream ``_build_task_tool`` + parent ``runtime.config`` propagation + resume bridging.

    ``subagents`` are lightweight descriptors (``name``/``description`` + the
    optional context-hint provider); the actual compiled graph is fetched
    lazily via ``resolve_subagent(name)`` so subagent ``create_agent`` cost is
    paid on first ``task(name)`` use rather than at graph-build time.

    For backward compatibility (and tests), ``resolve_subagent`` may be omitted
    when every descriptor already carries a pre-compiled ``runnable``; in that
    case a trivial dict-backed resolver is used.
    """
    subagent_names: set[str] = {spec["name"] for spec in subagents}

    if resolve_subagent is None:
        _eager_graphs: dict[str, Runnable] = {
            spec["name"]: spec["runnable"] for spec in subagents if "runnable" in spec
        }

        def resolve_subagent(name: str) -> Runnable:
            return _eager_graphs[name]

    # Sparse map of opt-in context-hint providers; each runs once per task()
    # call to prepend a string to the subagent's first HumanMessage. Failures
    # are swallowed so a broken hint never blocks the task.
    subagent_hint_providers: dict[str, ContextHintProvider] = {
        spec["name"]: provider
        for spec in subagents
        if (provider := spec.get(SURF_CONTEXT_HINT_PROVIDER_KEY)) is not None
    }
    subagent_description_str = "\n".join(
        f"- {s['name']}: {s['description']}" for s in subagents
    )

    if task_description is None:
        description = TASK_TOOL_DESCRIPTION.format(
            available_agents=subagent_description_str
        )
    elif "{available_agents}" in task_description:
        description = task_description.format(available_agents=subagent_description_str)
    else:
        description = task_description

    def task(
        description: Annotated[
            str | None,
            "Single-mode: a detailed task description for the subagent. Required unless `tasks` is provided.",
        ] = None,
        subagent_type: Annotated[
            str | None,
            "Single-mode: the type of subagent to use. Required unless `tasks` is provided.",
        ] = None,
        runtime: ToolRuntime = None,  # type: ignore[assignment]
        tasks: Annotated[
            list[dict] | None,
            (
                "Batch-mode: array of `{description, subagent_type}` objects. "
                "Synchronous path does not support batch mode; orchestrators "
                "must use the async event loop to fan out."
            ),
        ] = None,
    ) -> str | Command:
        if tasks is not None:
            return (
                "task: batch mode (`tasks=[...]`) is only supported on the async "
                "path. Nowing orchestrators always run in an event loop, so "
                "this should never fire — file a bug if you see it."
            )
        if not description or not subagent_type:
            return (
                "task: must provide either single-mode (`description`+`subagent_type`) "
                "or batch-mode (`tasks`)."
            )
        subagent_type = _canonical_subagent_type(subagent_type, subagent_names)
        if subagent_type not in subagent_names:
            allowed_types = ", ".join([f"`{k}`" for k in subagent_names])
            return (
                f"We cannot invoke subagent {subagent_type} because it does not exist, "
                f"the only allowed types are {allowed_types}"
            )
        if not runtime.tool_call_id:
            raise ValueError("Tool call ID is required for subagent invocation")
        subagent, subagent_state = _validate_and_prepare_state(
            subagent_type,
            description,
            runtime,
            resolve_subagent=resolve_subagent,
            hint_providers=subagent_hint_providers,
        )
        sub_config = subagent_invoke_config(runtime)

        # Resume bridge: forward the parent's stashed decision into the
        # subagent's pending ``interrupt()``, targeted by id.
        pending_id: str | None = None
        pending_value: Any = None
        get_state = getattr(subagent, "get_state", None)
        if callable(get_state):
            try:
                snapshot = get_state(sub_config)
                pending_id, pending_value = get_first_pending_subagent_interrupt(
                    snapshot
                )
            except Exception:  # subagent sync state lookup failure; re-raise if resume queued or fallback
                # Fail loud if a resume is queued: silent fallback would
                # replay the original interrupt to the user.
                if has_nowing_resume(runtime):
                    logger.exception(
                        "Subagent %r get_state raised with resume queued; re-raising.",
                        subagent_type,
                    )
                    raise
                logger.debug(
                    "Subagent get_state failed; falling back to fresh invoke",
                    exc_info=True,
                )

        invoke_path = "resume" if pending_value is not None else "fresh"
        invoke_start = time.perf_counter()
        invoke_outcome = "ok"
        if pending_value is not None:
            resume_value = consume_nowing_resume(runtime)
            if resume_value is None:
                # A pending interrupt must have a queued resume; otherwise replay
                # would silently re-prompt the user. Raise instead.
                raise RuntimeError(
                    f"Subagent {subagent_type!r} has a pending interrupt but no "
                    "nowing_resume_value on config; resume bridge is broken."
                )
            expected = hitlrequest_action_count(pending_value)
            resume_value = fan_out_decisions_to_match(resume_value, expected)
            # Stop the parent's resume leaking into subagent interrupts via
            # langgraph's parent_scratchpad fallback.
            drain_parent_null_resume(runtime)
            with ot.subagent_invoke_span(
                subagent_type=subagent_type, path=invoke_path
            ) as sp:
                try:
                    result = subagent.invoke(
                        build_resume_command(resume_value, pending_id),
                        config=sub_config,
                    )
                    sp.set_attribute("subagent.outcome", invoke_outcome)
                except GraphInterrupt as gi:
                    invoke_outcome = "interrupted"
                    sp.set_attribute("subagent.outcome", invoke_outcome)
                    ot_metrics.record_subagent_invoke_duration(
                        (time.perf_counter() - invoke_start) * 1000,
                        subagent_type=subagent_type,
                        path=invoke_path,
                        outcome=invoke_outcome,
                    )
                    ot_metrics.record_subagent_invoke_outcome(
                        subagent_type=subagent_type,
                        path=invoke_path,
                        outcome=invoke_outcome,
                    )
                    _reraise_stamped_subagent_interrupt(gi, runtime.tool_call_id)
                except Exception:  # subagent sync invoke failure; record metric and re-raise interrupt or bubble
                    invoke_outcome = "error"
                    sp.set_attribute("subagent.outcome", invoke_outcome)
                    ot_metrics.record_subagent_invoke_duration(
                        (time.perf_counter() - invoke_start) * 1000,
                        subagent_type=subagent_type,
                        path=invoke_path,
                        outcome=invoke_outcome,
                    )
                    ot_metrics.record_subagent_invoke_outcome(
                        subagent_type=subagent_type,
                        path=invoke_path,
                        outcome=invoke_outcome,
                    )
                    raise
        else:
            with ot.subagent_invoke_span(
                subagent_type=subagent_type, path=invoke_path
            ) as sp:
                try:
                    result = subagent.invoke(subagent_state, config=sub_config)
                    sp.set_attribute("subagent.outcome", invoke_outcome)
                except GraphInterrupt as gi:
                    invoke_outcome = "interrupted"
                    sp.set_attribute("subagent.outcome", invoke_outcome)
                    ot_metrics.record_subagent_invoke_duration(
                        (time.perf_counter() - invoke_start) * 1000,
                        subagent_type=subagent_type,
                        path=invoke_path,
                        outcome=invoke_outcome,
                    )
                    ot_metrics.record_subagent_invoke_outcome(
                        subagent_type=subagent_type,
                        path=invoke_path,
                        outcome=invoke_outcome,
                    )
                    _reraise_stamped_subagent_interrupt(gi, runtime.tool_call_id)
                except Exception:  # subagent sync retry invoke failure; record metric and re-raise interrupt or bubble
                    invoke_outcome = "error"
                    sp.set_attribute("subagent.outcome", invoke_outcome)
                    ot_metrics.record_subagent_invoke_duration(
                        (time.perf_counter() - invoke_start) * 1000,
                        subagent_type=subagent_type,
                        path=invoke_path,
                        outcome=invoke_outcome,
                    )
                    ot_metrics.record_subagent_invoke_outcome(
                        subagent_type=subagent_type,
                        path=invoke_path,
                        outcome=invoke_outcome,
                    )
                    raise
        invoke_elapsed_ms = (time.perf_counter() - invoke_start) * 1000
        ot_metrics.record_subagent_invoke_duration(
            invoke_elapsed_ms,
            subagent_type=subagent_type,
            path=invoke_path,
            outcome=invoke_outcome,
        )
        ot_metrics.record_subagent_invoke_outcome(
            subagent_type=subagent_type,
            path=invoke_path,
            outcome=invoke_outcome,
        )
        return _return_command_with_state_update(result, runtime.tool_call_id)

    async def atask(
        description: Annotated[
            str | None,
            "Single-mode: a detailed task description for the subagent. Required unless `tasks` is provided.",
        ] = None,
        subagent_type: Annotated[
            str | None,
            "Single-mode: the type of subagent to use. Required unless `tasks` is provided.",
        ] = None,
        runtime: ToolRuntime = None,  # type: ignore[assignment]
        tasks: Annotated[
            list[dict] | None,
            (
                "Batch-mode: array of `{description, subagent_type}` objects "
                "to fan out concurrently (max "
                f"{MAX_SUBAGENT_BATCH_SIZE}, concurrency "
                f"{DEFAULT_SUBAGENT_BATCH_CONCURRENCY}). Mutually exclusive "
                "with single-mode args. Batched children do not support "
                "human-in-the-loop interrupts; re-dispatch as single mode "
                "if a child needs approval."
            ),
        ] = None,
    ) -> str | Command:
        atask_start = time.perf_counter()
        # Ops kill switch: short-circuit every task() call for this workspace
        # so the orchestrator stops hammering downstream APIs.
        if await is_spawn_paused(workspace_id):
            logger.warning(
                "[hitl_route] atask SPAWN_PAUSED: workspace_id=%s tool_call_id=%s",
                workspace_id,
                runtime.tool_call_id,
            )
            return (
                "task: subagent dispatch is currently paused for this workspace. "
                "Acknowledge to the user that delegation is temporarily disabled "
                "(ops kill switch); do not retry until the pause is lifted."
            )
        if tasks is not None:
            if description or subagent_type:
                return (
                    "task: cannot combine `tasks` with `description`/`subagent_type`. "
                    "Use either single-mode (description+subagent_type) or batch-mode (tasks)."
                )
            if not runtime.tool_call_id:
                raise ValueError("Tool call ID is required for subagent invocation")
            coerced = _coerce_batch_arg(tasks)
            if isinstance(coerced, str):
                return coerced
            logger.info(
                "[hitl_route] atask BATCH ENTRY: size=%d tool_call_id=%s",
                len(coerced),
                runtime.tool_call_id,
            )
            return await _adispatch_batch(
                coerced,
                runtime,
                subagent_names=subagent_names,
                resolve_subagent=resolve_subagent,
                hint_providers=subagent_hint_providers,
            )
        if not description or not subagent_type:
            return (
                "task: must provide either single-mode (`description`+`subagent_type`) "
                "or batch-mode (`tasks`)."
            )
        logger.info(
            "[hitl_route] atask ENTRY: subagent_type=%r tool_call_id=%s",
            subagent_type,
            runtime.tool_call_id,
        )
        subagent_type = _canonical_subagent_type(subagent_type, subagent_names)
        if subagent_type not in subagent_names:
            allowed_types = ", ".join([f"`{k}`" for k in subagent_names])
            return (
                f"We cannot invoke subagent {subagent_type} because it does not exist, "
                f"the only allowed types are {allowed_types}"
            )
        if not runtime.tool_call_id:
            raise ValueError("Tool call ID is required for subagent invocation")
        subagent, subagent_state = _validate_and_prepare_state(
            subagent_type,
            description,
            runtime,
            resolve_subagent=resolve_subagent,
            hint_providers=subagent_hint_providers,
        )
        sub_config = subagent_invoke_config(runtime)

        # Resume bridge — see ``task`` above.
        pending_id: str | None = None
        pending_value: Any = None
        aget_state_elapsed = 0.0
        aget_state = getattr(subagent, "aget_state", None)
        if callable(aget_state):
            aget_state_start = time.perf_counter()
            try:
                snapshot = await aget_state(sub_config)
                pending_id, pending_value = get_first_pending_subagent_interrupt(
                    snapshot
                )
            except Exception:  # subagent async state lookup failure; re-raise if resume queued or fallback
                if has_nowing_resume(runtime):
                    logger.exception(
                        "Subagent %r aget_state raised with resume queued; re-raising.",
                        subagent_type,
                    )
                    raise
                logger.debug(
                    "Subagent aget_state failed; falling back to fresh ainvoke",
                    exc_info=True,
                )
            finally:
                aget_state_elapsed = time.perf_counter() - aget_state_start

        invoke_path = "resume" if pending_value is not None else "fresh"
        ainvoke_start = time.perf_counter()
        ainvoke_outcome = "ok"
        try:
            if pending_value is not None:
                resume_value = consume_nowing_resume(runtime)
                if resume_value is None:
                    raise RuntimeError(
                        f"Subagent {subagent_type!r} has a pending interrupt but no "
                        "nowing_resume_value on config; resume bridge is broken."
                    )
                expected = hitlrequest_action_count(pending_value)
                resume_value = fan_out_decisions_to_match(resume_value, expected)
                # Stop the parent's resume leaking into subagent interrupts via
                # langgraph's parent_scratchpad fallback.
                drain_parent_null_resume(runtime)
                with ot.subagent_invoke_span(
                    subagent_type=subagent_type, path=invoke_path
                ) as sp:
                    try:
                        result = await _ainvoke_with_timeout(
                            subagent.ainvoke(
                                build_resume_command(resume_value, pending_id),
                                config=sub_config,
                            ),
                            subagent_type=subagent_type,
                            started_at=ainvoke_start,
                        )
                        sp.set_attribute("subagent.outcome", ainvoke_outcome)
                    except SubagentInvokeTimeoutError as exc:
                        ainvoke_outcome = "timeout"
                        sp.set_attribute("subagent.outcome", ainvoke_outcome)
                        ot_metrics.record_subagent_invoke_duration(
                            (time.perf_counter() - ainvoke_start) * 1000,
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        ot_metrics.record_subagent_invoke_outcome(
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        logger.warning(
                            "Subagent %r ainvoke (resume) timed out after %.1fs",
                            subagent_type,
                            exc.elapsed_seconds,
                        )
                        return _synthesize_timeout_command(
                            exc, tool_call_id=runtime.tool_call_id
                        )
                    except GraphInterrupt as gi:
                        ainvoke_outcome = "interrupted"
                        sp.set_attribute("subagent.outcome", ainvoke_outcome)
                        ot_metrics.record_subagent_invoke_duration(
                            (time.perf_counter() - ainvoke_start) * 1000,
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        ot_metrics.record_subagent_invoke_outcome(
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        _perf_log.info(
                            "[hitl_route] atask EXIT subagent_type=%r path=%s outcome=%s "
                            "aget_state=%.3fs ainvoke=%.3fs total=%.3fs",
                            subagent_type,
                            invoke_path,
                            ainvoke_outcome,
                            aget_state_elapsed,
                            time.perf_counter() - ainvoke_start,
                            time.perf_counter() - atask_start,
                        )
                        _reraise_stamped_subagent_interrupt(gi, runtime.tool_call_id)
                    except Exception:  # subagent async invoke failure; record metric and re-raise interrupt or bubble
                        ainvoke_outcome = "error"
                        sp.set_attribute("subagent.outcome", ainvoke_outcome)
                        ot_metrics.record_subagent_invoke_duration(
                            (time.perf_counter() - ainvoke_start) * 1000,
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        ot_metrics.record_subagent_invoke_outcome(
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        raise
            else:
                with ot.subagent_invoke_span(
                    subagent_type=subagent_type, path=invoke_path
                ) as sp:
                    try:
                        result = await _ainvoke_with_timeout(
                            subagent.ainvoke(subagent_state, config=sub_config),
                            subagent_type=subagent_type,
                            started_at=ainvoke_start,
                        )
                        sp.set_attribute("subagent.outcome", ainvoke_outcome)
                    except SubagentInvokeTimeoutError as exc:
                        ainvoke_outcome = "timeout"
                        sp.set_attribute("subagent.outcome", ainvoke_outcome)
                        ot_metrics.record_subagent_invoke_duration(
                            (time.perf_counter() - ainvoke_start) * 1000,
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        ot_metrics.record_subagent_invoke_outcome(
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        logger.warning(
                            "Subagent %r ainvoke (fresh) timed out after %.1fs",
                            subagent_type,
                            exc.elapsed_seconds,
                        )
                        return _synthesize_timeout_command(
                            exc, tool_call_id=runtime.tool_call_id
                        )
                    except GraphInterrupt as gi:
                        ainvoke_outcome = "interrupted"
                        sp.set_attribute("subagent.outcome", ainvoke_outcome)
                        ot_metrics.record_subagent_invoke_duration(
                            (time.perf_counter() - ainvoke_start) * 1000,
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        ot_metrics.record_subagent_invoke_outcome(
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        _perf_log.info(
                            "[hitl_route] atask EXIT subagent_type=%r path=%s outcome=%s "
                            "aget_state=%.3fs ainvoke=%.3fs total=%.3fs",
                            subagent_type,
                            invoke_path,
                            ainvoke_outcome,
                            aget_state_elapsed,
                            time.perf_counter() - ainvoke_start,
                            time.perf_counter() - atask_start,
                        )
                        _reraise_stamped_subagent_interrupt(gi, runtime.tool_call_id)
                    except Exception:  # subagent async retry invoke failure; record metric and re-raise interrupt or bubble
                        ainvoke_outcome = "error"
                        sp.set_attribute("subagent.outcome", ainvoke_outcome)
                        ot_metrics.record_subagent_invoke_duration(
                            (time.perf_counter() - ainvoke_start) * 1000,
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        ot_metrics.record_subagent_invoke_outcome(
                            subagent_type=subagent_type,
                            path=invoke_path,
                            outcome=ainvoke_outcome,
                        )
                        raise
            ainvoke_elapsed = time.perf_counter() - ainvoke_start
        except GraphInterrupt:
            raise

        merge_start = time.perf_counter()
        cmd = _return_command_with_state_update(result, runtime.tool_call_id)
        merge_elapsed = time.perf_counter() - merge_start
        _perf_log.info(
            "[hitl_route] atask EXIT subagent_type=%r path=%s outcome=%s "
            "aget_state=%.3fs ainvoke=%.3fs merge=%.3fs total=%.3fs",
            subagent_type,
            invoke_path,
            ainvoke_outcome,
            aget_state_elapsed,
            ainvoke_elapsed,
            merge_elapsed,
            time.perf_counter() - atask_start,
        )
        ot_metrics.record_subagent_invoke_duration(
            ainvoke_elapsed * 1000,
            subagent_type=subagent_type,
            path=invoke_path,
            outcome=ainvoke_outcome,
        )
        ot_metrics.record_subagent_invoke_outcome(
            subagent_type=subagent_type,
            path=invoke_path,
            outcome=ainvoke_outcome,
        )
        return _attach_billable(cmd, subagent_type, runtime)

    return StructuredTool.from_function(
        name="task",
        func=task,
        coroutine=atask,
        description=description,
    )
