"""``chainlens`` sub-agent tools: the ``chainlens.research`` capability verb."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.shared.permissions import Ruleset
from app.capabilities.chainlens.research.definition import CHAINLENS_RESEARCH
from app.capabilities.core.access.agent import build_capability_tools

NAME = "chainlens"

RULESET = Ruleset(origin=NAME, rules=[])

_CI_VERBS = [CHAINLENS_RESEARCH]


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> list[BaseTool]:
    d = {**(dependencies or {}), **kwargs}
    return build_capability_tools(
        workspace_id=d.get("workspace_id"),
        capabilities=_CI_VERBS,
    )
