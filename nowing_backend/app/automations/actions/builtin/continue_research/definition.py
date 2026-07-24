"""Register the ``continue_research`` action definition."""

from __future__ import annotations

from ...store import register_action
from ...types import ActionDefinition
from .factory import build_handler
from .params import ContinueResearchActionParams

CONTINUE_RESEARCH_ACTION = ActionDefinition(
    type="continue_research",
    name="Continue research",
    description=(
        "Recall a saved research thread's memories and prior citations "
        "(reuses the research-continuity recall + citation aggregation)."
    ),
    params_model=ContinueResearchActionParams,
    build_handler=build_handler,
)

register_action(CONTINUE_RESEARCH_ACTION)
