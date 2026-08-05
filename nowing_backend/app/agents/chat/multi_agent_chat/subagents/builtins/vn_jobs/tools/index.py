"""``vn_jobs`` sub-agent tools: per-source scrapes and aggregate."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.shared.permissions import Ruleset
from app.capabilities.core.access.agent import build_capability_tools
from app.capabilities.itviec.scrape.definition import ITVIEC_SCRAPE
from app.capabilities.topcv.scrape.definition import TOPCV_SCRAPE
from app.capabilities.vietnamworks.scrape.definition import VIETNAMWORKS_SCRAPE
from app.capabilities.vn_jobs.aggregate.definition import VN_JOBS_AGGREGATE

NAME = "vn_jobs"

RULESET = Ruleset(origin=NAME, rules=[])

_CI_VERBS = [
    VIETNAMWORKS_SCRAPE,
    TOPCV_SCRAPE,
    ITVIEC_SCRAPE,
    VN_JOBS_AGGREGATE,
]


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> list[BaseTool]:
    d = {**(dependencies or {}), **kwargs}
    return build_capability_tools(
        workspace_id=d.get("workspace_id"),
        capabilities=_CI_VERBS,
        user_id=d.get("user_id"),
    )
