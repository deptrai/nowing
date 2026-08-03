from __future__ import annotations

import inspect
import json
import types
from pathlib import Path

import httpx
import pytest

from app.capabilities.chainlens.research.executor import (
    ChainLensError,
    _call_chainlens,
    _parse_sse,
    _SSEParser,
    build_research_executor,
)
from app.capabilities.chainlens.research.schemas import ResearchInput, ResearchOutput

pytestmark = [pytest.mark.unit, pytest.mark.contract]


def _sse_line(payload: object) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@pytest.mark.test_id("9-1b-001")
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


@pytest.mark.test_id("9-1b-002")
def test_parse_sse_raises_on_error_data_frame():
    raw = _sse_line({"type": "error", "data": "upstream boom"})
    with pytest.raises(ChainLensError):
        _parse_sse(raw)


@pytest.mark.test_id("9-1b-003")
def test_parse_sse_timeout_when_no_done_and_no_data():
    raw = "data: this is not json\n\n"
    output = _parse_sse(raw)

    assert output.status == "timeout"
    assert output.answer == ""
    assert output.sources == []


@pytest.mark.test_id("9-1b-004")
def test_parse_sse_done_but_empty_is_degraded():
    raw = _sse_line({"type": "done", "chatId": "chat-123"})
    output = _parse_sse(raw)

    assert output.status != "insufficient_evidence"
    assert output.status == "engine_unavailable"
    assert output.chat_id == "chat-123"


@pytest.mark.test_id("9-1b-005")
async def test_build_research_executor_maps_input_to_output():
    async def fake_search(payload: ResearchInput) -> ResearchOutput:
        return ResearchOutput(answer=f"Result for {payload.query}")

    execute = build_research_executor(fake_search)
    output = await execute(ResearchInput(query="hello"))

    assert output.answer == "Result for hello"


@pytest.mark.test_id("9-1b-006")
async def test_build_research_executor_catches_network_errors():
    import httpx

    async def failing_search(_payload: ResearchInput) -> ResearchOutput:
        raise httpx.ConnectError("network down")

    execute = build_research_executor(failing_search)
    output = await execute(ResearchInput(query="hello"))

    assert output.status == "engine_unavailable"
    assert output.degradation_reason == "unreachable"


@pytest.mark.test_id("9-1b-007")
def test_research_input_rejects_blank_query():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ResearchInput(query="   ")

    with pytest.raises(ValidationError):
        ResearchInput(query="")

    with pytest.raises(ValidationError):
        ResearchInput(query="\t\n")


@pytest.mark.test_id("9-1b-008")
def test_research_input_rejects_oversized_query():
    from pydantic import ValidationError

    from app.capabilities.chainlens.research.schemas import MAX_QUERY_LENGTH

    with pytest.raises(ValidationError):
        ResearchInput(query="x" * (MAX_QUERY_LENGTH + 1))

    # Boundary: exactly the limit is allowed.
    assert ResearchInput(query="x" * MAX_QUERY_LENGTH).query == "x" * MAX_QUERY_LENGTH


@pytest.mark.test_id("9-1b-009")
def test_parse_sse_raises_on_error_data_frame_with_json_payload():
    raw = _sse_line({"type": "error", "data": {"message": "boom"}})
    with pytest.raises(ChainLensError, match="boom"):
        _parse_sse(raw)


@pytest.mark.test_id("9-1b-010")
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


@pytest.mark.test_id("9-1b-011")
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


@pytest.mark.test_id("9-1b-012")
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

    assert output.status == "partial"
    assert getattr(output, "engine_reason", None) == "no reliable sources"


@pytest.mark.test_id("9-1b-013")
def test_parse_sse_heartbeat_only_does_not_return_insufficient_evidence():
    raw = _sse_line({"type": "heartbeat"})
    output = _parse_sse(raw)

    assert output.status != "insufficient_evidence"
    assert getattr(output, "saw_heartbeat", False) is True
    assert getattr(output, "degradation_reason", None) == "stream_incomplete"


@pytest.mark.test_id("9-1b-014")
def test_parse_sse_unknown_event_is_ignored_without_error():
    raw = _sse_line({"type": "noop"}) + _sse_line({"type": "done"})
    output = _parse_sse(raw)

    assert output.status != "insufficient_evidence"
    assert output.status == "engine_unavailable"


