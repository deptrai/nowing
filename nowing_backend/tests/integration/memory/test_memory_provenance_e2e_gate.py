"""Memory provenance end-to-end revalidation gate (Story 9.6c, AD-11.1, FR-39)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

pytestmark = [pytest.mark.integration, pytest.mark.memory]

_EMBEDDING_DIM = 384


class _FakeInput(BaseModel):
    """Permissive input schema for the mocked capability in these tests."""

    model_config = ConfigDict(extra="allow")


class _FakeCapability:
    """Minimal capability stand-in for revalidation tests."""

    def __init__(self, billing_unit=None):
        self.name = "reddit.scrape"
        self.description = "fake"
        self.input_schema = _FakeInput
        self.output_schema = BaseModel
        self.executor = AsyncMock()
        self.billing_unit = billing_unit
        self.docs_url = None
        self.context_aware = False


@pytest.fixture
def _patch_embed_texts(monkeypatch):
    """Patch embedding used by MemoryRepository._embed."""
    mock = MagicMock(side_effect=lambda texts: [[0.1] * _EMBEDDING_DIM for _ in texts])
    monkeypatch.setattr(
        "app.utils.document_converters.embed_texts",
        mock,
    )
    return mock


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


class _FakeOutput(BaseModel):
    """A Pydantic output that ``_extract_text`` and ``record_run`` can read."""

    answer: str | None = None
    items: list | None = None


def _make_fake_output(
    answer: str | None = None, items: list | None = None
) -> _FakeOutput:
    """Return a Pydantic object that ``_extract_text`` can read."""
    return _FakeOutput(answer=answer, items=items)


def _llm_returning_facts(content: str) -> AsyncMock:
    """LLM mock that returns a single fact JSON."""
    facts_json = (
        f'[{{"content": "{content}", '
        '"type": "semantic", "tags": ["pricing"], "confidence": 0.9}]'
    )
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=type("R", (), {"content": facts_json})())
    return llm


@pytest.mark.asyncio
async def test_run_extraction_populates_recipe(
    db_session, db_workspace, db_user, scraper_run, _patch_embed_texts
):
    """AC-1: a scraper run-derived memory carries source capability and input recipe."""
    from app.db import Memory, MemorySourceType
    from app.services.memory.run_extraction import RunMemoryExtractionService

    llm = _llm_returning_facts("Widget costs 19.99 USD")
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

    row = (
        await db_session.execute(select(Memory).where(Memory.id == memory.id))
    ).scalar_one()
    assert row.source_capability == "reddit.scrape"
    assert row.source_input == {"subreddit": "r/nowing", "query": "pricing"}


@pytest.mark.asyncio
async def test_revalidate_after_source_run_deleted(
    db_session, db_workspace, db_user, client, scraper_run, _patch_embed_texts
):
    """AC-2: revalidate succeeds using only the recipe after the source Run is gone."""
    from app.db import Memory, MemorySourceType, Run
    from app.services.memory.run_extraction import RunMemoryExtractionService

    llm = _llm_returning_facts("Widget costs 19.99 USD")
    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ):
        service = RunMemoryExtractionService(session=db_session)
        created = await service.extract_from_run(scraper_run.id)

    memory = created[0]
    assert memory.source_input is not None

    # Simulate 31-day cleanup: delete the source Run row.
    await db_session.delete(scraper_run)
    await db_session.commit()
    deleted_run = (
        await db_session.execute(select(Run).where(Run.id == scraper_run.id))
    ).scalar_one_or_none()
    assert deleted_run is None

    fake_output = _make_fake_output(answer="Widget costs 19.99 USD")
    cap = _FakeCapability(billing_unit="reddit_item")

    with (
        patch(
            "app.services.memory.revalidation_service.get_capability",
            return_value=cap,
        ),
        patch(
            "app.services.memory.revalidation_service.execute_with_context",
            new=AsyncMock(return_value=fake_output),
        ),
        patch(
            "app.services.memory.revalidation_service.charge_capability",
            new=AsyncMock(return_value=3500),
        ),
        patch(
            "app.services.memory.revalidation_service.gate_capability",
            new=AsyncMock(return_value=None),
        ),
    ):
        resp = await client.post(
            f"/api/v1/workspaces/{db_workspace.id}/memories/{memory.id}/revalidate"
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == memory.id
    assert body["confidence"] > 0.9

    refreshed = (
        await db_session.execute(select(Memory).where(Memory.id == memory.id))
    ).scalar_one()
    assert refreshed.source_type == MemorySourceType.SCRAPER_RUN
    assert refreshed.confidence > 0.9


@pytest.mark.asyncio
async def test_revalidate_mismatch_creates_version_after_run_deleted(
    db_session, db_workspace, db_user, client, scraper_run, _patch_embed_texts
):
    """AC-2 mismatch: revalidation creates MemoryVersion when the fact changes."""
    from app.db import Memory, MemoryVersion
    from app.services.memory.run_extraction import RunMemoryExtractionService

    llm = _llm_returning_facts("Widget costs 19.99 USD")
    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ):
        service = RunMemoryExtractionService(session=db_session)
        created = await service.extract_from_run(scraper_run.id)

    memory = created[0]

    # Simulate 31-day cleanup.
    await db_session.delete(scraper_run)
    await db_session.commit()

    fake_output = _make_fake_output(answer="Widget costs 29.99 USD")
    cap = _FakeCapability(billing_unit="reddit_item")

    with (
        patch(
            "app.services.memory.revalidation_service.get_capability",
            return_value=cap,
        ),
        patch(
            "app.services.memory.revalidation_service.execute_with_context",
            new=AsyncMock(return_value=fake_output),
        ),
        patch(
            "app.services.memory.revalidation_service.charge_capability",
            new=AsyncMock(return_value=3500),
        ),
        patch(
            "app.services.memory.revalidation_service.gate_capability",
            new=AsyncMock(return_value=None),
        ),
    ):
        resp = await client.post(
            f"/api/v1/workspaces/{db_workspace.id}/memories/{memory.id}/revalidate"
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == memory.id

    refreshed = (
        await db_session.execute(select(Memory).where(Memory.id == memory.id))
    ).scalar_one()
    assert refreshed.content == "Widget costs 29.99 USD"
    assert refreshed.confidence < 0.9

    versions = (
        (
            await db_session.execute(
                select(MemoryVersion).where(MemoryVersion.memory_id == memory.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(versions) == 1
    assert versions[0].previous_content == "Widget costs 19.99 USD"
    assert versions[0].corrected_content == "Widget costs 29.99 USD"


@pytest.mark.asyncio
async def test_revalidate_non_scraper_memory_returns_422(
    db_session, db_workspace, db_user, client, _patch_embed_texts
):
    """AC-3: a manual memory cannot be revalidated and returns 422, not 500."""
    from app.db import MemorySourceType
    from app.services.memory.repository import MemoryRepository

    repo = MemoryRepository(db_session)
    memory = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="User prefers dark mode",
        source_type=MemorySourceType.MANUAL,
        created_by_id=db_user.id,
        embedding=[0.1] * _EMBEDDING_DIM,
    )

    resp = await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/memories/{memory.id}/revalidate"
    )

    assert resp.status_code == 422
    body = resp.json()
    assert body["detail"]["code"] in ("not_revalidatable", "invalid_recipe")


@pytest.mark.asyncio
async def test_revalidate_records_cost_and_revalidate_run(
    db_session, db_workspace, db_user, client, scraper_run, _patch_embed_texts
):
    """AC-4: revalidation is charged and a revalidate Run row is recorded."""
    from app.db import Run
    from app.services.memory.run_extraction import RunMemoryExtractionService

    llm = _llm_returning_facts("Widget costs 19.99 USD")
    with patch(
        "app.services.memory.run_extraction.get_agent_llm",
        AsyncMock(return_value=llm),
    ):
        service = RunMemoryExtractionService(session=db_session)
        created = await service.extract_from_run(scraper_run.id)

    memory = created[0]
    await db_session.delete(scraper_run)
    await db_session.commit()

    fake_output = _make_fake_output(answer="Widget costs 19.99 USD")
    cap = _FakeCapability(billing_unit="reddit_item")

    with (
        patch(
            "app.services.memory.revalidation_service.get_capability",
            return_value=cap,
        ),
        patch(
            "app.services.memory.revalidation_service.execute_with_context",
            new=AsyncMock(return_value=fake_output),
        ),
        patch(
            "app.services.memory.revalidation_service.charge_capability",
            new=AsyncMock(return_value=3500),
        ),
        patch(
            "app.services.memory.revalidation_service.gate_capability",
            new=AsyncMock(return_value=None),
        ),
    ):
        resp = await client.post(
            f"/api/v1/workspaces/{db_workspace.id}/memories/{memory.id}/revalidate"
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == memory.id

    # Recorded a new Run for the revalidation.
    revalidate_runs = (
        (
            await db_session.execute(
                select(Run).where(
                    Run.workspace_id == db_workspace.id,
                    Run.origin == "revalidate",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(revalidate_runs) == 1
    assert revalidate_runs[0].cost_micros == 3500
    assert revalidate_runs[0].capability == "reddit.scrape"


@pytest.mark.asyncio
async def test_revalidate_invalid_recipe_returns_422(
    db_session, db_workspace, db_user, client, _patch_embed_texts
):
    """AC-5: missing/invalid recipe returns 422, not 500."""
    from app.db import MemorySourceType
    from app.services.memory.repository import MemoryRepository

    repo = MemoryRepository(db_session)
    memory = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Some fact",
        source_type=MemorySourceType.SCRAPER_RUN,
        source_run_id=uuid.uuid4(),
        source_capability="reddit.scrape",
        source_input=None,
        created_by_id=db_user.id,
        embedding=[0.1] * _EMBEDDING_DIM,
    )

    resp = await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/memories/{memory.id}/revalidate"
    )

    assert resp.status_code == 422
    body = resp.json()
    assert body["detail"]["code"] in ("not_revalidatable", "invalid_recipe")
