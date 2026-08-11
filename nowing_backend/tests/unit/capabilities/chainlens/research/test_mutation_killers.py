from __future__ import annotations

import json
import types
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.capabilities.chainlens.research.definition import CHAINLENS_RESEARCH
from app.capabilities.chainlens.research.executor import (
    ChainLensError,
    _block_type_for,
    _call_chainlens,
    _parse_sources,
    _parse_sse,
    _SSEParser,
    build_research_executor,
    execute_with_context,
)
from app.capabilities.chainlens.research.schemas import (
    MAX_QUERY_LENGTH,
    ResearchInput,
    ResearchOutput,
    Source,
    _default_next_action,
)
from app.capabilities.core import BillingUnit
from app.utils.crawl.classifier import BlockType

pytestmark = [pytest.mark.unit, pytest.mark.contract]


def _sse_line(payload: object) -> str:
    return f"data: {json.dumps(payload)}\n\n"


# ---------------------------------------------------------------------------
# definition.py literal fields
# ---------------------------------------------------------------------------


def test_definition_literal_fields():
    assert CHAINLENS_RESEARCH.name == "chainlens.research"
    assert "ChainLens Research" in CHAINLENS_RESEARCH.description
    assert CHAINLENS_RESEARCH.billing_unit is BillingUnit.CHAINLENS_QUERY
    assert CHAINLENS_RESEARCH.docs_url == "/docs/connectors/native/chainlens-research"
    assert CHAINLENS_RESEARCH.context_aware is True
    assert CHAINLENS_RESEARCH.input_schema is ResearchInput
    assert CHAINLENS_RESEARCH.output_schema is ResearchOutput


# ---------------------------------------------------------------------------
# schemas.py: Source model_post_init
# ---------------------------------------------------------------------------


def test_source_parses_nowing_url_and_derives_kb_fields():
    source = Source(title="KB", url="nowing://documents/7/chunks/12")
    assert source.document_id == 7
    assert source.chunk_id == 12
    assert source.source_type == "kb"


def test_source_preserves_existing_kb_ids():
    source = Source(
        title="KB",
        url="nowing://documents/7/chunks/12",
        document_id=99,
        chunk_id=88,
    )
    assert source.document_id == 99
    assert source.chunk_id == 88


def test_source_preserves_existing_source_type():
    source = Source(
        title="KB",
        url="nowing://documents/7/chunks/12",
        source_type="web",
    )
    assert source.source_type == "web"


def test_source_unmatched_nowing_url_does_not_parse():
    source = Source(title="KB", url="nowing://documents/7")
    assert source.document_id is None
    assert source.chunk_id is None
    assert source.source_type == "kb"


def test_source_web_url_gets_source_type_web():
    source = Source(title="Web", url="https://example.com")
    assert source.source_type == "web"
    assert source.document_id is None
    assert source.chunk_id is None


def test_source_rejects_empty_url():
    with pytest.raises(ValidationError):
        Source(title="Bad", url="")


# ---------------------------------------------------------------------------
# schemas.py: ResearchInput validators and boundaries
# ---------------------------------------------------------------------------


def test_research_input_strips_whitespace_before_length_check():
    payload = ResearchInput(query="  hello  ")
    assert payload.query == "hello"


def test_research_input_query_exactly_max_length():
    assert ResearchInput(query="x" * MAX_QUERY_LENGTH).query == "x" * MAX_QUERY_LENGTH


def test_research_input_rejects_query_one_over_max_length():
    with pytest.raises(ValidationError):
        ResearchInput(query="x" * (MAX_QUERY_LENGTH + 1))


def test_research_input_rejects_blank_query_after_strip():
    with pytest.raises(ValidationError):
        ResearchInput(query="   ")


def test_research_input_sources_min_length():
    with pytest.raises(ValidationError):
        ResearchInput(query="test", sources=[])


def test_research_input_history_inner_pair_length_exact():
    with pytest.raises(ValidationError):
        ResearchInput(query="test", history=[["user"]])


def test_research_input_history_outer_max_length():
    with pytest.raises(ValidationError):
        ResearchInput(
            query="test",
            history=[["user", str(i)] for i in range(51)],
        )


def test_research_input_system_instructions_max_length():
    with pytest.raises(ValidationError):
        ResearchInput(query="test", system_instructions="x" * 2001)


