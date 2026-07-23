"""Register the ``write_back_notion`` action definition."""

from __future__ import annotations

from ...store import register_action
from ...types import ActionDefinition
from .factory import build_handler
from .params import NotionActionParams

WRITE_BACK_NOTION_ACTION = ActionDefinition(
    type="write_back_notion",
    name="Write back to Notion",
    description="Create or update a Notion page via the workspace's MCP connector.",
    params_model=NotionActionParams,
    build_handler=build_handler,
)

register_action(WRITE_BACK_NOTION_ACTION)
