"""LiteLLM Router Service for Load Balancing (backward-compatible facade).

This module provides a singleton LiteLLM Router for automatic load balancing
across multiple LLM deployments. The implementation has been split into
``app.services.llm_router``; this file remains as a stable facade.
"""

from __future__ import annotations

import logging

import litellm
from litellm import Router

from app.services.llm_router.chat_model import ChatLiteLLMRouter, get_auto_mode_llm
from app.services.llm_router.config_builder import RouterConfigBuilder
from app.services.llm_router.constants import AUTO_MODE_ID, _sanitize_content
from app.services.llm_router.service import (
    _LLMRouterServiceImpl,
    _service,
    compute_premium_tokens,
    is_auto_mode,
    is_premium_model,
)

litellm.json_logs = False
litellm.store_audit_logs = False

logger = logging.getLogger(__name__)


class LLMRouterService:
    """Singleton service for managing LiteLLM Router."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> _LLMRouterServiceImpl:
        """Get the singleton instance of the router service."""
        return _service

    @classmethod
    def initialize(
        cls,
        global_configs: list[dict],
        router_settings: dict | None = None,
    ) -> None:
        """Initialize the router with global LLM configurations."""
        _service.initialize(
            global_configs,
            router_settings,
            router_class=Router,
            context_fallback_builder=cls._build_context_fallback_groups,
        )

    @classmethod
    def rebuild(
        cls,
        global_configs: list[dict],
        router_settings: dict | None = None,
    ) -> None:
        """Reset the router and re-run ``initialize`` with fresh configs."""
        _service.rebuild(global_configs, router_settings, router_class=Router)

    @classmethod
    def get_router(cls) -> Router | None:
        """Get the initialized router instance."""
        return _service.get_router()

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if the router has been initialized."""
        return _service.is_initialized()

    @classmethod
    def get_model_count(cls) -> int:
        """Get the number of models in the router."""
        return _service.get_model_count()

    @classmethod
    def is_premium_model(cls, model_string: str) -> bool:
        """Return True if *model_string* is a premium-tier deployment."""
        return _service.is_premium_model(model_string)

    @classmethod
    def compute_premium_tokens(cls, calls: list) -> int:
        """Sum ``total_tokens`` for calls whose model is premium."""
        return _service.compute_premium_tokens(calls)

    @classmethod
    def _build_context_fallback_groups(cls, model_list: list[dict]):
        """Create an ``auto-large`` model group for context-window fallbacks."""
        return RouterConfigBuilder.build_context_fallback_groups(model_list)

    @classmethod
    def _config_to_deployment(cls, config: dict):
        """Convert a global LLM config to a router deployment entry."""
        return RouterConfigBuilder.config_to_deployment(config)


__all__ = [
    "AUTO_MODE_ID",
    "ChatLiteLLMRouter",
    "LLMRouterService",
    "Router",
    "_sanitize_content",
    "compute_premium_tokens",
    "get_auto_mode_llm",
    "is_auto_mode",
    "is_premium_model",
]
