from __future__ import annotations

import json
import types
from unittest.mock import AsyncMock

import httpx
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
    output = await execute(ResearchInput(query="hello"))

    assert output.status == "engine_unavailable"
    assert getattr(output, "degradation_reason", None) == "unreachable"


def test_parse_sse_raises_on_error_event_with_json_payload():
    raw = _sse_line({"type": "error", "data": {"message": "boom"}})
    with pytest.raises(ChainLensError, match="boom"):
        _parse_sse(raw)


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


# Red-phase scaffolds for 9.1a


def test_parse_sse_partial_event_returns_degraded_partial():
    raw = _sse_line(
        {
            "type": "partial",
            "state": "insufficient_evidence",
            "reason": "low coverage",
            "answer": "partial answer",
            "sources": [{"title": "Partial", "url": "https://example.com/partial"}],
        }
    )
    output = _parse_sse(raw)

    assert output.status == "partial"
    assert output.answer == "partial answer"
    assert len(output.sources) == 1
    assert getattr(output, "engine_reason", None) == "low coverage"


def test_parse_sse_insufficient_evidence_event_returns_degraded_reason():
    raw = _sse_line(
        {
            "type": "insufficientEvidence",
            "reason": "no reliable sources",
            "partial": {
                "answer": "",
                "sources": [{"title": "Weak", "url": "https://example.com/weak"}],
            },
        }
    )
    output = _parse_sse(raw)

    assert output.status in ("insufficient_evidence", "partial")
    assert getattr(output, "engine_reason", None) == "no reliable sources"


def test_parse_sse_heartbeat_only_does_not_return_insufficient_evidence():
    raw = _sse_line({"type": "heartbeat"})
    output = _parse_sse(raw)

    assert output.status != "insufficient_evidence"
    assert getattr(output, "saw_heartbeat", False) is True
    assert getattr(output, "degradation_reason", None) == "stream_incomplete"


def test_parse_sse_unknown_event_is_ignored_without_error():
    raw = _sse_line({"type": "noop"}) + _sse_line({"type": "done"})
    output = _parse_sse(raw)

    assert output.status != "insufficient_evidence"
    assert output.status in ("engine_unavailable", "timeout")


def test_parse_sse_blocked_url_coverage_in_partial():
    raw = _sse_line(
        {
            "type": "partial",
            "state": "insufficient_evidence",
            "reason": "blocked",
            "blocked_metadata": [
                {"url": "https://example.com", "block_type": "cloudflare"}
            ],
        }
    )
    output = _parse_sse(raw)

    counter = getattr(output, "blocked_url_coverage_by_block_type", {})
    assert counter.get("cloudflare", 0) >= 1


async def test_call_chainlens_returns_engine_unavailable_when_key_empty(monkeypatch):
    from app.config import config as real_config

    fake_config = types.SimpleNamespace(
        CHAINLENS_API_KEY="",
        CHAINLENS_API_URL=real_config.CHAINLENS_API_URL,
        CHAINLENS_REQUEST_TIMEOUT_SECONDS=real_config.CHAINLENS_REQUEST_TIMEOUT_SECONDS,
    )
    monkeypatch.setattr(
        "app.capabilities.chainlens.research.executor.config", fake_config
    )

    output = await _call_chainlens(ResearchInput(query="test"))
    assert output.status == "engine_unavailable"
    assert getattr(output, "degradation_reason", None) == "not_configured"
    assert output.billable_units == 0
    assert "ConfigurationError" not in output.model_dump_json()


def _fake_http_client(response):
    class _Client:
        def __init__(self, **kwargs):
            self._response = response

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def post(self, *args, **kwargs):
            return self._response

    return _Client


def _stub_config_with_key(monkeypatch):
    from app.config import config as real_config

    fake_config = types.SimpleNamespace(
        CHAINLENS_API_KEY="test-key",
        CHAINLENS_API_URL=real_config.CHAINLENS_API_URL,
        CHAINLENS_REQUEST_TIMEOUT_SECONDS=real_config.CHAINLENS_REQUEST_TIMEOUT_SECONDS,
    )
    monkeypatch.setattr(
        "app.capabilities.chainlens.research.executor.config", fake_config
    )


async def test_call_chainlens_maps_401_to_auth_failed(monkeypatch):
    _stub_config_with_key(monkeypatch)
    from app.capabilities.chainlens.research import executor as executor_mod

    response = type("R", (), {"status_code": 401, "text": "unauthorized"})()
    monkeypatch.setattr(
        executor_mod.httpx, "AsyncClient", _fake_http_client(response)
    )

    output = await _call_chainlens(ResearchInput(query="test"))
    assert output.status == "engine_unavailable"
    assert getattr(output, "degradation_reason", None) == "auth_failed"


async def test_call_chainlens_maps_429_to_rate_limited(monkeypatch):
    _stub_config_with_key(monkeypatch)
    from app.capabilities.chainlens.research import executor as executor_mod

    response = type("R", (), {"status_code": 429, "text": "rate limited"})()
    monkeypatch.setattr(
        executor_mod.httpx, "AsyncClient", _fake_http_client(response)
    )

    output = await _call_chainlens(ResearchInput(query="test"))
    assert output.status == "engine_unavailable"
    assert getattr(output, "degradation_reason", None) == "rate_limited"


async def test_call_chainlens_maps_5xx_to_upstream_error(monkeypatch):
    _stub_config_with_key(monkeypatch)
    from app.capabilities.chainlens.research import executor as executor_mod

    response = type("R", (), {"status_code": 503, "text": "boom"})()
    monkeypatch.setattr(
        executor_mod.httpx, "AsyncClient", _fake_http_client(response)
    )

    output = await _call_chainlens(ResearchInput(query="test"))
    assert output.status == "engine_unavailable"
    assert getattr(output, "degradation_reason", None) == "upstream_error"


async def test_call_chainlens_maps_unknown_4xx_to_upstream_error(monkeypatch):
    _stub_config_with_key(monkeypatch)
    from app.capabilities.chainlens.research import executor as executor_mod

    response = type("R", (), {"status_code": 422, "text": "bad"})()
    monkeypatch.setattr(
        executor_mod.httpx, "AsyncClient", _fake_http_client(response)
    )

    output = await _call_chainlens(ResearchInput(query="test"))
    assert output.status == "engine_unavailable"
    assert getattr(output, "degradation_reason", None) in ("upstream_error", "auth_failed")


async def test_build_research_executor_degrades_on_timeout():
    async def raise_timeout(_):
        raise httpx.TimeoutException("timeout")

    execute = build_research_executor(raise_timeout)
    output = await execute(ResearchInput(query="test"))
    assert output.status == "engine_unavailable"
    assert getattr(output, "degradation_reason", None) == "timeout"


async def test_build_research_executor_degrades_on_request_error():
    async def raise_request_error(_):
        raise httpx.ConnectError("dns failed")

    execute = build_research_executor(raise_request_error)
    output = await execute(ResearchInput(query="test"))
    assert output.status == "engine_unavailable"
    assert getattr(output, "degradation_reason", None) == "unreachable"


async def test_build_research_executor_degrades_on_chainlens_error():
    async def raise_chainlens_error(_):
        raise ChainLensError("upstream typed error", code="CHAINLENS_UPSTREAM_ERROR")

    execute = build_research_executor(raise_chainlens_error)
    output = await execute(ResearchInput(query="test"))
    assert output.status == "engine_unavailable"
    assert getattr(output, "degradation_reason", None) == "upstream_error"
