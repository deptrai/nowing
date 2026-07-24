"""Red-phase tests for memory auto-extraction from chat turns (Story 4.5).

These tests will fail until `MemoryExtractionService`, the Celery task, and the
`Workspace.memory_auto_extract_enabled` column are implemented.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.integration, pytest.mark.memory]


@pytest_asyncio.fixture
async def chat_turn(db_session, db_workspace, db_user):
    """Create a user message and an assistant message sharing a turn_id."""
    from app.db import NewChatMessage, NewChatMessageRole, NewChatThread

    thread = NewChatThread(
        title="Memory Test",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
    )
    db_session.add(thread)
    await db_session.flush()

    turn_id = "chat:turn:123"
    user_message = NewChatMessage(
        thread_id=thread.id,
        role=NewChatMessageRole.USER,
        content=[
            {
                "type": "text",
                "text": "We discussed that competitor X raised prices by 10%.",
            }
        ],
        turn_id=turn_id,
        author_id=db_user.id,
    )
    assistant_message = NewChatMessage(
        thread_id=thread.id,
        role=NewChatMessageRole.ASSISTANT,
        content=[
            {
                "type": "text",
                "text": "Yes, competitor X raised prices by 10% in Q2 2026.",
            }
        ],
        turn_id=turn_id,
    )
    db_session.add(user_message)
    db_session.add(assistant_message)
    await db_session.flush()

    return thread, user_message, assistant_message


@pytest.fixture
def patched_embeddings(monkeypatch):
    """Return deterministic embeddings so tests don't need a real model."""

    def _fake_embed_texts(texts: list[str]) -> list[list[float]]:
        return [[0.1] * 384 for _ in texts]

    monkeypatch.setattr(
        "app.services.memory.repository.embed_texts",
        _fake_embed_texts,
    )
    return _fake_embed_texts


@pytest.fixture
def fake_llm_response():
    """A canned extraction response with one high-confidence fact."""
    return (
        '[{"content":"Competitor X raised prices by 10% in Q2 2026.",'
        '"type":"semantic","tags":["competitor","pricing"],'
        '"confidence":0.95}]'
    )


@pytest.fixture
def fake_llm_low_confidence_response():
    """A canned extraction response with a low-confidence fact."""
    return (
        '[{"content":"Maybe something happened.",'
        '"type":"semantic","tags":[],'
        '"confidence":0.3}]'
    )


async def test_extract_memory_after_chat_turn(
    db_session,
    db_workspace,
    db_user,
    chat_turn,
    patched_embeddings,
    fake_llm_response,
    monkeypatch,
):
    """Assistant turn is converted into a Memory row with source_type=chat_message."""
    from app.db import Memory
    from app.services.memory.extraction import MemoryExtractionService

    thread, user_message, assistant_message = chat_turn

    fake_llm = AsyncMock()
    fake_llm.ainvoke.return_value = type("FakeMsg", (), {"content": fake_llm_response})()
    monkeypatch.setattr(
        "app.services.memory.extraction.get_agent_llm",
        AsyncMock(return_value=fake_llm),
    )

    service = MemoryExtractionService(
        session=db_session,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
    )
    memories = await service.extract_from_turn(
        thread_id=thread.id,
        turn_id=assistant_message.turn_id,
        assistant_message_id=assistant_message.id,
    )

    assert len(memories) == 1
    memory = memories[0]
    assert isinstance(memory, Memory)
    assert memory.content == "Competitor X raised prices by 10% in Q2 2026."
    assert memory.type.value == "semantic"
    assert memory.source_type.value == "chat_message"
    assert memory.source_id == assistant_message.id
    assert memory.workspace_id == db_workspace.id
    assert memory.created_by_id == user_message.author_id


async def test_extract_memory_records_token_usage(
    db_session,
    db_workspace,
    db_user,
    chat_turn,
    patched_embeddings,
    fake_llm_response,
    monkeypatch,
):
    """Extraction records TokenUsage with usage_type='memory_create'."""
    from app.db import TokenUsage
    from app.services.memory.extraction import MemoryExtractionService

    thread, user_message, assistant_message = chat_turn

    fake_llm = AsyncMock()
    fake_llm.ainvoke.return_value = type("FakeMsg", (), {"content": fake_llm_response})()
    monkeypatch.setattr(
        "app.services.memory.extraction.get_agent_llm",
        AsyncMock(return_value=fake_llm),
    )

    service = MemoryExtractionService(
        session=db_session,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
    )
    await service.extract_from_turn(
        thread_id=thread.id,
        turn_id=assistant_message.turn_id,
        assistant_message_id=assistant_message.id,
    )

    from sqlalchemy import select
    from app.db import TokenUsage

    result = await db_session.execute(
        select(TokenUsage).where(
            TokenUsage.thread_id == thread.id,
            TokenUsage.usage_type == "memory_create",
        )
    )
    usage = result.scalar_one_or_none()
    assert usage is not None
    assert usage.workspace_id == db_workspace.id


