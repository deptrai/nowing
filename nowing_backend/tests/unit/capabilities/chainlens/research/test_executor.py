from __future__ import annotations

import json

import pytest

from app.capabilities.chainlens.research.executor import (
    ChainLensError,
    _call_chainlens,
    _parse_sse,
    build_research_executor,
)
from app.capabilities.chainlens.research.schemas import ResearchInput, ResearchOutput

pytestmark = pytest.mark.unit


def _sse_line(payload: object) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def test_parse_sse_extracts_answer_and_sources():
    raw = (
        _sse_line(
            {"type": "block", "block": {"id": "txt", "type": "text", "data": "Answer"}}
        )
        + _sse_line(
            {
                "type": "block",
                "block": {
                    "id": "src",
                    "type": "source",
                    "data": [
                        {
                            "metadata": {
                                "title": "Example",
                                "url": "https://example.com",
                            },
                            "content": "snippet",
                        }
                    ],
                },
            }
        )
        + _sse_line(
            {
                "type": "done",
                "chatId": "chat-123",
                "webUrl": "https://research.chainlens.net/c/chat-123",
            }
        )
    )
    output = _parse_sse(raw)

    assert output.answer == "Answer"
    assert len(output.sources) == 1
    assert output.sources[0].title == "Example"
    assert output.sources[0].url == "https://example.com"
    assert output.chat_id == "chat-123"
    assert output.web_url == "https://research.chainlens.net/c/chat-123"
    assert output.status == "complete"


def test_parse_sse_raises_on_error_event():
    raw = "event: error\ndata: upstream boom\n\n"
    with pytest.raises(ChainLensError):
        _parse_sse(raw)


def test_parse_sse_timeout_when_no_done_and_no_data():
    raw = "data: this is not json\n\n"
    output = _parse_sse(raw)

    assert output.status == "timeout"
    assert output.answer == ""
    assert output.sources == []


def test_parse_sse_insufficient_evidence_when_done_but_empty():
    raw = _sse_line({"type": "done", "chatId": "chat-123"})
    output = _parse_sse(raw)

    assert output.status == "insufficient_evidence"
    assert output.chat_id == "chat-123"


async def test_build_research_executor_maps_input_to_output():
    async def fake_search(payload: ResearchInput) -> ResearchOutput:
        return ResearchOutput(answer=f"Result for {payload.query}")

    execute = build_research_executor(fake_search)
    output = await execute(ResearchInput(query="hello"))

    assert output.answer == "Result for hello"


async def test_build_research_executor_catches_network_errors():
    import httpx

    async def failing_search(_payload: ResearchInput) -> ResearchOutput:
        raise httpx.ConnectError("network down")

    execute = build_research_executor(failing_search)
    from app.exceptions import ExternalServiceError

    with pytest.raises(ExternalServiceError):
        await execute(ResearchInput(query="hello"))


def test_parse_sse_raises_on_error_event_with_json_payload():
    raw = _sse_line({"type": "error", "data": {"message": "boom"}})
    with pytest.raises(ChainLensError, match="boom"):
        _parse_sse(raw)


async def test_call_chainlens_raises_when_api_key_missing(monkeypatch):
    import types

    from app.config import config as real_config
    from app.exceptions import ConfigurationError

    fake_config = types.SimpleNamespace(
        CHAINLENS_API_KEY="",
        CHAINLENS_API_URL=real_config.CHAINLENS_API_URL,
        CHAINLENS_REQUEST_TIMEOUT_SECONDS=real_config.CHAINLENS_REQUEST_TIMEOUT_SECONDS,
    )
    monkeypatch.setattr(
        "app.capabilities.chainlens.research.executor.config", fake_config
    )

    with pytest.raises(ConfigurationError):
        await _call_chainlens(ResearchInput(query="test"))


def test_parse_sse_skips_source_with_empty_url():
    raw = _sse_line(
        {
            "type": "block",
            "block": {
                "id": "src",
                "type": "source",
                "data": [
                    {"metadata": {"title": "No URL", "url": ""}, "content": "snippet"},
                    {
                        "metadata": {"title": "Good URL", "url": "https://example.com"},
                        "content": "snippet",
                    },
                ],
            },
        }
    ) + _sse_line({"type": "done"})
    output = _parse_sse(raw)

    assert len(output.sources) == 1
    assert output.sources[0].title == "Good URL"
    assert output.sources[0].url == "https://example.com"