# ---------------------------------------------------------------------------
# schemas.py: ResearchOutput degradation / fallback / next_action
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status, degradation_reason, engine_reason, expected_degraded, expected_reason, expected_next",
    [
        (
            "complete",
            None,
            None,
            False,
            None,
            None,
        ),
        (
            "engine_unavailable",
            None,
            None,
            True,
            "unknown",
            "The deep research engine is unavailable. Try again later.",
        ),
        (
            "engine_unavailable",
            "not_configured",
            None,
            True,
            "not_configured",
            "Deep research is not available in self-host Phase 1. Set CHAINLENS_API_KEY to use the hosted engine.",
        ),
        (
            "engine_unavailable",
            "fallback_kb_empty",
            None,
            True,
            "fallback_kb_empty",
            "The deep research engine is unavailable and no matching workspace knowledge base passages were found. Try rephrasing your query.",
        ),
        (
            "engine_unavailable",
            "fallback_kb_error",
            None,
            True,
            "fallback_kb_error",
            "The deep research engine is unavailable and workspace knowledge base lookup failed. Try again later.",
        ),
        (
            "engine_unavailable",
            "timeout",
            None,
            True,
            "timeout",
            "The deep research engine timed out. Try again with a faster mode or a narrower query.",
        ),
        (
            "engine_unavailable",
            "stream_incomplete",
            None,
            True,
            "stream_incomplete",
            "The deep research engine timed out. Try again with a faster mode or a narrower query.",
        ),
        (
            "engine_unavailable",
            "unreachable",
            None,
            True,
            "unreachable",
            "The deep research engine is unreachable. Check your network and try again.",
        ),
        (
            "engine_unavailable",
            "auth_failed",
            None,
            True,
            "auth_failed",
            "The deep research engine is temporarily unavailable. Try again later.",
        ),
        (
            "engine_unavailable",
            "rate_limited",
            None,
            True,
            "rate_limited",
            "The deep research engine is temporarily unavailable. Try again later.",
        ),
        (
            "engine_unavailable",
            "upstream_error",
            None,
            True,
            "upstream_error",
            "The deep research engine is temporarily unavailable. Try again later.",
        ),
        (
            "partial",
            None,
            "low coverage",
            True,
            "partial",
            "Partial result; low coverage.",
        ),
        (
            "partial",
            None,
            None,
            True,
            "partial",
            "Partial result; partial.",
        ),
        (
            "insufficient_evidence",
            None,
            None,
            True,
            "insufficient_evidence",
            "No relevant sources were found. Try rephrasing the query or wait for gap-fill indexing to complete.",
        ),
        (
            "timeout",
            None,
            None,
            True,
            "stream_incomplete",
            "The ChainLens stream ended before returning a complete result. Try again.",
        ),
    ],
)
def test_research_output_recompute_degradation(
    status,
    degradation_reason,
    engine_reason,
    expected_degraded,
    expected_reason,
    expected_next,
):
    # Use an equal, non-identical status string to defeat `is`/`is not` mutations.
    fresh_status = "".join(status) if isinstance(status, str) else status
    output = ResearchOutput(
        status=fresh_status,
        degradation_reason=degradation_reason,
        engine_reason=engine_reason,
    )
    assert output.degraded is expected_degraded
    assert output.degradation_reason == expected_reason
    assert output.next_action == expected_next


def test_research_output_preserves_manual_next_action():
    output = ResearchOutput(
        status="engine_unavailable",
        next_action="custom",
    )
    assert output.next_action == "custom"


def test_research_output_preserves_manual_degradation_reason():
    output = ResearchOutput(status="engine_unavailable", degradation_reason="custom")
    assert output.degradation_reason == "custom"
    assert (
        output.next_action
        == "The deep research engine is unavailable. Try again later."
    )


def test_research_output_validate_assignment_rejects_bad_status():
    output = ResearchOutput(status="complete")
    with pytest.raises(ValidationError):
        output.status = "invalid_status"


def test_research_output_saw_heartbeat_default_false():
    output = ResearchOutput()
    assert output.saw_heartbeat is False


def test_research_output_excludes_internal_fields_from_dump():
    output = ResearchOutput(
        saw_heartbeat=True, blocked_url_coverage_by_block_type={"x": 1}
    )
    dumped = output.model_dump()
    assert "saw_heartbeat" not in dumped
    assert "blocked_url_coverage_by_block_type" not in dumped


def test_research_output_billable_units_computed_field_in_dump():
    output = ResearchOutput(answer="yes")
    dumped = output.model_dump()
    assert dumped.get("billable_units") == 1


def test_research_output_recompute_fallback_mirrors_primary_kb_source():
    output = ResearchOutput(
        sources=[
            Source(title="A", url="nowing://documents/1/chunks/10"),
            Source(title="B", url="nowing://documents/2/chunks/20"),
        ],
    )
    assert output.fallback_hit_count == 2
    assert output.source_type == "kb"
    assert output.document_id == 1
    assert output.chunk_id == 10


