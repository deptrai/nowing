"""Mode-aware tool call budget and availability middleware.

Enforces per-mode limits for ``new_chat`` / ``resume_chat`` by reading
``configurable.research_mode`` at runtime. It blocks disallowed tools and
caps the number of expensive subagent invocations, then forces the agent to
answer when the budget is exhausted.

Categories:
- ``kb``: ``ask_knowledge_base`` and ``task(..., subagent_type="knowledge_base")``
- ``non_kb``: all other ``task`` subagent calls, including web research and
  ``chainlens.research``
- ``other``: built-in main-agent tools such as ``update_memory``,
  ``create_automation``, ``read_run``, ``search_run``

``other`` calls are not budgeted because they do not drive the cost/latency
regressions the mode policy targets. They still flow through the existing
``ToolCallLimitMiddleware`` (run limit 80).

ponytail: ``task`` batch mode (``args["tasks"]``) is expanded here so each
subagent counts toward the budget. A mixed batch is blocked if any of its
subagents violate the mode. The final ``AIMessage`` is left untouched; blocked
subagents return ``ToolMessage`` errors and are not executed.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from typing import Any

from langchain.agents.middleware import hook_config
from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ContextT,
    ResponseT,
)
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.config import get_config
from langgraph.runtime import Runtime

from app.agents.chat.multi_agent_chat.shared.feature_flags import AgentFeatureFlags
from app.agents.chat.multi_agent_chat.shared.middleware.flags import enabled

logger = logging.getLogger(__name__)


# per-mode budget: (kb_calls, non_kb_calls, total_calls)
# total is the hard cap across expensive calls.
_MODE_BUDGETS: dict[str, tuple[int, int, int]] = {
    "speed": (1, 0, 1),
    "balanced": (2, 1, 3),
    "quality": (3, 2, 5),
    "auto": (2, 5, 5),
}

# Subagent names that count as knowledge-base calls.
_KB_SUBAGENTS: frozenset[str] = frozenset({"knowledge_base", "knowledge_base_readonly"})

# Subagent names that are web/deep-research and therefore explicitly gated
# in speed/balanced modes.
_WEB_RESEARCH_SUBAGENTS: frozenset[str] = frozenset(
    {
        "chainlens",
        "google_search",
        "web_crawler",
        "google_maps",
        "reddit",
        "youtube",
        "tiktok",
        "instagram",
        "amazon",
        "batdongsan",
        "cafef",
        "chotot_bds",
        "muaban_bds",
    }
)

# Tools that are always allowed and do not count against mode budgets.
_OTHER_TOOLS: frozenset[str] = frozenset(
    {"update_memory", "create_automation", "read_run", "search_run"}
)


def _config_from_runtime(runtime: Runtime[Any] | None) -> dict[str, Any]:
    """Best-effort RunnableConfig: prefer ``get_config()``, fall back to ``runtime.config``."""
    try:
        cfg = get_config() or {}
    except Exception:
        logger.debug("get_config() failed, falling back to runtime.config", exc_info=True)
        cfg = getattr(runtime, "config", None) or {}
    if not isinstance(cfg, dict):
        return {}
    return cfg


def _get_mode_from_config(runtime: Runtime[Any] | None = None) -> str:
    """Read ``research_mode`` from the active LangGraph RunnableConfig."""
    cfg = _config_from_runtime(runtime)
    mode = (cfg.get("configurable") or {}).get("research_mode")
    if mode is None:
        return "auto"
    if isinstance(mode, str):
        mode = mode.lower()
    if mode not in _MODE_BUDGETS:
        logger.warning("Unknown research_mode %r, falling back to auto", mode)
        return "auto"
    return mode


def _call_key_from_config(runtime: Runtime[Any] | None = None) -> str:
    """Build a per-turn counter key from ``thread_id`` and ``turn_id``."""
    cfg = _config_from_runtime(runtime)
    configurable = cfg.get("configurable") or {}
    thread_id = configurable.get("thread_id") or "no_thread"
    turn_id = configurable.get("turn_id") or "no_turn"
    return f"{thread_id}::{turn_id}"


@dataclass(frozen=True, slots=True)
class _CallItem:
    """One budget-able invocation inside a tool call."""

    category: str  # "kb" | "non_kb" | "other"
    subagent: str | None


@dataclass
class _CallBreakdown:
    """Aggregated counts for a single tool call (which may be a batch)."""

    items: list[_CallItem]

    @property
    def kb_count(self) -> int:
        return sum(1 for i in self.items if i.category == "kb")

    @property
    def non_kb_count(self) -> int:
        return sum(1 for i in self.items if i.category == "non_kb")

    @property
    def other_count(self) -> int:
        return sum(1 for i in self.items if i.category == "other")

    @property
    def is_all_other(self) -> bool:
        return self.other_count == len(self.items)

    @property
    def subagent_names(self) -> list[str]:
        return [i.subagent or "?" for i in self.items if i.subagent is not None]

    @property
    def has_chainlens(self) -> bool:
        return any(i.subagent == "chainlens" for i in self.items)

    @property
    def has_web_research(self) -> bool:
        return any(i.subagent in _WEB_RESEARCH_SUBAGENTS for i in self.items)


def _breakdown_tool_call(tool_call: dict[str, Any]) -> _CallBreakdown:
    """Expand a tool call into one or more ``_CallItem``s for budget checks."""
    name = tool_call.get("name")
    args = tool_call.get("args") or {}

    if name == "ask_knowledge_base":
        return _CallBreakdown(items=[_CallItem("kb", None)])

    if name == "task":
        tasks = args.get("tasks")
        if isinstance(tasks, list) and tasks:
            items: list[_CallItem] = []
            for t in tasks:
                subagent = (t or {}).get("subagent_type")
                if subagent is None:
                    logger.debug("task tool call missing subagent_type, treating as non_kb")
                if subagent in _KB_SUBAGENTS:
                    items.append(_CallItem("kb", subagent))
                else:
                    items.append(_CallItem("non_kb", subagent))
            return _CallBreakdown(items=items)

        subagent = args.get("subagent_type")
        if subagent in _KB_SUBAGENTS:
            return _CallBreakdown(items=[_CallItem("kb", subagent)])
        return _CallBreakdown(items=[_CallItem("non_kb", subagent)])

    if name in _OTHER_TOOLS:
        return _CallBreakdown(items=[_CallItem("other", None)])

    # Unknown tools are treated as non-kb and still subject to total cap.
    return _CallBreakdown(items=[_CallItem("non_kb", None)])


class _ModeBudgetCounter:
    """Per-turn mutable counters protected from unbounded growth."""

    __slots__ = ("kb", "non_kb", "total")

    def __init__(self) -> None:
        self.kb = 0
        self.non_kb = 0
        self.total = 0


@hook_config(can_jump_to=["end"])
class ModeBudgetMiddleware(AgentMiddleware[AgentState[ResponseT], ContextT, ResponseT]):
    """Cap and filter main-agent tool calls by ``research_mode``."""

    def __init__(self, *, max_history: int = 1000) -> None:
        super().__init__()
        self._counters: dict[str, _ModeBudgetCounter] = {}
        # Prevent memory growth from long-lived cross-thread cache.
        self._history: deque[str] = deque(maxlen=max_history)

    def _counter(self, key: str) -> _ModeBudgetCounter:
        if key not in self._counters:
            self._counters[key] = _ModeBudgetCounter()
            self._history.append(key)
            if len(self._history) == self._history.maxlen:
                oldest = self._history.popleft()
                self._counters.pop(oldest, None)
        return self._counters[key]

    def _budgets(self, mode: str) -> tuple[int, int, int]:
        return _MODE_BUDGETS.get(mode, _MODE_BUDGETS["auto"])

    def _evaluate_call(
        self,
        tool_call: dict[str, Any],
        counter: _ModeBudgetCounter,
        mode: str,
    ) -> tuple[bool, str]:
        """Return (allowed, reason)."""
        breakdown = _breakdown_tool_call(tool_call)
        kb_limit, non_kb_limit, total_limit = self._budgets(mode)

        if breakdown.is_all_other:
            return True, ""

        # ChainLens research is disallowed in speed and balanced.
        if mode in ("speed", "balanced") and breakdown.has_chainlens:
            return False, f"ChainLens research is disabled in {mode} mode."

        # Web/deep-research subagents are disallowed in speed; in balanced the
        # non-kb budget of 1 already gates them, but the message is clearer here.
        if mode == "speed" and breakdown.has_web_research:
            return False, f"Web/deep-research tools are disabled in {mode} mode."

        if counter.kb + breakdown.kb_count > kb_limit:
            return (
                False,
                f"Knowledge-base call budget ({kb_limit}) used in {mode} mode.",
            )

        if counter.non_kb + breakdown.non_kb_count > non_kb_limit:
            return (
                False,
                f"Non-knowledge-base call budget ({non_kb_limit}) used in {mode} mode.",
            )

        if counter.total + breakdown.kb_count + breakdown.non_kb_count > total_limit:
            return False, f"Tool call budget ({total_limit}) reached in {mode} mode."

        return True, ""

    def _apply_call(
        self,
        tool_call: dict[str, Any],
        counter: _ModeBudgetCounter,
    ) -> None:
        breakdown = _breakdown_tool_call(tool_call)
        if breakdown.is_all_other:
            return
        counter.kb += breakdown.kb_count
        counter.non_kb += breakdown.non_kb_count
        counter.total += breakdown.kb_count + breakdown.non_kb_count

    def _tool_message(self, tool_call: dict[str, Any], reason: str) -> ToolMessage:
        return ToolMessage(
            content=f"Mode budget blocked: {reason}",
            tool_call_id=str(tool_call.get("id", "")),
            name=str(tool_call.get("name", "")),
            status="error",
        )

    def after_model(  # type: ignore[override]
        self,
        state: AgentState[ResponseT],
        runtime: Runtime[ContextT],
    ) -> dict[str, Any] | None:
        messages = state.get("messages") or []
        if not messages:
            return None

        last = messages[-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return None

        mode = _get_mode_from_config(runtime)
        counter = self._counter(_call_key_from_config(runtime))
        allowed: list[dict[str, Any]] = []
        blocked_messages: list[ToolMessage] = []

        for tool_call in last.tool_calls:
            is_allowed, reason = self._evaluate_call(tool_call, counter, mode)
            if is_allowed:
                # Increment immediately so subsequent calls in the same
                # batch are evaluated against the updated counter.
                self._apply_call(tool_call, counter)
                allowed.append(tool_call)
            else:
                name = tool_call.get("name")
                breakdown = _breakdown_tool_call(tool_call)
                subagent = ""
                if name == "task" and breakdown.subagent_names:
                    subagent = f" ({', '.join(breakdown.subagent_names)})"
                logger.warning(
                    "ModeBudgetMiddleware: blocking %s%s in %s mode: %s",
                    name,
                    subagent,
                    mode,
                    reason,
                )
                blocked_messages.append(self._tool_message(tool_call, reason))

        if not allowed and blocked_messages:
            # Budget is fully exhausted: force the agent to answer.
            final = AIMessage(
                content=(
                    f"I have reached the {mode} mode tool budget. "
                    "I will now answer based on the information I have gathered."
                )
            )
            return {
                "messages": [*blocked_messages, final],
                "jump_to": "end",
            }

        if blocked_messages:
            return {"messages": blocked_messages}

        return None

    async def aafter_model(  # type: ignore[override]
        self,
        state: AgentState[ResponseT],
        runtime: Runtime[ContextT],
    ) -> dict[str, Any] | None:
        return self.after_model(state, runtime)


def build_mode_budget_mw(flags: AgentFeatureFlags) -> ModeBudgetMiddleware | None:
    """Builder for the mode-aware tool call budget middleware."""
    return ModeBudgetMiddleware() if enabled(flags, "enable_mode_budget") else None


__all__ = ["ModeBudgetMiddleware", "build_mode_budget_mw"]
