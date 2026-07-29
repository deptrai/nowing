"""Capability framework kernel: registry contracts, store, billing, and access doors."""

from __future__ import annotations

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


async def execute_with_context(
    executor: Executor,
    *,
    payload: Any,
    ctx: CapabilityContext | None = None,
) -> Any:
    """Invoke a capability executor, passing context when the executor accepts it.

    Context-aware executors (e.g. ``chainlens.research``) accept a second
    positional ``CapabilityContext``. Legacy executors take only the payload;
    this helper falls back to the single-argument call so existing verbs keep
    working and the workspace context is still surfaced in the result.
    """

    async def _call() -> Any:
        if ctx is None:
            return await executor(payload)

        try:
            return await executor(payload, ctx)
        except TypeError as exc:
            msg = str(exc).lower()
            if "takes" in msg and "positional argument" in msg:
                return await executor(payload)
            if "unexpected keyword" in msg or "got an unexpected" in msg:
                return await executor(payload)
            raise

    result = await _call()

    if ctx is not None and isinstance(result, dict) and "workspace_id" not in result:
        result["workspace_id"] = ctx.workspace_id

    return result
