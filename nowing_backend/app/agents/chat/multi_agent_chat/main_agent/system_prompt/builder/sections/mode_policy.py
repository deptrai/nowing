"""Mode-aware instruction appendix for the main-agent system prompt."""

from __future__ import annotations

_MODE_DESCRIPTIONS: dict[str, str] = {
    "speed": (
        "speed: answer as fast as possible. Use ONLY `ask_knowledge_base` or "
        "`task` with `subagent_type='knowledge_base'` (at most ONE call). "
        "Do NOT call web search, ChainLens research, or any other subagent. "
        "If the workspace knowledge base cannot answer, respond with the best "
        "partial answer; do not escalate."
    ),
    "balanced": (
        "balanced: fast, accurate answers grounded in the workspace. You may "
        "call `ask_knowledge_base` or `task` with `subagent_type='knowledge_base'` "
        "up to TWO times. You may call `task` with a non-KB subagent ONCE if "
        "the knowledge base is clearly insufficient, but do NOT call ChainLens "
        "research. Prefer not to call web search unless the user clearly needs "
        "live web data."
    ),
    "quality": (
        "quality: thorough, well-cited answers. You may call the knowledge base "
        "up to THREE times and other subagents (including ChainLens research or "
        "web search) up to TWO times, for a maximum of FIVE expensive tool calls. "
        "Prioritize the workspace knowledge base before opening web/deep research."
    ),
    "auto": (
        "auto: choose the appropriate depth for the question. You may use any "
        "subagent, but the total number of expensive tool calls is capped at FIVE. "
        "Start with the workspace knowledge base; escalate to web or ChainLens "
        "research only if the knowledge base is insufficient."
    ),
}


def build_mode_policy_section(research_mode: str | None) -> str:
    """Append a concise mode-budget instruction to the system prompt."""
    mode = research_mode if research_mode in _MODE_DESCRIPTIONS else "auto"
    text = _MODE_DESCRIPTIONS[mode]
    return (
        "\n## Research mode policy\n"
        f"The user selected `{mode}` for this turn. {text}\n"
        "If you are about to exceed the budget, stop and answer immediately.\n"
    )


__all__ = ["build_mode_policy_section"]
