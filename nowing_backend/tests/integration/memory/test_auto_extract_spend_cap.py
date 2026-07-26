"""Red-phase integration scaffolds for auto-extract cost controls (Story 8.7).

Exercises ``MemoryExtractionService.extract_from_turn`` (and the enqueue-side
short-circuit in ``finalize_assistant_message``) end-to-end against the memory
subsystem, asserting that the NEW spend/budget cap, wallet pre-check, time
rate-limit, and anonymous-skip behaviours gate extraction BEFORE any LLM call.

Every test is ``@pytest.mark.skip`` (TDD red phase) so the suite collects
cleanly; a developer removes the skip on the task they activate, and the test
then FAILS until the gate (``app.services.memory.extract_budget`` +
its wiring into ``extraction.py`` / ``assistant_finalize.py``) is implemented.

Reuses the shared memory fixtures (``db_session``, ``db_workspace``, ``db_user``)
from ``tests/integration/conftest.py`` and the local ``chat_turn`` /
``patched_embeddings`` helpers below. Does NOT modify any shared conftest.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.integration, pytest.mark.memory]

_HIGH_CONFIDENCE_FACT = (
    '[{"content":"Competitor X raised prices by 10% in Q2 2026.",'
    '"type":"semantic","tags":["competitor","pricing"],"confidence":0.95}]'
)


@pytest_asyncio.fixture
async def chat_turn(db_session, db_workspace, db_user):
    """A user+assistant message pair sharing one ``turn_id`` (owner-authored)."""
    from app.db import NewChatMessage, NewChatMessageRole, NewChatThread

    thread = NewChatThread(
        title="Spend-Cap Test",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
    )
    db_session.add(thread)
    await db_session.flush()

    turn_id = "chat:turn:8-7"
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
        content=[{"type": "text", "text": "Yes, competitor X raised prices 10% in Q2 2026."}],
        turn_id=turn_id,
    )
    db_session.add(user_message)
    db_session.add(assistant_message)
    await db_session.flush()
    return thread, user_message, assistant_message


@pytest_asyncio.fixture
async def anon_chat_turn(db_session, db_workspace):
    """A turn whose user message has NO author (anonymous / no billable owner)."""
    from app.db import NewChatMessage, NewChatMessageRole, NewChatThread

    thread = NewChatThread(title="Anon Turn", workspace_id=db_workspace.id)
    db_session.add(thread)
    await db_session.flush()

    turn_id = "chat:turn:8-7-anon"
    user_message = NewChatMessage(
        thread_id=thread.id,
        role=NewChatMessageRole.USER,
        content=[{"type": "text", "text": "Remember I like dark mode."}],
        turn_id=turn_id,
        author_id=None,
    )
    assistant_message = NewChatMessage(
        thread_id=thread.id,
        role=NewChatMessageRole.ASSISTANT,
        content=[{"type": "text", "text": "Noted — you prefer dark mode."}],
        turn_id=turn_id,
    )
    db_session.add(user_message)
    db_session.add(assistant_message)
    await db_session.flush()
    return thread, user_message, assistant_message


@pytest.fixture
def patched_embeddings(monkeypatch):
    """Deterministic embeddings so persistence works without a real model."""

    def _fake_embed_texts(texts):
        return [[0.1] * 384 for _ in texts]

    monkeypatch.setattr(
        "app.services.memory.repository.embed_texts", _fake_embed_texts
    )
    return _fake_embed_texts


@pytest.fixture
def fake_llm(monkeypatch):
    """Patch ``get_agent_llm`` to return an AsyncMock; used to assert (non-)calls."""
    llm = AsyncMock()
    llm.ainvoke.return_value = type("FakeMsg", (), {"content": _HIGH_CONFIDENCE_FACT})()
    monkeypatch.setattr(
        "app.services.memory.extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    )
    return llm


async def _memory_create_usage_count(db_session, thread_id) -> int:
    from sqlalchemy import func, select

    from app.db import TokenUsage

    result = await db_session.execute(
        select(func.count())
        .select_from(TokenUsage)
        .where(
            TokenUsage.thread_id == thread_id,
            TokenUsage.usage_type == "memory_create",
        )
    )
    return int(result.scalar_one())


async def _memory_count_for_message(db_session, message_id) -> int:
    from sqlalchemy import func, select

    from app.db import Memory

    result = await db_session.execute(
        select(func.count()).select_from(Memory).where(Memory.source_id == message_id)
    )
    return int(result.scalar_one())


# ---------------------------------------------------------------------------
# AC1 — Wallet pre-check BEFORE the extraction LLM call
# ---------------------------------------------------------------------------


async def test_extract_skips_before_llm_when_wallet_insufficient(
    db_session, db_workspace, db_user, chat_turn, patched_embeddings, fake_llm
):
    """P0/AC1: owner balance 0 -> no LLM call, no memories, no memory_create usage."""
    from app.services.memory.extraction import MemoryExtractionService

    db_user.credit_micros_balance = 0
    db_user.credit_micros_reserved = 0
    await db_session.flush()

    thread, _user, assistant = chat_turn
    service = MemoryExtractionService(
        session=db_session, workspace_id=db_workspace.id, user_id=db_user.id
    )
    memories = await service.extract_from_turn(thread.id, assistant.turn_id, assistant.id)

    assert memories == []
    fake_llm.ainvoke.assert_not_awaited()
    assert await _memory_count_for_message(db_session, assistant.id) == 0
    assert await _memory_create_usage_count(db_session, thread.id) == 0


async def test_extract_proceeds_when_wallet_funded(
    db_session, db_workspace, db_user, chat_turn, patched_embeddings, fake_llm
):
    """P0/AC1: sufficient balance -> LLM called, qualifying fact persisted."""
    from app.services.memory.extraction import MemoryExtractionService

    db_user.credit_micros_balance = 5_000_000
    db_user.credit_micros_reserved = 0
    await db_session.flush()

    thread, _user, assistant = chat_turn
    service = MemoryExtractionService(
        session=db_session, workspace_id=db_workspace.id, user_id=db_user.id
    )
    memories = await service.extract_from_turn(thread.id, assistant.turn_id, assistant.id)

    assert len(memories) == 1
    fake_llm.ainvoke.assert_awaited_once()
    assert await _memory_create_usage_count(db_session, thread.id) == 1


# ---------------------------------------------------------------------------
# AC2 — Per-workspace spend/budget cap over a rolling period
# ---------------------------------------------------------------------------


async def test_extract_skips_when_workspace_over_budget(
    db_session, db_workspace, db_user, chat_turn, patched_embeddings, fake_llm, monkeypatch
):
    """P0/AC2: prior memory_create spend >= cap -> skip, no new spend."""
    from app.config import config
    from app.db import TokenUsage
    from app.services.memory.extraction import MemoryExtractionService

    db_user.credit_micros_balance = 5_000_000
    await db_session.flush()
    monkeypatch.setattr(config, "MEMORY_AUTO_EXTRACT_BUDGET_MICROS", 10_000, raising=False)

    # Seed prior in-period spend that meets the cap.
    db_session.add(
        TokenUsage(
            usage_type="memory_create",
            workspace_id=db_workspace.id,
            user_id=db_user.id,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_micros=10_000,
        )
    )
    await db_session.flush()

    thread, _user, assistant = chat_turn
    service = MemoryExtractionService(
        session=db_session, workspace_id=db_workspace.id, user_id=db_user.id
    )
    memories = await service.extract_from_turn(thread.id, assistant.turn_id, assistant.id)

    assert memories == []
    fake_llm.ainvoke.assert_not_awaited()
    assert await _memory_count_for_message(db_session, assistant.id) == 0


async def test_extract_unchanged_when_budget_default(
    db_session, db_workspace, db_user, chat_turn, patched_embeddings, fake_llm, monkeypatch
):
    """P1/AC2+AC6: budget unset/0 -> no budget gating (baseline behaviour)."""
    from app.config import config
    from app.services.memory.extraction import MemoryExtractionService

    db_user.credit_micros_balance = 5_000_000
    await db_session.flush()
    monkeypatch.setattr(config, "MEMORY_AUTO_EXTRACT_BUDGET_MICROS", 0, raising=False)

    thread, _user, assistant = chat_turn
    service = MemoryExtractionService(
        session=db_session, workspace_id=db_workspace.id, user_id=db_user.id
    )
    memories = await service.extract_from_turn(thread.id, assistant.turn_id, assistant.id)

    assert len(memories) == 1
    fake_llm.ainvoke.assert_awaited_once()


# ---------------------------------------------------------------------------
# AC3 — Time-based rate-limit
# ---------------------------------------------------------------------------


async def test_extract_skips_when_rate_limited(
    db_session, db_workspace, db_user, chat_turn, patched_embeddings, fake_llm, monkeypatch
):
    """P1/AC3: window count at the rate max -> skip."""
    import app.services.memory.extract_budget as gate
    from app.config import config
    from app.services.memory.extraction import MemoryExtractionService

    db_user.credit_micros_balance = 5_000_000
    await db_session.flush()
    monkeypatch.setattr(config, "MEMORY_AUTO_EXTRACT_RATE_MAX", 3, raising=False)

    async def _at_limit(_workspace_id):
        return 3

    monkeypatch.setattr(gate, "_rate_count", _at_limit, raising=False)

    thread, _user, assistant = chat_turn
    service = MemoryExtractionService(
        session=db_session, workspace_id=db_workspace.id, user_id=db_user.id
    )
    memories = await service.extract_from_turn(thread.id, assistant.turn_id, assistant.id)

    assert memories == []
    fake_llm.ainvoke.assert_not_awaited()


# ---------------------------------------------------------------------------
# AC4 — Anonymous-chat attribution edge (FR-17)
# ---------------------------------------------------------------------------


async def test_extract_skips_anonymous_turn(
    db_session, db_workspace, anon_chat_turn, patched_embeddings, fake_llm
):
    """P0/AC4: no billable owner on the turn -> skip, no LLM, no usage."""
    from app.services.memory.extraction import MemoryExtractionService

    thread, _user, assistant = anon_chat_turn
    service = MemoryExtractionService(session=db_session, workspace_id=db_workspace.id)
    memories = await service.extract_from_turn(thread.id, assistant.turn_id, assistant.id)

    assert memories == []
    fake_llm.ainvoke.assert_not_awaited()
    assert await _memory_create_usage_count(db_session, thread.id) == 0


# ---------------------------------------------------------------------------
# AC5 — Kill-switch / flags remain authoritative (regression, Dep 8.4a)
# ---------------------------------------------------------------------------


async def test_global_kill_switch_off_skips_without_llm(
    db_session, db_workspace, db_user, chat_turn, patched_embeddings, fake_llm, monkeypatch
):
    """P0/AC5: MEMORY_AUTO_EXTRACT_ENABLED=False -> [] and no LLM call."""
    from app.config import config
    from app.services.memory.extraction import MemoryExtractionService

    monkeypatch.setattr(config, "MEMORY_AUTO_EXTRACT_ENABLED", False, raising=False)

    thread, _user, assistant = chat_turn
    service = MemoryExtractionService(
        session=db_session, workspace_id=db_workspace.id, user_id=db_user.id
    )
    memories = await service.extract_from_turn(thread.id, assistant.turn_id, assistant.id)

    assert memories == []
    fake_llm.ainvoke.assert_not_awaited()


async def test_workspace_flag_off_skips_without_llm(
    db_session, db_workspace, db_user, chat_turn, patched_embeddings, fake_llm
):
    """P0/AC5: workspace.memory_auto_extract_enabled=False -> [] and no LLM call."""
    from app.services.memory.extraction import MemoryExtractionService

    db_workspace.memory_auto_extract_enabled = False
    await db_session.flush()

    thread, _user, assistant = chat_turn
    service = MemoryExtractionService(
        session=db_session, workspace_id=db_workspace.id, user_id=db_user.id
    )
    memories = await service.extract_from_turn(thread.id, assistant.turn_id, assistant.id)

    assert memories == []
    fake_llm.ainvoke.assert_not_awaited()


# ---------------------------------------------------------------------------
# AC7 — Enqueue-side short-circuit (defense in depth)
# ---------------------------------------------------------------------------


@pytest.fixture
def _finalize_deps(monkeypatch, db_session):
    """Wire finalize_assistant_message's real DB lookups onto the test session.

    ``shielded_async_session`` normally opens a brand-new engine connection,
    which would not see the (uncommitted, savepoint-scoped) db_workspace /
    db_user rows this test seeds. Patching it to hand back the test's own
    ``db_session`` keeps the gate's queries inside the same transaction that
    gets rolled back at teardown, while still exercising the REAL
    ``finalize_assistant_message`` control flow (no mocking of the gate or
    the enqueue check itself).

    Also stubs ``finalize_assistant_turn`` (the DB write for the assistant
    message content, covered by its own tests elsewhere) so this test can
    call ``finalize_assistant_message`` without pre-creating a full
    streaming payload.
    """
    from contextlib import asynccontextmanager

    import app.db as db_module

    @asynccontextmanager
    async def _fake_shielded_session():
        yield db_session

    monkeypatch.setattr(db_module, "shielded_async_session", _fake_shielded_session)

    finalize_turn = AsyncMock()
    monkeypatch.setattr(
        "app.tasks.chat.persistence.finalize_assistant_turn", finalize_turn
    )
    return finalize_turn


def _make_stream_result(assistant_message_id: int, turn_id: str):
    from app.tasks.chat.streaming.shared.stream_result import StreamResult

    return StreamResult(
        turn_id=turn_id,
        assistant_message_id=assistant_message_id,
        accumulated_text="ok",
    )


async def test_finalize_skips_enqueue_when_gate_blocks(
    db_session, db_workspace, db_user, chat_turn, _finalize_deps, monkeypatch
):
    """P1/AC7: insufficient wallet -> finalize_assistant_message does NOT
    enqueue the Celery extraction task (real gate, real DB, no mocking of
    check_extract_allowed itself)."""
    from app.services.token_tracking_service import TurnTokenAccumulator
    from app.tasks.chat.streaming.flows.shared.assistant_finalize import (
        finalize_assistant_message,
    )

    db_user.credit_micros_balance = 0
    db_user.credit_micros_reserved = 0
    await db_session.flush()

    thread, _user, assistant = chat_turn
    # ``.delay(...)`` is a synchronous Celery call (never awaited by the
    # production code), so a plain MagicMock — not AsyncMock — matches how
    # it is actually invoked.
    delay = MagicMock()
    monkeypatch.setattr(
        "app.tasks.celery_tasks.memory_extraction_task.extract_memory_after_chat_turn.delay",
        delay,
        raising=False,
    )

    await finalize_assistant_message(
        stream_result=_make_stream_result(assistant.id, assistant.turn_id),
        chat_id=thread.id,
        workspace_id=db_workspace.id,
        user_id=str(db_user.id),
        accumulator=TurnTokenAccumulator(),
        log_prefix="test",
    )

    delay.assert_not_called()


async def test_finalize_enqueues_when_gate_allows(
    db_session, db_workspace, db_user, chat_turn, _finalize_deps, monkeypatch
):
    """P2/AC7: funded wallet, no caps -> the Celery task IS enqueued exactly
    once (real gate allows; only the Celery boundary itself is mocked)."""
    from app.services.token_tracking_service import TurnTokenAccumulator
    from app.tasks.chat.streaming.flows.shared.assistant_finalize import (
        finalize_assistant_message,
    )

    db_user.credit_micros_balance = 5_000_000
    db_user.credit_micros_reserved = 0
    await db_session.flush()

    thread, _user, assistant = chat_turn
    delay = MagicMock()
    monkeypatch.setattr(
        "app.tasks.celery_tasks.memory_extraction_task.extract_memory_after_chat_turn.delay",
        delay,
        raising=False,
    )

    await finalize_assistant_message(
        stream_result=_make_stream_result(assistant.id, assistant.turn_id),
        chat_id=thread.id,
        workspace_id=db_workspace.id,
        user_id=str(db_user.id),
        accumulator=TurnTokenAccumulator(),
        log_prefix="test",
    )

    delay.assert_called_once_with(assistant.id)


# ---------------------------------------------------------------------------
# AC8 — Observability of skips
# ---------------------------------------------------------------------------


async def test_skip_emits_structured_log_and_no_usage(
    db_session, db_workspace, db_user, chat_turn, patched_embeddings, fake_llm, caplog
):
    """P1/AC8: insufficient-wallet skip logs reason + workspace_id, no usage row."""
    import logging

    from app.services.memory.extraction import MemoryExtractionService

    db_user.credit_micros_balance = 0
    await db_session.flush()

    thread, _user, assistant = chat_turn
    service = MemoryExtractionService(
        session=db_session, workspace_id=db_workspace.id, user_id=db_user.id
    )
    with caplog.at_level(logging.INFO):
        memories = await service.extract_from_turn(thread.id, assistant.turn_id, assistant.id)

    assert memories == []
    assert any("insufficient_wallet" in record.getMessage() for record in caplog.records)
    assert await _memory_create_usage_count(db_session, thread.id) == 0
