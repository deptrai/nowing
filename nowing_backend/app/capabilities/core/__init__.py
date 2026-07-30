"""Capability framework kernel: registry contracts, store, billing, and access doors."""

from __future__ import annotations

import inspect
import logging
from typing import Any

from app.capabilities.core.billing import charge_capability, gate_capability
from app.capabilities.core.store import (
    all_capabilities,
    get_capability,
    register_capability,
)
from app.capabilities.core.types import (
    BillableInput,
    BillableOutput,
    BillingUnit,
    Capability,
    CapabilityContext,
    Executor,
)

logger = logging.getLogger(__name__)

__all__ = [
    "BillableInput",
    "BillableOutput",
    "BillingUnit",
    "Capability",
    "CapabilityContext",
    "Executor",
    "all_capabilities",
    "charge_capability",
    "execute_with_context",
    "gate_capability",
    "get_capability",
    "register_capability",
]


def _executor_accepts_ctx(executor: Executor) -> bool:
    """Return True when ``executor`` has a ``ctx`` parameter or catches ``**kwargs``."""
    if executor is None:
        return False
    sig = inspect.signature(executor)
    if "ctx" in sig.parameters:
        return True
    return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())


def _executor_accepts_positional_ctx(executor: Executor) -> bool:
    """Return True when ``ctx`` can be passed as a second positional argument."""
    if executor is None:
        return False
    sig = inspect.signature(executor)
    ctx_param = sig.parameters.get("ctx")
    if ctx_param is not None and ctx_param.kind in (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    ):
        return True
    return any(
        p.kind == inspect.Parameter.VAR_POSITIONAL for p in sig.parameters.values()
    )


async def execute_with_context(
    executor: Executor,
    *,
    payload: Any,
    ctx: CapabilityContext | None = None,
) -> Any:
    """Invoke a capability executor, passing context when the executor accepts it.

    Context-aware executors (e.g. ``chainlens.research``) accept a second
    positional ``CapabilityContext``. Legacy executors take only the payload;
    this helper inspects the executor signature to choose the right arity and
    never falls back by catching a ``TypeError``.
    """
    if ctx is None or not _executor_accepts_ctx(executor):
        return await executor(payload)

    if _executor_accepts_positional_ctx(executor):
        return await executor(payload, ctx)
    return await executor(payload, ctx=ctx)
