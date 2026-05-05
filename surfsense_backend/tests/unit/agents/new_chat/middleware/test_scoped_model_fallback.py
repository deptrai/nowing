"""Exception-scope contract for ``ScopedModelFallbackMiddleware``.

Upstream ``ModelFallbackMiddleware`` catches every ``Exception`` and walks
the fallback chain. That means a programming bug (``KeyError`` from a
botched tool config, ``TypeError`` from middleware, ...) burns 1+N model
round-trips and ~Nx tokens before its real cause surfaces. The scoped
variant only falls back on provider/network exception types so bugs fail
fast, with clean tracebacks.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class _RaisingChatModel(BaseChatModel):
    """LLM that raises a configurable exception on every invocation."""

    exc_to_raise: Any

    @property
    def _llm_type(self) -> str:
        return "raising-test-model"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise self.exc_to_raise

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise self.exc_to_raise

    def _stream(self, *args: Any, **kwargs: Any) -> Iterator[ChatGeneration]:
        raise self.exc_to_raise

    async def _astream(
        self, *args: Any, **kwargs: Any
    ) -> AsyncIterator[ChatGeneration]:
        raise self.exc_to_raise
        yield  # pragma: no cover - unreachable


class _RecordingChatModel(BaseChatModel):
    """Returns a fixed message and counts how often it was called."""

    response_text: str = "fallback-ok"
    call_count: int = 0

    @property
    def _llm_type(self) -> str:
        return "recording-test-model"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.call_count += 1
        return ChatResult(
            generations=[
                ChatGeneration(message=AIMessage(content=self.response_text))
            ]
        )

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop, None, **kwargs)


# Locally defined provider-style error: importing openai/anthropic/etc.
# would couple the test to provider SDKs the contract intentionally avoids.
class RateLimitError(Exception):
    """Mimics ``openai.RateLimitError`` for name-based eligibility."""


def _build_agent(primary: BaseChatModel, fallback: BaseChatModel):
    """Compile a no-tools agent with the scoped fallback wired in."""
    from langchain.agents import create_agent

    from app.agents.new_chat.middleware.scoped_model_fallback import (
        ScopedModelFallbackMiddleware,
    )

    return create_agent(
        model=primary,
        tools=[],
        middleware=[ScopedModelFallbackMiddleware(fallback)],
        system_prompt="be helpful",
    )


@pytest.mark.asyncio
async def test_provider_errors_trigger_fallback():
    """Class names matching the provider allowlist drive the fallback chain."""
    primary = _RaisingChatModel(exc_to_raise=RateLimitError("429 from provider"))
    fallback = _RecordingChatModel(response_text="recovered")

    agent = _build_agent(primary, fallback)
    result = await agent.ainvoke({"messages": [("user", "hi")]})

    final = result["messages"][-1]
    assert isinstance(final, AIMessage)
    assert final.content == "recovered"
    assert fallback.call_count == 1


@pytest.mark.asyncio
async def test_programming_errors_propagate_without_invoking_fallback():
    """``KeyError`` from agent-side bugs must surface immediately, no fallback retry."""
    primary = _RaisingChatModel(exc_to_raise=KeyError("missing_state_field"))
    fallback = _RecordingChatModel(response_text="should-never-arrive")

    agent = _build_agent(primary, fallback)

    with pytest.raises(KeyError, match="missing_state_field"):
        await agent.ainvoke({"messages": [("user", "hi")]})

    assert fallback.call_count == 0, (
        "fallback was invoked for a programming error; "
        "scoping rule is broken"
    )
