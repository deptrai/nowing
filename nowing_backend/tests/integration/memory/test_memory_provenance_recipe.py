"""Memory provenance recipe tests (Story 9.6a, AD-11.1).

* Run-derived memory carries ``source_capability`` + ``source_input``.
* Chat/manual memory has ``None`` for both.
* Recipe is an immutable snapshot: a duplicate overwrite never mutates an
  existing recipe (re-validation creates a new memory or version instead).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import text

pytestmark = [pytest.mark.integration, pytest.mark.memory]

_EMBEDDING_DIM = 384


@pytest_asyncio.fixture
async def scraper_run(db_session, db_workspace, db_user):
    """A successful run with a recipe-bearing input."""
    from app.db import Run

    run = Run(
        id=uuid.uuid4(),
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        thread_id="2099::task:call_x",
        capability="reddit.scrape",
        origin="api",
        status="success",
        input={"subreddit": "r/nowing", "query": "pricing"},
        output_text='{"title": "Widget price", "price": "19.99 USD"}',
        item_count=1,
        char_count=64,
    )
    db_session.add(run)
    await db_session.commit()
    return run


@pytest.mark.asyncio
async def test_run_extraction_copies_recipe_to_memory(
    db_session, db_workspace, db_user, scraper_run, patched_embed_texts
):
    """Run-derived memory copies capability and input from the run."""
    from app.db import MemorySourceType
    from app.services.memory.run_extraction import RunMemoryExtractionService

    facts_json = (
        '[{"content": "Widget costs 19.99 USD", '
        '"type": "semantic", "tags": ["pricing"], "confidence": 0.9}]'
    )
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=type("R", (), {"content": facts_json})())

    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ):
        service = RunMemoryExtractionService(session=db_session)
        created = await service.extract_from_run(scraper_run.id)

    assert len(created) == 1
    memory = created[0]
    assert memory.source_type == MemorySourceType.SCRAPER_RUN
    assert memory.source_run_id == scraper_run.id
    assert memory.source_capability == "reddit.scrape"
    assert memory.source_input == {"subreddit": "r/nowing", "query": "pricing"}

    assert (
        await db_session.execute(
            text("SELECT source_capability FROM memories WHERE id = :id"),
            {"id": memory.id},
        )
    ).scalar_one() == "reddit.scrape"


@pytest.mark.asyncio
async def test_chat_memory_has_no_recipe(db_session, db_workspace, db_user):
    """Chat-extracted memory has no source recipe."""
    from app.db import MemorySourceType
    from app.services.memory.repository import MemoryRepository

    repo = MemoryRepository(db_session)
    memory = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="User prefers dark mode.",
        source_type=MemorySourceType.CHAT_MESSAGE,
        source_id=4242,
        created_by_id=db_user.id,
        embedding=[0.1] * _EMBEDDING_DIM,
    )

    assert memory.source_type == MemorySourceType.CHAT_MESSAGE
    assert memory.source_id == 4242
    assert memory.source_run_id is None
    assert memory.source_capability is None
    assert memory.source_input is None


@pytest.mark.asyncio
async def test_create_memory_dedup_preserves_existing_recipe(
    db_session, db_workspace, db_user, scraper_run
):
    """A duplicate run fact never mutates the original recipe."""
    from app.db import MemorySourceType
    from app.services.memory.repository import MemoryRepository

    repo = MemoryRepository(db_session)
    original = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Widget costs 19.99 USD",
        source_type=MemorySourceType.SCRAPER_RUN,
        source_run_id=scraper_run.id,
        source_capability=scraper_run.capability,
        source_input=scraper_run.input,
        created_by_id=db_user.id,
        embedding=[0.1] * _EMBEDDING_DIM,
    )

    # Second run with same fact but different recipe; dedup should preserve the
    # original recipe (immutable snapshot) while allowing source_run_id to refresh.
    another_run_id = uuid.uuid4()
    duplicate = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Widget costs 19.99 USD",
        source_type=MemorySourceType.SCRAPER_RUN,
        source_run_id=another_run_id,
        source_capability="different.scrape",
        source_input={"different": True},
        created_by_id=db_user.id,
        embedding=[0.1] * _EMBEDDING_DIM,
        update_on_duplicate=True,
    )

    assert duplicate.id == original.id
    assert duplicate.source_run_id == another_run_id
    assert duplicate.source_capability == scraper_run.capability
    assert duplicate.source_input == scraper_run.input


@pytest.mark.asyncio
async def test_create_memory_exact_match_sets_recipe_when_missing(
    db_session, db_workspace, db_user
):
    """Exact-content match (update_on_duplicate=False) seeds recipe when absent."""
    from app.db import MemorySourceType
    from app.services.memory.repository import MemoryRepository

    repo = MemoryRepository(db_session)
    original = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Widget costs 19.99 USD",
        source_type=MemorySourceType.MANUAL,
        created_by_id=db_user.id,
        embedding=[0.2] * _EMBEDDING_DIM,
    )
    assert original.source_capability is None
    assert original.source_input is None

    matched = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Widget costs 19.99 USD",
        source_type=MemorySourceType.SCRAPER_RUN,
        source_run_id=uuid.uuid4(),
        source_capability="reddit.scrape",
        source_input={"query": "pricing"},
        created_by_id=db_user.id,
        embedding=[0.2] * _EMBEDDING_DIM,
        # Default update_on_duplicate=False; exact content match triggers the
        # metadata-update branch, not the update_memory branch.
    )

    assert matched.id == original.id
    assert matched.source_capability == "reddit.scrape"
    assert matched.source_input == {"query": "pricing"}


@pytest.mark.asyncio
async def test_run_extraction_with_none_input(
    db_session, db_workspace, db_user, patched_embed_texts
):
    """Run with input=None still yields a memory, with source_input=None."""
    from app.db import MemorySourceType, Run
    from app.services.memory.run_extraction import RunMemoryExtractionService

    run = Run(
        id=uuid.uuid4(),
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        thread_id="2099::task:call_x",
        capability="reddit.scrape",
        origin="api",
        status="success",
        input=None,
        output_text='{"title": "Widget price"}',
        item_count=1,
        char_count=32,
    )
    db_session.add(run)
    await db_session.commit()

    facts_json = (
        '[{"content": "Widget costs 19.99 USD", '
        '"type": "semantic", "tags": ["pricing"], "confidence": 0.9}]'
    )
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=type("R", (), {"content": facts_json})())

    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ):
        service = RunMemoryExtractionService(session=db_session)
        created = await service.extract_from_run(run.id)

    assert len(created) == 1
    assert created[0].source_type == MemorySourceType.SCRAPER_RUN
    assert created[0].source_capability == "reddit.scrape"
    assert created[0].source_input is None


@pytest.mark.asyncio
async def test_update_memory_does_not_clear_recipe(db_session, db_workspace, db_user):
    """Calling update_memory with source_capability=None must not erase a recipe."""
    from app.db import MemorySourceType
    from app.services.memory.repository import MemoryRepository

    repo = MemoryRepository(db_session)
    original = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Widget costs 19.99 USD",
        source_type=MemorySourceType.SCRAPER_RUN,
        source_run_id=uuid.uuid4(),
        source_capability="reddit.scrape",
        source_input={"subreddit": "r/nowing"},
        created_by_id=db_user.id,
        embedding=[0.1] * _EMBEDDING_DIM,
    )

    updated = await repo.update_memory(
        original.id,
        corrected_content="Widget costs 18.99 USD",
        corrected_by_id=db_user.id,
        source_type=MemorySourceType.SCRAPER_RUN,
        source_run_id=uuid.uuid4(),
        source_capability=None,
        source_input=None,
        embedding=[0.1] * _EMBEDDING_DIM,
    )

    assert updated is not None
    assert updated.content == "Widget costs 18.99 USD"
    assert updated.source_capability == "reddit.scrape"
    assert updated.source_input == {"subreddit": "r/nowing"}
