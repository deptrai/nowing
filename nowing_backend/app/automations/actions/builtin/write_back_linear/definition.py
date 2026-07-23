"""Register the ``write_back_linear`` action definition."""

from __future__ import annotations

from ...store import register_action
from ...types import ActionDefinition
from .factory import build_handler
from .params import LinearActionParams

WRITE_BACK_LINEAR_ACTION = ActionDefinition(
    type="write_back_linear",
    name="Write back to Linear",
    description="Create or update a Linear issue via the workspace's MCP connector.",
    params_model=LinearActionParams,
    build_handler=build_handler,
)

register_action(WRITE_BACK_LINEAR_ACTION)
