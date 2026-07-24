"""ATDD acceptance tests for Story 6.5 — ``continue_research`` action (AC-3).

Red-phase: activated during ``dev-story`` (red -> green). The action reuses the
Story 4.6 recall + citation aggregation in-process (no HTTP, no divergent
ranking):

  AC-3  the action returns a JSON-serializable dict
        {research_thread_id, memories: [...], citations: [...]}, its memories
        equal ``MemoryHybridSearch`` scoped by research_thread_id, its citations
        equal ``collect_thread_citations``, and a non-existent thread fails the
        step with a clear error WITHOUT implicitly creating a thread.

Assumptions to reconcile during green (documented in the ATDD checklist):
  * ``get_action("continue_research")`` returns an ``ActionDefinition`` whose
    ``build_handler(ctx)`` yields ``handle(params: dict) -> dict``.
  * The handler is read-only w.r.t. the run; ``ActionContext.run_id`` may be a
    placeholder here.
  * The result's ``memories`` items are serialized hits carrying an ``id`` key
    (mirroring ``MemorySearchHit``).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

_EMBEDDING = [0.1] * 384


async def _make_research_thread(session, workspace, user, *, title="Q3 research"):
    """Create a ResearchThread + linked chat thread + assistant message carrying
    persisted [citation:...] markers, plus a thread-scoped memory (mirrors the
    Story 4.6 fixture)."""
    from app.db import (
        Memory,
        MemorySourceType,
        MemoryType,
        NewChatMessage,
        NewChatMessageRole,
        NewChatThread,
        ResearchThread,
    )

    thread = ResearchThread(
        workspace_id=workspace.id,
        created_by_id=user.id,
        title=title,
    )
    session.add(thread)
    await session.flush()

    chat = NewChatThread(
        title="Session 1",
        workspace_id=workspace.id,
        created_by_id=user.id,
        research_thread_id=thread.id,
    )
    session.add(chat)
    await session.flush()

    assistant_msg = NewChatMessage(
        thread_id=chat.id,
        role=NewChatMessageRole.ASSISTANT,
        content=[
            {
                "type": "text",
                "text": (
                    "Competitor X raised prices [citation:https://example.com/pricing] "
                    "and shipped a new tier [citation:https://example.com/tier]."
                ),
            }
        ],
        turn_id="chat:turn:1",
    )
    session.add(assistant_msg)

    memory = Memory(
        workspace_id=workspace.id,
        content="Competitor X raised prices by 10% in Q3.",
        embedding=_EMBEDDING,
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.CHAT_MESSAGE,
        source_id=assistant_msg.id,
        research_thread_id=thread.id,
        created_by_id=user.id,
    )
    session.add(memory)
    await session.flush()
    return thread


def _action_context(session, workspace, user):
    from app.automations.actions.types import ActionContext

    return ActionContext(
        session=session,
        run_id=0,
        step_id="continue",
        workspace_id=workspace.id,
        creator_user_id=user.id,
    )


async def test_continue_research_returns_thread_memories_and_citations(
    db_session, db_workspace, db_user
):
    """AC-3: the action returns {research_thread_id, memories, citations}."""
    from app.automations.actions.store import get_action

    thread = await _make_research_thread(db_session, db_workspace, db_user)

    definition = get_action("continue_research")
    assert definition is not None
    handler = definition.build_handler(
        _action_context(db_session, db_workspace, db_user)
    )

    result = await handler({"research_thread_id": thread.id, "top_k": 5})

    assert set(result.keys()) >= {"research_thread_id", "memories", "citations"}
    assert result["research_thread_id"] == thread.id
    assert len(result["memories"]) >= 1
    urls = {c.get("url") for c in result["citations"]}
    assert "https://example.com/pricing" in urls
    assert "https://example.com/tier" in urls


async def test_continue_research_recall_matches_hybrid_search(
    db_session, db_workspace, db_user
):
    """AC-3: the action's memories match ``MemoryHybridSearch`` scoped by the
    thread (no divergent ranking) — same members AND same order."""
    from app.automations.actions.store import get_action
    from app.services.memory.search import MemoryHybridSearch

    thread = await _make_research_thread(db_session, db_workspace, db_user)

    expected = await MemoryHybridSearch(db_session).search(
        workspace_id=db_workspace.id,
        query="",
        query_embedding=None,
        top_k=5,
        research_thread_id=thread.id,
    )

    handler = get_action("continue_research").build_handler(
        _action_context(db_session, db_workspace, db_user)
    )
    result = await handler({"research_thread_id": thread.id, "top_k": 5})

    assert [m["id"] for m in result["memories"]] == [m.id for m in expected]


async def test_continue_research_citations_match_thread_citations(
    db_session, db_workspace, db_user
):
    """AC-3: the action's citations match ``collect_thread_citations`` (the same
    aggregation the Story 4.6 route uses)."""
    from app.automations.actions.store import get_action
    from app.db import ResearchThread
    from app.services.memory.thread_citations import collect_thread_citations

    thread = await _make_research_thread(db_session, db_workspace, db_user)
    thread_obj = await db_session.get(ResearchThread, thread.id)
    expected = await collect_thread_citations(db_session, thread_obj)

    handler = get_action("continue_research").build_handler(
        _action_context(db_session, db_workspace, db_user)
    )
    result = await handler({"research_thread_id": thread.id})

    assert [c.get("url") for c in result["citations"]] == [c.url for c in expected]


async def test_continue_research_missing_thread_fails_without_creating(
    db_session, db_workspace, db_user
):
    """AC-3: a non-existent thread fails the step with a clear error and does NOT
    implicitly create a thread (consistent with Story 4.6 AC-2)."""
    from sqlalchemy import func, select

    from app.automations.actions.store import get_action
    from app.db import ResearchThread

    before = await db_session.scalar(
        select(func.count())
        .select_from(ResearchThread)
        .where(ResearchThread.workspace_id == db_workspace.id)
    )

    handler = get_action("continue_research").build_handler(
        _action_context(db_session, db_workspace, db_user)
    )

    raised = False
    try:
        await handler({"research_thread_id": 99999999})
    except Exception:
        raised = True
    assert raised, "a missing research thread must fail the step with a clear error"

    after = await db_session.scalar(
        select(func.count())
        .select_from(ResearchThread)
        .where(ResearchThread.workspace_id == db_workspace.id)
    )
    assert after == before  # no implicit creation


async def test_continue_research_other_workspace_thread_fails_without_creating(
    db_session, db_workspace, db_user
):
    """AC-3 (isolation): a thread that exists but belongs to ANOTHER workspace is
    unreachable — the step fails and creates nothing in the caller's workspace."""
    from sqlalchemy import func, select

    from app.automations.actions.store import get_action
    from app.db import ResearchThread, Workspace
    from app.routes.workspaces_routes import create_default_roles_and_membership

    workspace_b = Workspace(name="Workspace B", user_id=db_user.id)
    db_session.add(workspace_b)
    await db_session.flush()
    await create_default_roles_and_membership(db_session, workspace_b.id, db_user.id)
    await db_session.flush()

    other_thread = ResearchThread(
        workspace_id=workspace_b.id, created_by_id=db_user.id, title="B research"
    )
    db_session.add(other_thread)
    await db_session.flush()

    before = await db_session.scalar(
        select(func.count())
        .select_from(ResearchThread)
        .where(ResearchThread.workspace_id == db_workspace.id)
    )

    # The action context is scoped to workspace A (db_workspace).
    handler = get_action("continue_research").build_handler(
        _action_context(db_session, db_workspace, db_user)
    )

    raised = False
    try:
        await handler({"research_thread_id": other_thread.id})
    except Exception:
        raised = True
    assert raised, "a thread from another workspace must be unreachable"

    after = await db_session.scalar(
        select(func.count())
        .select_from(ResearchThread)
        .where(ResearchThread.workspace_id == db_workspace.id)
    )
    assert after == before  # no implicit creation in the caller's workspace


