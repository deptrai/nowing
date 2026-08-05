"""respx-mocked tests for the Nowing HTTP clients."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from nowing_evals.core.arms import ArmRequest
from nowing_evals.core.arms.nowing import NowingArm
from nowing_evals.core.clients import (
    DocumentsClient,
    NewChatClient,
    SearchSpaceClient,
)
from nowing_evals.core.clients.new_chat import StreamedAnswer, ThreadBusyError

_BASE = "http://test"


@pytest.fixture
def http() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=_BASE)


# ---------------------------------------------------------------------------
# SearchSpaceClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_create_search_space_returns_row(respx_mock, http):
    respx_mock.post("/api/v1/searchspaces").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 99,
                "name": "eval-medical-2026",
                "description": None,
                "user_id": "user-x",
                "citations_enabled": True,
                "qna_custom_instructions": None,
            },
        )
    )
    client = SearchSpaceClient(http, _BASE)
    row = await client.create("eval-medical-2026")
    assert row.id == 99
    assert row.name == "eval-medical-2026"


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_delete_search_space_idempotent_on_404(respx_mock, http):
    respx_mock.delete("/api/v1/searchspaces/42").mock(
        return_value=httpx.Response(404, json={"detail": "gone"})
    )
    client = SearchSpaceClient(http, _BASE)
    await client.delete(42)  # must not raise


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_set_model_roles_partial_update(respx_mock, http):
    route = respx_mock.put("/api/v1/search-spaces/42/model-roles").mock(
        return_value=httpx.Response(
            200,
            json={
                "chat_model_id": -10042,
                "image_gen_model_id": None,
                "vision_model_id": None,
            },
        )
    )
    client = SearchSpaceClient(http, _BASE)
    roles = await client.set_model_roles(42, chat_model_id=-10042)
    assert roles.chat_model_id == -10042
    sent_body = json.loads(route.calls[-1].request.content)
    assert sent_body == {"chat_model_id": -10042}


# ---------------------------------------------------------------------------
# DocumentsClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_documents_status_parses_state(respx_mock, http):
    respx_mock.get("/api/v1/documents/status").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": 1,
                        "title": "a.pdf",
                        "document_type": "FILE",
                        "status": {"state": "ready", "reason": None},
                    },
                    {
                        "id": 2,
                        "title": "b.pdf",
                        "document_type": "FILE",
                        "status": {"state": "failed", "reason": "ETL boom"},
                    },
                ]
            },
        )
    )
    client = DocumentsClient(http, _BASE)
    statuses = await client.get_status(search_space_id=1, document_ids=[1, 2])
    assert {s.document_id for s in statuses} == {1, 2}
    assert {s.is_ready for s in statuses} == {True, False}


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_documents_upload_returns_payload(respx_mock, http, tmp_path: Path):
    f1 = tmp_path / "a.pdf"
    f1.write_bytes(b"%PDF-1.4 small")
    respx_mock.post("/api/v1/documents/fileupload").mock(
        return_value=httpx.Response(
            200,
            json={
                "message": "Files uploaded",
                "document_ids": [101],
                "duplicate_document_ids": [],
                "total_files": 1,
                "pending_files": 1,
                "skipped_duplicates": 0,
            },
        )
    )
    client = DocumentsClient(http, _BASE)
    result = await client.upload(files=[f1], search_space_id=7)
    assert result.document_ids == [101]
    assert result.pending_files == 1


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_documents_list_chunks_paginated(respx_mock, http):
    respx_mock.get("/api/v1/documents/5/chunks").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "items": [{"id": 1, "content": "a"}, {"id": 2, "content": "b"}],
                    "total": 3,
                    "page": 0,
                    "page_size": 2,
                    "has_more": True,
                },
            ),
            httpx.Response(
                200,
                json={
                    "items": [{"id": 3, "content": "c"}],
                    "total": 3,
                    "page": 1,
                    "page_size": 2,
                    "has_more": False,
                },
            ),
        ]
    )
    client = DocumentsClient(http, _BASE)
    rows = await client.list_chunks(5, page_size=2)
    assert [r.id for r in rows] == [1, 2, 3]


# ---------------------------------------------------------------------------
# NewChatClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_create_thread_returns_id(respx_mock, http):
    respx_mock.post("/api/v1/threads").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 555,
                "title": "eval",
                "archived": False,
                "visibility": "PRIVATE",
                "search_space_id": 1,
                "messages": [],
                "created_at": "2026-05-11T00:00:00Z",
                "updated_at": "2026-05-11T00:00:00Z",
            },
        )
    )
    client = NewChatClient(http, _BASE)
    tid = await client.create_thread(search_space_id=1)
    assert tid == 555


def _sse_body(events: list[dict]) -> bytes:
    parts = []
    for ev in events:
        parts.append(f"data: {json.dumps(ev)}\n\n")
    parts.append("data: [DONE]\n\n")
    return "".join(parts).encode("utf-8")


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_ask_accumulates_text_deltas(respx_mock, http):
    body = _sse_body(
        [
            {"type": "start", "messageId": "m1"},
            {"type": "text-start", "id": "t1"},
            {"type": "text-delta", "id": "t1", "delta": "Answer "},
            {"type": "text-delta", "id": "t1", "delta": "is "},
            {"type": "text-delta", "id": "t1", "delta": "B [citation:42]."},
            {"type": "text-end", "id": "t1"},
            {"type": "finish"},
        ]
    )
    respx_mock.post("/api/v1/new_chat").mock(
        return_value=httpx.Response(
            200,
            content=body,
            headers={"Content-Type": "text/event-stream"},
        )
    )
    client = NewChatClient(http, _BASE)
    answer = await client.ask(thread_id=1, search_space_id=2, user_query="What is the answer?")
    assert answer.text == "Answer is B [citation:42]."
    assert answer.finished_normally is True
    assert any(c["chunk_id"] == 42 for c in answer.citations)


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_ask_409_thread_busy_retries(respx_mock, http):
    body = _sse_body(
        [
            {"type": "text-delta", "id": "t1", "delta": "ok"},
            {"type": "finish"},
        ]
    )
    busy = httpx.Response(
        409,
        json={"detail": {"errorCode": "THREAD_BUSY", "message": "busy"}},
        headers={"Retry-After": "1"},
    )
    success = httpx.Response(200, content=body, headers={"Content-Type": "text/event-stream"})
    respx_mock.post("/api/v1/new_chat").mock(side_effect=[busy, success])
    client = NewChatClient(http, _BASE)
    answer = await client.ask(thread_id=1, search_space_id=2, user_query="hi", max_busy_retries=2)
    assert answer.text == "ok"


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_ask_parses_telemetry_events(respx_mock, http):
    body = _sse_body(
        [
            {"type": "data-turn-info", "data": {"chat_turn_id": "533:1762900000000"}},
            {
                "type": "data-user-message-id",
                "data": {"message_id": 1843, "turn_id": "533:1762900000000"},
            },
            {
                "type": "data-assistant-message-id",
                "data": {"message_id": 1844, "turn_id": "533:1762900000000"},
            },
            {"type": "start", "messageId": "m1"},
            {"type": "text-start", "id": "t1"},
            {"type": "text-delta", "id": "t1", "delta": "Answer "},
            {"type": "text-delta", "id": "t1", "delta": "is B."},
            {"type": "text-end", "id": "t1"},
            {
                "type": "data-token-usage",
                "data": {
                    "usage": {
                        "openai/gpt-5.4-mini": {
                            "prompt_tokens": 10,
                            "completion_tokens": 5,
                            "total_tokens": 15,
                            "cost_micros": 100,
                        }
                    },
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                    "cost_micros": 100,
                    "call_details": [{"model": "openai/gpt-5.4-mini", "cost_micros": 100}],
                },
            },
            {"type": "finish"},
        ]
    )
    respx_mock.post("/api/v1/new_chat").mock(
        return_value=httpx.Response(
            200,
            content=body,
            headers={"Content-Type": "text/event-stream"},
        )
    )
    client = NewChatClient(http, _BASE)
    answer = await client.ask(thread_id=1, search_space_id=2, user_query="What is the answer?")
    assert answer.text == "Answer is B."
    assert answer.turn_id == "533:1762900000000"
    assert answer.user_message_id == "1843"
    assert answer.assistant_message_id == "1844"
    assert answer.prompt_tokens == 10
    assert answer.completion_tokens == 5
    assert answer.total_tokens == 15
    assert answer.cost_micros == 100
    assert answer.ttfb_ms is not None
    assert answer.finished_normally is True
    assert answer.model_breakdown is not None


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_ask_409_exhausts_retries(respx_mock, http):
    busy = httpx.Response(
        409,
        json={"detail": {"errorCode": "TURN_CANCELLING", "message": "wait"}},
        headers={"Retry-After": "1"},
    )
    respx_mock.post("/api/v1/new_chat").mock(return_value=busy)
    client = NewChatClient(http, _BASE)
    with pytest.raises(ThreadBusyError):
        await client.ask(thread_id=1, search_space_id=2, user_query="hi", max_busy_retries=1)


# ---------------------------------------------------------------------------
# MemoriesClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_memories_create_serializes_full_memory_contract(respx_mock, http):
    """The eval client must preserve the backend create-memory contract."""
    from nowing_evals.core.clients import MemoriesClient

    route = respx_mock.post("/api/v1/workspaces/7/memories").mock(
        return_value=httpx.Response(
            201,
            json={"id": 42, "workspace_id": 7, "content": "Q2 pricing increased"},
        )
    )
    client = MemoriesClient(http, _BASE)
    memory = await client.create(
        7,
        "Q2 pricing increased",
        type_="semantic",
        tags=["competitor", "pricing"],
        confidence=0.95,
        # Must be a real ``MemorySourceType``. This test previously asserted
        # ``source_type="eval"``, a value the backend enum has no member for — so
        # a test named after "the create-memory contract" was serialising a
        # payload the API would have rejected with a 422.
        source_type="manual",
        source_id=11,
    )

    assert memory["id"] == 42
    assert json.loads(route.calls[-1].request.content) == {
        "content": "Q2 pricing increased",
        "type": "semantic",
        "tags": ["competitor", "pricing"],
        "confidence": 0.95,
        "source_type": "manual",
        "source_id": 11,
        "research_thread_id": None,
    }


@pytest.mark.asyncio
async def test_memories_create_rejects_unknown_source_type(http):
    """Fail locally instead of sending a payload the backend will 422."""
    from nowing_evals.core.clients import MemoriesClient

    client = MemoriesClient(http, _BASE)
    with pytest.raises(ValueError, match="MemorySourceType"):
        await client.create(7, "x", source_type="eval")


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_memories_search_preserves_rank_of_malformed_items(respx_mock, http):
    """A non-object item must raise, not be silently dropped.

    Filtering one out shifts every later item up a rank, so the item that was
    really 6th gets scored as if it were 5th.
    """
    from nowing_evals.core.clients import MemoriesClient

    respx_mock.post("/api/v1/workspaces/7/memories/search").mock(
        return_value=httpx.Response(200, json={"items": [None, {"id": 1}]})
    )
    client = MemoriesClient(http, _BASE)
    with pytest.raises(RuntimeError, match="rank 1"):
        await client.search(7, "q", top_k=5)


@pytest.mark.asyncio
async def test_memories_search_validates_top_k_locally(http):
    """A local error beats a bare 422 from the server."""
    from nowing_evals.core.clients import MemoriesClient

    client = MemoriesClient(http, _BASE)
    with pytest.raises(ValueError, match="top_k"):
        await client.search(7, "q", top_k=0)


@pytest.mark.asyncio
async def test_memories_search_rejects_top_k_above_backend_ceiling(http):
    """Story 3.14 (D9) tightened ``MemorySearchRequest.top_k`` to ``le=5``; the
    client's local pre-check must track that ceiling, not the old ``le=100``."""
    from nowing_evals.core.clients import MemoriesClient

    client = MemoriesClient(http, _BASE)
    with pytest.raises(ValueError, match="top_k must be between 1 and 5"):
        await client.search(7, "q", top_k=6)


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_memories_search_reports_non_json_body(respx_mock, http):
    """A proxy or login page returning 200 text/html must name the failing call."""
    from nowing_evals.core.clients import MemoriesClient

    respx_mock.post("/api/v1/workspaces/7/memories/search").mock(
        return_value=httpx.Response(200, text="<html>login</html>")
    )
    client = MemoriesClient(http, _BASE)
    with pytest.raises(RuntimeError, match="non-JSON body"):
        await client.search(7, "q", top_k=5)


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_memories_delete_tolerates_already_deleted(respx_mock, http):
    """``purge`` must be re-runnable after a partial failure."""
    from nowing_evals.core.clients import MemoriesClient

    respx_mock.delete("/api/v1/memories/42").mock(return_value=httpx.Response(404))
    client = MemoriesClient(http, _BASE)
    await client.delete(42)  # does not raise


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_memories_create_reports_unexpected_payload_shape(respx_mock, http):
    """A 200 that isn't a JSON object must raise, not return a garbage dict."""
    from nowing_evals.core.clients import MemoriesClient

    respx_mock.post("/api/v1/workspaces/7/memories").mock(
        return_value=httpx.Response(200, json=[1, 2, 3])
    )
    client = MemoriesClient(http, _BASE)
    with pytest.raises(RuntimeError, match="Unexpected memory create payload"):
        await client.create(7, "x")


