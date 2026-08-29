"""Build LiteLLM Router deployments and fallback groups."""

from __future__ import annotations

import logging
from typing import Any

from litellm import get_model_info

from app.services.model_resolver import native_connection_from_config, to_litellm

logger = logging.getLogger(__name__)

# Default router settings optimized for rate limit handling
DEFAULT_ROUTER_SETTINGS = {
    "routing_strategy": "usage-based-routing",  # Best for rate limit management
    "num_retries": 3,
    "allowed_fails": 3,
    "cooldown_time": 60,  # Cooldown for 60 seconds after failures
    "retry_after": 5,  # Wait 5 seconds between retries
}


class RouterConfigBuilder:
    """Convert global LLM configs to LiteLLM Router deployments."""

    @staticmethod
    def config_to_deployment(config: dict) -> dict | None:
        """Convert a global LLM config to a router deployment entry.

        Args:
            config: Global LLM config dictionary.

        Returns:
            Router deployment dictionary or None if invalid.
        """
        try:
            # Skip if essential fields are missing
            if not config.get("model_name") or not config.get("api_key"):
                return None

            model_string, resolved_kwargs = to_litellm(
                native_connection_from_config(config),
                config["model_name"],
            )
            litellm_params = {"model": model_string, **resolved_kwargs}

            deployment = {
                "model_name": "auto",  # All configs use the same alias
                "litellm_params": litellm_params,
            }

            # Add rate limits from config if available
            if config.get("rpm"):
                deployment["rpm"] = config["rpm"]
            if config.get("tpm"):
                deployment["tpm"] = config["tpm"]

            return deployment
        except Exception as e:
            logger.warning("Failed to convert config to deployment: %s", e)
            return None

    @staticmethod
    def build_pool(
        global_configs: list[dict],
    ) -> tuple[list[dict], set[str]]:
        """Build the router pool from global configs.

        Configs with ``router_pool_eligible=False`` are skipped so that
        dynamic OpenRouter entries stay out of the shared router pool used
        by title-gen / sub-agent ``model="auto"`` flows. Those dynamic
        entries are still available for user-facing Auto-mode thread pinning
        via ``auto_model_pin_service``.

        Returns:
            (model_list, premium_model_strings).
        """
        model_list: list[dict] = []
        premium_models: set[str] = set()
        for config in global_configs:
            if config.get("router_pool_eligible") is False:
                continue
            deployment = RouterConfigBuilder.config_to_deployment(config)
            if deployment:
                model_list.append(deployment)
                if config.get("billing_tier") == "premium":
                    params = deployment["litellm_params"]
                    model_string = params["model"]
                    premium_models.add(model_string)
                    base = params.get("base_model") or config.get("model_name", "")
                    if base and base != model_string:
                        premium_models.add(base)
        return model_list, premium_models

    @staticmethod
    def final_settings(router_settings: dict | None) -> dict:
        """Merge provided settings with sensible defaults."""
        return {**DEFAULT_ROUTER_SETTINGS, **(router_settings or {})}

    @staticmethod
    def build_context_fallback_groups(
        model_list: list[dict],
    ) -> tuple[list[dict], list[dict[str, list[str]]] | None]:
        """Create an ``auto-large`` model group for context-window fallbacks.

        Uses ``litellm.get_model_info`` to discover the context window of each
        deployment.  Deployments whose ``max_input_tokens`` exceeds the smallest
        window are duplicated into an ``auto-large`` group.  The returned
        fallback config tells the Router: on ``ContextWindowExceededError`` for
        ``auto``, retry with ``auto-large``.

        Returns:
            (full_model_list, context_window_fallbacks) — ``full_model_list``
            contains the original entries plus any ``auto-large`` duplicates.
            ``context_window_fallbacks`` is ``None`` when every deployment has
            the same context size (no useful fallback).
        """
        ctx_map: dict[str, int] = {}
        for dep in model_list:
            params = dep.get("litellm_params", {})
            base_model = params.get("base_model") or params.get("model", "")
            try:
                info = get_model_info(base_model)
                ctx = info.get("max_input_tokens")
                if isinstance(ctx, int) and ctx > 0:
                    ctx_map[base_model] = ctx
            except Exception:
                continue

        if not ctx_map:
            return model_list, None

        min_ctx = min(ctx_map.values())

        large_deployments: list[dict] = []
        for dep in model_list:
            params = dep.get("litellm_params", {})
            base_model = params.get("base_model") or params.get("model", "")
            if ctx_map.get(base_model, 0) > min_ctx:
                dup = {**dep, "model_name": "auto-large"}
                large_deployments.append(dup)

        if not large_deployments:
            return model_list, None

        logger.info(
            "Context-window fallback: %d large-context deployments "
            "(min_ctx=%d) added to 'auto-large' group",
            len(large_deployments),
            min_ctx,
        )
        return model_list + large_deployments, [{"auto": ["auto-large"]}]

    @staticmethod
    def build_router_kwargs(
        model_list: list[dict],
        final_settings: dict,
        context_fallback_builder: Any | None = None,
    ) -> dict[str, Any]:
        """Build the keyword arguments for ``litellm.Router``.

        Also returns the final model list including any ``auto-large``
        fallbacks.
        """
        if context_fallback_builder is None:
            context_fallback_builder = RouterConfigBuilder.build_context_fallback_groups
        full_model_list, ctx_fallbacks = context_fallback_builder(model_list)

        # Build a general-purpose fallback list so NotFound/timeout/rate-limit
        # style failures on one deployment don't bubble up as hard errors —
        # the router retries with a sibling deployment in ``auto-large``.
        # ``auto-large`` is the large-context subset of ``auto``; if it is
        # empty we fall back to ``auto`` itself so the router at least picks a
        # different deployment in the same group.
        fallbacks: list[dict[str, list[str]]] | None = None
        if ctx_fallbacks:
            fallbacks = [{"auto": ["auto-large"]}]

        router_kwargs: dict[str, Any] = {
            "model_list": full_model_list,
            "routing_strategy": final_settings.get(
                "routing_strategy", "usage-based-routing"
            ),
            "num_retries": final_settings.get("num_retries", 3),
            "allowed_fails": final_settings.get("allowed_fails", 3),
            "cooldown_time": final_settings.get("cooldown_time", 60),
            "set_verbose": False,
        }
        if ctx_fallbacks:
            router_kwargs["context_window_fallbacks"] = ctx_fallbacks
        if fallbacks:
            router_kwargs["fallbacks"] = fallbacks
        return router_kwargs


__all__ = [
    "DEFAULT_ROUTER_SETTINGS",
    "RouterConfigBuilder",
]
