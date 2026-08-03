"""Built-in action types — each in its own subpackage, self-registering at import."""

from __future__ import annotations

from . import (
    agent_task,  # noqa: F401
    continue_research,  # noqa: F401
    write_back_jira,  # noqa: F401
    write_back_linear,  # noqa: F401
    write_back_notion,  # noqa: F401
    write_back_slack,  # noqa: F401
    write_back_telegram,  # noqa: F401
)