@pytest.mark.asyncio
async def test_memories_search_rejects_non_integer_top_k(http):
    """A bool or float top_k must be rejected before the request is sent."""
    from nowing_evals.core.clients import MemoriesClient

    client = MemoriesClient(http, _BASE)
    with pytest.raises(ValueError, match="top_k must be an integer"):
        await client.search(7, "q", top_k=True)
    with pytest.raises(ValueError, match="top_k must be an integer"):
        await client.search(7, "q", top_k=2.5)


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_memories_search_reports_unexpected_payload_shape(respx_mock, http):
    """A JSON body that decodes but has no 'items' list must raise clearly."""
    from nowing_evals.core.clients import MemoriesClient

    respx_mock.post("/api/v1/workspaces/7/memories/search").mock(
        return_value=httpx.Response(200, json={"result": "ok"})
    )
    client = MemoriesClient(http, _BASE)
    with pytest.raises(RuntimeError, match="Unexpected memory search payload"):
        await client.search(7, "q", top_k=5)


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_memories_delete_raises_on_non_404_error(respx_mock, http):
    """A real server error must propagate rather than being swallowed like 404."""
    from nowing_evals.core.clients import MemoriesClient

    respx_mock.delete("/api/v1/memories/42").mock(return_value=httpx.Response(500))
    client = MemoriesClient(http, _BASE)
    with pytest.raises(httpx.HTTPStatusError):
        await client.delete(42)


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_memories_search_unwraps_ranked_items_and_filters(respx_mock, http):
    """Search posts the workspace-scoped payload and returns the ordered items."""
    from nowing_evals.core.clients import MemoriesClient

    route = respx_mock.post("/api/v1/workspaces/7/memories/search").mock(
        return_value=httpx.Response(
            200,
            json={"items": [{"id": 42, "content": "Q2 pricing increased", "score": 0.0}]},
        )
    )
    client = MemoriesClient(http, _BASE)
    items = await client.search(
        7,
        "pricing",
        top_k=5,
        type_="semantic",
        tags=["competitor"],
        research_thread_id=3,
    )

    assert items == [{"id": 42, "content": "Q2 pricing increased", "score": 0.0}]
    assert json.loads(route.calls[-1].request.content) == {
        "query": "pricing",
        "top_k": 5,
        "type": "semantic",
        "tags": ["competitor"],
        "research_thread_id": 3,
    }


