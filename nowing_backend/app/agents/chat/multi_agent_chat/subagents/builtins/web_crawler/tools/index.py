"""``web_crawler`` sub-agent tools: the unified web.crawl capability verb."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.shared.permissions import Ruleset
from app.capabilities.browser_operator.definition import BROWSER_OPERATOR_EXECUTE
from app.capabilities.core.access.agent import build_capability_tools
from app.capabilities.web.crawl.definition import WEB_CRAWL

NAME = "web_crawler"

RULESET = Ruleset(origin=NAME, rules=[])

_CI_VERBS = [WEB_CRAWL, BROWSER_OPERATOR_EXECUTE]


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> list[BaseTool]:
    d = {**(dependencies or {}), **kwargs}
    return build_capability_tools(
        workspace_id=d.get("workspace_id"),
        capabilities=_CI_VERBS,
        # Story 3.13 (D4/T4): thread the active chat principal through so an
        # agent-origin run is recorded with a creator and its memory extraction
        # is attributable instead of skipped as `missing_creator`.
        user_id=d.get("user_id"),
    )
