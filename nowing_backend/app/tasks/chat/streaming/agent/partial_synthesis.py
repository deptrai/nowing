"""Partial synthesis khi model-call cap chặn run (Story 42.6).

Khi ``ModelCallLimitMiddleware`` ngắt run (exit_behavior="end"), tin nhắn cuối
trong state là AIMessage injected "Model call limits exceeded: ...". Thay vì
để turn trống (text=0), module này tổng hợp partial answer từ tool-call parts
đã hoàn tất trong turn và sinh text thông báo cho user.

Best-effort toàn bộ: synthesis fail/timeout → notice-only; không bao giờ raise.
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from app.utils.perf import get_perf_logger

_perf_log = get_perf_logger()

# Prefix injected bởi langchain ``_build_limit_exceeded_message`` — stable
# theo langchain hiện tại; fallback state-count nằm ở ``cap_hit``.
_LIMIT_MESSAGE_PREFIX = "Model call limits exceeded"

# Timeout cho 1 LLM synthesis call.
SYNTHESIS_TIMEOUT_S = 15.0

# Status part vocabulary (enumerted, xem Design Notes spec 42.6):
#   text ∈ {"(no text response)", "(partial response — step cap reached)"}
#   partial: bool optional (vắng = false)
PARTIAL_STATUS_PART: dict[str, Any] = {
    "type": "status",
    "text": "(partial response — step cap reached)",
    "partial": True,
}

# llm_caller: nhận prompt string, trả text (hoặc None). Test-friendly seam.
LlmCaller = Callable[[str], Awaitable[str | None]]


def cap_hit(state_values: dict[str, Any]) -> str | None:
    """Trả về 'run' | 'thread' khi cap-hit, None nếu không.

    Primary: last AIMessage content bắt đầu bằng prefix injected. Fallback:
    state counters >= limit (phòng khi langchain đổi text message).
    """
    from app.agents.chat.multi_agent_chat.shared.middleware.resilience.model_call_limit import (
        MODEL_RUN_LIMIT,
        MODEL_THREAD_LIMIT,
    )

    messages = state_values.get("messages") or []
    for message in reversed(messages):
        if getattr(message, "type", None) != "ai":
            continue
        content = getattr(message, "content", "")
        if isinstance(content, str) and content.startswith(_LIMIT_MESSAGE_PREFIX):
            return "run"
        break  # chỉ xét AIMessage cuối cùng

    run_count = state_values.get("run_model_call_count", 0) or 0
    if run_count >= MODEL_RUN_LIMIT:
        return "run"
    thread_count = state_values.get("thread_model_call_count", 0) or 0
    if thread_count >= MODEL_THREAD_LIMIT:
        return "thread"
    return None


def completed_tool_parts(content_builder: Any) -> list[dict[str, Any]]:
    """Tool-call parts đã có result trong builder (state completed)."""
    if content_builder is None:
        return []
    return [
        part
        for part in getattr(content_builder, "parts", [])
        if part.get("type") == "tool-call" and "result" in part
    ]


def _tool_names(tool_parts: list[dict[str, Any]]) -> list[str]:
    return [
        str(part.get("toolName") or "unknown_tool")
        for part in tool_parts
    ]


def notice_only_partial(tool_parts: list[dict[str, Any]]) -> str:
    """Fallback notice khi synthesis LLM fail: liệt kê tên tools đã chạy."""
    names = _tool_names(tool_parts)
    if not names:
        return no_tools_partial()
    listed = ", ".join(names)
    return (
        f"Đã xử lý {len(names)} tool calls ({listed}) nhưng chưa hoàn tất "
        f"phản hồi đầy đủ do đạt giới hạn số bước xử lý."
    )


def no_tools_partial() -> str:
    """Notice khi cap hit mà không có tool result nào."""
    return (
        "Không hoàn tất tool call nào trước khi đạt giới hạn số bước xử lý. "
        "Vui lòng thử lại."
    )


async def synthesize_partial(
    tool_parts: list[dict[str, Any]], llm_caller: LlmCaller
) -> str | None:
    """Tóm tắt tool results bằng 1 LLM call (timeout 15s). Fail → None."""
    if not tool_parts:
        return None
    snippets: list[str] = []
    # Cap số parts đưa vào prompt — cap-hit run có thể có ~80 tool parts;
    # prompt 160KB cho 1 notice là lãng phí (phần dư nói trong tổng số).
    for part in tool_parts[:20]:
        name = part.get("toolName") or "unknown_tool"
        result = part.get("result")
        text = result if isinstance(result, str) else str(result)
        snippets.append(f"- {name}: {text[:2000]}")
    prompt = (
        "Tóm tắt ngắn các kết quả tool sau và nói rõ đã xử lý "
        f"{len(tool_parts)} tool calls, chưa hoàn tất (đạt giới hạn số bước "
        "xử lý). Trả lời bằng tiếng Việt, tối đa ~4 câu.\n\n" + "\n".join(snippets)
    )
    try:
        text = await asyncio.wait_for(llm_caller(prompt), timeout=SYNTHESIS_TIMEOUT_S)
    except Exception as exc:  # synthesis fail/timeout → fallback notice-only
        _perf_log.warning(
            "[partial_synthesis] LLM synthesis failed: %s", exc
        )
        return None
    if not text or not text.strip():
        return None
    return text.strip()
