"""Cap model calls per thread / per run to prevent runaway cost."""

from __future__ import annotations

from langchain.agents.middleware import ModelCallLimitMiddleware

from app.agents.chat.multi_agent_chat.shared.feature_flags import AgentFeatureFlags

from ..flags import enabled

# Giới hạn model call — export để event_loop detect cap-hit mà không hardcode.
MODEL_THREAD_LIMIT = 120
MODEL_RUN_LIMIT = 80


def build_model_call_limit_mw(
    flags: AgentFeatureFlags,
) -> ModelCallLimitMiddleware | None:
    if not enabled(flags, "enable_model_call_limit"):
        return None
    return ModelCallLimitMiddleware(
        thread_limit=MODEL_THREAD_LIMIT,
        run_limit=MODEL_RUN_LIMIT,
        exit_behavior="end",
    )
