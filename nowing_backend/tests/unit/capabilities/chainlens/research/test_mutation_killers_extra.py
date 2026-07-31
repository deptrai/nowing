from __future__ import annotations

import inspect
import json
import types
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.capabilities.chainlens.research.executor import (
    _call_chainlens,
    _kb_fallback,
    _parse_sse,
    _SSEParser,
    build_research_executor,
    execute_with_context,
)
from app.capabilities.chainlens.research.schemas import (
    ResearchInput,
    ResearchOutput,
    Source,
    _default_next_action,
)
from app.config import config

pytestmark = [pytest.mark.unit, pytest.mark.contract]


def _fresh(value: object) -> object:
    """Return an equal, non-identical string so `is`/`is not` mutations fail."""
    return "".join(value) if isinstance(value, str) else value


def _sse_line(payload: object) -> str:
    return f"data: {json.dumps(payload)}\n\n"


# ---------------------------------------------------------------------------
# schemas.py: Source model_post_init
# ---------------------------------------------------------------------------


def test_source_parses_missing_document_id_from_nowing_url():
    # chunk_id is already present; the `or` -> `and` and `is` -> `is not`
    # mutants must still parse document_id.
    source = Source(
        title="KB",
        url="nowing://documents/7/chunks/12",
        chunk_id=12,
    )
    assert source.document_id == 7
    assert source.chunk_id == 12
    assert source.source_type == "kb"


def test_source_parses_missing_chunk_id_from_nowing_url():
    source = Source(
        title="KB",
        url="nowing://documents/7/chunks/12",
        document_id=7,
    )
    assert source.document_id == 7
    assert source.chunk_id == 12
    assert source.source_type == "kb"


def test_source_preserves_web_source_type_when_provided():
    # The `elif self.url and self.source_type is None:` `and` -> `or` mutant
    # would overwrite an explicit source_type.
    source = Source(
        title="Web",
        url="https://example.com",
        source_type="kb",
    )
    assert source.source_type == "kb"


# ---------------------------------------------------------------------------
# schemas.py: _default_next_action fresh string coverage
# ---------------------------------------------------------------------------


def test_default_next_action_uses_equality_not_identity():
    status = _fresh("engine_unavailable")
    degradation_reason = _fresh("not_configured")
    assert _default_next_action(status, degradation_reason, None) == (
        "Deep research is not available in self-host Phase 1. "
        "Set CHAINLENS_API_KEY to use the hosted engine."
    )


# ---------------------------------------------------------------------------
# schemas.py: ResearchOutput computed field / property
# ---------------------------------------------------------------------------


def test_research_output_billable_units_requires_property():
    output = ResearchOutput(
        answer="answer", sources=[Source(title="S", url="https://x.com")]
    )
    # If @property is removed, `output.billable_units` becomes the method object.
    assert output.billable_units == 1


# ---------------------------------------------------------------------------
# schemas.py: boundary length / count values
# ---------------------------------------------------------------------------


def test_research_input_rejects_query_at_max_plus_one():
    with pytest.raises(ValidationError):
        ResearchInput(query="x" * (500 + 1))


def test_research_input_accepts_query_at_max():
    payload = ResearchInput(query="x" * 500)
    assert len(payload.query) == 500


def test_research_input_rejects_blank_query_after_strip():
    with pytest.raises(ValidationError):
        ResearchInput(query="   ")


def test_research_input_accepts_single_character_query():
    payload = ResearchInput(query="a")
    assert payload.query == "a"


def test_source_url_min_length_one():
    source = Source(title="S", url="x")
    assert source.url == "x"


def test_research_input_system_instructions_max_length():
    ResearchInput(query="q", system_instructions="x" * 2000)
    with pytest.raises(ValidationError):
        ResearchInput(query="q", system_instructions="x" * (2000 + 1))


def test_research_input_history_pair_length():
    ResearchInput(query="q", history=[["user", "hi"]])
    with pytest.raises(ValidationError):
        ResearchInput(query="q", history=[["user"]])


