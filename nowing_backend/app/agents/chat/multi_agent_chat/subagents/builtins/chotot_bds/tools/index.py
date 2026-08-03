"""``chotot_bds`` sub-agent tools: the nha.chotot.com scrape capability verb."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.shared.permissions import Ruleset
from app.capabilities.chotot.scrape.definition import CHOTOT_BDS_SCRAPE
from app.capabilities.core.access.agent import build_capability_tools

NAME = "chotot_bds"

RULESET = Ruleset(origin=NAME, rules=[])

_CI_VERBS = [CHOTOT_BDS_SCRAPE]


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> list[BaseTool]:
    d = {**(dependencies or {}), **kwargs}
    return build_capability_tools(
        workspace_id=d.get("workspace_id"),
        capabilities=_CI_VERBS,
        user_id=d.get("user_id"),
    )
