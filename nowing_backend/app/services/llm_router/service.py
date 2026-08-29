"""Internal state holder for the LLM router service."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.services.llm_router.config_builder import RouterConfigBuilder
from app.services.llm_router.model_resolver import (
    reset_instance_cache,
    reset_profile_cache,
)

logger = logging.getLogger(__name__)


class _LLMRouterServiceImpl:
    """Async-safe singleton state holder for the LLM router."""

    def __init__(self) -> None:
        self._router: Any | None = None
        self._model_list: list[dict] = []
        self._router_settings: dict = {}
        self._initialized: bool = False
        self._premium_model_strings: set[str] = set()
        self._lock = asyncio.Lock()

    def reset(self) -> None:
        """Reset all state and caches."""
        self._initialized = False
        self._router = None
        self._model_list = []
        self._premium_model_strings = set()
        self._router_settings = {}
        reset_profile_cache()
        reset_instance_cache()

    def _do_initialize(
        self,
        global_configs: list[dict],
        router_settings: dict | None,
        router_class: Any,
        context_fallback_builder: Any | None = None,
    ) -> None:
        if context_fallback_builder is None:
            context_fallback_builder = RouterConfigBuilder.build_context_fallback_groups

        model_list, premium_models = RouterConfigBuilder.build_pool(global_configs)
        if not model_list:
            logger.warning("No valid LLM configs found for router initialization")
            return

        final_settings = RouterConfigBuilder.final_settings(router_settings)
        logger.info(
            "Router pool: %d deployments, premium model strings: %s",
            len(model_list),
            sorted(premium_models),
        )

        router_kwargs = RouterConfigBuilder.build_router_kwargs(
            model_list, final_settings, context_fallback_builder
        )
        try:
            self._router = router_class(**router_kwargs)
            self._model_list = model_list
            self._premium_model_strings = premium_models
            self._router_settings = final_settings
            self._initialized = True
            reset_profile_cache()
            reset_instance_cache()
            logger.info(
                "LLM Router initialized with %d deployments, "
                "strategy: %s, context_window_fallbacks: %s, fallbacks: %s",
                len(model_list),
                final_settings.get("routing_strategy"),
                router_kwargs.get("context_window_fallbacks") or "none",
                router_kwargs.get("fallbacks") or "none",
            )
        except Exception as e:
            logger.error("Failed to initialize LLM Router: %s", e)
            self._router = None

    def initialize(
        self,
        global_configs: list[dict],
        router_settings: dict | None = None,
        router_class: Any | None = None,
        context_fallback_builder: Any | None = None,
    ) -> None:
        """Initialize the router with global LLM configurations."""
        if self._initialized:
            logger.debug("LLM Router already initialized, skipping")
            return
        if router_class is None:
            from litellm import Router as _Router

            router_class = _Router
        self._do_initialize(
            global_configs,
            router_settings,
            router_class,
            context_fallback_builder,
        )

    async def initialize_async(
        self,
        global_configs: list[dict],
        router_settings: dict | None = None,
        router_class: Any | None = None,
    ) -> None:
        """Async-safe entry point for router initialization."""
        async with self._lock:
            if self._initialized:
                logger.debug("LLM Router already initialized, skipping")
                return
            self.initialize(global_configs, router_settings, router_class)

    def rebuild(
        self,
        global_configs: list[dict],
        router_settings: dict | None = None,
        router_class: Any | None = None,
    ) -> None:
        """Reset the router and re-run ``initialize`` with fresh configs."""
        self.reset()
        self.initialize(global_configs, router_settings, router_class)

    def get_router(self) -> Any | None:
        """Get the initialized router instance."""
        return self._router

    def is_initialized(self) -> bool:
        """Check if the router has been initialized."""
        return self._initialized and self._router is not None

    def get_model_count(self) -> int:
        """Get the number of models in the router."""
        return len(self._model_list)

    def is_premium_model(self, model_string: str) -> bool:
        """Return True if *model_string* is a premium-tier deployment."""
        return model_string in self._premium_model_strings

    def compute_premium_tokens(self, calls: list) -> int:
        """Sum ``total_tokens`` for calls whose model is premium."""
        total = sum(
            c.total_tokens for c in calls if c.model in self._premium_model_strings
        )
        if calls:
            call_models = [c.model for c in calls]
            logger.info(
                "[premium_tokens] call models=%s, premium_set=%s, result=%d",
                call_models,
                sorted(self._premium_model_strings),
                total,
            )
        return total


_service = _LLMRouterServiceImpl()


def get_router() -> Any | None:
    """Get the initialized router instance."""
    return _service.get_router()


def is_initialized() -> bool:
    """Check if the router has been initialized."""
    return _service.is_initialized()


def get_model_count() -> int:
    """Get the number of models in the router."""
    return _service.get_model_count()


def is_premium_model(model_string: str) -> bool:
    """Return True if *model_string* is a premium-tier deployment."""
    return _service.is_premium_model(model_string)


def compute_premium_tokens(calls: list) -> int:
    """Sum ``total_tokens`` for calls whose model is premium."""
    return _service.compute_premium_tokens(calls)


def reset_service() -> None:
    """Reset router state and caches."""
    _service.reset()


AUTO_MODE_ID = 0


def is_auto_mode(llm_config_id: int | None) -> bool:
    """Check if the given LLM config ID represents Auto mode."""
    return llm_config_id == AUTO_MODE_ID


__all__ = [
    "AUTO_MODE_ID",
    "_LLMRouterServiceImpl",
    "_service",
    "compute_premium_tokens",
    "get_model_count",
    "get_router",
    "is_auto_mode",
    "is_initialized",
    "is_premium_model",
    "reset_service",
]