def test_research_input_history_max_items():
    history = [["user", f"{i}"] for i in range(50)]
    ResearchInput(query="q", history=history)
    with pytest.raises(ValidationError):
        ResearchInput(query="q", history=[*history, ["user", "one more"]])


# ---------------------------------------------------------------------------
# executor.py: _SSEParser feed_line
# ---------------------------------------------------------------------------


def test_feed_line_data_prefix_required_for_payload():
    parser = _SSEParser()
    parser.feed_line('data: {"type": "heartbeat"}')
    assert parser.saw_heartbeat is True


def test_feed_line_done_event_prefers_chatid_field():
    parser = _SSEParser()
    parser.feed_line('data: {"type": "done", "chatId": "abc-123"}')
    assert parser.chat_id == "abc-123"


def test_feed_line_done_event_prefers_chatid_over_chat_id():
    parser = _SSEParser()
    parser.feed_line('data: {"type": "done", "chatId": "first", "chat_id": "second"}')
    # `or` -> `and` mutant would skip the first field and leave chat_id unused.
    assert parser.chat_id == "first"


def test_feed_line_block_type_lte_inequality():
    parser = _SSEParser()
    parser.feed_line(
        'data: {"type": "aaa", "block": {"id": "b1", "type": "text", "data": "hello"}}'
    )
    assert "b1" not in parser.blocks
    assert parser.saw_unknown is True


def test_feed_line_block_type_gte_inequality():
    parser = _SSEParser()
    parser.feed_line(
        'data: {"type": "zzz", "block": {"id": "b1", "type": "text", "data": "hello"}}'
    )
    assert "b1" not in parser.blocks
    assert parser.saw_unknown is True


def test_feed_line_update_block_type_lte_inequality():
    parser = _SSEParser()
    parser.blocks["b1"] = types.SimpleNamespace(type="text", data="old")
    parser.feed_line(
        'data: {"type": "aaa", "blockId": "b1", "patch": [{"path": "/data", "op": "replace", "value": "new"}]}'
    )
    assert parser.blocks["b1"].data == "old"


def test_feed_line_update_block_type_gte_inequality():
    parser = _SSEParser()
    parser.blocks["b1"] = types.SimpleNamespace(type="text", data="old")
    parser.feed_line(
        'data: {"type": "zzz", "blockId": "b1", "patch": [{"path": "/data", "op": "replace", "value": "new"}]}'
    )
    assert parser.blocks["b1"].data == "old"


def test_feed_line_update_patch_path_inequalities():
    parser = _SSEParser()
    parser.blocks["b1"] = types.SimpleNamespace(type="text", data="old")
    for path in ["zdata", ".data"]:
        parser.feed_line(
            'data: {"type": "updateBlock", "blockId": "b1", "patch": [{"path": "'
            + path
            + '", "op": "replace", "value": "new"}]}'
        )
    assert parser.blocks["b1"].data == "old"


def test_feed_line_partial_state_inequalities():
    parser = _SSEParser()
    for state in ["aaa", "zzz"]:
        parser = _SSEParser()
        parser.feed_line(
            'data: {"type": "partial", "state": "'
            + state
            + '", "answer": "", "sources": []}'
        )
        assert parser.status == "partial"


def test_feed_line_heartbeat_type_inequality():
    parser = _SSEParser()
    parser.feed_line('data: {"type": "aaa"}')
    assert parser.saw_heartbeat is False
    assert parser.saw_unknown is True


# ---------------------------------------------------------------------------
# executor.py: _SSEParser finalize
# ---------------------------------------------------------------------------


def test_finalize_text_block_type_inequalities():
    parser = _SSEParser()
    for block_type in ["aaa", "zzz"]:
        parser.blocks[block_type] = types.SimpleNamespace(type=block_type, data="hello")
    output = parser.finalize()
    assert output.answer == ""


def test_finalize_text_block_and_or_mutant():
    parser = _SSEParser()
    parser.blocks["x"] = types.SimpleNamespace(type="aaa", data="hello")
    output = parser.finalize()
    assert output.answer == ""