@pytest.mark.test_id("9-1b-015")
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


@pytest.mark.test_id("9-1b-016")
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
    class _StreamingResponse:
        def __init__(self, inner):
            self._inner = inner

        @property
        def status_code(self):
            return getattr(self._inner, "status_code", 200)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def aclose(self):
            return None

        async def aiter_lines(self):
            text = getattr(self._inner, "text", "") or ""
            for line in text.splitlines():
                yield line

    class _Client:
        def __init__(self, **kwargs):
            self._response = _StreamingResponse(response)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        def stream(self, *args, **kwargs):
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


@pytest.mark.test_id("9-1b-017")
async def test_call_chainlens_maps_401_to_auth_failed(monkeypatch):
    _stub_config_with_key(monkeypatch)
    from app.capabilities.chainlens.research import executor as executor_mod

    response = type("R", (), {"status_code": 401, "text": "unauthorized"})()
    monkeypatch.setattr(executor_mod.httpx, "AsyncClient", _fake_http_client(response))

    output = await _call_chainlens(ResearchInput(query="test"))
    assert output.status == "engine_unavailable"
    assert getattr(output, "degradation_reason", None) == "auth_failed"


@pytest.mark.test_id("9-1b-018")
async def test_call_chainlens_maps_429_to_rate_limited(monkeypatch):
    _stub_config_with_key(monkeypatch)
    from app.capabilities.chainlens.research import executor as executor_mod

    response = type("R", (), {"status_code": 429, "text": "rate limited"})()
    monkeypatch.setattr(executor_mod.httpx, "AsyncClient", _fake_http_client(response))

    output = await _call_chainlens(ResearchInput(query="test"))
    assert output.status == "engine_unavailable"
    assert getattr(output, "degradation_reason", None) == "rate_limited"


@pytest.mark.test_id("9-1b-019")
async def test_call_chainlens_maps_5xx_to_upstream_error(monkeypatch):
    _stub_config_with_key(monkeypatch)
    from app.capabilities.chainlens.research import executor as executor_mod

    response = type("R", (), {"status_code": 503, "text": "boom"})()
    monkeypatch.setattr(executor_mod.httpx, "AsyncClient", _fake_http_client(response))

    output = await _call_chainlens(ResearchInput(query="test"))
    assert output.status == "engine_unavailable"
    assert getattr(output, "degradation_reason", None) == "upstream_error"


@pytest.mark.test_id("9-1b-020")
async def test_call_chainlens_maps_unknown_4xx_to_upstream_error(monkeypatch):
    _stub_config_with_key(monkeypatch)
    from app.capabilities.chainlens.research import executor as executor_mod

    response = type("R", (), {"status_code": 422, "text": "bad"})()
    monkeypatch.setattr(executor_mod.httpx, "AsyncClient", _fake_http_client(response))

    output = await _call_chainlens(ResearchInput(query="test"))
    assert output.status == "engine_unavailable"
    assert output.degradation_reason == "upstream_error"


@pytest.mark.test_id("9-1b-021")
async def test_build_research_executor_degrades_on_timeout():
    async def raise_timeout(_):
        raise httpx.TimeoutException("timeout")

    execute = build_research_executor(raise_timeout)
    output = await execute(ResearchInput(query="test"))
    assert output.status == "engine_unavailable"
    assert getattr(output, "degradation_reason", None) == "timeout"


@pytest.mark.test_id("9-1b-022")
async def test_build_research_executor_degrades_on_request_error():
    async def raise_request_error(_):
        raise httpx.ConnectError("dns failed")

    execute = build_research_executor(raise_request_error)
    output = await execute(ResearchInput(query="test"))
    assert output.status == "engine_unavailable"
    assert output.degradation_reason == "unreachable"


@pytest.mark.test_id("9-1b-023")
async def test_build_research_executor_degrades_on_chainlens_error():
    async def raise_chainlens_error(_):
        raise ChainLensError("upstream typed error", code="CHAINLENS_UPSTREAM_ERROR")

    execute = build_research_executor(raise_chainlens_error)
    output = await execute(ResearchInput(query="test"))
    assert output.status == "engine_unavailable"
    assert getattr(output, "degradation_reason", None) == "upstream_error"


