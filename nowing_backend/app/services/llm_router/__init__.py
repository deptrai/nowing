"""LiteLLM Router service package."""

from __future__ import annotations

from app.services.llm_router.chat_model import ChatLiteLLMRouter, get_auto_mode_llm
from app.services.llm_router.constants import AUTO_MODE_ID
from app.services.llm_router.service import is_auto_mode

__all__ = [
    "AUTO_MODE_ID",
    "ChatLiteLLMRouter",
    "get_auto_mode_llm",
    "is_auto_mode",
]