def test_finalize_source_block_type_inequalities():
    parser = _SSEParser()
    for block_type in ["aaa", "zzz"]:
        parser.blocks[block_type] = types.SimpleNamespace(
            type=block_type,
            data=[{"metadata": {"url": "https://example.com", "title": "S"}}],
        )
    output = parser.finalize()
    assert output.sources == []


def test_finalize_does_not_degrade_non_complete_status():
    parser = _SSEParser()
    parser.status = "partial"
    parser.saw_done = True
    output = parser.finalize()
    assert output.status == "partial"


def test_finalize_degrades_complete_status_with_no_content():
    parser = _SSEParser()
    parser.saw_done = True
    output = parser.finalize()
    assert output.status == "engine_unavailable"
    assert output.degradation_reason == "stream_incomplete"


# ---------------------------------------------------------------------------
# executor.py: _parse_sse with __aiter__ only
# ---------------------------------------------------------------------------


def test_parse_sse_accepts_object_with_aiter():
    class _AsyncLineSource:
        def __aiter__(self):
            return self

    result = _parse_sse(_AsyncLineSource())
    assert inspect.iscoroutine(result)
    result.close()


# ---------------------------------------------------------------------------
# executor.py: _call_chainlens
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_call_chainlens_degrades_on_whitespace_api_key():
    with (
        patch.object(config, "CHAINLENS_API_KEY", "   "),
        patch("httpx.AsyncClient") as client_cls,
    ):
        client_cls.side_effect = AssertionError("should not instantiate client")
        output = await _call_chainlens(ResearchInput(query="q"))
    assert output.status == "engine_unavailable"
    assert output.degradation_reason == "not_configured"


# ---------------------------------------------------------------------------
# executor.py: _kb_fallback
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_kb_fallback_defaults_none_scope():
    with patch(
        "app.agents.chat.multi_agent_chat.shared.retrieval.hybrid_search.search_chunks",
        new_callable=AsyncMock,
    ) as search_chunks:
        await _kb_fallback(
            query="q",
            scope=None,
            top_k=3,
            session="session",
            workspace_id=1,
        )
    call_kwargs = search_chunks.call_args.kwargs
    assert call_kwargs["scope"].__class__.__name__ == "SearchScope"


# ---------------------------------------------------------------------------
# executor.py: execute_with_context
# ---------------------------------------------------------------------------


def _make_hit(
    document_id: int = 1, title: str = "KB Document", chunks: list | None = None
):
    if chunks is None:
        chunks = [types.SimpleNamespace(chunk_id=10, content="c1")]
    return types.SimpleNamespace(
        document_id=document_id,
        title=title,
        chunks=chunks,
    )


@pytest.mark.anyio
async def test_execute_with_context_records_fallback_attempted_false_when_no_fallback():
    with patch(
        "app.capabilities.chainlens.research.executor.metrics.record_chainlens_degradation"
    ) as record:
        output = await execute_with_context(
            ResearchInput(query="q"),
            None,
            search_fn=AsyncMock(
                return_value=ResearchOutput(
                    status="engine_unavailable", degradation_reason="unreachable"
                )
            ),
        )
    assert output.status == "engine_unavailable"
    call_kwargs = record.call_args.kwargs
    assert call_kwargs["fallback_attempted"] is False
    assert call_kwargs["fallback_used"] is False
    assert call_kwargs["fallback_hit_count"] == 0


@pytest.mark.anyio
async def test_execute_with_context_clamps_top_k_to_five():
    hits = [_make_hit(document_id=i) for i in range(6)]

    async def fallback_fn(**_kwargs):
        return hits

    output = await execute_with_context(
        ResearchInput(query="q"),
        types.SimpleNamespace(session="session", workspace_id=1),
        search_fn=AsyncMock(
            return_value=ResearchOutput(
                status="engine_unavailable", degradation_reason="unreachable"
            )
        ),
        fallback_fn=fallback_fn,
        top_k=10,
    )
    assert output.status == "partial"
    assert len(output.sources) == 5