def test_research_output_recompute_fallback_clears_primary_for_web_sources():
    output = ResearchOutput(
        sources=[Source(title="Web", url="https://example.com")],
    )
    assert output.fallback_hit_count == 0
    assert output.source_type is None
    assert output.document_id is None
    assert output.chunk_id is None


# ---------------------------------------------------------------------------
# executor.py: _block_type_for and _parse_sources
# ---------------------------------------------------------------------------


def test_block_type_for_unknown_returns_unknown():
    assert _block_type_for("not-a-type") is BlockType.UNKNOWN


def test_block_type_for_empty_or_none_returns_unknown():
    assert _block_type_for(None) is BlockType.UNKNOWN
    assert _block_type_for("") is BlockType.UNKNOWN


def test_parse_sources_skips_non_list_input():
    assert _parse_sources({"foo": "bar"}) == []


def test_parse_sources_continues_past_invalid_entries():
    raw = [
        "not a dict",
        ["also not a dict"],
        {"metadata": {"title": "Good", "url": "https://example.com"}},
    ]
    sources = _parse_sources(raw)
    assert len(sources) == 1
    assert sources[0].title == "Good"
    assert sources[0].url == "https://example.com"


def test_parse_sources_prefers_metadata_block():
    raw = [
        {
            "metadata": {"title": "Meta", "url": "https://meta.example.com"},
            "content": "meta content",
        },
    ]
    sources = _parse_sources(raw)
    assert sources[0].title == "Meta"
    assert sources[0].content == "meta content"


def test_parse_sources_falls_back_to_page_content():
    raw = [
        {
            "title": "Page",
            "url": "https://page.example.com",
            "pageContent": "page text",
        },
    ]
    sources = _parse_sources(raw)
    assert sources[0].content == "page text"


def test_parse_sources_uses_name_as_title_fallback():
    raw = [
        {"name": "Named", "url": "https://named.example.com"},
    ]
    sources = _parse_sources(raw)
    assert sources[0].title == "Named"


def test_parse_sources_skips_empty_url_and_missing_content():
    raw = [
        {"title": "No URL", "url": "", "content": "skip me"},
        {"title": "No content", "url": "https://content.example.com"},
    ]
    sources = _parse_sources(raw)
    assert len(sources) == 1
    assert sources[0].title == "No content"
    assert sources[0].content is None


# ---------------------------------------------------------------------------
# executor.py: _SSEParser feed_line branches
# ---------------------------------------------------------------------------


def test_feed_line_ignores_empty_and_event_lines():
    parser = _SSEParser()
    parser.feed_line("")
    parser.feed_line("   ")
    parser.feed_line("event: error")
    assert parser.saw_unknown is False
    assert not parser.error_msg


def test_feed_line_done_and_empty_payload_never_calls_json_loads():
    parser = _SSEParser()
    with patch("app.capabilities.chainlens.research.executor.json.loads") as mock_loads:
        parser.feed_line("data: [DONE]")
        parser.feed_line("data:")
        parser.feed_line("data:   ")
        assert mock_loads.call_count == 0


def test_feed_line_valid_payload_calls_json_loads_and_done_is_parsed():
    parser = _SSEParser()
    with patch(
        "app.capabilities.chainlens.research.executor.json.loads",
        wraps=json.loads,
    ) as mock_loads:
        parser.feed_line(_sse_line({"type": "done", "chatId": "chat-1"}))
        assert mock_loads.call_count == 1
        assert parser.chat_id == "chat-1"


def test_feed_line_error_event_with_string():
    parser = _SSEParser()
    parser.feed_line(_sse_line({"type": "error", "data": "boom"}))
    assert parser.error_msg == "boom"


def test_feed_line_error_event_with_dict():
    parser = _SSEParser()
    parser.feed_line(_sse_line({"type": "error", "data": {"message": "boom"}}))
    assert "boom" in parser.error_msg


def test_feed_line_error_event_with_none():
    parser = _SSEParser()
    parser.feed_line(_sse_line({"type": "error"}))
    assert parser.error_msg == "Upstream SSE error"


def test_feed_line_block_event_requires_dict_block():
    parser = _SSEParser()
    parser.feed_line(_sse_line({"type": "block", "block": "not a dict"}))
    parser.feed_line(
        _sse_line(
            {"type": "block", "block": {"id": 123, "type": "text", "data": "nope"}}
        )
    )
    assert len(parser.blocks) == 0


def test_feed_line_block_replaces_existing_block():
    parser = _SSEParser()
    parser.feed_line(
        _sse_line(
            {"type": "block", "block": {"id": "x", "type": "text", "data": "First"}}
        )
    )
    parser.feed_line(
        _sse_line(
            {"type": "block", "block": {"id": "x", "type": "text", "data": "Second"}}
        )
    )
    assert parser.blocks["x"].data == "Second"