@pytest.mark.asyncio
async def test_nowing_arm_maps_answer_telemetry_to_arm_result():
    """`NowingArm` should expose per-answer telemetry in `ArmResult`."""
    client = AsyncMock(spec=NewChatClient)
    client.create_thread = AsyncMock(return_value=42)
    client.delete_thread = AsyncMock(return_value=None)
    client.ask = AsyncMock(
        return_value=StreamedAnswer(
            text="Answer: B.",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost_micros=100,
            ttfb_ms=55,
            latency_ms=123,
            user_message_id="1843",
            assistant_message_id="1844",
            turn_id="533:1762900000000",
            finished_normally=True,
        )
    )

    arm = NowingArm(client=client, search_space_id=7, ephemeral_threads=True)
    result = await arm.answer(
        ArmRequest(
            question_id="q1",
            prompt="What is the answer?",
            mentioned_document_ids=[1, 2],
        )
    )

    assert result.ok
    assert result.answer_letter == "B"
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert result.cost_micros == 100
    assert result.latency_ms == 123
    assert result.extra["ttfb_ms"] == 55
    assert result.extra["turn_id"] == "533:1762900000000"
    client.delete_thread.assert_awaited_once_with(42)


@pytest.mark.asyncio
async def test_nowing_arm_deletes_thread_when_answer_times_out():
    """`NowingArm` must delete the thread even if `answer` is cancelled."""
    client = AsyncMock(spec=NewChatClient)
    client.create_thread = AsyncMock(return_value=42)
    client.delete_thread = AsyncMock(return_value=None)
    client.ask = AsyncMock(side_effect=asyncio.CancelledError)

    arm = NowingArm(client=client, search_space_id=7, ephemeral_threads=True)
    with pytest.raises(asyncio.CancelledError):
        await arm.answer(
            ArmRequest(
                question_id="q1",
                prompt="What is the answer?",
            )
        )

    client.delete_thread.assert_awaited_once_with(42)


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_ask_coerces_integer_start_message_id(respx_mock, http):
    body = _sse_body(
        [
            {"type": "start", "messageId": 1843},
            {"type": "text-start", "id": "t1"},
            {"type": "text-delta", "id": "t1", "delta": "ok"},
            {"type": "text-end", "id": "t1"},
            {"type": "finish"},
        ]
    )
    respx_mock.post("/api/v1/new_chat").mock(
        return_value=httpx.Response(
            200,
            content=body,
            headers={"Content-Type": "text/event-stream"},
        )
    )
    client = NewChatClient(http, _BASE)
    answer = await client.ask(thread_id=1, search_space_id=2, user_query="hi")
    assert answer.user_message_id == "1843"


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_ask_without_token_usage_defaults_to_no_cost(respx_mock, http):
    """Backward compatibility: older backends may not emit data-token-usage."""
    body = _sse_body(
        [
            {"type": "text-start", "id": "t1"},
            {"type": "text-delta", "id": "t1", "delta": "ok"},
            {"type": "text-end", "id": "t1"},
            {"type": "finish"},
        ]
    )
    respx_mock.post("/api/v1/new_chat").mock(
        return_value=httpx.Response(
            200,
            content=body,
            headers={"Content-Type": "text/event-stream"},
        )
    )
    client = NewChatClient(http, _BASE)
    answer = await client.ask(thread_id=1, search_space_id=2, user_query="hi")
    assert answer.text == "ok"
    assert answer.prompt_tokens == 0
    assert answer.completion_tokens == 0
    assert answer.total_tokens == 0
    assert answer.cost_micros is None
    assert answer.model_breakdown is None


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_ask_token_usage_zero_overrides_previous_values(respx_mock, http):
    """Explicitly-zero token counts must replace previous non-zero values."""
    body = _sse_body(
        [
            {"type": "text-start", "id": "t1"},
            {"type": "text-delta", "id": "t1", "delta": "ok"},
            {
                "type": "data-token-usage",
                "data": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                    "cost_micros": 100,
                    "usage": {"openai/gpt-5.4-mini": {"prompt_tokens": 10}},
                },
            },
            {
                "type": "data-token-usage",
                "data": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cost_micros": 0,
                    "usage": {},
                },
            },
            {"type": "text-end", "id": "t1"},
            {"type": "finish"},
        ]
    )
    respx_mock.post("/api/v1/new_chat").mock(
        return_value=httpx.Response(
            200,
            content=body,
            headers={"Content-Type": "text/event-stream"},
        )
    )
    client = NewChatClient(http, _BASE)
    answer = await client.ask(thread_id=1, search_space_id=2, user_query="hi")
    assert answer.prompt_tokens == 0
    assert answer.completion_tokens == 0
    assert answer.total_tokens == 0
    assert answer.cost_micros == 0
    assert answer.model_breakdown == {}


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_create_thread_uses_workspace_id_when_given(respx_mock, http):
    route = respx_mock.post("/api/v1/threads").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 555,
                "title": "eval",
                "archived": False,
                "visibility": "PRIVATE",
                "search_space_id": 1,
                "messages": [],
                "created_at": "2026-05-11T00:00:00Z",
                "updated_at": "2026-05-11T00:00:00Z",
            },
        )
    )
    client = NewChatClient(http, _BASE)
    tid = await client.create_thread(search_space_id=1, workspace_id=42)
    assert tid == 555
    sent = json.loads(route.calls[-1].request.content)
    assert sent["workspace_id"] == 42
    assert sent["search_space_id"] == 1


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_create_thread_falls_back_to_search_space_id(respx_mock, http):
    route = respx_mock.post("/api/v1/threads").mock(
        return_value=httpx.Response(200, json={"id": 555})
    )
    client = NewChatClient(http, _BASE)
    await client.create_thread(search_space_id=7)
    sent = json.loads(route.calls[-1].request.content)
    assert sent["workspace_id"] == 7
    assert sent["search_space_id"] == 7


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_ask_uses_workspace_id_when_given(respx_mock, http):
    body = _sse_body(
        [
            {"type": "text-start", "id": "t1"},
            {"type": "text-delta", "id": "t1", "delta": "ok"},
            {"type": "text-end", "id": "t1"},
            {"type": "finish"},
        ]
    )
    route = respx_mock.post("/api/v1/new_chat").mock(
        return_value=httpx.Response(
            200,
            content=body,
            headers={"Content-Type": "text/event-stream"},
        )
    )
    client = NewChatClient(http, _BASE)
    answer = await client.ask(thread_id=1, search_space_id=2, workspace_id=42, user_query="hi")
    assert answer.text == "ok"
    sent = json.loads(route.calls[-1].request.content)
    assert sent["workspace_id"] == 42
    assert sent["search_space_id"] == 2


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_ask_coerces_string_token_usage(respx_mock, http):
    body = _sse_body(
        [
            {"type": "text-start", "id": "t1"},
            {"type": "text-delta", "id": "t1", "delta": "ok"},
            {"type": "text-end", "id": "t1"},
            {
                "type": "data-token-usage",
                "data": {
                    "prompt_tokens": "10",
                    "completion_tokens": "5.0",
                    "total_tokens": "15",
                    "cost_micros": "100",
                },
            },
            {"type": "finish"},
        ]
    )
    respx_mock.post("/api/v1/new_chat").mock(
        return_value=httpx.Response(
            200,
            content=body,
            headers={"Content-Type": "text/event-stream"},
        )
    )
    client = NewChatClient(http, _BASE)
    answer = await client.ask(thread_id=1, search_space_id=2, user_query="hi")
    assert answer.prompt_tokens == 10
    assert answer.completion_tokens == 5
    assert answer.total_tokens == 15
    assert answer.cost_micros == 100


