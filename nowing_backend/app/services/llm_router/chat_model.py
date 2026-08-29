"""LangChain-compatible chat model backed by the LiteLLM Router."""

from __future__ import annotations

import copy
import json
import logging
import time
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from litellm.exceptions import (
    BadRequestError as LiteLLMBadRequestError,
    ContextWindowExceededError,
)
from pydantic import Field

from app.services.llm_router.constants import _sanitize_content
from app.services.llm_router.model_resolver import (
    _router_instance_cache,
    get_cached_context_profile,
)
from app.services.llm_router.retry_handler import (
    handle_completion_error,
    handle_streaming_error,
)
from app.services.llm_router.service import (
    get_model_count,
    get_router,
    is_initialized,
)
from app.utils.perf import get_perf_logger

logger = logging.getLogger(__name__)


class ChatLiteLLMRouter(BaseChatModel):
    """A LangChain-compatible chat model that uses LiteLLM Router for
    load balancing.

    This wraps the LiteLLM Router to provide the same interface as
    ChatLiteLLM, making it a drop-in replacement for auto-mode routing.

    Exposes a ``profile`` with ``max_input_tokens`` set to the smallest
    context window across all router deployments so that deepagents
    SummarizationMiddleware can use fraction-based triggers.

    **Singleton-ish**: Use ``get_auto_mode_llm()`` or call
    ``ChatLiteLLMRouter()`` directly — instances without bound tools are
    cached per ``streaming`` flag to avoid per-request re-initialization
    overhead and memory growth.
    """

    # Use model_config for Pydantic v2 compatibility
    model_config = {"arbitrary_types_allowed": True}

    # Public attributes that Pydantic will manage
    model: str = "auto"
    streaming: bool = True
    # Static kwargs that flow through to ``litellm.completion(...)`` on
    # every invocation (e.g. ``cache_control_injection_points`` set by
    # ``apply_litellm_prompt_caching``). Per-call ``**kwargs`` from
    # ``invoke()`` still take precedence — see ``_generate``/``_astream``.
    model_kwargs: dict[str, Any] = Field(default_factory=dict)

    # Bound tools and tool choice for tool calling
    _bound_tools: list[dict] | None = None
    _tool_choice: str | dict | None = None
    _router: Any | None = None

    def __init__(
        self,
        router: Any | None = None,
        bound_tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
        **kwargs,
    ):
        try:
            super().__init__(**kwargs)
            resolved_router = router or get_router()
            object.__setattr__(self, "_router", resolved_router)
            object.__setattr__(self, "_bound_tools", bound_tools)
            object.__setattr__(self, "_tool_choice", tool_choice)
            if not self._router:
                raise ValueError(
                    "LLM Router not initialized. "
                    "Call LLMRouterService.initialize() first."
                )

            computed_profile = get_cached_context_profile(self._router)
            if computed_profile is not None:
                object.__setattr__(self, "profile", computed_profile)

            logger.debug(
                "ChatLiteLLMRouter ready (models=%d, streaming=%s, has_tools=%s)",
                get_model_count(),
                self.streaming,
                bound_tools is not None,
            )
        except Exception as e:
            logger.error("Failed to initialize ChatLiteLLMRouter: %s", e)
            raise

    # -----------------------------------------------------------------
    # Context-aware trimming helpers
    # -----------------------------------------------------------------

    def _get_token_count_model_names(self) -> list[str]:
        """Return concrete model names usable by ``litellm.token_counter``.

        The router uses ``"auto"`` as the model group name but tokenizers
        need concrete model identifiers. We keep multiple candidates and
        take the most conservative count across them.
        """
        names: list[str] = []
        profile = getattr(self, "profile", None)
        if isinstance(profile, dict):
            tcms = profile.get("token_count_models")
            if isinstance(tcms, list):
                for name in tcms:
                    if isinstance(name, str) and name and name not in names:
                        names.append(name)
            tcm = profile.get("token_count_model")
            if isinstance(tcm, str) and tcm and tcm not in names:
                names.append(tcm)

        if self._router and self._router.model_list:
            for dep in self._router.model_list:
                params = dep.get("litellm_params", {})
                base = params.get("base_model") or params.get("model", "")
                if base and base not in names:
                    names.append(base)
                    if len(names) >= 3:
                        break
        if not names:
            return ["gpt-4o"]
        return names

    def _count_tokens(self, messages: list[dict]) -> int | None:
        """Return conservative token count across candidate deployment
        models."""
        from litellm import token_counter as _tc

        models = self._get_token_count_model_names()
        counts: list[int] = []
        for model_name in models:
            try:
                counts.append(_tc(messages=messages, model=model_name))
            except Exception:
                continue
        return max(counts) if counts else None

    def _get_max_input_tokens(self) -> int:
        """Return the max input tokens to use for context trimming.

        Prefers the *largest* context window across all deployments so we
        maximise usable context (the router's ``context_window_fallbacks``
        handle routing to the right model).  Falls back to the minimum
        profile value or a conservative default.
        """
        profile = getattr(self, "profile", None)
        if isinstance(profile, dict):
            upper = profile.get("max_input_tokens_upper")
            if isinstance(upper, int) and upper > 0:
                return upper
            lower = profile.get("max_input_tokens")
            if isinstance(lower, int) and lower > 0:
                return lower
        return 128_000

    def _trim_messages_to_fit_context(
        self,
        messages: list[dict],
        output_reserve_fraction: float = 0.10,
    ) -> list[dict]:
        """Trim message content via binary search to fit the model's
        context window.

        When the total token count exceeds the model's ``max_input_tokens``,
        this method identifies the largest messages (typically tool
        responses containing search results) and uses binary search on each
        to find the maximum content length that keeps the total within
        budget.

        Cutting prefers ``</document>`` XML boundaries so complete documents
        are preserved when possible.

        This is model-aware: it reads the context limit from
        ``litellm.get_model_info`` (cached in ``self.profile``) and counts
        tokens with ``litellm.token_counter``.
        """
        max_input = self._get_max_input_tokens()
        output_reserve = min(int(max_input * output_reserve_fraction), 16_384)
        budget = max_input - output_reserve

        total_tokens = self._count_tokens(messages)
        if total_tokens is None:
            return messages

        if total_tokens <= budget:
            return messages

        perf = get_perf_logger()
        perf.warning(
            "[llm_router] context overflow detected: %d tokens > %d budget "
            "(max_input=%d, reserve=%d). Trimming messages.",
            total_tokens,
            budget,
            max_input,
            output_reserve,
        )

        trimmed = copy.deepcopy(messages)

        # Per-message token counts for trimmable candidates.
        # Skip system messages to preserve agent instructions.
        msg_token_map: dict[int, int] = {}
        candidate_priority: dict[int, int] = {}
        for i, msg in enumerate(trimmed):
            if msg.get("role") == "system":
                continue
            role = msg.get("role")
            content = msg.get("content", "")
            if not isinstance(content, str) or len(content) < 500:
                continue
            # Prefer trimming tool/assistant outputs first.
            # User messages are only trimmed if they clearly contain
            # injected document context blobs.
            is_doc_blob = "<document>" in content or "<mentioned_documents>" in content
            if role in ("tool", "assistant"):
                candidate_priority[i] = 0
            elif role == "user" and is_doc_blob:
                candidate_priority[i] = 1
            else:
                continue
            token_count = self._count_tokens([msg])
            if token_count is not None:
                msg_token_map[i] = token_count

        if not msg_token_map:
            perf.warning("[llm_router] no trimmable messages found, returning as-is")
            return trimmed

        # Trim largest messages first
        candidates = sorted(
            msg_token_map.items(),
            key=lambda x: (candidate_priority.get(x[0], 9), -x[1]),
        )
        running_total = total_tokens

        trim_suffix = (
            "\n\n<!-- Content trimmed to fit model context window. "
            "Some documents were omitted. Refine your query or "
            "reduce top_k for different results. -->"
        )

        for idx, orig_msg_tokens in candidates:
            if running_total <= budget:
                break

            content = trimmed[idx]["content"]
            orig_len = len(content)

            # Binary search: find maximum content[:mid] that keeps total
            # within budget.
            lo, hi = 200, orig_len - 1
            best = 200

            while lo <= hi:
                mid = (lo + hi) // 2
                trimmed[idx]["content"] = content[:mid] + trim_suffix
                new_msg_tokens = self._count_tokens([trimmed[idx]])
                if new_msg_tokens is None:
                    hi = mid - 1
                    continue

                projected_total = running_total - orig_msg_tokens + new_msg_tokens
                if projected_total <= budget:
                    best = mid
                    lo = mid + 1
                else:
                    hi = mid - 1

            # Prefer cutting at a </document> boundary for cleaner output
            last_doc_end = content[:best].rfind("</document>")
            if last_doc_end > min(200, best // 4):
                best = last_doc_end + len("</document>")

            trimmed[idx]["content"] = content[:best] + trim_suffix

            try:
                new_msg_tokens = self._count_tokens([trimmed[idx]])
                if new_msg_tokens is None:
                    continue
                running_total = running_total - orig_msg_tokens + new_msg_tokens
            except Exception:
                pass

        # Hard guarantee: if still over budget, replace remaining large
        # non-system messages with compact placeholders until we fit.
        if running_total > budget:
            fallback_indices: list[int] = []
            for i, msg in enumerate(trimmed):
                if msg.get("role") == "system":
                    continue
                content = msg.get("content")
                if isinstance(content, str) and len(content) > 0:
                    fallback_indices.append(i)

            for idx in fallback_indices:
                if running_total <= budget:
                    break
                role = trimmed[idx].get("role", "message")
                placeholder = (
                    f"[content omitted to fit model context window; role={role}]"
                )
                old_tokens = self._count_tokens([trimmed[idx]]) or 0
                trimmed[idx]["content"] = placeholder
                new_tokens = self._count_tokens([trimmed[idx]]) or 0
                running_total = running_total - old_tokens + new_tokens

            if running_total > budget:
                perf.error(
                    "[llm_router] unable to fit context even after "
                    "aggressive trimming: tokens=%d budget=%d",
                    running_total,
                    budget,
                )
                # Final safety net: clear oldest non-system contents.
                for idx in fallback_indices:
                    if running_total <= budget:
                        break
                    old_tokens = self._count_tokens([trimmed[idx]]) or 0
                    trimmed[idx]["content"] = ""
                    new_tokens = self._count_tokens([trimmed[idx]]) or 0
                    running_total = running_total - old_tokens + new_tokens

        perf.info(
            "[llm_router] messages trimmed: %d → %d tokens "
            "(budget=%d, max_input=%d)",
            total_tokens,
            running_total,
            budget,
            max_input,
        )

        return trimmed

    # -----------------------------------------------------------------

    @property
    def _llm_type(self) -> str:
        return "litellm-router"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "model_count": get_model_count(),
        }

    def bind_tools(
        self,
        tools: list[Any],
        *,
        tool_choice: str | dict | None = None,
        **kwargs: Any,
    ) -> ChatLiteLLMRouter:
        """Bind tools to the model for function/tool calling.

        Args:
            tools: List of tools to bind (LangChain tools, Pydantic models,
                or dicts).
            tool_choice: Optional tool choice strategy ("auto", "required",
                "none", or a specific tool).
            **kwargs: Additional arguments.

        Returns:
            New ChatLiteLLMRouter instance with tools bound.
        """
        from langchain_core.utils.function_calling import convert_to_openai_tool

        # Convert tools to OpenAI format
        formatted_tools = []
        for tool in tools:
            if isinstance(tool, dict):
                # Already in dict format
                formatted_tools.append(tool)
            else:
                # Convert using LangChain utility
                try:
                    formatted_tools.append(convert_to_openai_tool(tool))
                except Exception as e:
                    logger.warning("Failed to convert tool %s: %s", tool, e)
                    continue

        # Create a new instance with tools bound. Carry through ``model_kwargs``
        # so static settings (e.g. cache_control_injection_points) survive the
        # bind_tools rebuild.
        return ChatLiteLLMRouter(
            router=self._router,
            bound_tools=formatted_tools if formatted_tools else None,
            tool_choice=tool_choice,
            model=self.model,
            streaming=self.streaming,
            model_kwargs=dict(self.model_kwargs),
            **kwargs,
        )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate a response using the router (synchronous)."""
        if not self._router:
            raise ValueError("Router not initialized")

        perf = get_perf_logger()
        t0 = time.perf_counter()
        msg_count = len(messages)

        # Convert LangChain messages to OpenAI format
        formatted_messages = self._convert_messages(messages)
        formatted_messages = self._trim_messages_to_fit_context(formatted_messages)

        # Merge static model_kwargs (e.g. cache_control_injection_points) under
        # per-call kwargs so callers can still override per invocation. Then add
        # bound tools.
        call_kwargs = {**self.model_kwargs, **kwargs}
        if self._bound_tools:
            call_kwargs["tools"] = self._bound_tools
        if self._tool_choice is not None:
            call_kwargs["tool_choice"] = self._tool_choice

        try:
            response = self._router.completion(
                model=self.model,
                messages=formatted_messages,
                stop=stop,
                **call_kwargs,
            )
        except (ContextWindowExceededError, LiteLLMBadRequestError) as e:
            handle_completion_error(
                e,
                perf=perf,
                stage="_generate",
                msg_count=msg_count,
                t0=t0,
            )

        elapsed = time.perf_counter() - t0
        perf.info(
            "[llm_router] _generate completed msgs=%d tools=%d in %.3fs",
            msg_count,
            len(self._bound_tools) if self._bound_tools else 0,
            elapsed,
        )

        # Convert response to ChatResult with potential tool calls
        message = self._convert_response_to_message(
            response.choices[0].message, response=response
        )
        generation = ChatGeneration(message=message)

        return ChatResult(generations=[generation])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate a response using the router (asynchronous)."""
        if not self._router:
            raise ValueError("Router not initialized")

        perf = get_perf_logger()
        t0 = time.perf_counter()
        msg_count = len(messages)

        # Convert LangChain messages to OpenAI format
        formatted_messages = self._convert_messages(messages)
        formatted_messages = self._trim_messages_to_fit_context(formatted_messages)

        # Merge static model_kwargs (e.g. cache_control_injection_points) under
        # per-call kwargs so callers can still override per invocation. Then add
        # bound tools.
        call_kwargs = {**self.model_kwargs, **kwargs}
        if self._bound_tools:
            call_kwargs["tools"] = self._bound_tools
        if self._tool_choice is not None:
            call_kwargs["tool_choice"] = self._tool_choice

        try:
            response = await self._router.acompletion(
                model=self.model,
                messages=formatted_messages,
                stop=stop,
                **call_kwargs,
            )
        except (ContextWindowExceededError, LiteLLMBadRequestError) as e:
            handle_completion_error(
                e,
                perf=perf,
                stage="_agenerate",
                msg_count=msg_count,
                t0=t0,
            )

        elapsed = time.perf_counter() - t0
        perf.info(
            "[llm_router] _agenerate completed msgs=%d tools=%d in %.3fs",
            msg_count,
            len(self._bound_tools) if self._bound_tools else 0,
            elapsed,
        )

        # Convert response to ChatResult with potential tool calls
        message = self._convert_response_to_message(
            response.choices[0].message, response=response
        )
        generation = ChatGeneration(message=message)

        return ChatResult(generations=[generation])

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ):
        """Stream a response using the router (synchronous)."""
        if not self._router:
            raise ValueError("Router not initialized")

        formatted_messages = self._convert_messages(messages)
        formatted_messages = self._trim_messages_to_fit_context(formatted_messages)

        # Merge static model_kwargs (e.g. cache_control_injection_points) under
        # per-call kwargs so callers can still override per invocation. Then add
        # bound tools.
        call_kwargs = {**self.model_kwargs, **kwargs}
        if self._bound_tools:
            call_kwargs["tools"] = self._bound_tools
        if self._tool_choice is not None:
            call_kwargs["tool_choice"] = self._tool_choice

        try:
            response = self._router.completion(
                model=self.model,
                messages=formatted_messages,
                stop=stop,
                stream=True,
                **call_kwargs,
            )
        except (ContextWindowExceededError, LiteLLMBadRequestError) as e:
            handle_streaming_error(e)

        # Yield chunks
        for chunk in response:
            if hasattr(chunk, "choices") and chunk.choices:
                delta = chunk.choices[0].delta
                chunk_msg = self._convert_delta_to_chunk(delta)
                if chunk_msg:
                    yield ChatGenerationChunk(message=chunk_msg)

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ):
        """Stream a response using the router (asynchronous)."""
        if not self._router:
            raise ValueError("Router not initialized")

        perf = get_perf_logger()
        t0 = time.perf_counter()
        msg_count = len(messages)

        formatted_messages = self._convert_messages(messages)
        formatted_messages = self._trim_messages_to_fit_context(formatted_messages)

        # Merge static model_kwargs (e.g. cache_control_injection_points) under
        # per-call kwargs so callers can still override per invocation. Then add
        # bound tools.
        call_kwargs = {**self.model_kwargs, **kwargs}
        if self._bound_tools:
            call_kwargs["tools"] = self._bound_tools
        if self._tool_choice is not None:
            call_kwargs["tool_choice"] = self._tool_choice

        try:
            response = await self._router.acompletion(
                model=self.model,
                messages=formatted_messages,
                stop=stop,
                stream=True,
                stream_options={"include_usage": True},
                **call_kwargs,
            )
        except (ContextWindowExceededError, LiteLLMBadRequestError) as e:
            handle_completion_error(
                e,
                perf=perf,
                stage="_astream",
                msg_count=msg_count,
                t0=t0,
            )

        t_first_chunk = time.perf_counter()
        perf.info(
            "[llm_router] _astream connection established msgs=%d in %.3fs",
            msg_count,
            t_first_chunk - t0,
        )

        chunk_count = 0
        first_chunk_logged = False
        async for chunk in response:
            if hasattr(chunk, "choices") and chunk.choices:
                delta = chunk.choices[0].delta
                chunk_msg = self._convert_delta_to_chunk(delta)
                if chunk_msg:
                    chunk_count += 1
                    if not first_chunk_logged:
                        perf.info(
                            "[llm_router] _astream first chunk in %.3fs "
                            "(total %.3fs from start)",
                            time.perf_counter() - t_first_chunk,
                            time.perf_counter() - t0,
                        )
                        first_chunk_logged = True
                    yield ChatGenerationChunk(message=chunk_msg)

        perf.info(
            "[llm_router] _astream completed chunks=%d total=%.3fs",
            chunk_count,
            time.perf_counter() - t0,
        )

    def _convert_messages(self, messages: list[BaseMessage]) -> list[dict]:
        """Convert LangChain messages to OpenAI format."""
        from langchain_core.messages import (
            AIMessage as AIMsg,
            HumanMessage,
            SystemMessage,
            ToolMessage,
        )

        result = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                result.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                result.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMsg):
                ai_msg: dict[str, Any] = {"role": "assistant"}
                has_tool_calls = hasattr(msg, "tool_calls") and msg.tool_calls

                sanitized = _sanitize_content(msg.content) if msg.content else ""
                ai_msg["content"] = sanitized if sanitized else ""

                if has_tool_calls:
                    ai_msg["tool_calls"] = [
                        {
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": tc.get("name", ""),
                                "arguments": tc.get("args", "{}")
                                if isinstance(tc.get("args"), str)
                                else json.dumps(tc.get("args", {})),
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                result.append(ai_msg)
            elif isinstance(msg, ToolMessage):
                result.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id,
                        "content": msg.content
                        if isinstance(msg.content, str)
                        else json.dumps(msg.content),
                    }
                )
            else:
                # Fallback for other message types
                role = getattr(msg, "type", "user")
                if role == "human":
                    role = "user"
                elif role == "ai":
                    role = "assistant"
                result.append({"role": role, "content": msg.content})

        return result

    def _convert_response_to_message(
        self, response_message: Any, response: Any = None
    ) -> AIMessage:
        """Convert a LiteLLM response message to a LangChain AIMessage."""

        content = getattr(response_message, "content", None) or ""

        # Check for tool calls
        tool_calls = []
        if hasattr(response_message, "tool_calls") and response_message.tool_calls:
            for tc in response_message.tool_calls:
                tool_call = {
                    "id": tc.id if hasattr(tc, "id") else "",
                    "name": tc.function.name if hasattr(tc, "function") else "",
                    "args": {},
                }
                # Parse arguments
                if hasattr(tc, "function") and hasattr(tc.function, "arguments"):
                    try:
                        tool_call["args"] = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        tool_call["args"] = tc.function.arguments
                tool_calls.append(tool_call)

        extra_kwargs: dict[str, Any] = {}
        if response:
            usage = getattr(response, "usage", None)
            if usage:
                extra_kwargs["usage_metadata"] = {
                    "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                    "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
                    "total_tokens": getattr(usage, "total_tokens", 0) or 0,
                }
            extra_kwargs["response_metadata"] = {
                "model_name": getattr(response, "model", "unknown"),
            }

        if tool_calls:
            return AIMessage(content=content, tool_calls=tool_calls, **extra_kwargs)
        return AIMessage(content=content, **extra_kwargs)

    def _convert_delta_to_chunk(self, delta: Any) -> AIMessageChunk | None:
        """Convert a streaming delta to an AIMessageChunk."""

        content = getattr(delta, "content", None) or ""

        # Check for tool calls in delta
        tool_call_chunks = []
        if hasattr(delta, "tool_calls") and delta.tool_calls:
            for tc in delta.tool_calls:
                chunk = {
                    "index": tc.index if hasattr(tc, "index") else 0,
                    "id": tc.id if hasattr(tc, "id") else None,
                    "name": tc.function.name
                    if hasattr(tc, "function") and hasattr(tc.function, "name")
                    else None,
                    "args": tc.function.arguments
                    if hasattr(tc, "function") and hasattr(tc.function, "arguments")
                    else "",
                }
                tool_call_chunks.append(chunk)

        if content or tool_call_chunks:
            if tool_call_chunks:
                return AIMessageChunk(
                    content=content, tool_call_chunks=tool_call_chunks
                )
            return AIMessageChunk(content=content)

        return None


def get_auto_mode_llm(
    *,
    streaming: bool = True,
) -> ChatLiteLLMRouter | None:
    """Return a cached ChatLiteLLMRouter for auto mode.

    Base (no tools) instances are cached per ``streaming`` flag so we
    avoid re-constructing them on every request.  ``bind_tools()`` still
    returns a fresh instance because bound tools differ per agent.
    """
    if not is_initialized():
        logger.warning("LLM Router not initialized for auto mode")
        return None

    cached = _router_instance_cache.get(streaming)
    if cached is not None:
        return cached

    try:
        instance = ChatLiteLLMRouter(streaming=streaming)
        _router_instance_cache[streaming] = instance
        return instance
    except Exception as e:
        logger.error("Failed to create ChatLiteLLMRouter: %s", e)
        return None


__all__ = [
    "ChatLiteLLMRouter",
    "get_auto_mode_llm",
]
