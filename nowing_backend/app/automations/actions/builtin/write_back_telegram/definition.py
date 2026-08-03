"""Register the ``write_back_telegram`` action definition."""

from __future__ import annotations

from ...store import register_action
from ...types import ActionDefinition
from .factory import build_handler
from .params import TelegramActionParams

WRITE_BACK_TELEGRAM_ACTION = ActionDefinition(
    type="write_back_telegram",
    name="Write back to Telegram",
    description="Send a Telegram message via a workspace or system account.",
    params_model=TelegramActionParams,
    build_handler=build_handler,
)

register_action(WRITE_BACK_TELEGRAM_ACTION)