async def test_auto_extract_respects_workspace_toggle(
    db_session,
    db_workspace,
    db_user,
    chat_turn,
    patched_embeddings,
    fake_llm_response,
    monkeypatch,
):
    """Workspace with memory_auto_extract_enabled=False produces no memories."""
    from app.db import Memory
    from app.services.memory.extraction import MemoryExtractionService

    thread, user_message, assistant_message = chat_turn
    db_workspace.memory_auto_extract_enabled = False

    fake_llm = AsyncMock()
    fake_llm.ainvoke.return_value = type("FakeMsg", (), {"content": fake_llm_response})()
    monkeypatch.setattr(
        "app.services.memory.extraction.get_agent_llm",
        AsyncMock(return_value=fake_llm),
    )

    service = MemoryExtractionService(
        session=db_session,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
    )
    memories = await service.extract_from_turn(
        thread_id=thread.id,
        turn_id=assistant_message.turn_id,
        assistant_message_id=assistant_message.id,
    )

    assert memories == []

    from sqlalchemy import select
    from app.db import Memory

    remaining = await db_session.execute(
        select(Memory).where(Memory.source_id == assistant_message.id)
    )
    assert remaining.scalar_one_or_none() is None


async def test_extract_filters_low_confidence_facts(
    db_session,
    db_workspace,
    db_user,
    chat_turn,
    patched_embeddings,
    fake_llm_low_confidence_response,
    monkeypatch,
):
    """Facts below the configured confidence threshold are not persisted."""
    from app.services.memory.extraction import MemoryExtractionService

    thread, user_message, assistant_message = chat_turn

    fake_llm = AsyncMock()
    fake_llm.ainvoke.return_value = type(
        "FakeMsg", (), {"content": fake_llm_low_confidence_response}
    )()
    monkeypatch.setattr(
        "app.services.memory.extraction.get_agent_llm",
        AsyncMock(return_value=fake_llm),
    )

    service = MemoryExtractionService(
        session=db_session,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
    )
    memories = await service.extract_from_turn(
        thread_id=thread.id,
        turn_id=assistant_message.turn_id,
        assistant_message_id=assistant_message.id,
    )

    assert memories == []


async def test_extract_updates_near_duplicate(
    db_session,
    db_workspace,
    db_user,
    chat_turn,
    patched_embeddings,
    fake_llm_response,
    monkeypatch,
):
    """A fact semantically near an existing memory updates it and versions the old content."""
    from app.db import Memory
    from app.services.memory.extraction import MemoryExtractionService
    from app.services.memory.repository import MemoryRepository

    thread, user_message, assistant_message = chat_turn

    repo = MemoryRepository(session=db_session)
    first = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Competitor X raised prices by 10% in Q2 2026.",
        embedding=[0.1] * 384,
        type="semantic",
        source_type="chat_message",
        source_id=assistant_message.id,
        created_by_id=db_user.id,
    )

    fake_llm = AsyncMock()
    fake_llm.ainvoke.return_value = type("FakeMsg", (), {"content": fake_llm_response})()
    monkeypatch.setattr(
        "app.services.memory.extraction.get_agent_llm",
        AsyncMock(return_value=fake_llm),
    )

    service = MemoryExtractionService(
        session=db_session,
        workspace_id=db_workspace.id,
        user_id=db_user.id,
    )
    memories = await service.extract_from_turn(
        thread_id=thread.id,
        turn_id=assistant_message.turn_id,
        assistant_message_id=assistant_message.id,
    )

    assert len(memories) == 1
    assert memories[0].id == first.id
    assert len(memories[0].versions) == 1
    assert memories[0].versions[0].previous_content == first.content


async def test_celery_extraction_task_exists(
    db_session,
    chat_turn,
):
    """extract_memory_after_chat_turn Celery task loads the message and calls the service."""
    from app.tasks.celery_tasks.memory_extraction_task import (
        extract_memory_after_chat_turn,
    )

    _, _, assistant_message = chat_turn

    # The task is async-wrapped; calling .apply or the async helper should not crash.
    result = extract_memory_after_chat_turn.apply(args=[assistant_message.id])
    assert result is not None
