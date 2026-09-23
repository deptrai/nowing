"""
ToolCallNameRepairMiddleware — three-stage tool-call repair.

Operation:
0. **Stage 0 — markup recovery:** if the model emitted tool calls as
   ``<|open|>call tool="name" ...<|close|>call`` markup inside the message
   text (instead of the provider's structured ``tool_calls`` field), parse
   them out, attach them to ``message.tool_calls``, and strip the markup
   from the visible content. Some upstream models intermittently produce
   this wire format when their tool-call channel degrades.
1. **Stage 1 — lowercase repair:** if a tool call's ``name`` is not in
   the registry but ``name.lower()`` is, rewrite in place. Catches
   models that emit ``Search`` instead of ``search``.
2. **Stage 2 — invalid fallback:** if still unmatched, rewrite the call
   to ``invalid`` with ``args={"tool": original_name, "error": <error>}``
   so the registered :func:`invalid_tool` returns the error to the model
   for self-correction.

Ported from OpenCode's ``packages/opencode/src/session/llm.ts:339-358``
+ ``packages/opencode/src/tool/invalid.ts``. LangChain has no equivalent:
:class:`deepagents.middleware.PatchToolCallsMiddleware` patches
*dangling* tool calls (no matching ToolMessage) but does nothing about
wrong names, and the model framework's default behavior on an unknown
name is to crash the turn rather than route to a self-correction
fallback.
"""

from __future__ import annotations

import difflib
import json
import logging
import re
from typing import Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ContextT,
    ResponseT,
)
from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)

# Some models occasionally emit tool calls as plain text using this
# wire markup instead of the provider's structured tool_calls field.
# Example: <|open|>call tool="task" index="1"<|sep|><|open|>argument
# key="subagent_type"<|sep|>chainlens<|close|>argument<|sep|><|close|>call
_TOOL_MARKUP_CALL_RE = re.compile(
    r'<\|open\|>call\s+tool="(?P<name>[^"]+)"'
    r'(?:\s+index="(?P<index>\d+)")?<\|sep\|>'
    r"(?P<body>.*?)"
    r"<\|close\|>call",
    re.DOTALL,
)
_TOOL_MARKUP_ARG_RE = re.compile(
    r'<\|open\|>argument\s+key="(?P<key>[^"]+)"'
    r'(?:\s+type="[^"]*")?<\|sep\|>'
    r"(?P<value>.*?)"
    r"<\|close\|>argument",
    re.DOTALL,
)
# The full markup block (including the wrapping tools/message envelopes) is
# stripped from the visible text once its calls have been recovered.
_TOOL_MARKUP_BLOCK_RE = re.compile(
    r"<\|open\|>tools<\|sep\|>.*?<\|close\|>tools"
    r"(?:<\|sep\|><\|close\|>message)?(?:<\|sep\|>)?",
    re.DOTALL,
)


def _parse_tool_markup_calls(text: str) -> list[dict[str, Any]]:
    """Extract structured tool calls from ``<|open|>call`` text markup."""
    calls: list[dict[str, Any]] = []
    for match in _TOOL_MARKUP_CALL_RE.finditer(text):
        args: dict[str, Any] = {}
        for arg_match in _TOOL_MARKUP_ARG_RE.finditer(match.group("body")):
            key = arg_match.group("key")
            raw_value = arg_match.group("value").strip()
            try:
                args[key] = json.loads(raw_value)
            except (json.JSONDecodeError, ValueError):
                args[key] = raw_value
        calls.append(
            {
                "name": match.group("name"),
                "args": args,
                "id": f"call_markup_{len(calls)}",
                "type": "tool_call",
            }
        )
    return calls


def _strip_tool_markup(text: str) -> str:
    """Remove the tool markup block (and any dangling markup tokens)."""
    cleaned = _TOOL_MARKUP_BLOCK_RE.sub("", text)
    # Dangling tokens outside a complete block (partial/truncated emissions).
    cleaned = re.sub(r"<\|(?:open|close|sep)\|>", "", cleaned)
    return cleaned


def _coerce_existing_tool_call(call: Any) -> dict[str, Any]:
    """Normalize a tool call entry to a mutable dict."""
    if isinstance(call, dict):
        return dict(call)
    return {
        "name": getattr(call, "name", None),
        "args": getattr(call, "args", {}),
        "id": getattr(call, "id", None),
        "type": "tool_call",
    }


