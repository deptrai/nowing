"""Re-validation acceptance tests (Story 9.6b, FR-39, AD-11.1)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from pydantic import BaseModel, ConfigDict

pytestmark = [pytest.mark.integration, pytest.mark.memory]

_EMBEDDING_DIM = 384


class _FakeInput(BaseModel):
    """Permissive input schema for the mocked capability in these tests."""

    model_config = ConfigDict(extra="allow")


class _FakeCapability:
    """Minimal capability stand-in."""

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
def _patch_embed(monkeypatch):
    """Patch the embedding function used by MemoryRepository._embed."""
    mock = MagicMock(return_value=[[0.1] * _EMBEDDING_DIM])
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


def _make_fake_output(answer: str | None = None, items: list | None = None):
    """Return a plain object that ``_extract_text`` can read."""
    data: dict = {}
    if answer is not None:
        data["answer"] = answer
    if items is not None:
        data["items"] = items

    obj = type("O", (), {"answer": answer, "items": items})()
    obj.model_dump = lambda **_: data
    return obj


@pytest.mark.asyncio
async def test_revalidate_run_memory_match_bumps_confidence(
    db_session, db_workspace, db_user, scraper_run, _patch_embed
):
    """Re-executing the same recipe and getting the same fact bumps confidence."""
    from app.db import MemorySourceType
    from app.services.memory.repository import MemoryRepository
    from app.services.memory.revalidation_service import RevalidationService

    repo = MemoryRepository(db_session)
    memory = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Widget costs 19.99 USD",
        source_type=MemorySourceType.SCRAPER_RUN,
        source_run_id=scraper_run.id,
        source_capability=scraper_run.capability,
        source_input=scraper_run.input,
        created_by_id=db_user.id,
        embedding=[0.1] * _EMBEDDING_DIM,
        confidence=0.85,
    )
    original_confidence = memory.confidence

    fake_output = _make_fake_output(answer="Widget costs 19.99 USD")

    with patch(
        "app.services.memory.revalidation_service.get_capability",
        return_value=_FakeCapability(),
    ), patch(
        "app.services.memory.revalidation_service.execute_with_context",
        new=AsyncMock(return_value=fake_output),
    ), patch(
        "app.services.memory.revalidation_service.charge_capability",
        new=AsyncMock(return_value=3500),
    ), patch(
        "app.services.memory.revalidation_service.gate_capability",
        new=AsyncMock(return_value=None),
    ):
        service = RevalidationService(db_session)
        result = await service.revalidate(memory.id, workspace_id=db_workspace.id)

    assert result.memory_id == memory.id
    assert result.status == "verified"
    assert result.memory.content == "Widget costs 19.99 USD"
    assert result.memory.confidence > original_confidence
    assert len(result.memory.versions) == 0


@pytest.mark.asyncio
async def test_revalidate_run_memory_mismatch_creates_version(
    db_session, db_workspace, db_user, scraper_run, _patch_embed
):
    """Re-executing and getting a different fact drops confidence and creates a version."""
    from app.db import MemorySourceType
    from app.services.memory.repository import MemoryRepository
    from app.services.memory.revalidation_service import RevalidationService

    repo = MemoryRepository(db_session)
    memory = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Widget costs 19.99 USD",
        source_type=MemorySourceType.SCRAPER_RUN,
        source_run_id=scraper_run.id,
        source_capability=scraper_run.capability,
        source_input=scraper_run.input,
        created_by_id=db_user.id,
        embedding=[0.1] * _EMBEDDING_DIM,
        confidence=0.85,
    )
    original_confidence = memory.confidence

    fake_output = _make_fake_output(answer="Widget costs 29.99 USD")

    with patch(
        "app.services.memory.revalidation_service.get_capability",
        return_value=_FakeCapability(),
    ), patch(
        "app.services.memory.revalidation_service.execute_with_context",
        new=AsyncMock(return_value=fake_output),
    ), patch(
        "app.services.memory.revalidation_service.charge_capability",
        new=AsyncMock(return_value=3500),
    ), patch(
        "app.services.memory.revalidation_service.gate_capability",
        new=AsyncMock(return_value=None),
    ):
        service = RevalidationService(db_session)
        result = await service.revalidate(memory.id, workspace_id=db_workspace.id)

    assert result.status == "mismatch"
    assert result.memory.confidence < original_confidence
    assert result.memory.content == "Widget costs 29.99 USD"
    assert len(result.memory.versions) == 1
    assert result.memory.versions[0].previous_content == "Widget costs 19.99 USD"
    assert result.memory.versions[0].corrected_content == "Widget costs 29.99 USD"


@pytest.mark.asyncio
async def test_revalidate_chat_memory_not_revalidatable(
    db_session, db_workspace, db_user
):
    """Chat/document/manual memories have no recipe and cannot be re-validated."""
    from app.db import MemorySourceType
    from app.services.memory.repository import MemoryRepository
    from app.services.memory.revalidation_service import (
        RevalidationError,
        RevalidationService,
    )

    repo = MemoryRepository(db_session)
    memory = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="User prefers dark mode",
        source_type=MemorySourceType.CHAT_MESSAGE,
        source_id=4242,
        created_by_id=db_user.id,
        embedding=[0.1] * _EMBEDDING_DIM,
    )

    service = RevalidationService(db_session)
    with pytest.raises(RevalidationError) as exc_info:
        await service.revalidate(memory.id, workspace_id=db_workspace.id)
    assert exc_info.value.code == "not_revalidatable"


@pytest.mark.asyncio
async def test_revalidate_memory_with_none_input_not_revalidatable(
    db_session, db_workspace, db_user, patched_embed_texts
):
    """A run-derived memory whose source_input is None cannot be re-executed."""
    from app.db import Run
    from app.services.memory.revalidation_service import (
        RevalidationError,
        RevalidationService,
    )
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
        '[{"content": "Widget price is unknown", '
        '"type": "semantic", "tags": ["pricing"], "confidence": 0.9}]'
    )
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=type("R", (), {"content": facts_json})())
    with patch("app.services.memory.run_extraction.get_agent_llm", AsyncMock(return_value=llm)):
        created = await RunMemoryExtractionService(session=db_session).extract_from_run(run.id)

    assert len(created) == 1
    memory = created[0]
    assert memory.source_input is None

    service = RevalidationService(db_session)
    with pytest.raises(RevalidationError) as exc_info:
        await service.revalidate(memory.id, workspace_id=db_workspace.id)
    assert exc_info.value.code == "not_revalidatable"


@pytest.mark.asyncio
async def test_revalidate_works_after_source_run_deleted(
    db_session, db_workspace, db_user, scraper_run, _patch_embed
):
    """Re-validation must work after the original run log is cleaned up."""
    from app.db import MemorySourceType
    from app.services.memory.repository import MemoryRepository
    from app.services.memory.revalidation_service import RevalidationService

    repo = MemoryRepository(db_session)
    memory = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Widget costs 19.99 USD",
        source_type=MemorySourceType.SCRAPER_RUN,
        source_run_id=scraper_run.id,
        source_capability=scraper_run.capability,
        source_input=scraper_run.input,
        created_by_id=db_user.id,
        embedding=[0.1] * _EMBEDDING_DIM,
    )

    # Delete the source run to simulate retention cleanup.
    await db_session.delete(scraper_run)
    await db_session.commit()

    fake_output = _make_fake_output(answer="Widget costs 19.99 USD")

    with patch(
        "app.services.memory.revalidation_service.get_capability",
        return_value=_FakeCapability(),
    ), patch(
        "app.services.memory.revalidation_service.execute_with_context",
        new=AsyncMock(return_value=fake_output),
    ), patch(
        "app.services.memory.revalidation_service.charge_capability",
        new=AsyncMock(return_value=3500),
    ), patch(
        "app.services.memory.revalidation_service.gate_capability",
        new=AsyncMock(return_value=None),
    ):
        service = RevalidationService(db_session)
        result = await service.revalidate(memory.id, workspace_id=db_workspace.id)

    assert result.status == "verified"


@pytest.mark.asyncio
async def test_revalidate_records_cost_for_metered_capability(
    db_session, db_workspace, db_user, scraper_run, _patch_embed
):
    """A metered re-validate call records TokenUsage like a normal capability call."""
    from app.db import MemorySourceType
    from app.services.memory.repository import MemoryRepository
    from app.services.memory.revalidation_service import RevalidationService

    repo = MemoryRepository(db_session)
    memory = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Widget costs 19.99 USD",
        source_type=MemorySourceType.SCRAPER_RUN,
        source_run_id=scraper_run.id,
        source_capability=scraper_run.capability,
        source_input=scraper_run.input,
        created_by_id=db_user.id,
        embedding=[0.1] * _EMBEDDING_DIM,
    )

    fake_output = _make_fake_output(answer="Widget costs 19.99 USD")

    with patch(
        "app.services.memory.revalidation_service.get_capability",
        return_value=_FakeCapability(),
    ), patch(
        "app.services.memory.revalidation_service.execute_with_context",
        new=AsyncMock(return_value=fake_output),
    ), patch(
        "app.services.memory.revalidation_service.charge_capability",
        new=AsyncMock(return_value=3500),
    ), patch(
        "app.services.memory.revalidation_service.gate_capability",
        new=AsyncMock(return_value=None),
    ):
        service = RevalidationService(db_session)
        result = await service.revalidate(memory.id, workspace_id=db_workspace.id)

    assert result.cost_micros == 3500


@pytest.mark.asyncio
async def test_revalidate_route_returns_memory(
    client, db_session, db_workspace, db_user, scraper_run, _patch_embed
):
    """POST /workspaces/{id}/memories/{id}/revalidate returns the updated memory."""
    from app.db import MemorySourceType
    from app.services.memory.repository import MemoryRepository

    repo = MemoryRepository(db_session)
    memory = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Widget costs 19.99 USD",
        source_type=MemorySourceType.SCRAPER_RUN,
        source_run_id=scraper_run.id,
        source_capability=scraper_run.capability,
        source_input=scraper_run.input,
        created_by_id=db_user.id,
        embedding=[0.1] * _EMBEDDING_DIM,
        confidence=0.85,
    )

    fake_output = _make_fake_output(answer="Widget costs 19.99 USD")

    with patch(
        "app.services.memory.revalidation_service.get_capability",
        return_value=_FakeCapability(),
    ), patch(
        "app.services.memory.revalidation_service.execute_with_context",
        new=AsyncMock(return_value=fake_output),
    ), patch(
        "app.services.memory.revalidation_service.charge_capability",
        new=AsyncMock(return_value=3500),
    ), patch(
        "app.services.memory.revalidation_service.gate_capability",
        new=AsyncMock(return_value=None),
    ):
        resp = await client.post(
            f"/api/v1/workspaces/{db_workspace.id}/memories/{memory.id}/revalidate"
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == memory.id
    assert body["confidence"] > 0.85


@pytest.mark.asyncio
async def test_revalidate_route_rejects_non_revalidatable_memory(
    client, db_session, db_workspace, db_user
):
    """POST revalidate on a manual memory returns 422, not 500."""
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
    assert body["detail"]["code"] == "not_revalidatable"


@pytest.mark.asyncio
async def test_revalidate_route_rejects_non_workspace_member(
    client_as_other, db_session, db_workspace, db_user, scraper_run, _patch_embed
):
    """AC-5: A non-workspace-member gets 403 on POST /memories/{id}/revalidate."""
    from app.db import MemorySourceType
    from app.services.memory.repository import MemoryRepository

    repo = MemoryRepository(db_session)
    memory = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Widget costs 19.99 USD",
        source_type=MemorySourceType.SCRAPER_RUN,
        source_run_id=scraper_run.id,
        source_capability=scraper_run.capability,
        source_input=scraper_run.input,
        created_by_id=db_user.id,
        embedding=[0.1] * _EMBEDDING_DIM,
        confidence=0.85,
    )

    resp = await client_as_other.post(
        f"/api/v1/workspaces/{db_workspace.id}/memories/{memory.id}/revalidate"
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_revalidate_capability_failure_returns_failed_not_500(
    db_session, db_workspace, db_user, scraper_run, _patch_embed
):
    """AC-6: When the capability executor raises, result.status='failed' (not 500)."""
    from app.db import MemorySourceType
    from app.services.memory.repository import MemoryRepository
    from app.services.memory.revalidation_service import RevalidationService

    repo = MemoryRepository(db_session)
    memory = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="Widget costs 19.99 USD",
        source_type=MemorySourceType.SCRAPER_RUN,
        source_run_id=scraper_run.id,
        source_capability=scraper_run.capability,
        source_input=scraper_run.input,
        created_by_id=db_user.id,
        embedding=[0.1] * _EMBEDDING_DIM,
        confidence=0.85,
    )

    cap = _FakeCapability()
    cap.executor = AsyncMock(side_effect=RuntimeError("upstream blew up"))

    with patch(
        "app.services.memory.revalidation_service.get_capability",
        return_value=cap,
    ), patch(
        "app.services.memory.revalidation_service.gate_capability",
        new=AsyncMock(return_value=None),
    ):
        service = RevalidationService(db_session)
        result = await service.revalidate(memory.id, workspace_id=db_workspace.id)

    assert result.status == "failed"
    assert result.memory_id == memory.id
    assert result.reason is not None
    assert "upstream blew up" in result.reason
