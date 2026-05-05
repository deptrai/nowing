"""Resilience contract for subagents built via ``pack_subagent``.

Subagents (jira, linear, notion, ...) run on the same LLM as the parent. When
the provider rate-limits or returns an empty stream, a single hiccup must not
abort the user's HITL flow — the connector subagent has to keep moving. This
relies on ``ModelFallbackMiddleware`` being usable as a subagent
``extra_middleware`` so the production builder can wire it in.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.agents.multi_agent_chat.subagents.shared.subagent_builder import (
    pack_subagent,
)


class _AlwaysFailingChatModel(BaseChatModel):
    """Mimics a provider hard-failing on every call (rate limit / empty stream).

    ``ModelFallbackMiddleware`` triggers on any ``Exception``, so the exact
    error type doesn't matter for the contract under test.
    """

    @property
    def _llm_type(self) -> str:
        return "always-failing-test-model"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        msg = "primary llm exploded"
        raise RuntimeError(msg)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        msg = "primary llm exploded"
        raise RuntimeError(msg)

    def _stream(self, *args: Any, **kwargs: Any) -> Iterator[ChatGeneration]:
        msg = "primary llm exploded"
        raise RuntimeError(msg)

    async def _astream(
        self, *args: Any, **kwargs: Any
    ) -> AsyncIterator[ChatGeneration]:
        msg = "primary llm exploded"
        raise RuntimeError(msg)
        yield  # pragma: no cover - unreachable, satisfies async generator typing


@pytest.mark.asyncio
async def test_subagent_recovers_when_primary_llm_fails():
    """Primary blows up → fallback in extra_middleware finishes the turn."""
    primary = _AlwaysFailingChatModel()
    fallback = FakeMessagesListChatModel(
        responses=[AIMessage(content="recovered via fallback")]
    )

    spec = pack_subagent(
        name="resilience_test",
        description="test subagent",
        system_prompt="be helpful",
        tools=[],
        model=primary,
        extra_middleware=[ModelFallbackMiddleware(fallback)],
    )

    agent = create_agent(
        model=spec["model"],
        tools=spec["tools"],
        middleware=spec["middleware"],
        system_prompt=spec["system_prompt"],
    )

    result = await agent.ainvoke({"messages": [HumanMessage(content="hi")]})

    final = result["messages"][-1]
    assert isinstance(final, AIMessage)
    assert final.content == "recovered via fallback"
