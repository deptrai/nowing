"""Integration tests for the production chat query sampler."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.admin.chat_query_sampler import (
    _classify_tags,
    _extract_document_ids,
    _extract_text,
    _hash_workspace,
    redact_pii,
    sample_chat_queries,
)
from app.db import AgentActionLog, NewChatMessage, NewChatMessageRole, NewChatThread


@pytest.mark.asyncio
async def test_redact_pii_masks_common_patterns() -> None:
    text = (
        "Contact alice@example.com or +1 415-555-0123. "
        "SSN 123-45-6789 and card 4111-1111-1111-1111."
    )
    out = redact_pii(text)
    assert "<EMAIL>" in out
    assert "<PHONE>" in out
    assert "<SSN>" in out
    assert "<CC>" in out
    assert "alice@example.com" not in out
    assert "123-45-6789" not in out
    assert "4111-1111-1111-1111" not in out


@pytest.mark.asyncio
async def test_extract_text_handles_string_and_assistant_ui_content() -> None:
    assert _extract_text("plain string") == "plain string"
    assert (
        _extract_text(
            [{"type": "text", "text": "hello"}, {"type": "text", "text": "world"}]
        )
        == "hello world"
    )
    assert _extract_text(["a", "b"]) == "a b"
    assert _extract_text(None) == ""


@pytest.mark.asyncio
async def test_hash_workspace_is_stable_with_salt() -> None:
    a = _hash_workspace("Acme", "salt-1")
    b = _hash_workspace("Acme", "salt-1")
    c = _hash_workspace("Acme", "salt-2")
    d = _hash_workspace("Beta", "salt-1")
    assert a == b
    assert a.startswith("w-")
    assert a != c
    assert a != d


@pytest.mark.asyncio
async def test_classify_tags_from_query_and_tools() -> None:
    assert _classify_tags("What do we remember about this?", [], []) == ["memory"]
    assert _classify_tags("Draft a welcome email.", [], []) == ["creative"]
    assert _classify_tags("Find revenue numbers.", ["search_knowledge_base"], []) == [
        "document"
    ]
    assert _classify_tags(
        "Compare Apple and Samsung.",
        ["search_knowledge_base", "chainlens.research"],
        [],
    ) == ["document", "deep-research", "multi-tool"]
    assert _classify_tags("Hello", [], [42]) == ["document"]


@pytest.mark.asyncio
async def test_extract_document_ids_from_args() -> None:
    assert _extract_document_ids({"document_id": 7}) == [7]
    assert _extract_document_ids({"document_ids": [1, 2, 3]}) == [1, 2, 3]
    assert _extract_document_ids({"mentioned_document_ids": [4, 5]}) == [4, 5]
    assert _extract_document_ids(None) == []
    assert _extract_document_ids([1, 2, 3]) == []


@pytest.mark.asyncio
async def test_sample_chat_queries_anonymizes_and_tags(
    db_session, db_user, db_workspace
) -> None:
    """End-to-end sampler run against a seeded chat thread."""
    db_user.is_superuser = True

    workspace = db_workspace
    thread = NewChatThread(
        workspace_id=workspace.id,
        title="Test thread",
        created_by_id=db_user.id,
    )
    db_session.add(thread)
    await db_session.flush()

    user_msg = NewChatMessage(
        thread_id=thread.id,
        role=NewChatMessageRole.USER,
        content=[
            {
                "type": "text",
                "text": "What do we know about our competitor X? Their email is contact@x.com.",
            }
        ],
        turn_id="t1",
        author_id=db_user.id,
    )
    db_session.add(user_msg)
    await db_session.flush()

    # Tool call in the same turn triggers the document/deep-research/multi-tool tags.
    db_session.add(
        AgentActionLog(
            thread_id=thread.id,
            workspace_id=workspace.id,
            user_id=db_user.id,
            chat_turn_id="t1",
            tool_name="search_knowledge_base",
            args={"document_ids": [10, 11]},
        )
    )
    db_session.add(
        AgentActionLog(
            thread_id=thread.id,
            workspace_id=workspace.id,
            user_id=db_user.id,
            chat_turn_id="t1",
            tool_name="chainlens.research",
            args={},
        )
    )
    await db_session.flush()

    rows = await sample_chat_queries(
        db_session, days=30, max_queries=10, salt="salty", dry_run=False
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["case_id"] == f"prod-{user_msg.id}"
    assert "<EMAIL>" in row["query"]
    assert "contact@x.com" not in row["query"]
    assert "we" in row["query"].lower()
    assert "memory" in row["tags"]
    assert "document" in row["tags"]
    assert "deep-research" in row["tags"]
    assert "multi-tool" in row["tags"]
    assert row["mentioned_document_ids"] == [10, 11]
    assert row["disabled_tools"] == []
    assert row["workspace_id_hash"].startswith("w-")


@pytest.mark.asyncio
async def test_sample_chat_queries_dry_run_returns_empty_list(
    db_session, db_user, db_workspace
) -> None:
    thread = NewChatThread(workspace_id=db_workspace.id, title="Dry run thread")
    db_session.add(thread)
    await db_session.flush()

    db_session.add(
        NewChatMessage(
            thread_id=thread.id,
            role=NewChatMessageRole.USER,
            content=[{"type": "text", "text": "Tell me a fact."}],
            author_id=db_user.id,
        )
    )
    await db_session.flush()

    rows = await sample_chat_queries(
        db_session, days=30, max_queries=10, salt="salty", dry_run=True
    )
    assert rows == []


@pytest.mark.asyncio
async def test_sample_chat_queries_filters_by_days(
    db_session, db_user, db_workspace
) -> None:
    thread = NewChatThread(workspace_id=db_workspace.id, title="Old thread")
    db_session.add(thread)
    await db_session.flush()

    old_msg = NewChatMessage(
        thread_id=thread.id,
        role=NewChatMessageRole.USER,
        content=[{"type": "text", "text": "Old question."}],
        created_at=datetime.now(UTC) - timedelta(days=60),
        author_id=db_user.id,
    )
    db_session.add(old_msg)
    await db_session.flush()

    rows = await sample_chat_queries(db_session, days=30, max_queries=10, salt="salty")
    assert all(row["query"] != "Old question." for row in rows)