def test_feed_line_update_block_only_acts_on_replace_and_add():
    parser = _SSEParser()
    parser.feed_line(
        _sse_line(
            {"type": "block", "block": {"id": "x", "type": "text", "data": "Initial"}}
        )
    )
    parser.feed_line(
        _sse_line(
            {
                "type": "updateBlock",
                "blockId": "x",
                "patch": [
                    {"op": "remove", "path": "/data", "value": "Removed"},
                    {"op": "test", "path": "/data", "value": "Test"},
                    {"op": "replace", "path": "/type", "value": "markdown"},
                ],
            }
        )
    )
    assert parser.blocks["x"].data == "Initial"


def test_feed_line_update_block_missing_block_id_is_ignored():
    parser = _SSEParser()
    parser.feed_line(
        _sse_line(
            {
                "type": "updateBlock",
                "patch": [{"op": "replace", "path": "/data", "value": "X"}],
            }
        )
    )
    assert not parser.blocks


def test_feed_line_unknown_event_with_block_dict_is_not_unknown():
    """A noop frame that also carries a `block` dict should *not* be treated as a block.

    This specifically targets the `and` short-circuit in the block branch.
    """
    parser = _SSEParser()
    parser.feed_line(
        _sse_line({"type": "noop", "block": {"id": "x", "type": "text", "data": "A"}})
    )
    parser.feed_line(_sse_line({"type": "done"}))
    assert parser.saw_unknown is True


def test_feed_line_partial_state_insufficient_evidence_with_answer_is_partial():
    parser = _SSEParser()
    parser.feed_line(
        _sse_line(
            {
                "type": "partial",
                "state": "insufficient_evidence",
                "answer": "some answer",
                "sources": [],
            }
        )
    )
    assert parser.status == "partial"
    assert parser.degradation_reason == "partial"


def test_feed_line_partial_state_insufficient_evidence_with_sources_is_partial():
    parser = _SSEParser()
    parser.feed_line(
        _sse_line(
            {
                "type": "partial",
                "state": "insufficient_evidence",
                "answer": "",
                "sources": [{"title": "S", "url": "https://example.com"}],
            }
        )
    )
    assert parser.status == "partial"
    assert parser.answer == ""
    assert len(parser.sources) == 1


def test_feed_line_partial_state_insufficient_evidence_empty_is_insufficient():
    parser = _SSEParser()
    parser.feed_line(
        _sse_line(
            {
                "type": "partial",
                "state": "insufficient_evidence",
                "answer": "",
                "sources": [],
            }
        )
    )
    assert parser.status == "insufficient_evidence"
    assert parser.degradation_reason == "insufficient_evidence"


def test_feed_line_insufficient_evidence_with_partial_answer_is_partial():
    parser = _SSEParser()
    parser.feed_line(
        _sse_line(
            {
                "type": "insufficientEvidence",
                "reason": "no sources",
                "partial": {
                    "answer": "partial answer",
                    "sources": [],
                },
            }
        )
    )
    assert parser.status == "partial"
    assert parser.answer == "partial answer"


def test_feed_line_insufficient_evidence_non_string_answer_is_partial():
    parser = _SSEParser()
    parser.feed_line(
        _sse_line(
            {
                "type": "insufficientEvidence",
                "reason": "no sources",
                "partial": {
                    "answer": 123,
                    "sources": [],
                },
            }
        )
    )
    assert parser.status == "insufficient_evidence"
    assert parser.answer == ""


def test_feed_line_insufficient_evidence_skips_blocked_metadata_non_dicts():
    parser = _SSEParser()
    parser.feed_line(
        _sse_line(
            {
                "type": "insufficientEvidence",
                "reason": "blocked",
                "partial": {"answer": "", "sources": []},
                "blocked_metadata": [
                    "not a dict",
                    {"url": "https://example.com", "block_type": "cloudflare"},
                    {"not_url": "ignored"},
                ],
            }
        )
    )
    assert parser.blocked_url_coverage == {"cloudflare": 1}


def test_feed_line_heartbeat_is_tolerated():
    parser = _SSEParser()
    parser.feed_line(_sse_line({"type": "heartbeat"}))
    assert parser.saw_heartbeat is True
    assert parser.saw_unknown is False


