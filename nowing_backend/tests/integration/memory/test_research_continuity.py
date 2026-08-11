"""ATDD acceptance tests for Story 4.6 — Research Continuity (FR-33).

Activated during ``dev-story`` (red -> green). These exercise the
research-thread context endpoint:
  GET /api/v1/workspaces/{workspace_id}/research-threads/{thread_id}/context
    -> 200 {thread_id, title, memories: [...], citations: [...]}
    -> 404 when the thread does not exist / belongs to another workspace

Existing (already built, do NOT re-test here): ResearchThread schema,
Memory.research_thread_id, thread-scoped memory recall via memories/search.
"""

from __future__ import annotations

import pytest

from tests.integration.conftest import _EMBEDDING_DIM

pytestmark = [pytest.mark.integration, pytest.mark.memory]

BASE = "/api/v1/workspaces"


async def _make_research_thread(
    db_session, workspace, user, *, title="Q3 competitor research"
):
    """Create a ResearchThread + a linked chat thread + an assistant message
    that carries persisted [citation:...] markers, plus a thread-scoped memory."""
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
    db_session.add(thread)
    await db_session.flush()

    chat = NewChatThread(
        title="Session 1",
        workspace_id=workspace.id,
        created_by_id=user.id,
        research_thread_id=thread.id,
    )
    db_session.add(chat)
    await db_session.flush()

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
    db_session.add(assistant_msg)

    memory = Memory(
        workspace_id=workspace.id,
        content="Competitor X raised prices by 10% in Q3.",
        embedding=[0.1] * _EMBEDDING_DIM,
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.CHAT_MESSAGE,
        source_id=assistant_msg.id,
        research_thread_id=thread.id,
        created_by_id=user.id,
    )
    db_session.add(memory)
    await db_session.flush()
    return thread


