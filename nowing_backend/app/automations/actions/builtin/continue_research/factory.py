"""Build a ``continue_research`` handler closure."""

from __future__ import annotations

from typing import Any

from ...types import ActionContext, ActionHandler
from .invoke import continue_research


def build_handler(ctx: ActionContext) -> ActionHandler:
    """Return a handler closure that recalls a research thread's context."""

    async def handle(params: dict[str, Any]) -> dict[str, Any]:
        return await continue_research(ctx, params)

    return handle