def test_feed_line_block_done_heartbeat_do_not_set_unknown():
    parser = _SSEParser()
    parser.feed_line(
        _sse_line({"type": "block", "block": {"id": "x", "type": "text", "data": "A"}})
    )
    parser.feed_line(
        _sse_line(
            {
                "type": "updateBlock",
                "blockId": "x",
                "patch": [{"op": "add", "path": "/data", "value": "B"}],
            }
        )
    )
    parser.feed_line(_sse_line({"type": "done"}))
    parser.feed_line(_sse_line({"type": "heartbeat"}))
    assert parser.saw_unknown is False


# ---------------------------------------------------------------------------
# executor.py: _SSEParser finalize
# ---------------------------------------------------------------------------


def test_finalize_raises_chainlens_error_for_error_frame():
    parser = _SSEParser()
    parser.error_msg = "upstream boom"
    with pytest.raises(ChainLensError, match="upstream boom"):
        parser.finalize()


def test_finalize_uses_text_and_source_blocks():
    parser = _SSEParser()
    parser.feed_line(
        _sse_line(
            {
                "type": "block",
                "block": {
                    "id": "src",
                    "type": "source",
                    "data": [
                        {"metadata": {"title": "S", "url": "https://example.com"}}
                    ],
                },
            }
        )
    )
    parser.feed_line(_sse_line({"type": "done"}))
    output = parser.finalize()
    assert output.answer == ""
    assert len(output.sources) == 1
    assert output.status == "complete"


def test_finalize_no_done_no_data_is_timeout():
    parser = _SSEParser()
    output = parser.finalize()
    assert output.status == "timeout"
    assert output.degradation_reason == "stream_incomplete"


def test_finalize_done_without_data_is_engine_unavailable():
    parser = _SSEParser()
    parser.feed_line(_sse_line({"type": "done"}))
    output = parser.finalize()
    assert output.status == "engine_unavailable"
    assert output.degradation_reason == "stream_incomplete"


def test_finalize_heartbeat_without_data_is_engine_unavailable():
    parser = _SSEParser()
    parser.feed_line(_sse_line({"type": "heartbeat"}))
    output = parser.finalize()
    assert output.status == "engine_unavailable"


def test_finalize_rounds_non_integer_micros_in_cost_breakdown():
    parser = _SSEParser()
    parser.feed_line(
        _sse_line(
            {
                "type": "done",
                "costDollars": 0.025,
                "costBreakdown": {
                    "searchCostMicros": 12345.6,
                    "gapFillCostMicros": 7000.0,
                    "scraperCostMicros": 5000,
                    "scraperId": "batdongsan",
                },
            }
        )
    )
    output = parser.finalize()
    assert output.cost_breakdown is not None
    assert output.cost_breakdown["search_micros"] == 12346
    assert output.cost_breakdown["gap_fill_micros"] == 7000
    assert output.cost_breakdown["scraper_micros"] == 5000
    assert output.cost_breakdown["scraper_id"] == "batdongsan"


# ---------------------------------------------------------------------------
# executor.py: _parse_sse source dispatch
# ---------------------------------------------------------------------------


def test_parse_sse_string_path():
    output = _parse_sse(_sse_line({"type": "done"}))
    assert isinstance(output, ResearchOutput)


async def test_parse_sse_async_iterator_path():
    async def _gen():
        yield _sse_line(
            {"type": "block", "block": {"id": "x", "type": "text", "data": "A"}}
        )
        yield _sse_line({"type": "done"})

    result = _parse_sse(_gen())
    output = await result
    assert isinstance(output, ResearchOutput)
    assert output.answer == "A"


def test_parse_sse_rejects_invalid_source_type():
    with pytest.raises(TypeError):
        _parse_sse(123)


# ---------------------------------------------------------------------------
# executor.py: _call_chainlens HTTP status mapping
# ---------------------------------------------------------------------------


def _fake_http_client_class(response):
    class _FakeResponse:
        def __init__(self, status_code, text="", lines=None):
            self.status_code = status_code
            self.text = text
            self._lines = lines or []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def aiter_lines(self):
            for line in self._lines:
                yield line

        async def aclose(self):
            pass

    class _FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        def stream(self, *args, **kwargs):
            return _FakeResponse(
                response["status_code"],
                response.get("text", ""),
                response.get("lines", []),
            )

    return _FakeClient


@pytest.fixture
def stub_config(monkeypatch):
    fake = types.SimpleNamespace(
        CHAINLENS_API_KEY="test-key",
        CHAINLENS_API_URL="https://chainlens.test",
        CHAINLENS_REQUEST_TIMEOUT_SECONDS=30,
    )
    monkeypatch.setattr("app.capabilities.chainlens.research.executor.config", fake)
    return fake


