"""``build_handler`` for the ``write_back_telegram`` action."""

from __future__ import annotations

from typing import Any

from ...types import ActionContext, ActionHandler
from .invoke import write_back_telegram
from .params import TelegramActionParams


def build_handler(ctx: ActionContext) -> ActionHandler:
    """Return a handler closure that sends a Telegram message.

    ``execute_step`` already validates ``resolved_params`` against
    ``TelegramActionParams`` before the retry loop, so the handler builds the
    model instance without re-running validation to avoid deterministic
    ``ValidationError`` retries.
    """

    async def handle(params: dict[str, Any]) -> dict[str, Any]:
        validated = TelegramActionParams.model_construct(**params)
        return await write_back_telegram(ctx, validated)

    return handle
