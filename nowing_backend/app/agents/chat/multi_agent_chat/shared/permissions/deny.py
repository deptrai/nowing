"""Synthesise a ``ToolMessage`` for a denied tool call.

The denied call is replaced with this message so the model sees a typed
``permission_denied`` error in ``ToolMessage.additional_kwargs["error"]``
and can adjust its plan without retrying the same forbidden call.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import ToolMessage

from app.agents.chat.multi_agent_chat.shared.permissions.model import Rule
from app.agents.chat.runtime.errors import StreamingError


def build_deny_message(tool_call: dict[str, Any], rule: Rule) -> ToolMessage:
    err = StreamingError(
        code="permission_denied",
        retryable=False,
        suggestion=(
            f"rule permission={rule.permission!r} pattern={rule.pattern!r} "
            f"blocked this call"
        ),
    )
    return ToolMessage(
        content=(
            f"Permission denied: rule {rule.permission}/{rule.pattern} "
            f"blocked tool {tool_call.get('name')!r}."
        ),
        tool_call_id=tool_call.get("id") or "",
        name=tool_call.get("name"),
        status="error",
        additional_kwargs={"error": err.model_dump()},
    )


def build_reject_message(tool_call: dict[str, Any], feedback: str | None) -> ToolMessage:
    """Synthesise a ``ToolMessage`` cho tool call bị user reject (spec 42.5).

    Reject path KHÔNG raise ``RejectedError``/``CorrectedError`` — exception
    thoát ra stream loop để tool_call lơ lửng không ToolMessage, converter
    Gemini drop functionResponse → 400 C1 (functionCall != functionResponse).
    Thay vào đó pending call bị drop kèm ToolMessage ``status="error"`` cùng
    ``tool_call_id`` (shape giống :func:`build_deny_message`, code
    ``"cancelled"``), feedback của user (nếu có) nằm trong content để model
    thấy chỉ dẫn và điều chỉnh.
    """
    err = StreamingError(
        code="cancelled",
        retryable=False,
        suggestion="User rejected this tool call; adjust or ask before retrying.",
    )
    detail = f" User feedback: {feedback}" if feedback and feedback.strip() else ""
    return ToolMessage(
        content=(
            f"User rejected the tool call for {tool_call.get('name')!r} "
            f"(tool_call_id={tool_call.get('id')!r}).{detail}"
        ),
        tool_call_id=tool_call.get("id") or "",
        name=tool_call.get("name"),
        status="error",
        additional_kwargs={"error": err.model_dump()},
    )


__all__ = ["build_deny_message", "build_reject_message"]
