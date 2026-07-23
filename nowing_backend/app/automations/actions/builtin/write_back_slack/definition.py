"""Register the ``write_back_slack`` action definition."""

from __future__ import annotations

from ...store import register_action
from ...types import ActionDefinition
from .factory import build_handler
from .params import SlackActionParams

WRITE_BACK_SLACK_ACTION = ActionDefinition(
    type="write_back_slack",
    name="Write back to Slack",
    description="Send a Slack message via the workspace's MCP connector.",
    params_model=SlackActionParams,
    build_handler=build_handler,
)

register_action(WRITE_BACK_SLACK_ACTION)
