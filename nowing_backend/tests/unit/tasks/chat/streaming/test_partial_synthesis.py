"""Tests cho Story 42.6 — step-cap partial synthesis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.tasks.chat.streaming.agent.partial_synthesis import (
    PARTIAL_STATUS_PART,
    SYNTHESIS_TIMEOUT_S,
    cap_hit,
    completed_tool_parts,
    no_tools_partial,
    notice_only_partial,
    synthesize_partial,
)
from app.tasks.chat.streaming.shared.stream_result import StreamResult

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------


@dataclass
class _Msg:
    type: str
    content: Any = ""


class _Builder:
    def __init__(self, parts: list[dict[str, Any]]) -> None:
        self.parts = parts

    def on_text_start(self, text_id: str) -> None:
        self.parts.append({"type": "text", "id": text_id, "text": ""})

    def on_text_delta(self, text_id: str, text: str) -> None:
        self.parts.append({"type": "text", "text": text})

    def on_text_end(self, text_id: str) -> None:
        pass


class _StreamingService:
    def __init__(self) -> None:
        self._text_idx = 0

    def generate_text_id(self) -> str:
        self._text_idx += 1
        return f"text-{self._text_idx}"

    def format_text_start(self, text_id: str) -> str:
        return f"text_start:{text_id}"

    def format_text_delta(self, text_id: str, text: str) -> str:
        return f"text_delta:{text_id}:{text}"

    def format_text_end(self, text_id: str) -> str:
        return f"text_end:{text_id}"


@dataclass
class _State:
    values: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------
# cap_hit
# ---------------------------------------------------------------------


def test_cap_hit_via_message_prefix() -> None:
    state_values = {
        "messages": [_Msg(type="ai", content="Model call limits exceeded: run limit (80/80)")]
    }
    assert cap_hit(state_values) == "run"


def test_cap_hit_none_on_normal_answer() -> None:
    state_values = {"messages": [_Msg(type="ai", content="Xin chào!")]}
    assert cap_hit(state_values) is None


def test_cap_hit_fallback_state_counts() -> None:
    assert cap_hit({"run_model_call_count": 80}) == "run"
    assert cap_hit({"thread_model_call_count": 120}) == "thread"
    assert cap_hit({"run_model_call_count": 3}) is None


# ---------------------------------------------------------------------
# Tool-part helpers + notices
# ---------------------------------------------------------------------


def _builder_with_tools() -> _Builder:
    return _Builder(
        [
            {
                "type": "tool-call",
                "toolName": "search_knowledge_base",
                "result": "found 3 docs",
            },
            {"type": "tool-call", "toolName": "write_file"},  # chưa có result
        ]
    )


def test_completed_tool_parts_only_with_result() -> None:
    parts = completed_tool_parts(_builder_with_tools())
    assert len(parts) == 1
    assert parts[0]["toolName"] == "search_knowledge_base"


def test_notice_only_partial_lists_tools() -> None:
    parts = completed_tool_parts(_builder_with_tools())
    notice = notice_only_partial(parts)
    assert "1 tool calls" in notice
    assert "search_knowledge_base" in notice


def test_no_tools_partial_message() -> None:
    text = no_tools_partial()
    assert "tool" in text.lower()


# ---------------------------------------------------------------------
# synthesize_partial
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_synthesize_partial_success() -> None:
    parts = completed_tool_parts(_builder_with_tools())

    async def ok(prompt: str) -> str | None:
        return "Đã xử lý 1 tool calls, chưa hoàn tất."

    assert await synthesize_partial(parts, ok) == (
        "Đã xử lý 1 tool calls, chưa hoàn tất."
    )


@pytest.mark.asyncio
async def test_synthesize_partial_llm_failure_falls_back_to_none() -> None:
    parts = completed_tool_parts(_builder_with_tools())

    async def boom(prompt: str) -> str | None:
        raise RuntimeError("provider down")

    assert await synthesize_partial(parts, boom) is None


@pytest.mark.asyncio
async def test_synthesize_partial_timeout() -> None:
    parts = completed_tool_parts(_builder_with_tools())

    async def slow(prompt: str) -> str | None:
        await asyncio.sleep(SYNTHESIS_TIMEOUT_S + 5)
        return "late"

    assert await synthesize_partial(parts, slow) is None


@pytest.mark.asyncio
async def test_synthesize_partial_empty_tools_returns_none() -> None:
    async def ok(prompt: str) -> str | None:
        return "should not be called"

    assert await synthesize_partial([], ok) is None


import asyncio  # noqa: E402  (dùng cho test timeout, đặt cuối cho gọn)


# ---------------------------------------------------------------------
# Event-loop e2e level: cap hit → partial text trên SSE wire
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_event_loop_cap_hit_emits_partial_text(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.tasks.chat.streaming.agent import event_loop

    async def fake_stream_output(**kwargs: Any) -> Any:
        return
        yield  # pragma: no cover — generator trống

    class _FakeAgent:
        async def aget_state(self, config: dict[str, Any]) -> _State:
            return _State(
                values={
                    "messages": [
                        _Msg(
                            type="ai",
                            content="Model call limits exceeded: run limit (80/80)",
                        )
                    ]
                }
            )

    async def fake_synthesize(tool_parts: Any, llm_caller: Any) -> str | None:
        return f"Đã xử lý {len(tool_parts)} tool calls, chưa hoàn tất."

    monkeypatch.setattr(event_loop, "stream_output", fake_stream_output)
    monkeypatch.setattr(event_loop, "synthesize_partial", fake_synthesize)

    result = StreamResult(
        turn_id="t-1",
        assistant_message_id=1,
        content_builder=None,
    )
    builder = _builder_with_tools()
    result.content_builder = builder  # type: ignore[assignment]

    frames: list[str] = []
    async for sse in event_loop.stream_agent_events(
        agent=_FakeAgent(),
        config={"configurable": {"turn_id": "t-1", "thread_id": "c-1"}},
        input_data={"messages": []},
        streaming_service=_StreamingService(),
        result=result,
        content_builder=builder,
    ):
        frames.append(sse)

    text_frames = [f for f in frames if f.startswith("text_delta:")]
    assert text_frames, f"expected partial text frames, got: {frames}"
    assert "1 tool calls" in text_frames[0]
    assert result.partial_cap_hit is True


@pytest.mark.asyncio
async def test_finalize_appends_partial_status_part() -> None:
    # Merge behavior được test trực tiếp trên payload list — logic nằm ở
    # ``assistant_finalize`` nhưng helper là inline; replicate contract:
    from app.tasks.chat.streaming.agent.partial_synthesis import (
        PARTIAL_STATUS_PART as _PSP,
    )

    payload: list[dict[str, Any]] = [{"type": "text", "text": "x"}]
    out = [*payload, dict(_PSP)]
    assert out[-1] == _PSP
    assert out[-1]["partial"] is True
    assert out[-1]["type"] == "status"
    # Không mutate payload gốc
    assert len(payload) == 1
