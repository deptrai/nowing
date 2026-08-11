"""Unit tests for ``finalize_assistant_message``.

Coverage focuses on Story 18.5: the ``research_thread_id`` is forwarded to the
Celery memory-extraction task and the workspace toggle / gate fast-path is
respected.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.tasks.chat.streaming.flows.shared.assistant_finalize import (
    finalize_assistant_message,
)
from app.tasks.chat.streaming.shared.stream_result import StreamResult

pytestmark = pytest.mark.unit


def _make_stream_result(**overrides) -> StreamResult:
    defaults = {
        "turn_id": "turn-1",
        "assistant_message_id": 42,
        "accumulated_text": "hello",
    }
    defaults.update(overrides)
    return StreamResult(**defaults)


@pytest.fixture
def finalize_deps(monkeypatch):
    """Patch the external seams of ``finalize_assistant_message`` for unit testing."""
    # Story 18.5: memory extraction is enabled by default for these tests.
    monkeypatch.setattr("app.config.config.MEMORY_AUTO_EXTRACT_ENABLED", True)

    workspace = MagicMock()
    workspace.memory_auto_extract_enabled = True

    session = AsyncMock()
    session.get = AsyncMock(return_value=workspace)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr("app.db.shielded_async_session", lambda: cm)
    monkeypatch.setattr("app.db.Workspace", MagicMock)

    gate = AsyncMock(return_value=MagicMock(allowed=True))
    monkeypatch.setattr(
        "app.services.memory.extract_budget.check_workspace_gates", gate
    )

    extract_task = MagicMock()
    extract_task.delay = MagicMock()
    monkeypatch.setattr(
        "app.tasks.celery_tasks.memory_extraction_task.extract_memory_after_chat_turn",
        extract_task,
    )

    turn = AsyncMock()
    monkeypatch.setattr("app.tasks.chat.persistence.finalize_assistant_turn", turn)
    monkeypatch.setattr(
        "app.tasks.chat.message_parts_normalizer.merge_streamed_and_final_parts",
        lambda content, final_parts: content,
    )

    return {
        "workspace": workspace,
        "session": session,
        "cm": cm,
        "check_workspace_gates": gate,
        "extract_task": extract_task,
        "finalize_assistant_turn": turn,
    }


@pytest.mark.anyio
async def test_finalize_enqueues_memory_extraction_with_research_thread_id(
    finalize_deps,
):
    """18.5-UNIT-010 - P1/AC7: research_thread_id reaches the Celery enqueue."""
    stream_result = _make_stream_result()

    await finalize_assistant_message(
        stream_result=stream_result,
        chat_id=1,
        workspace_id=2,
        user_id="u",
        accumulator=MagicMock(),
        log_prefix="test",
        client_id="client-a",
        research_thread_id=123,
    )

    finalize_deps["extract_task"].delay.assert_called_once_with(
        42,
        client_id="client-a",
        research_thread_id=123,
    )


@pytest.mark.anyio
async def test_finalize_skips_extraction_when_disabled(finalize_deps, monkeypatch):
    """Memory extraction is skipped when the workspace toggle is off."""
    monkeypatch.setattr("app.config.config.MEMORY_AUTO_EXTRACT_ENABLED", False)
    stream_result = _make_stream_result()

    await finalize_assistant_message(
        stream_result=stream_result,
        chat_id=1,
        workspace_id=2,
        user_id="u",
        accumulator=MagicMock(),
        log_prefix="test",
        client_id="client-a",
        research_thread_id=123,
    )

    finalize_deps["extract_task"].delay.assert_not_called()


@pytest.mark.anyio
async def test_finalize_skips_extraction_when_workspace_not_found(finalize_deps):
    """A missing workspace stops enqueue before any Celery call."""
    finalize_deps["session"].get.return_value = None
    stream_result = _make_stream_result()

    await finalize_assistant_message(
        stream_result=stream_result,
        chat_id=1,
        workspace_id=2,
        user_id="u",
        accumulator=MagicMock(),
        log_prefix="test",
        client_id="client-a",
        research_thread_id=123,
    )

    finalize_deps["extract_task"].delay.assert_not_called()


@pytest.mark.anyio
async def test_finalize_enqueues_despite_pre_check_exception(finalize_deps):
    """Fast-path failures are swallowed and extraction is still enqueued."""
    finalize_deps["session"].get.side_effect = ValueError("db boom")
    stream_result = _make_stream_result()

    await finalize_assistant_message(
        stream_result=stream_result,
        chat_id=1,
        workspace_id=2,
        user_id="u",
        accumulator=MagicMock(),
        log_prefix="test",
        client_id="client-a",
        research_thread_id=123,
    )

    finalize_deps["extract_task"].delay.assert_called_once_with(
        42,
        client_id="client-a",
        research_thread_id=123,
    )


@pytest.mark.anyio
async def test_finalize_continues_when_enqueue_raises(finalize_deps):
    """Celery enqueue errors are logged but never propagated."""
    finalize_deps["extract_task"].delay.side_effect = ValueError("celery boom")
    stream_result = _make_stream_result()

    await finalize_assistant_message(
        stream_result=stream_result,
        chat_id=1,
        workspace_id=2,
        user_id="u",
        accumulator=MagicMock(),
        log_prefix="test",
        client_id="client-a",
        research_thread_id=123,
    )

    finalize_deps["extract_task"].delay.assert_called_once_with(
        42,
        client_id="client-a",
        research_thread_id=123,
    )


@pytest.mark.anyio
async def test_finalize_returns_early_without_message_id(finalize_deps):
    stream_result = _make_stream_result(assistant_message_id=None)

    await finalize_assistant_message(
        stream_result=stream_result,
        chat_id=1,
        workspace_id=2,
        user_id="u",
        accumulator=MagicMock(),
        log_prefix="test",
        client_id="client-a",
        research_thread_id=123,
    )

    finalize_deps["finalize_assistant_turn"].assert_not_called()
    finalize_deps["extract_task"].delay.assert_not_called()


@pytest.mark.anyio
async def test_finalize_returns_early_without_turn_id(finalize_deps):
    stream_result = _make_stream_result(turn_id="")

    await finalize_assistant_message(
        stream_result=stream_result,
        chat_id=1,
        workspace_id=2,
        user_id="u",
        accumulator=MagicMock(),
        log_prefix="test",
        client_id="client-a",
        research_thread_id=123,
    )

    finalize_deps["finalize_assistant_turn"].assert_not_called()
    finalize_deps["extract_task"].delay.assert_not_called()