async def test_continue_context_returns_memories_and_citations(
    client, db_session, db_workspace, db_user
):
    """AC-1: context returns BOTH ranked memories and the thread's prior citations."""
    thread = await _make_research_thread(db_session, db_workspace, db_user)

    resp = await client.get(
        f"{BASE}/{db_workspace.id}/research-threads/{thread.id}/context"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["thread_id"] == thread.id
    # AC-1a: ranked related memories scoped to the thread
    assert len(body["memories"]) >= 1
    # AC-1b: previous citations of the thread (deduped)
    urls = {c.get("url") for c in body["citations"]}
    assert "https://example.com/pricing" in urls
    assert "https://example.com/tier" in urls


async def test_continue_context_missing_thread_returns_404_and_creates_nothing(
    client, db_session, db_workspace
):
    """AC-2: a non-existent thread_id fails clearly and does NOT create a thread implicitly."""
    from sqlalchemy import func, select

    from app.db import ResearchThread

    before = await db_session.execute(
        select(func.count())
        .select_from(ResearchThread)
        .where(ResearchThread.workspace_id == db_workspace.id)
    )
    resp = await client.get(
        f"{BASE}/{db_workspace.id}/research-threads/99999999/context"
    )
    assert resp.status_code == 404

    after = await db_session.execute(
        select(func.count())
        .select_from(ResearchThread)
        .where(ResearchThread.workspace_id == db_workspace.id)
    )
    assert after.scalar_one() == before.scalar_one()  # no implicit creation


async def test_context_denied_for_non_member(
    client_as_other, db_session, db_workspace, db_user
):
    """AC-4 / permission gate: a non-member of the workspace is denied (403)."""
    thread = await _make_research_thread(db_session, db_workspace, db_user)

    resp = await client_as_other.get(
        f"{BASE}/{db_workspace.id}/research-threads/{thread.id}/context"
    )
    assert resp.status_code == 403


async def test_context_thread_scoped_to_workspace_returns_404(
    client, db_session, db_workspace, db_user
):
    """AC-4 isolation: a thread in workspace A is NOT reachable via workspace B's
    URL, even for a member of B — the route loads by (thread_id, workspace_id)."""
    from app.db import Workspace
    from app.routes.workspaces_routes import create_default_roles_and_membership

    # db_workspace = workspace A (owner is a member). Create workspace B (owner too).
    workspace_b = Workspace(name="Workspace B", user_id=db_user.id)
    db_session.add(workspace_b)
    await db_session.flush()
    await create_default_roles_and_membership(db_session, workspace_b.id, db_user.id)
    await db_session.flush()

    thread_in_a = await _make_research_thread(db_session, db_workspace, db_user)

    # Caller is a member of B, so permission passes; the thread lives in A, so the
    # workspace-scoped lookup must 404 (no cross-workspace leak, no existence probe).
    resp = await client.get(
        f"{BASE}/{workspace_b.id}/research-threads/{thread_in_a.id}/context"
    )
    assert resp.status_code == 404


async def test_continue_context_dedupes_and_skips_malformed_citations(
    client, db_session, db_workspace, db_user
):
    """AC-4: duplicate citations are deduped and malformed markers are skipped (no raise)."""
    from app.db import (
        NewChatMessage,
        NewChatMessageRole,
        NewChatThread,
        ResearchThread,
    )

    thread = ResearchThread(
        workspace_id=db_workspace.id, created_by_id=db_user.id, title="dupe"
    )
    db_session.add(thread)
    await db_session.flush()
    chat = NewChatThread(
        title="s",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
        research_thread_id=thread.id,
    )
    db_session.add(chat)
    await db_session.flush()
    db_session.add(
        NewChatMessage(
            thread_id=chat.id,
            role=NewChatMessageRole.ASSISTANT,
            content=[
                {
                    "type": "text",
                    "text": (
                        "A [citation:https://example.com/dup] then again "
                        "[citation:https://example.com/dup] and a broken [citation: "
                        "marker that never closes."
                    ),
                }
            ],
            turn_id="t1",
        )
    )
    await db_session.flush()

    resp = await client.get(
        f"{BASE}/{db_workspace.id}/research-threads/{thread.id}/context"
    )
    assert resp.status_code == 200
    citations = resp.json()["citations"]
    dup_urls = [c for c in citations if c.get("url") == "https://example.com/dup"]
    assert len(dup_urls) == 1  # deduped, and the malformed marker did not crash


async def test_continue_context_recall_matches_recall_definition(
    client, db_session, db_workspace, db_user
):
    """AC-3: memories in continue match the same hybrid recall (scoped by research_thread_id)."""
    thread = await _make_research_thread(db_session, db_workspace, db_user)

    context_resp = await client.get(
        f"{BASE}/{db_workspace.id}/research-threads/{thread.id}/context"
    )
    recall_resp = await client.post(
        f"{BASE}/{db_workspace.id}/memories/search",
        json={"query": "", "top_k": 5, "research_thread_id": thread.id},
    )
    assert context_resp.status_code == 200
    assert recall_resp.status_code == 200
    ctx_ids = [m["id"] for m in context_resp.json()["memories"]]
    recall_ids = [m["id"] for m in recall_resp.json()["items"]]
    assert ctx_ids == recall_ids  # same members AND same ranking order (no divergence)


async def test_continue_context_citations_do_not_leak_across_threads(
    client, db_session, db_workspace, db_user
):
    """AC-4: only the target thread's citations are returned; a sibling thread's
    citations in the SAME workspace must not appear (thread scoping)."""
    from app.db import (
        NewChatMessage,
        NewChatMessageRole,
        NewChatThread,
        ResearchThread,
    )

    target = await _make_research_thread(
        db_session, db_workspace, db_user, title="target"
    )

    sibling = ResearchThread(
        workspace_id=db_workspace.id, created_by_id=db_user.id, title="sibling"
    )
    db_session.add(sibling)
    await db_session.flush()
    sibling_chat = NewChatThread(
        title="s",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
        research_thread_id=sibling.id,
    )
    db_session.add(sibling_chat)
    await db_session.flush()
    db_session.add(
        NewChatMessage(
            thread_id=sibling_chat.id,
            role=NewChatMessageRole.ASSISTANT,
            content=[
                {
                    "type": "text",
                    "text": "Sibling [citation:https://example.com/SIBLING-ONLY].",
                }
            ],
            turn_id="t1",
        )
    )
    await db_session.flush()

    resp = await client.get(
        f"{BASE}/{db_workspace.id}/research-threads/{target.id}/context"
    )
    assert resp.status_code == 200
    urls = {c.get("url") for c in resp.json()["citations"]}
    assert "https://example.com/pricing" in urls  # target's own citation present
    assert "https://example.com/SIBLING-ONLY" not in urls  # no cross-thread leak


async def test_continue_context_includes_chunk_citations_without_url(
    client, db_session, db_workspace, db_user
):
    """AC-1b: knowledge-base chunk/document citations are returned with a label and url=None."""
    from app.db import (
        NewChatMessage,
        NewChatMessageRole,
        NewChatThread,
        ResearchThread,
    )

    thread = ResearchThread(
        workspace_id=db_workspace.id, created_by_id=db_user.id, title="kb"
    )
    db_session.add(thread)
    await db_session.flush()
    chat = NewChatThread(
        title="s",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
        research_thread_id=thread.id,
    )
    db_session.add(chat)
    await db_session.flush()
    db_session.add(
        NewChatMessage(
            thread_id=chat.id,
            role=NewChatMessageRole.ASSISTANT,
            content=[
                {"type": "text", "text": "See [citation:42] and [citation:doc-7]."}
            ],
            turn_id="t1",
        )
    )
    await db_session.flush()

    resp = await client.get(
        f"{BASE}/{db_workspace.id}/research-threads/{thread.id}/context"
    )
    assert resp.status_code == 200
    citations = resp.json()["citations"]
    assert any(c["url"] is None and c["source_type"] == "kb_chunk" for c in citations)
    assert any(
        c["url"] is None and c["source_type"] == "kb_document" for c in citations
    )