@pytest.mark.parametrize(
    "status_code, expected_reason",
    [
        (401, "auth_failed"),
        (403, "auth_failed"),
        (429, "rate_limited"),
        (500, "upstream_error"),
        (503, "upstream_error"),
        (422, "upstream_error"),
        (400, "upstream_error"),
        (405, "upstream_error"),
        (300, "upstream_error"),
        (199, "upstream_error"),
        (201, "upstream_error"),
    ],
)
async def test_call_chainlens_status_code_mapping(
    status_code, expected_reason, stub_config, monkeypatch
):
    from app.capabilities.chainlens.research import executor as executor_mod

    response = {"status_code": status_code, "text": "whatever", "lines": []}
    monkeypatch.setattr(
        executor_mod.httpx, "AsyncClient", _fake_http_client_class(response)
    )

    output = await _call_chainlens(ResearchInput(query="test"))
    assert output.status == "engine_unavailable"
    assert output.degradation_reason == expected_reason


async def test_call_chainlens_not_configured(stub_config, monkeypatch):
    stub_config.CHAINLENS_API_KEY = ""
    output = await _call_chainlens(ResearchInput(query="test"))
    assert output.status == "engine_unavailable"
    assert output.degradation_reason == "not_configured"


async def test_call_chainlens_200_parses_sse(stub_config, monkeypatch):
    from app.capabilities.chainlens.research import executor as executor_mod

    response = {
        "status_code": 200,
        "lines": [
            _sse_line(
                {"type": "block", "block": {"id": "x", "type": "text", "data": "A"}}
            ),
            _sse_line({"type": "done"}),
        ],
    }
    monkeypatch.setattr(
        executor_mod.httpx, "AsyncClient", _fake_http_client_class(response)
    )

    output = await _call_chainlens(ResearchInput(query="test"))
    assert output.status == "complete"
    assert output.answer == "A"


# ---------------------------------------------------------------------------
# executor.py: execute_with_context fallback and exceptions
# ---------------------------------------------------------------------------


def _make_hit(doc_id: int, chunks: list[object], title: str = "Doc") -> object:
    return types.SimpleNamespace(
        document_id=doc_id,
        title=title,
        chunks=chunks,
    )


async def test_execute_with_context_kb_fallback_partial():
    async def search_fn(_):
        return ResearchOutput(
            status="engine_unavailable", degradation_reason="not_configured"
        )

    async def fallback_fn(**kwargs):
        return [
            _make_hit(
                1,
                [
                    types.SimpleNamespace(
                        chunk_id=10, content="kb content", position=1, score=0.9
                    )
                ],
            )
        ]

    ctx = types.SimpleNamespace(session="session", workspace_id=1)
    output = await execute_with_context(
        ResearchInput(query="test"),
        ctx,
        search_fn=search_fn,
        fallback_fn=fallback_fn,
        top_k=5,
    )
    assert output.status == "partial"
    assert output.degradation_reason == "fallback_kb_hits"
    assert output.fallback_hit_count == 1
    assert output.answer and "kb content" in output.answer


async def test_execute_with_context_kb_fallback_empty():
    async def search_fn(_):
        return ResearchOutput(
            status="engine_unavailable", degradation_reason="not_configured"
        )

    async def fallback_fn(**kwargs):
        return []

    ctx = types.SimpleNamespace(session="session", workspace_id=1)
    output = await execute_with_context(
        ResearchInput(query="test"),
        ctx,
        search_fn=search_fn,
        fallback_fn=fallback_fn,
        top_k=5,
    )
    assert output.status == "engine_unavailable"
    assert output.degradation_reason == "fallback_kb_empty"


@pytest.mark.parametrize(
    "exc", [SQLAlchemyError, RuntimeError, OSError, httpx.RequestError]
)
async def test_execute_with_context_kb_fallback_exception(exc):
    async def search_fn(_):
        return ResearchOutput(
            status="engine_unavailable", degradation_reason="not_configured"
        )

    async def fallback_fn(**kwargs):
        raise exc("kb failed")

    ctx = types.SimpleNamespace(session="session", workspace_id=1)
    output = await execute_with_context(
        ResearchInput(query="test"),
        ctx,
        search_fn=search_fn,
        fallback_fn=fallback_fn,
        top_k=5,
    )
    assert output.status == "engine_unavailable"
    assert output.degradation_reason == "fallback_kb_error"


async def test_execute_with_context_timeout_triggers_fallback():
    async def search_fn(_):
        raise httpx.TimeoutException("timeout")

    async def fallback_fn(**kwargs):
        return [
            _make_hit(
                1,
                [
                    types.SimpleNamespace(
                        chunk_id=10, content="kb content", position=1, score=0.9
                    )
                ],
            )
        ]

    ctx = types.SimpleNamespace(session="session", workspace_id=1)
    output = await execute_with_context(
        ResearchInput(query="test"),
        ctx,
        search_fn=search_fn,
        fallback_fn=fallback_fn,
        top_k=5,
    )
    assert output.status == "partial"
    assert output.degradation_reason == "fallback_kb_hits"


