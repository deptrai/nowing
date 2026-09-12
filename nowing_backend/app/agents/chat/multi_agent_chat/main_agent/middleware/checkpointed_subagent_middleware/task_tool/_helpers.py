"""Module-level helpers for the ``task`` tool: timeout + interrupt stamping.

Split out of the original ``task_tool.py`` — see :mod:`._factory` for the
``build_task_tool_with_parent_config`` factory that consumes these.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable
from typing import NoReturn, TypeVar

from langchain_core.messages import ToolMessage
from langgraph.errors import GraphInterrupt
from langgraph.types import Command, Interrupt

from ..constants import DEFAULT_SUBAGENT_INVOKE_TIMEOUT_SECONDS
from ..propagation import wrap_with_tool_call_id

logger = logging.getLogger(__name__)


class SubagentInvokeTimeoutError(Exception):
    """Raised when ``subagent.ainvoke`` exceeds the configured wall-clock budget.

    Carries the subagent name and the elapsed seconds so the caller can
    synthesize a ToolMessage that the orchestrator can act on (re-route,
    surface to the user, or retry with a smaller scope).
    """

    def __init__(self, subagent_type: str, elapsed_seconds: float) -> None:
        super().__init__(
            f"subagent {subagent_type!r} exceeded "
            f"{DEFAULT_SUBAGENT_INVOKE_TIMEOUT_SECONDS:.0f}s budget "
            f"(elapsed={elapsed_seconds:.1f}s)"
        )
        self.subagent_type = subagent_type
        self.elapsed_seconds = elapsed_seconds


_T = TypeVar("_T")


async def _ainvoke_with_timeout[T](
    coro: Awaitable[_T], *, subagent_type: str, started_at: float
) -> _T:
    """Apply the subagent invoke timeout to ``coro`` (non-positive disables it).

    On expiry the task is cancelled and :class:`SubagentInvokeTimeoutError` is
    raised for the caller to turn into a synthetic ToolMessage.
    """
    timeout = DEFAULT_SUBAGENT_INVOKE_TIMEOUT_SECONDS
    if timeout <= 0:
        return await coro
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except TimeoutError as exc:
        elapsed = time.perf_counter() - started_at
        raise SubagentInvokeTimeoutError(subagent_type, elapsed) from exc


def _synthesize_timeout_command(
    exc: SubagentInvokeTimeoutError, *, tool_call_id: str
) -> Command:
    """Turn a :class:`SubagentInvokeTimeoutError` into a ToolMessage the parent can read."""
    content = (
        f"Subagent {exc.subagent_type!r} timed out after "
        f"{exc.elapsed_seconds:.1f}s (budget="
        f"{DEFAULT_SUBAGENT_INVOKE_TIMEOUT_SECONDS:.0f}s). "
        "The work was cancelled. Treat as status=error; re-route with a "
        "narrower scope or different specialist."
    )
    return Command(
        update={"messages": [ToolMessage(content=content, tool_call_id=tool_call_id)]}
    )


def _reraise_stamped_subagent_interrupt(
    gi: GraphInterrupt, tool_call_id: str
) -> NoReturn:
    """Stamp ``tool_call_id`` onto each pending interrupt value and re-raise.

    See :mod:`...propagation` for why this stamp is required for resume routing.
    Chained via ``from gi`` so tracebacks point at the subagent's original
    ``interrupt(...)`` site.
    """
    interrupts = gi.args[0] if gi.args else ()
    stamped = tuple(
        Interrupt(
            value=wrap_with_tool_call_id(i.value, tool_call_id),
            id=i.id,
        )
        for i in interrupts
    )
    logger.info(
        "[hitl_route] stamped %d subagent interrupt(s) with tool_call_id=%s",
        len(stamped),
        tool_call_id,
    )
    raise GraphInterrupt(stamped) from gi