async def test_continue_research_empty_thread_returns_empty_lists(
    db_session, db_workspace, db_user
):
    """AC-3: a real thread with no memories and no cited chat history recalls
    cleanly — empty ``memories``/``citations`` rather than an error."""
    from app.automations.actions.store import get_action
    from app.db import ResearchThread

    thread = ResearchThread(
        workspace_id=db_workspace.id, created_by_id=db_user.id, title="Empty thread"
    )
    db_session.add(thread)
    await db_session.flush()

    handler = get_action("continue_research").build_handler(
        _action_context(db_session, db_workspace, db_user)
    )
    result = await handler({"research_thread_id": thread.id, "top_k": 5})

    assert result["research_thread_id"] == thread.id
    assert result["memories"] == []
    assert result["citations"] == []


async def test_continue_research_top_k_limits_recall(db_session, db_workspace, db_user):
    """AC-3: ``top_k`` bounds the recall — with 3 thread-scoped memories and
    ``top_k=2``, only 2 are returned (recall never exceeds the requested cap)."""
    from app.automations.actions.store import get_action
    from app.db import Memory, MemorySourceType, MemoryType, ResearchThread

    thread = ResearchThread(
        workspace_id=db_workspace.id, created_by_id=db_user.id, title="Busy thread"
    )
    db_session.add(thread)
    await db_session.flush()

    for i in range(3):
        db_session.add(
            Memory(
                workspace_id=db_workspace.id,
                content=f"Thread-scoped fact number {i}.",
                embedding=[0.1 * (i + 1)] * 384,
                type=MemoryType.SEMANTIC,
                source_type=MemorySourceType.MANUAL,
                research_thread_id=thread.id,
                created_by_id=db_user.id,
            )
        )
    await db_session.flush()

    handler = get_action("continue_research").build_handler(
        _action_context(db_session, db_workspace, db_user)
    )
    result = await handler({"research_thread_id": thread.id, "top_k": 2})

    assert len(result["memories"]) == 2