async def test_execute_with_context_request_error_degrades():
    async def search_fn(_):
        raise httpx.ConnectError("unreachable")

    output = await execute_with_context(
        ResearchInput(query="test"),
        None,
        search_fn=search_fn,
    )
    assert output.status == "engine_unavailable"
    assert output.degradation_reason == "unreachable"


async def test_execute_with_context_chainlens_error_degrades():
    async def search_fn(_):
        raise ChainLensError("typed error", code="X")

    output = await execute_with_context(
        ResearchInput(query="test"),
        None,
        search_fn=search_fn,
    )
    assert output.status == "engine_unavailable"
    assert output.degradation_reason == "upstream_error"


async def test_execute_with_context_generic_exception_degrades():
    async def search_fn(_):
        raise ValueError("unexpected")

    output = await execute_with_context(
        ResearchInput(query="test"),
        None,
        search_fn=search_fn,
    )
    assert output.status == "engine_unavailable"
    assert output.degradation_reason == "upstream_error"


async def test_execute_with_context_no_fallback_for_partial():
    async def search_fn(_):
        return ResearchOutput(status="partial", answer="partial answer")

    fallback_fn = AsyncMock()
    ctx = types.SimpleNamespace(session="session", workspace_id=1)
    output = await execute_with_context(
        ResearchInput(query="test"),
        ctx,
        search_fn=search_fn,
        fallback_fn=fallback_fn,
    )
    assert output.status == "partial"
    fallback_fn.assert_not_awaited()


async def test_execute_with_context_no_session_skips_fallback():
    async def search_fn(_):
        return ResearchOutput(
            status="engine_unavailable", degradation_reason="not_configured"
        )

    fallback_fn = AsyncMock()
    output = await execute_with_context(
        ResearchInput(query="test"),
        None,
        search_fn=search_fn,
        fallback_fn=fallback_fn,
    )
    assert output.status == "engine_unavailable"
    fallback_fn.assert_not_awaited()


async def test_execute_with_context_top_k_clamping_and_loop_breaks():
    async def search_fn(_):
        return ResearchOutput(
            status="engine_unavailable", degradation_reason="not_configured"
        )

    async def fallback_fn(**kwargs):
        return [
            _make_hit(
                1,
                [
                    types.SimpleNamespace(
                        chunk_id=10, content="c1", position=1, score=0.9
                    ),
                    types.SimpleNamespace(
                        chunk_id=11, content="c2", position=2, score=0.8
                    ),
                ],
            ),
            _make_hit(
                2,
                [
                    types.SimpleNamespace(
                        chunk_id=20, content="c3", position=1, score=0.7
                    ),
                    types.SimpleNamespace(
                        chunk_id=21, content="c4", position=2, score=0.6
                    ),
                ],
            ),
        ]

    ctx = types.SimpleNamespace(session="session", workspace_id=1)
    output = await execute_with_context(
        ResearchInput(query="test"),
        ctx,
        search_fn=search_fn,
        fallback_fn=fallback_fn,
        top_k=2,
    )
    assert output.fallback_hit_count == 2


async def test_execute_with_context_top_k_default_is_five():
    async def search_fn(_):
        return ResearchOutput(
            status="engine_unavailable", degradation_reason="not_configured"
        )

    hits = [
        _make_hit(
            1,
            [
                types.SimpleNamespace(
                    chunk_id=i, content=f"c{i}", position=i, score=0.9
                )
                for i in range(1, 7)
            ],
        )
    ]

    async def fallback_fn(**kwargs):
        return hits

    ctx = types.SimpleNamespace(session="session", workspace_id=1)
    output = await execute_with_context(
        ResearchInput(query="test"),
        ctx,
        search_fn=search_fn,
        fallback_fn=fallback_fn,
    )
    assert output.fallback_hit_count == 5


async def test_execute_with_context_empty_content_shows_no_preview():
    async def search_fn(_):
        return ResearchOutput(
            status="engine_unavailable", degradation_reason="not_configured"
        )

    async def fallback_fn(**kwargs):
        return [
            _make_hit(
                1,
                [types.SimpleNamespace(chunk_id=10, content="", position=1, score=0.9)],
            )
        ]

    ctx = types.SimpleNamespace(session="session", workspace_id=1)
    output = await execute_with_context(
        ResearchInput(query="test"),
        ctx,
        search_fn=search_fn,
        fallback_fn=fallback_fn,
        top_k=1,
    )
    assert output.answer and "(no preview)" in output.answer


