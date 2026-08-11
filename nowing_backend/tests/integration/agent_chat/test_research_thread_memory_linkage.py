"""Memory/Celery integration tests for Story 18.5: ResearchThread auto-linkage.

These tests verify that ``MemoryExtractionService`` and the Celery
``extract_memory_after_chat_turn`` task tag new ``Memory`` rows with the linked
``research_thread_id``.

Test id / priority convention: ``18.5-INT-{seq} - P{n}/AC{n}:``
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    Memory,
    NewChatMessage,
    NewChatMessageRole,
    NewChatThread,
    User,
    VerticalClient,
    Workspace,
)
from tests.integration.agent_chat.conftest import (
    _fake_extraction_llm,
    _make_research_chat_pair,
)

pytestmark = [pytest.mark.integration]


def _threads_url(workspace_id: int) -> str:
    return f"/api/v1/workspaces/{workspace_id}/agent-chat/threads"


async def _add_turn_messages(
    db_session: AsyncSession,
    db_user: User,
    chat_thread: NewChatThread,
    user_text: str,
    assistant_text: str,
    turn_id: str,
) -> NewChatMessage:
    """Create one user + one assistant message for a turn, return assistant."""
    user_message = NewChatMessage(
        thread_id=chat_thread.id,
        role=NewChatMessageRole.USER,
        content=[{"type": "text", "text": user_text}],
        turn_id=turn_id,
        author_id=db_user.id,
    )
    assistant_message = NewChatMessage(
        thread_id=chat_thread.id,
        role=NewChatMessageRole.ASSISTANT,
        content=[{"type": "text", "text": assistant_text}],
        turn_id=turn_id,
        author_id=db_user.id,
    )
    db_session.add(user_message)
    db_session.add(assistant_message)
    await db_session.flush()
    return assistant_message


async def test_memory_extraction_includes_research_thread_id(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
    db_vertical_client: VerticalClient,
    patched_memory_embeddings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """18.5-INT-005 - P1/AC3: MemoryExtractionService persists extracted facts with the linked ResearchThread."""
    from app.services.memory.extraction import MemoryExtractionService

    research_thread, chat_thread = await _make_research_chat_pair(
        db_session,
        db_workspace,
        db_user,
        db_vertical_client,
        title="Story 18.5 research thread",
    )

    turn_id = "chat:turn:18-5"
    assistant_message = await _add_turn_messages(
        db_session,
        db_user,
        chat_thread,
        "What did we learn about competitor X?",
        "Competitor X raised prices by 10% in Q2 2026.",
        turn_id,
    )

    fake_llm = _fake_extraction_llm(
        '[{"content":"Competitor X raised prices by 10% in Q2 2026.",'
        '"type":"semantic","tags":[],"confidence":0.95}]'
    )
    monkeypatch.setattr(
        "app.services.memory.extraction.get_agent_llm",
        AsyncMock(return_value=fake_llm),
    )

    service = MemoryExtractionService(
        session=db_session,
        client_id=db_vertical_client.client_id,
    )
    memories = await service.extract_from_turn(
        thread_id=chat_thread.id,
        turn_id=turn_id,
        assistant_message_id=assistant_message.id,
    )

    assert len(memories) == 1
    assert isinstance(memories[0], Memory)
    assert memories[0].research_thread_id == research_thread.id


async def test_celery_extraction_task_passes_research_thread_id(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
    db_vertical_client: VerticalClient,
    patched_memory_embeddings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """18.5-INT-006 - P1/AC3: the chat-turn Celery task passes the linked research_thread_id to the service."""
    from app.tasks.celery_tasks.memory_extraction_task import (
        _extract_memory_after_chat_turn,
    )

    research_thread, chat_thread = await _make_research_chat_pair(
        db_session,
        db_workspace,
        db_user,
        db_vertical_client,
        title="Celery research thread",
    )

    turn_id = "chat:turn:celery"
    assistant_message = await _add_turn_messages(
        db_session,
        db_user,
        chat_thread,
        "Track this competitor insight.",
        "Competitor Y launched a premium tier in March.",
        turn_id,
    )

    fake_llm = _fake_extraction_llm(
        '[{"content":"Competitor Y launched a premium tier in March.",'
        '"type":"semantic","tags":[],"confidence":0.95}]'
    )
    monkeypatch.setattr(
        "app.services.memory.extraction.get_agent_llm",
        AsyncMock(return_value=fake_llm),
    )

    class _FakeSessionMaker:
        async def __aenter__(self) -> AsyncSession:
            return db_session

        async def __aexit__(self, *_args: object, **_kwargs: object) -> None:
            pass

    monkeypatch.setattr(
        "app.tasks.celery_tasks.get_celery_session_maker",
        lambda: _FakeSessionMaker,
    )

    await _extract_memory_after_chat_turn(
        assistant_message.id,
        client_id=db_vertical_client.client_id,
        research_thread_id=research_thread.id,
    )

    result = await db_session.execute(
        select(Memory).where(
            Memory.source_id == assistant_message.id,
            Memory.research_thread_id == research_thread.id,
        )
    )
    memory = result.scalars().one_or_none()
    assert memory is not None
    assert memory.research_thread_id == research_thread.id