@pytest.mark.asyncio
async def test_nowing_arm_passes_workspace_id_from_options():
    client = AsyncMock(spec=NewChatClient)
    client.create_thread = AsyncMock(return_value=42)
    client.delete_thread = AsyncMock(return_value=None)
    client.ask = AsyncMock(
        return_value=StreamedAnswer(
            text="ok",
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            finished_normally=True,
        )
    )
    arm = NowingArm(client=client, search_space_id=7)
    await arm.answer(
        ArmRequest(
            question_id="q1",
            prompt="hi",
            options={"workspace_id": 42},
        )
    )
    client.create_thread.assert_awaited_once_with(
        search_space_id=7, workspace_id=42, title="eval:q1"
    )
    client.ask.assert_awaited_once()
    assert client.ask.await_args.kwargs["workspace_id"] == 42


@pytest.mark.asyncio
async def test_nowing_arm_passes_workspace_id_from_init():
    client = AsyncMock(spec=NewChatClient)
    client.create_thread = AsyncMock(return_value=42)
    client.delete_thread = AsyncMock(return_value=None)
    client.ask = AsyncMock(return_value=StreamedAnswer(text="ok", finished_normally=True))
    arm = NowingArm(client=client, search_space_id=7, workspace_id=99)
    await arm.answer(ArmRequest(question_id="q1", prompt="hi"))
    client.create_thread.assert_awaited_once_with(
        search_space_id=7, workspace_id=99, title="eval:q1"
    )


