"""End-to-end first-run value: run -> extraction -> recall (Story 3.13, AC-3/AC-7).

Every other suite stops at the service boundary. This one closes the loop the
story is actually about: a workspace with **no** memory at all runs one
capability, and afterwards the recall path a real client uses returns something
useful — with a citation that points back at the run.

Two properties beyond "it returns a row":

* the recall goes through ``MemoryHybridSearch`` and the ``MemorySearchHit``
  contract, i.e. the same path ``/memories/search`` and MCP ``nowing_recall``
  serve, not a hand-rolled ``select``;
* deleting the run afterwards (what the 30-day retention cleanup does) leaves
  recall working and the citation byte-identical (AC-7).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

pytestmark = [pytest.mark.integration, pytest.mark.memory]


FACTS_JSON = (
    '[{"content": "Competitor X sells the widget at 19.99 USD", '
    '"type": "semantic", "tags": ["pricing", "widget"], "confidence": 0.95}]'
)


def _llm_returning(text: str) -> AsyncMock:
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=type("R", (), {"content": text})())
    return llm


@pytest_asyncio.fixture
async def fresh_run(db_session, db_workspace, db_user):
    """A brand-new workspace's very first successful run — and no memory yet."""
    from app.db import Memory, Run

    existing = await db_session.execute(
        select(func.count(Memory.id)).where(Memory.workspace_id == db_workspace.id)
    )
    assert existing.scalar_one() == 0, "fixture precondition: workspace has no memory"

    run = Run(
        id=uuid.uuid4(),
        workspace_id=db_workspace.id,
        user_id=db_user.id,
        thread_id=None,
        capability="amazon.scrape",
        origin="rest",
        status="success",
        input={"url": "https://example.com/widget"},
        output_text='{"title": "Widget", "price": "19.99 USD"}',
        item_count=1,
        char_count=42,
    )
    db_session.add(run)
    await db_session.commit()
    return run


async def _recall(db_session, workspace_id: int, query: str):
    """Recall exactly the way the REST/MCP surfaces do."""
    from app.indexing_pipeline.cache.cached_indexing import embed_texts
    from app.schemas.memory import MemorySearchHit
    from app.services.memory.search import MemoryHybridSearch

    query_embedding = embed_texts([query])[0]
    hits = await MemoryHybridSearch(db_session).search(
        workspace_id=workspace_id,
        query=query,
        query_embedding=query_embedding,
        top_k=5,
    )
    return [MemorySearchHit.from_memory(hit.memory) for hit in hits]


@pytest.mark.asyncio
async def test_first_run_makes_recall_non_empty_with_run_citation(
    db_session, db_workspace, fresh_run, patched_embed_texts
):
    """AC-3: the first run alone gives recall something to return, with a citation."""
    from app.services.memory.run_extraction import RunMemoryExtractionService

    llm = _llm_returning(FACTS_JSON)
    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ):
        created = await RunMemoryExtractionService(session=db_session).extract_from_run(
            fresh_run.id
        )

    assert len(created) == 1

    hits = await _recall(db_session, db_workspace.id, "widget pricing")

    assert hits, "recall returned nothing after the first successful run"
    hit = next(h for h in hits if h.source_run_id == str(fresh_run.id))
    assert hit.source_type == "scraper_run"
    assert hit.citation == f"run_{fresh_run.id}"
    assert hit.source_id is None

    # The citation must survive JSON serialization: that is the form the REST
    # response and the MCP payload actually carry.
    payload = hit.model_dump(mode="json")
    assert payload["citation"] == f"run_{fresh_run.id}"


@pytest.mark.asyncio
async def test_recall_survives_run_retention_cleanup(
    db_session, db_workspace, fresh_run, patched_embed_texts
):
    """AC-7: deleting the run leaves recall working and the citation unchanged."""
    from app.db import Run
    from app.services.memory.run_extraction import RunMemoryExtractionService

    run_id = fresh_run.id
    workspace_id = db_workspace.id

    llm = _llm_returning(FACTS_JSON)
    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ):
        await RunMemoryExtractionService(session=db_session).extract_from_run(run_id)

    before = await _recall(db_session, workspace_id, "widget pricing")
    citation_before = next(
        h.citation for h in before if h.source_run_id == str(run_id)
    )

    # Exactly what the opportunistic 30-day cleanup does. It succeeds only
    # because there is no hard FK from `memories` to `runs` (AC-7).
    await db_session.execute(delete(Run).where(Run.id == run_id))
    await db_session.commit()

    after = await _recall(db_session, workspace_id, "widget pricing")

    dangling = next(h for h in after if h.source_run_id == str(run_id))
    assert dangling.citation == citation_before
    assert dangling.content == before[0].content