@pytest.mark.test_id("9-1b-024")
async def test_call_chainlens_maps_400_to_upstream_error(monkeypatch):
    _stub_config_with_key(monkeypatch)
    from app.capabilities.chainlens.research import executor as executor_mod

    response = type("R", (), {"status_code": 400, "text": "bad request"})()
    monkeypatch.setattr(executor_mod.httpx, "AsyncClient", _fake_http_client(response))

    output = await _call_chainlens(ResearchInput(query="test"))
    assert output.status == "engine_unavailable"
    assert getattr(output, "degradation_reason", None) == "upstream_error"


@pytest.mark.test_id("9-1b-025")
async def test_call_chainlens_maps_405_to_upstream_error(monkeypatch):
    _stub_config_with_key(monkeypatch)
    from app.capabilities.chainlens.research import executor as executor_mod

    response = type("R", (), {"status_code": 405, "text": "method not allowed"})()
    monkeypatch.setattr(executor_mod.httpx, "AsyncClient", _fake_http_client(response))

    output = await _call_chainlens(ResearchInput(query="test"))
    assert output.status == "engine_unavailable"
    assert getattr(output, "degradation_reason", None) == "upstream_error"


def _request_capturing_client(captured: dict, done_chat_id: str | None = None):
    """Return a fake httpx.AsyncClient that records the outgoing POST request."""

    class _FakeResponse:
        status_code = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def aiter_lines(self):
            payload = {"type": "done"}
            if done_chat_id:
                payload["chatId"] = done_chat_id
            yield f"data: {json.dumps(payload)}"

        async def aclose(self):
            pass

    class _FakeClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        def stream(self, method, url, **kwargs):
            captured["url"] = url
            captured["headers"] = kwargs.get("headers")
            captured["json"] = kwargs.get("json")
            captured["stream"] = True
            return _FakeResponse()

    return _FakeClient


@pytest.mark.test_id("9-1b-026")
async def test_call_chainlens_request_contract_full_payload(monkeypatch):
    from app.capabilities.chainlens.research import executor as executor_mod

    fake_config = types.SimpleNamespace(
        CHAINLENS_API_KEY="contract-key",
        CHAINLENS_API_URL="https://contract.chainlens.test",
        CHAINLENS_REQUEST_TIMEOUT_SECONDS=42,
    )
    monkeypatch.setattr(
        "app.capabilities.chainlens.research.executor.config", fake_config
    )

    captured: dict = {}
    monkeypatch.setattr(
        executor_mod.httpx,
        "AsyncClient",
        _request_capturing_client(captured, done_chat_id="chat-contract"),
    )

    payload = ResearchInput(
        query="contract query",
        mode="balanced",
        sources=["academic"],
        history=[["user", "hi"]],
        system_instructions="answer in english",
        chat_id="chat-1",
    )
    output = await _call_chainlens(payload)

    assert captured["url"] == "https://contract.chainlens.test/api/v1/search"
    assert captured["headers"] == {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "Authorization": "Bearer contract-key",
    }
    assert captured["json"] == {
        "query": "contract query",
        "optimizationMode": "balanced",
        "tier": "research",
        "sources": ["academic"],
        "history": [["user", "hi"]],
        "stream": True,
        "systemInstructions": "answer in english",
        "chatId": "chat-1",
    }
    assert captured["stream"] is True
    assert output.chat_id == "chat-contract"


@pytest.mark.test_id("9-1b-027")
async def test_call_chainlens_request_contract_omits_optional_fields(monkeypatch):
    from app.capabilities.chainlens.research import executor as executor_mod

    fake_config = types.SimpleNamespace(
        CHAINLENS_API_KEY="contract-key",
        CHAINLENS_API_URL="https://contract.chainlens.test",
        CHAINLENS_REQUEST_TIMEOUT_SECONDS=42,
    )
    monkeypatch.setattr(
        "app.capabilities.chainlens.research.executor.config", fake_config
    )

    captured: dict = {}
    monkeypatch.setattr(
        executor_mod.httpx,
        "AsyncClient",
        _request_capturing_client(captured),
    )

    _ = await _call_chainlens(ResearchInput(query="minimal"))

    assert captured["json"] == {
        "query": "minimal",
        "optimizationMode": "balanced",
        "tier": "research",
        "sources": ["web", "academic"],
        "history": [],
        "stream": True,
    }
    assert "systemInstructions" not in captured["json"]
    assert "chatId" not in captured["json"]