async def test_execute_with_context_records_metrics_on_degraded_output(monkeypatch):
    from app.capabilities.chainlens.research import executor as executor_mod

    record_degradation = MagicMock()
    record_kb_hits = MagicMock()
    monkeypatch.setattr(
        executor_mod.metrics, "record_chainlens_degradation", record_degradation
    )
    monkeypatch.setattr(
        executor_mod.metrics, "record_kb_fallback_hit_count", record_kb_hits
    )

    async def search_fn(_):
        return ResearchOutput(
            status="engine_unavailable", degradation_reason="not_configured"
        )

    async def fallback_fn(**kwargs):
        return [
            _make_hit(
                1,
                [
                    types.SimpleNamespace(
                        chunk_id=10, content="kb content", position=1, score=0.9
                    )
                ],
            )
        ]

    ctx = types.SimpleNamespace(session="session", workspace_id=1)
    output = await execute_with_context(
        ResearchInput(query="test"),
        ctx,
        search_fn=search_fn,
        fallback_fn=fallback_fn,
        top_k=5,
    )
    assert output.status == "partial"
    record_degradation.assert_called_once()
    call_kwargs = record_degradation.call_args.kwargs
    assert call_kwargs["fallback_attempted"] is True
    assert call_kwargs["fallback_used"] is True
    assert call_kwargs["fallback_hit_count"] == 1
    record_kb_hits.assert_called_once_with(1)


# ---------------------------------------------------------------------------
# executor.py: build_research_executor default wiring
# ---------------------------------------------------------------------------


async def test_build_research_executor_uses_provided_search_fn():
    async def search_fn(payload):
        return ResearchOutput(answer=f"answer: {payload.query}")

    execute = build_research_executor(search_fn)
    output = await execute(ResearchInput(query="test"))
    assert output.answer == "answer: test"


# ---------------------------------------------------------------------------
# schemas.py: _default_next_action direct coverage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status, degradation_reason, engine_reason, expected",
    [
        (
            "engine_unavailable",
            "not_configured",
            None,
            "Deep research is not available in self-host Phase 1. Set CHAINLENS_API_KEY to use the hosted engine.",
        ),
        (
            "engine_unavailable",
            "fallback_kb_empty",
            None,
            "The deep research engine is unavailable and no matching workspace knowledge base passages were found. Try rephrasing your query.",
        ),
        (
            "engine_unavailable",
            "fallback_kb_error",
            None,
            "The deep research engine is unavailable and workspace knowledge base lookup failed. Try again later.",
        ),
        (
            "engine_unavailable",
            "timeout",
            None,
            "The deep research engine timed out. Try again with a faster mode or a narrower query.",
        ),
        (
            "engine_unavailable",
            "stream_incomplete",
            None,
            "The deep research engine timed out. Try again with a faster mode or a narrower query.",
        ),
        (
            "engine_unavailable",
            "unreachable",
            None,
            "The deep research engine is unreachable. Check your network and try again.",
        ),
        (
            "engine_unavailable",
            "auth_failed",
            None,
            "The deep research engine is temporarily unavailable. Try again later.",
        ),
        (
            "engine_unavailable",
            "rate_limited",
            None,
            "The deep research engine is temporarily unavailable. Try again later.",
        ),
        (
            "engine_unavailable",
            "upstream_error",
            None,
            "The deep research engine is temporarily unavailable. Try again later.",
        ),
        (
            "engine_unavailable",
            "unknown",
            None,
            "The deep research engine is unavailable. Try again later.",
        ),
        (
            "engine_unavailable",
            None,
            "no reason",
            "The deep research engine is unavailable. Try again later.",
        ),
        ("partial", None, "low coverage", "Partial result; low coverage."),
        ("partial", "partial", None, "Partial result; partial."),
        ("partial", None, None, "Partial result; some evidence was found."),
        (
            "insufficient_evidence",
            None,
            None,
            "No relevant sources were found. Try rephrasing the query or wait for gap-fill indexing to complete.",
        ),
        (
            "timeout",
            None,
            None,
            "The ChainLens stream ended before returning a complete result. Try again.",
        ),
        ("complete", None, None, None),
    ],
)
def test_default_next_action_branches(
    status, degradation_reason, engine_reason, expected
):
    def _fresh(value):
        # Build an equal but non-identical string so `is`/`is not` mutations fail.
        return "".join(value) if isinstance(value, str) else value

    assert (
        _default_next_action(
            _fresh(status), _fresh(degradation_reason), _fresh(engine_reason)
        )
        == expected
    )
