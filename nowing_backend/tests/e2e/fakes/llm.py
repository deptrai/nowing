"""Deterministic LLM fake for the E2E indexing pipeline and memory extraction.

The production indexing pipeline summarizes documents with:

    summary_chain = SUMMARY_PROMPT_TEMPLATE | llm
    summary_result = await summary_chain.ainvoke({"document": ...})
    summary_content = summary_result.content

Memory extraction reuses ``app.services.llm_service.get_agent_llm`` and calls
``llm.ainvoke(prompt)`` directly.  We return a stub that emits a deterministic
summary for normal prompts and a valid JSON fact array for extraction prompts.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)

_EXTRACTION_MARKER = "memory extraction assistant"


def _make_fake_llm() -> FakeListChatModel:
    """Build a fresh FakeListChatModel that returns a deterministic summary."""
    fake = FakeListChatModel(
        responses=[
            "E2E_FAKE_SUMMARY: Indexed by Playwright E2E run with deterministic LLM stub."
        ]
    )
    return fake


class ConditionalFakeChatModel:
    """Returns a memory-extraction JSON array for extraction prompts, else a summary."""

    async def ainvoke(
        self,
        input: Any,
        config: Any | None = None,
        **kwargs: Any,
    ) -> Any:
        prompt = input if isinstance(input, str) else str(input)
        if _EXTRACTION_MARKER in prompt or "Return ONLY a valid JSON array" in prompt:
            logger.info("[fake-llm] returning memory extraction JSON")
            content = (
                '[{"content":"Competitor X raised prices by 10% in Q2 2026.",'
                '"type":"episodic","tags":["competitor","pricing"],'
                '"confidence":0.95}]'
            )
        else:
            logger.info("[fake-llm] returning deterministic summary")
            content = (
                "E2E_FAKE_SUMMARY: Indexed by Playwright E2E run with deterministic LLM stub."
            )
        return AIMessage(content=content)


async def fake_get_agent_llm(*args: Any, **kwargs: Any) -> Any:
    """Drop-in replacement for app.services.llm_service.get_agent_llm."""
    logger.info("[fake-llm] returning ConditionalFakeChatModel for E2E")
    return ConditionalFakeChatModel()
