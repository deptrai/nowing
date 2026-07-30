"""Integration tests for chainlens.research fallback + CapabilityContext (Story 9.1a)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.agents.chat.multi_agent_chat.shared.retrieval.hybrid_search import (
    search_chunks,
)
from app.agents.chat.multi_agent_chat.shared.retrieval.models import SearchScope
from app.capabilities.chainlens.research.schemas import (
    ResearchInput,
    ResearchOutput,
    Source,
)
from app.capabilities.core.billing import charge_capability
from app.capabilities.core.types import BillingUnit, CapabilityContext
from app.config import config
from app.db import Chunk, Document, DocumentType, Run, TokenUsage, Workspace

pytestmark = [pytest.mark.integration]

BASE = "/api/v1/workspaces/{workspace_id}/scrapers/chainlens/research"


async def _add_kb_document(
    db_session,
    *,
    workspace_id: int,
    title: str = "KB Doc",
    keyword: str = "evidence",
    embedding: list[float] | None = None,
) -> Document:
    """Seed one indexed Document with one Chunk for fallback retrieval."""
    if embedding is None:
        embedding = [0.0] * config.embedding_model_instance.dimension

    document = Document(
        title=title,
        document_type=DocumentType.FILE,
        content=f"{keyword} fallback content.",
        content_hash=uuid.uuid4().hex,
        workspace_id=workspace_id,
        status={"state": "ready"},
        embedding=embedding,
    )
    db_session.add(document)
    await db_session.flush()

    db_session.add(
        Chunk(
            content=f"{keyword} fallback content.",
            document_id=document.id,
            position=0,
            embedding=embedding,
        )
    )
    await db_session.flush()
    return document


@pytest.mark.asyncio
async def test_fallback_search_returns_zero_rows_for_empty_workspace(
    db_session,
    db_workspace,
):
    """AC-1 P6: fallback query runs and returns 0 rows when workspace has no docs."""
    results = await search_chunks(
        db_session,
        workspace_id=db_workspace.id,
        query="evidence",
        scope=SearchScope(),
        top_k=5,
        query_embedding=[0.0] * config.embedding_model_instance.dimension,
    )
    assert results == []


@pytest.mark.asyncio
async def test_fallback_search_respects_workspace_id_filter(
    db_session,
    db_workspace,
    db_other_workspace,
):
    """AC-1/AC-3 P6: workspace_id filter keeps unauthorized documents out."""
    mine = await _add_kb_document(db_session, workspace_id=db_workspace.id)
    await _add_kb_document(db_session, workspace_id=db_other_workspace.id)

    results = await search_chunks(
        db_session,
        workspace_id=db_workspace.id,
        query="evidence",
        scope=SearchScope(),
        top_k=5,
        query_embedding=[0.0] * config.embedding_model_instance.dimension,
    )

    found = {hit.document_id for hit in results}
    assert mine.id in found
    assert db_other_workspace.id not in found


@pytest.mark.asyncio
async def test_fallback_search_returns_real_chunk_and_document_ids(
    db_session,
    db_workspace,
):
    """AC-4 P6: fallback sources carry real document_id and chunk_id."""
    document = await _add_kb_document(db_session, workspace_id=db_workspace.id)
    chunk_id_before = (
        await db_session.execute(
            select(Chunk.id).where(Chunk.document_id == document.id)
        )
    ).scalar_one()

    results = await search_chunks(
        db_session,
        workspace_id=db_workspace.id,
        query="evidence",
        scope=SearchScope(),
        top_k=5,
        query_embedding=[0.0] * config.embedding_model_instance.dimension,
    )

    assert len(results) == 1
    hit = results[0]
    assert hit.document_id == document.id
    assert hit.chunks
    assert any(chunk.chunk_id == chunk_id_before for chunk in hit.chunks)


@pytest.mark.asyncio
async def test_fallback_search_top_k_bounded(
    db_session,
    db_workspace,
):
    """AC-2/AC-3 P6: fallback query uses a top_k of at most 5 documents."""
    for i in range(7):
        await _add_kb_document(
            db_session,
            workspace_id=db_workspace.id,
            title=f"Doc {i}",
        )

    results = await search_chunks(
        db_session,
        workspace_id=db_workspace.id,
        query="evidence",
        scope=SearchScope(),
        top_k=5,
        query_embedding=[0.0] * config.embedding_model_instance.dimension,
    )

    assert len(results) <= 5


@pytest.mark.asyncio
async def test_foreign_key_rejects_chunk_for_nonexistent_document(
    db_session,
):
    """AC-3 P6: Chunk.document_id FK enforces that citations reference real rows."""
    with pytest.raises(IntegrityError):
        db_session.add(
            Chunk(
                content="orphan chunk",
                document_id=-1,
                position=0,
                embedding=[0.0] * config.embedding_model_instance.dimension,
            )
        )
        await db_session.flush()


@pytest.mark.asyncio
async def test_charge_capability_creates_no_token_usage_for_engine_unavailable(
    db_session,
    db_user,
    db_workspace,
    monkeypatch,
):
    """AC-10 P6: no TokenUsage row for engine_unavailable with no content."""
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    db_user.credit_micros_balance = 10_000_000

    # Schema update for engine_unavailable is pending; model_construct lets us
    # exercise the future status without waiting for the Pydantic Literal change.
    output = ResearchOutput.model_construct(
        status="engine_unavailable",
        degradation_reason="not_configured",
    )
    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)
    await charge_capability(output, BillingUnit.CHAINLENS_QUERY, ctx)

    rows = (
        await db_session.execute(
            select(TokenUsage).where(
                TokenUsage.workspace_id == db_workspace.id,
                TokenUsage.usage_type == BillingUnit.CHAINLENS_QUERY.value,
            )
        )
    ).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_charge_capability_creates_token_usage_for_partial_with_sources(
    db_session,
    db_user,
    db_workspace,
    monkeypatch,
):
    """AC-10 P6: a degraded partial with citable sources bills exactly one unit."""
    monkeypatch.setattr(config, "PLATFORM_SCRAPE_BILLING_ENABLED", True)
    db_user.credit_micros_balance = 10_000_000

    output = ResearchOutput(
        status="partial",
        answer="The engine is unavailable; here is workspace evidence.",
        sources=[
            Source(
                title="KB fallback",
                url="nowing://documents/1/chunks/1",
                content="Relevant passage.",
            )
        ],
    )
    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)
    await charge_capability(output, BillingUnit.CHAINLENS_QUERY, ctx)

    rows = (
        await db_session.execute(
            select(TokenUsage).where(
                TokenUsage.workspace_id == db_workspace.id,
                TokenUsage.usage_type == "deep_research",
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].cost_micros > 0
    assert rows[0].call_details["cost_basis"] == "fallback"
    # FK: the TokenUsage is tied to the workspace owner.
    assert rows[0].user_id == db_user.id


@pytest.mark.asyncio
async def test_rest_sync_records_degraded_run_output_text(
    client,
    db_session,
    db_workspace,
    monkeypatch,
):
    """AC-7 P6: sync POST persists a Run row whose output_text carries the status."""
    # Force the no-key self-host path so the request degrades instead of networking.
    monkeypatch.setattr(
        "app.capabilities.chainlens.research.executor.config.CHAINLENS_API_KEY",
        "",
    )

    payload = ResearchInput(query="self-host deep research").model_dump()
    resp = await client.post(
        BASE.format(workspace_id=db_workspace.id),
        json=payload,
    )

    # The route should eventually return a typed 200 with engine_unavailable.
    # Until implemented it returns 500; this assertion is the red-phase target.
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "engine_unavailable"

    # The Run row must mirror the same status in output_text.
    run_row = (
        await db_session.execute(
            select(Run).where(
                Run.workspace_id == db_workspace.id,
                Run.capability == "chainlens.research",
            )
        )
    ).scalar_one()
    assert run_row.output_text is not None
    assert "engine_unavailable" in run_row.output_text


@pytest.mark.asyncio
async def test_rest_non_member_cannot_trigger_research(
    client_as_other,
    db_workspace,
):
    """Tenant boundary: a non-member must not reach the research route."""
    payload = {"query": "self-host deep research"}
    resp = await client_as_other.post(
        BASE.format(workspace_id=db_workspace.id),
        json=payload,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_run_foreign_key_rejects_nonexistent_workspace(db_session):
    """AC-7 P6: Run.workspace_id FK rejects a row for a missing workspace."""
    from uuid import uuid4

    with pytest.raises(IntegrityError):
        db_session.add(
            Run(
                id=uuid4(),
                workspace_id=-1,
                capability="chainlens.research",
                origin="ui",
                status="success",
            )
        )
        await db_session.flush()
