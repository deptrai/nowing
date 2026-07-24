"""Automation-origin propagation for in-process memory writes (Story 6.5, AC-5).

A run's executor stamps the current automation run id into a contextvar for the
duration of the run. Any in-process memory write that happens inside the run —
e.g. the ``agent_task`` action's native ``update_memory`` tool calling
``MemoryRepository.create_memory`` — reads it (without a hand-passed kwarg) so
the repository knows the write originated from an automation and skips emitting
``memory.changed``. That is the loop guard (mechanism 1) that stops a
memory-writing automation from re-firing its own ``memory_change`` trigger.

Why a contextvar reaches the write: ``ContextVar`` values propagate across
``await`` within one asyncio task and are copied into child tasks at creation,
so a write anywhere in the run's async call graph sees the origin — even one
that opens its own ``async_session_maker`` session, because the session is
irrelevant to the context. It does NOT cross a process/HTTP boundary; a
cross-process write (an external MCP server calling the REST API) instead
threads the origin via the ``X-Automation-Run-Id`` header, and the selector's
mechanism-2 drop is the final backstop.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

# ``None`` means "no automation origin". A real run id is a positive serial PK,
# so 0 is never valid — callers treat 0/None identically (see the repository
# emit-skip and the selector drop, which both use truthiness).
current_automation_run_id: ContextVar[int | None] = ContextVar(
    "current_automation_run_id", default=None
)


@contextmanager
def automation_run_origin(run_id: int | None) -> Iterator[None]:
    """Mark every in-process memory write in this block as originating from ``run_id``.

    Used by the run executor to wrap a run's execution. Restores the previous
    value on exit so a reused event loop never leaks one run's origin into the
    next task.
    """
    token = current_automation_run_id.set(run_id)
    try:
        yield
    finally:
        current_automation_run_id.reset(token)


def get_current_automation_run_id() -> int | None:
    """Return the automation run id stamped on the current context, else ``None``."""
    return current_automation_run_id.get()
