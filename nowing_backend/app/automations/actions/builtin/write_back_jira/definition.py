"""Register the ``write_back_jira`` action definition."""

from __future__ import annotations

from ...store import register_action
from ...types import ActionDefinition
from .factory import build_handler
from .params import JiraActionParams

WRITE_BACK_JIRA_ACTION = ActionDefinition(
    type="write_back_jira",
    name="Write back to Jira",
    description="Create or update a Jira issue via the workspace's MCP connector.",
    params_model=JiraActionParams,
    build_handler=build_handler,
)

register_action(WRITE_BACK_JIRA_ACTION)