@pytest.mark.anyio
async def test_execute_with_context_default_top_k_five():
    hits = [
        _make_hit(
            document_id=i, chunks=[types.SimpleNamespace(chunk_id=i, content=f"c{i}")]
        )
        for i in range(6)
    ]

    async def fallback_fn(**_kwargs):
        return hits

    output = await execute_with_context(
        ResearchInput(query="q"),
        types.SimpleNamespace(session="session", workspace_id=1),
        search_fn=AsyncMock(
            return_value=ResearchOutput(
                status="engine_unavailable", degradation_reason="unreachable"
            )
        ),
        fallback_fn=fallback_fn,
    )
    assert output.status == "partial"
    assert len(output.sources) == 5


@pytest.mark.anyio
async def test_execute_with_context_fallback_title_or_default():
    hits = [
        _make_hit(
            document_id=1,
            title="Custom Title",
            chunks=[types.SimpleNamespace(chunk_id=10, content="c1")],
        )
    ]

    async def fallback_fn(**_kwargs):
        return hits

    output = await execute_with_context(
        ResearchInput(query="q"),
        types.SimpleNamespace(session="session", workspace_id=1),
        search_fn=AsyncMock(
            return_value=ResearchOutput(
                status="engine_unavailable", degradation_reason="unreachable"
            )
        ),
        fallback_fn=fallback_fn,
    )
    assert output.sources[0].title == "Custom Title"


@pytest.mark.anyio
async def test_execute_with_context_fallback_break_continue_inner():
    hits = [
        _make_hit(
            document_id=1,
            chunks=[
                types.SimpleNamespace(chunk_id=10, content="c1"),
                types.SimpleNamespace(chunk_id=11, content="c2"),
            ],
        )
    ]

    async def fallback_fn(**_kwargs):
        return hits

    output = await execute_with_context(
        ResearchInput(query="q"),
        types.SimpleNamespace(session="session", workspace_id=1),
        search_fn=AsyncMock(
            return_value=ResearchOutput(
                status="engine_unavailable", degradation_reason="unreachable"
            )
        ),
        fallback_fn=fallback_fn,
        top_k=1,
    )
    assert output.status == "partial"
    assert len(output.sources) == 1
    assert output.fallback_hit_count == 1


@pytest.mark.anyio
async def test_execute_with_context_fallback_engine_reason_or():
    hits = [_make_hit()]

    async def fallback_fn(**_kwargs):
        return hits

    output = await execute_with_context(
        ResearchInput(query="q"),
        types.SimpleNamespace(session="session", workspace_id=1),
        search_fn=AsyncMock(
            return_value=ResearchOutput(
                status="engine_unavailable",
                degradation_reason="unreachable",
                engine_reason="engine-reason",
            )
        ),
        fallback_fn=fallback_fn,
    )
    assert output.engine_reason == "engine-reason"


@pytest.mark.anyio
async def test_execute_with_context_fallback_error_engine_reason_or():
    async def fallback_fn(**_kwargs):
        raise RuntimeError("boom")

    output = await execute_with_context(
        ResearchInput(query="q"),
        types.SimpleNamespace(session="session", workspace_id=1),
        search_fn=AsyncMock(
            return_value=ResearchOutput(
                status="engine_unavailable",
                degradation_reason="unreachable",
                engine_reason="engine-reason",
            )
        ),
        fallback_fn=fallback_fn,
    )
    assert output.degradation_reason == "fallback_kb_error"
    assert output.engine_reason == "unreachable"


# ---------------------------------------------------------------------------
# executor.py: build_research_executor
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_build_research_executor_default_top_k_five():
    hits = [_make_hit(document_id=i) for i in range(6)]

    async def search_fn(payload: ResearchInput) -> ResearchOutput:
        return ResearchOutput(
            status="engine_unavailable", degradation_reason="unreachable"
        )

    with patch(
        "app.capabilities.chainlens.research.executor._kb_fallback",
        new_callable=AsyncMock,
        side_effect=lambda **_kwargs: hits,
    ):
        execute = build_research_executor(search_fn)
        output = await execute(
            ResearchInput(query="q"),
            types.SimpleNamespace(session="session", workspace_id=1),
        )
    assert output.status == "partial"
    assert len(output.sources) == 5
