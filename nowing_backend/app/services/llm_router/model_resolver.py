"""Model metadata cache and token-count helpers for the LLM router."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_cached_context_profile: dict | None = None
_cached_context_profile_computed: bool = False

# Cached singleton instances keyed by (streaming,) to avoid re-creating
# on every call.
_router_instance_cache: dict[bool, Any] = {}


def get_cached_context_profile(router: Any) -> dict | None:
    """Compute and cache context profile across all router deployments.

    Called once on first ChatLiteLLMRouter creation; subsequent calls return
    the cached value. This avoids calling litellm.get_model_info() for every
    deployment on every request.

    Caches both ``max_input_tokens`` (minimum across deployments, used by
    SummarizationMiddleware) and ``max_input_tokens_upper`` (maximum across
    deployments, used for context-trimming so we can target the largest
    available model — the router's fallback logic handles smaller ones).
    """
    global _cached_context_profile, _cached_context_profile_computed
    if _cached_context_profile_computed:
        return _cached_context_profile

    from litellm import get_model_info

    min_ctx: int | None = None
    max_ctx: int | None = None
    token_count_model: str | None = None
    ctx_pairs: list[tuple[int, str]] = []
    for deployment in router.model_list:
        params = deployment.get("litellm_params", {})
        base_model = params.get("base_model") or params.get("model", "")
        try:
            info = get_model_info(base_model)
            ctx = info.get("max_input_tokens")
            if isinstance(ctx, int) and ctx > 0:
                if min_ctx is None or ctx < min_ctx:
                    min_ctx = ctx
                if max_ctx is None or ctx > max_ctx:
                    max_ctx = ctx
                if token_count_model is None:
                    token_count_model = base_model
                ctx_pairs.append((ctx, base_model))
        except Exception:
            continue

    if min_ctx is not None:
        token_count_models: list[str] = []
        if token_count_model:
            token_count_models.append(token_count_model)
        if ctx_pairs:
            ctx_pairs.sort(key=lambda x: x[0])
            smallest_model = ctx_pairs[0][1]
            largest_model = ctx_pairs[-1][1]
            if smallest_model not in token_count_models:
                token_count_models.append(smallest_model)
            if largest_model not in token_count_models:
                token_count_models.append(largest_model)
        logger.info(
            "ChatLiteLLMRouter profile: max_input_tokens=%d, upper=%s, "
            "token_models=%s",
            min_ctx,
            max_ctx,
            token_count_models,
        )
        _cached_context_profile = {
            "max_input_tokens": min_ctx,
            "max_input_tokens_upper": max_ctx,
            "token_count_model": token_count_model,
            "token_count_models": token_count_models,
        }
    else:
        _cached_context_profile = None

    _cached_context_profile_computed = True
    return _cached_context_profile


def reset_profile_cache() -> None:
    """Clear the cached context profile."""
    global _cached_context_profile, _cached_context_profile_computed
    _cached_context_profile = None
    _cached_context_profile_computed = False


def reset_instance_cache() -> None:
    """Clear the ChatLiteLLMRouter instance cache."""
    _router_instance_cache.clear()


__all__ = [
    "get_cached_context_profile",
    "reset_instance_cache",
    "reset_profile_cache",
]