@pytest.mark.test_id("9-1b-028")
def test_parse_sse_block_replaces_existing_id():
    raw = (
        _sse_line(
            {"type": "block", "block": {"id": "txt", "type": "text", "data": "First"}}
        )
        + _sse_line(
            {"type": "block", "block": {"id": "txt", "type": "text", "data": "Second"}}
        )
        + _sse_line({"type": "done"})
    )
    output = _parse_sse(raw)

    assert output.answer == "Second"
    assert output.status == "complete"


@pytest.mark.test_id("9-1b-029")
def test_parse_sse_done_contract_carries_metadata():
    raw = _sse_line(
        {"type": "block", "block": {"id": "txt", "type": "text", "data": "Answer"}}
    ) + _sse_line(
        {
            "type": "done",
            "chatId": "chat-contract",
            "webUrl": "https://research.chainlens.test/c/chat-contract",
        }
    )
    output = _parse_sse(raw)

    assert output.answer == "Answer"
    assert output.chat_id == "chat-contract"
    assert output.web_url == "https://research.chainlens.test/c/chat-contract"
    assert output.status == "complete"


@pytest.mark.test_id("9-1b-030")
def test_parse_sse_update_block_replaces_data():
    raw = (
        _sse_line(
            {"type": "block", "block": {"id": "txt", "type": "text", "data": "Initial"}}
        )
        + _sse_line(
            {
                "type": "updateBlock",
                "blockId": "txt",
                "patch": [{"op": "replace", "path": "/data", "value": "Replaced"}],
            }
        )
        + _sse_line({"type": "done"})
    )
    output = _parse_sse(raw)

    assert output.answer == "Replaced"
    assert output.status == "complete"


@pytest.mark.test_id("9-1b-031")
def test_parse_sse_update_block_adds_data():
    raw = (
        _sse_line(
            {"type": "block", "block": {"id": "txt", "type": "text", "data": "Initial"}}
        )
        + _sse_line(
            {
                "type": "updateBlock",
                "blockId": "txt",
                "patch": [{"op": "add", "path": "/data", "value": "Added"}],
            }
        )
        + _sse_line({"type": "done"})
    )
    output = _parse_sse(raw)

    assert output.answer == "Added"
    assert output.status == "complete"


@pytest.mark.test_id("9-1b-032")
def test_parse_sse_update_block_ignores_unsupported_patch():
    raw = (
        _sse_line(
            {"type": "block", "block": {"id": "txt", "type": "text", "data": "Initial"}}
        )
        + _sse_line(
            {
                "type": "updateBlock",
                "blockId": "txt",
                "patch": [
                    {"op": "remove", "path": "/data", "value": "Removed"},
                    {"op": "replace", "path": "/type", "value": "markdown"},
                    {"op": "test", "path": "/data", "value": "Test"},
                ],
            }
        )
        + _sse_line({"type": "done"})
    )
    output = _parse_sse(raw)

    assert output.answer == "Initial"
    assert output.status == "complete"


@pytest.mark.test_id("9-1b-033")
def test_parse_sse_unknown_type_is_ignored():
    raw = _sse_line({"type": "noop"})
    output = _parse_sse(raw)

    assert output.status == "engine_unavailable"
    assert output.degradation_reason == "stream_incomplete"


@pytest.mark.test_id("9-1b-034")
def test_parse_sse_unknown_type_does_not_break_known_frames():
    raw = (
        _sse_line({"type": "noop"})
        + _sse_line({"type": "progress"})
        + _sse_line(
            {"type": "block", "block": {"id": "txt", "type": "text", "data": "Hello"}}
        )
        + _sse_line({"type": "noop"})
        + _sse_line({"type": "done"})
    )
    output = _parse_sse(raw)

    assert output.answer == "Hello"
    assert output.status == "complete"


