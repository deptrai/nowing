"""Fallback only on provider/network errors; let programming bugs raise.

Upstream :class:`langchain.agents.middleware.ModelFallbackMiddleware` catches
every ``Exception``. With a non-provider bug (``KeyError``, ``TypeError``,
``AttributeError`` from middleware/state), every fallback model in the chain
hits the same bug — burning latency and tokens before the real cause finally
surfaces. Scoping the catch to provider-style exception types lets bugs fail
fast with clean tracebacks.

Class-name matching (instead of ``isinstance`` against imported provider
types) keeps the dependency surface flat: openai, anthropic, google,
mistral, etc. all ship their own ``RateLimitError`` and we don't want to
import them all.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import ModelFallbackMiddleware

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langchain.agents.middleware.types import ModelRequest, ModelResponse
    from langchain_core.messages import AIMessage


_FALLBACK_ELIGIBLE_NAMES: frozenset[str] = frozenset(
    {
        # Rate / quota
        "RateLimitError",
        # Server-side
        "APIStatusError",
        "InternalServerError",
        "ServiceUnavailableError",
        "BadGatewayError",
        "GatewayTimeoutError",
        # Network
        "APIConnectionError",
        "APITimeoutError",
        "ConnectError",
        "ConnectTimeout",
        "ReadTimeout",
        "RemoteProtocolError",
        "TimeoutError",
        "TimeoutException",
    }
)


def _is_fallback_eligible(exc: BaseException) -> bool:
    """Eligible if the exception or any base in its MRO matches by class name."""
    return any(cls.__name__ in _FALLBACK_ELIGIBLE_NAMES for cls in type(exc).__mro__)


class ScopedModelFallbackMiddleware(ModelFallbackMiddleware):
    """``ModelFallbackMiddleware`` that re-raises non-provider exceptions."""

    def wrap_model_call(  # type: ignore[override]
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any] | AIMessage:
        last_exception: Exception
        try:
            return handler(request)
        except Exception as e:
            if not _is_fallback_eligible(e):
                raise
            last_exception = e

        for fallback_model in self.models:
            try:
                return handler(request.override(model=fallback_model))
            except Exception as e:
                if not _is_fallback_eligible(e):
                    raise
                last_exception = e
                continue

        raise last_exception

    async def awrap_model_call(  # type: ignore[override]
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any] | AIMessage:
        last_exception: Exception
        try:
            return await handler(request)
        except Exception as e:
            if not _is_fallback_eligible(e):
                raise
            last_exception = e

        for fallback_model in self.models:
            try:
                return await handler(request.override(model=fallback_model))
            except Exception as e:
                if not _is_fallback_eligible(e):
                    raise
                last_exception = e
                continue

        raise last_exception
