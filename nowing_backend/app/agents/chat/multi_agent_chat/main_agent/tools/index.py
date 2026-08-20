"""Main-agent Nowing builtin tool names (not full ``new_chat``).

Connector integrations, MCP, deliverables, etc. are delegated via ``task`` subagents.
"""

from __future__ import annotations

MAIN_AGENT_NOWING_TOOL_NAMES_ORDERED: tuple[str, ...] = (
    "update_memory",
    "create_automation",
    "multi_source_lead_gen",
)

MAIN_AGENT_NOWING_TOOL_NAMES: frozenset[str] = frozenset(
    MAIN_AGENT_NOWING_TOOL_NAMES_ORDERED,
)
