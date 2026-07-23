"""Build a ``write_back_linear`` handler closure."""

from __future__ import annotations

from typing import Any

from ...types import ActionContext, ActionHandler
from .invoke import write_back
from .params import LinearActionParams


def build_handler(ctx: ActionContext) -> ActionHandler:
    """Return a handler closure that validates params and writes to Linear."""

    async def handle(params: dict[str, Any]) -> dict[str, Any]:
        return await write_back(ctx, params)

    return handle
