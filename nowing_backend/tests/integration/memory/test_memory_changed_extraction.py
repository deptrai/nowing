"""Story 6.5 (AC-1): auto-extraction emits ``memory.changed`` after its commit.

Auto-extraction writes facts with ``commit=False`` and commits the whole batch
itself, so ``MemoryRepository`` defers each ``memory.changed`` into a buffer and
the service flushes them AFTER the durable commit. These tests assert that the
trigger's primary source (auto-extracted facts) is no longer dormant, and that
Celery redelivery does not double-emit (the extraction idempotency guard).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.integration, pytest.mark.memory]


@pytest_asyncio.fixture
async def chat_turn(db_session, db_workspace, db_user):
    """A user + assistant message sharing a turn_id (an extractable turn)."""
    from app.db import NewChatMessage, NewChatMessageRole, NewChatThread

    thread = NewChatThread(
        title="Memory Test",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
    )
    db_session.add(thread)
    await db_session.flush()

    turn_id = "chat:turn:evt"
    user_message = NewChatMessage(
        thread_id=thread.id,
        role=NewChatMessageRole.USER,
        content=[{"type": "text", "text": "Competitor X raised prices by 10%."}],
        turn_id=turn_id,
        author_id=db_user.id,
    )
    assistant_message = NewChatMessage(
        thread_id=thread.id,
        role=NewChatMessageRole.ASSISTANT,
        content=[{"type": "text", "text": "Yes, competitor X raised prices 10% in Q2."}],
        turn_id=turn_id,
    )
    db_session.add(user_message)
    db_session.add(assistant_message)
    await db_session.flush()
    return thread, user_message, assistant_message


@pytest.fixture
def patched_embeddings(monkeypatch):
    """Deterministic embeddings so extraction never touches the real model."""

    def _fake_embed_texts(texts: list[str]) -> list[list[float]]:
        return [[0.1] * 384 for _ in texts]

    monkeypatch.setattr(
        "app.services.memory.repository.embed_texts",
        _fake_embed_texts,
    )
    return _fake_embed_texts


@pytest.fixture
def fake_llm_response() -> str:
    """A canned extraction response with one high-confidence fact."""
    return (
        '[{"content":"Competitor X raised prices by 10% in Q2 2026.",'
        '"type":"semantic","tags":["competitor","pricing"],"confidence":0.95}]'
    )


@pytest.fixture
def memory_events():
    """Capture ``memory.changed`` events and isolate the bus from the real
    trigger subscribers (no Celery enqueue) for the test's duration."""
    from app.event_bus import bus

    captured = []

    async def _spy(event) -> None:
        if event.event_type == "memory.changed":
            captured.append(event)

    snapshot = bus.subscribers()
    bus._subscribers = [_spy]
    try:
        yield captured
    finally:
        bus._subscribers = snapshot


def _patch_llm(monkeypatch, response: str) -> None:
    fake_llm = AsyncMock()
    fake_llm.ainvoke.return_value = type("FakeMsg", (), {"content": response})()
    monkeypatch.setattr(
        "app.services.memory.extraction.get_agent_llm",
        AsyncMock(return_value=fake_llm),
    )


async def test_auto_extraction_publishes_memory_changed_after_commit(
    db_session,
    db_workspace,
    db_user,
    chat_turn,
    patched_embeddings,
    fake_llm_response,
    memory_events,
    monkeypatch,
):
    """AC-1: one ``memory.changed`` per durable extracted memory, after commit."""
    from app.services.memory.extraction import MemoryExtractionService

    thread, _user, assistant_message = chat_turn
    _patch_llm(monkeypatch, fake_llm_response)

    service = MemoryExtractionService(
        session=db_session, workspace_id=db_workspace.id, user_id=db_user.id
    )
    memories = await service.extract_from_turn(
        thread_id=thread.id,
        turn_id=assistant_message.turn_id,
        assistant_message_id=assistant_message.id,
    )

    assert len(memories) == 1
    assert len(memory_events) == 1
    payload = memory_events[0].payload
    assert payload["memory_id"] == memories[0].id
    assert payload["workspace_id"] == db_workspace.id
    assert payload["change"] == "created"


async def test_auto_extraction_emits_exactly_once_on_reextract(
    db_session,
    db_workspace,
    db_user,
    chat_turn,
    patched_embeddings,
    fake_llm_response,
    memory_events,
    monkeypatch,
):
    """AC-1: Celery redelivery re-hits the idempotency guard → no duplicate event."""
    from app.services.memory.extraction import MemoryExtractionService

    thread, _user, assistant_message = chat_turn
    _patch_llm(monkeypatch, fake_llm_response)

    service = MemoryExtractionService(
        session=db_session, workspace_id=db_workspace.id, user_id=db_user.id
    )
    await service.extract_from_turn(
        thread.id, assistant_message.turn_id, assistant_message.id
    )
    assert len(memory_events) == 1

    second = await service.extract_from_turn(
        thread.id, assistant_message.turn_id, assistant_message.id
    )
    assert second == []
    assert len(memory_events) == 1