class ToolCallNameRepairMiddleware(
    AgentMiddleware[AgentState[ResponseT], ContextT, ResponseT]
):
    """Three-stage tool-call repair on the most recent ``AIMessage``.

    Args:
        registered_tool_names: Set of canonically-registered tool names.
            ``invalid`` should be in this set so the fallback dispatches.
        fuzzy_match_threshold: Optional ``difflib`` ratio (0-1) for the
            fuzzy-match step that runs *between* lowercase and invalid.
            Set to ``None`` to disable fuzzy matching (default in
            OpenCode; we mirror that to avoid silent rewrites).
    """

    def __init__(
        self,
        *,
        registered_tool_names: set[str],
        fuzzy_match_threshold: float | None = 0.85,
    ) -> None:
        super().__init__()
        self._registered = set(registered_tool_names)
        self._registered_lower = {name.lower(): name for name in self._registered}
        self._fuzzy_threshold = fuzzy_match_threshold
        self.tools = []

    def _registered_for_runtime(self, runtime: Runtime[ContextT]) -> set[str]:
        """Allow runtime overrides to expand the set (e.g. dynamic MCP tools)."""
        ctx_tools = getattr(runtime.context, "registered_tool_names", None)
        if isinstance(ctx_tools, set | frozenset):
            return self._registered | set(ctx_tools)
        if isinstance(ctx_tools, list | tuple):
            return self._registered | set(ctx_tools)
        return self._registered

    def _repair_one(
        self,
        call: dict[str, Any],
        registered: set[str],
    ) -> dict[str, Any]:
        name = call.get("name")
        if not isinstance(name, str):
            return call

        if name in registered:
            return call

        # Stage 1 — lowercase
        lowered = name.lower()
        if lowered in registered:
            call["name"] = lowered
            metadata = dict(call.get("response_metadata") or {})
            metadata.setdefault("repair", "lowercase")
            call["response_metadata"] = metadata
            return call

        # Optional fuzzy step (off by default — see class docstring)
        if self._fuzzy_threshold is not None:
            close = difflib.get_close_matches(
                name, registered, n=1, cutoff=self._fuzzy_threshold
            )
            if close:
                call["name"] = close[0]
                metadata = dict(call.get("response_metadata") or {})
                metadata.setdefault("repair", f"fuzzy:{name}->{close[0]}")
                call["response_metadata"] = metadata
                return call

        # Stage 2 — invalid fallback
        # Local import keeps the middleware module import-light and avoids any
        # tools <-> middleware import-order coupling at module scope.
        from app.agents.chat.multi_agent_chat.main_agent.tools.invalid_tool import (
            INVALID_TOOL_NAME,
        )

        if INVALID_TOOL_NAME in registered:
            original_args = call.get("args") or {}
            error_msg = (
                f"Tool name '{name}' is not registered. "
                f"Original arguments were: {original_args!r}."
            )
            call["name"] = INVALID_TOOL_NAME
            call["args"] = {"tool": name, "error": error_msg}
            metadata = dict(call.get("response_metadata") or {})
            metadata.setdefault("repair", f"invalid_fallback:{name}")
            call["response_metadata"] = metadata
        else:
            logger.warning(
                "Could not repair unknown tool call %r; 'invalid' tool not registered",
                name,
            )
        return call

    def _maybe_repair(
        self,
        message: AIMessage,
        registered: set[str],
    ) -> AIMessage | None:
        content = message.content
        if isinstance(content, list):
            # LangChain allows the message body to be a list of blocks; keep the
            # textual parts for markup recovery while preserving the rest.
            text_blocks = [
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            markup_source = "\n".join(text_blocks)
        else:
            markup_source = str(content or "")

        markup_calls = (
            _parse_tool_markup_calls(markup_source)
            if "<|open|>" in markup_source
            else []
        )

        calls = list(message.tool_calls)
        if markup_calls:
            # Merge the recovered calls with any structured ones the model
            # already emitted so we don't double-dispatch.
            def _call_key(c: dict[str, Any]) -> tuple[str, str]:
                return (
                    str(c.get("name")),
                    json.dumps(c.get("args") or {}, sort_keys=True, default=str),
                )

            existing_pairs = {_call_key(c) for c in calls}
            for recovered in markup_calls:
                pair = _call_key(recovered)
                if pair in existing_pairs:
                    continue
                calls.append(recovered)
                existing_pairs.add(pair)

        if not calls:
            return None

        new_calls: list[dict[str, Any]] = []
        any_changed = bool(markup_calls)
        for raw in calls:
            call = _coerce_existing_tool_call(raw)
            before = (call.get("name"), call.get("args"))
            repaired = self._repair_one(call, registered)
            after = (repaired.get("name"), repaired.get("args"))
            if before != after:
                any_changed = True
            new_calls.append(repaired)

        update: dict[str, Any] = {"tool_calls": new_calls}
        if markup_calls:
            cleaned = _strip_tool_markup(markup_source)
            if isinstance(content, list):
                new_blocks = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        block_text = block.get("text", "")
                        cleaned_block = _strip_tool_markup(block_text)
                        if cleaned_block:
                            new_blocks.append({**block, "text": cleaned_block})
                    else:
                        new_blocks.append(block)
                update["content"] = new_blocks
            else:
                update["content"] = cleaned
            any_changed = True

        if not any_changed:
            return None

        return message.model_copy(update=update)

    def after_model(  # type: ignore[override]
        self,
        state: AgentState[ResponseT],
        runtime: Runtime[ContextT],
    ) -> dict[str, Any] | None:
        messages = state.get("messages") or []
        if not messages:
            return None
        last = messages[-1]
        if not isinstance(last, AIMessage):
            return None

        registered = self._registered_for_runtime(runtime)
        repaired = self._maybe_repair(last, registered)
        if repaired is None:
            return None
        return {"messages": [repaired]}

    async def aafter_model(  # type: ignore[override]
        self,
        state: AgentState[ResponseT],
        runtime: Runtime[ContextT],
    ) -> dict[str, Any] | None:
        return self.after_model(state, runtime)


__all__ = [
    "ToolCallNameRepairMiddleware",
]