@pytest.mark.asyncio
async def test_nowing_arm_maps_http_error_to_error_code():
    client = AsyncMock(spec=NewChatClient)
    client.create_thread = AsyncMock(return_value=42)
    client.delete_thread = AsyncMock(return_value=None)
    client.ask = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "Server error",
            request=httpx.Request("POST", "http://test"),
            response=httpx.Response(503),
        )
    )
    arm = NowingArm(client=client, search_space_id=7)
    result = await arm.answer(ArmRequest(question_id="q1", prompt="hi"))
    assert result.error is not None
    assert result.extra["error_code"] == "HTTP503"
    assert result.extra["workspace_id"] == 7


@pytest.mark.asyncio
async def test_nowing_arm_coerces_string_cost():
    client = AsyncMock(spec=NewChatClient)
    client.create_thread = AsyncMock(return_value=42)
    client.delete_thread = AsyncMock(return_value=None)
    client.ask = AsyncMock(
        return_value=StreamedAnswer(
            text="ok",
            prompt_tokens="10",
            completion_tokens="5",
            total_tokens="15",
            cost_micros="100",
            finished_normally=True,
        )
    )
    arm = NowingArm(client=client, search_space_id=7)
    result = await arm.answer(ArmRequest(question_id="q1", prompt="hi"))
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert result.cost_micros == 100