@pytest.mark.test_id("9-1b-035")
def test_parse_sse_preserves_source_order():
    raw = _sse_line(
        {
            "type": "block",
            "block": {
                "id": "src",
                "type": "source",
                "data": [
                    {
                        "metadata": {"title": "Alpha", "url": "https://a.example.com"},
                        "content": "alpha",
                    },
                    {
                        "metadata": {"title": "Bravo", "url": "https://b.example.com"},
                        "content": "bravo",
                    },
                    {
                        "metadata": {
                            "title": "Charlie",
                            "url": "https://c.example.com",
                        },
                        "content": "charlie",
                    },
                ],
            },
        }
    ) + _sse_line({"type": "done"})
    output = _parse_sse(raw)

    assert len(output.sources) == 3
    assert [s.title for s in output.sources] == ["Alpha", "Bravo", "Charlie"]
    assert [s.url for s in output.sources] == [
        "https://a.example.com",
        "https://b.example.com",
        "https://c.example.com",
    ]


@pytest.mark.test_id("9-1b-036")
def test_parse_sse_ignores_event_and_done_markers():
    raw = (
        "event: error\n\n"
        + "data: should be ignored\n\n"
        + "data: [DONE]\n\n"
        + _sse_line(
            {"type": "block", "block": {"id": "txt", "type": "text", "data": "Real"}}
        )
        + _sse_line({"type": "done"})
    )
    output = _parse_sse(raw)

    assert output.answer == "Real"
    assert output.status == "complete"


@pytest.mark.test_id("9-1b-037")
async def test_parse_sse_async_iterator_path():
    async def async_generator():
        yield _sse_line(
            {"type": "block", "block": {"id": "txt", "type": "text", "data": "Async"}}
        )
        yield _sse_line({"type": "done"})

    coro = _parse_sse(async_generator())
    assert inspect.isawaitable(coro)
    output = await coro

    assert isinstance(output, ResearchOutput)
    assert output.answer == "Async"
    assert output.status == "complete"


@pytest.mark.test_id("9-1b-038")
def test_parse_sse_insufficient_evidence_empty_returns_insufficient_evidence():
    raw = _sse_line(
        {
            "type": "insufficientEvidence",
            "reason": "no evidence",
            "partial": {"answer": "", "sources": []},
        }
    )
    output = _parse_sse(raw)

    assert output.status == "insufficient_evidence"
    assert output.degradation_reason == "insufficient_evidence"


@pytest.mark.test_id("9-1b-039")
def test_parse_sse_golden_fixture_parses():
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "chainlens-sse-golden.json").read_text()
    )
    raw = "".join(_sse_line(frame) for frame in fixture)
    output = _parse_sse(raw)

    assert isinstance(output, ResearchOutput)
    assert output.status not in ("insufficient_evidence", "timeout")
    assert output.answer or output.sources


@pytest.mark.test_id("9-1b-040")
def test_parse_sse_progress_milestones_record_ttfb_and_phases():
    from app.capabilities.core.progress import progress_scope

    raw = (
        _sse_line(
            {
                "type": "progress",
                "requestAcceptedAt": "1970-01-01T00:00:01Z",
                "firstProgressAt": "1970-01-01T00:00:01.200Z",
                "evidenceReadyAt": "1970-01-01T00:00:03.500Z",
                "firstFactualChunkAt": "1970-01-01T00:00:02.800Z",
            }
        )
        + _sse_line({"type": "evidence_ready"})
        + _sse_line({"type": "synthesizing"})
        + _sse_line({"type": "researchComplete"})
        + _sse_line({"type": "unknown"})
        + _sse_line({"type": "done"})
    )

    with progress_scope() as reporter:
        parser = _SSEParser()
        for line in raw.splitlines():
            parser.feed_line(line)
        output = parser.finalize()

    assert output.first_token_time_ms == 1800
    phases = [e["phase"] for e in reporter.coarse]
    assert "first_token" in phases
    first_token_event = next(e for e in reporter.coarse if e["phase"] == "first_token")
    assert first_token_event["detail"]["ttfb_ms"] == 1800
    assert "evidence_ready" in phases
    assert "synthesizing" in phases
    assert "research_complete" in phases
    assert parser.saw_unknown is True
