"""Red-phase scaffolds for ChainLens degradation and bounded KB fallback."""

from __future__ import annotations

import importlib
from unittest.mock import AsyncMock

import httpx
import pytest

from app.agents.chat.multi_agent_chat.shared.retrieval.models import (
    ChunkHit,
    DocumentHit,
)
from app.capabilities.chainlens.research.schemas import ResearchInput
from app.capabilities.core.types import CapabilityContext

pytestmark = pytest.mark.unit


def _load_execute_with_context():
    """Resolve the context-aware execution seam that 9.1a adds."""
    mod = importlib.import_module("app.capabilities.chainlens.research.executor")
    return getattr(mod, "execute_with_context", None)


def _make_hit(doc_id: int, chunk_id: int) -> DocumentHit:
    return DocumentHit(
        document_id=doc_id,
        title="KB Document",
        document_type="pdf",
        metadata={},
        score=0.9,
        chunks=[
            ChunkHit(
                chunk_id=chunk_id,
                content="relevant chunk",
                position=0,
                score=0.9,
            )
        ],
    )


async def test_knowledge_base_fallback_returns_internal_citations():
    execute = _load_execute_with_context()
    assert execute is not None

    async def search(_):
        raise httpx.TimeoutException("timeout")

    async def fallback(*, query, scope, top_k, session, workspace_id):
        return [_make_hit(7, 12)]

    ctx = CapabilityContext(session=AsyncMock(), workspace_id=1)
    output = await execute(
        ResearchInput(query="hello"),
        ctx,
        search_fn=search,
        fallback_fn=fallback,
    )

    assert output.status == "partial"
    assert output.degraded is True
    assert output.fallback_hit_count == 1
    assert output.sources[0].url == "nowing://documents/7/chunks/12"
    assert output.sources[0].document_id == 7
    assert output.sources[0].chunk_id == 12


async def test_knowledge_base_fallback_empty_returns_engine_unavailable():
    execute = _load_execute_with_context()
    assert execute is not None

    async def search(_):
        raise httpx.ConnectError("unreachable")

    async def fallback(*, query, scope, top_k, session, workspace_id):
        return []

    ctx = CapabilityContext(session=AsyncMock(), workspace_id=1)
    output = await execute(
        ResearchInput(query="hello"),
        ctx,
        search_fn=search,
        fallback_fn=fallback,
    )

    assert output.status == "engine_unavailable"
    assert output.degradation_reason == "fallback_kb_empty"
    assert output.fallback_hit_count == 0
    assert not output.answer
    assert not output.sources


async def test_knowledge_base_fallback_error_returns_engine_unavailable():
    execute = _load_execute_with_context()
    assert execute is not None

    async def search(_):
        raise httpx.TimeoutException("timeout")

    async def fallback(*, query, scope, top_k, session, workspace_id):
        raise RuntimeError("Postgres down")

    ctx = CapabilityContext(session=AsyncMock(), workspace_id=1)
    output = await execute(
        ResearchInput(query="hello"),
        ctx,
        search_fn=search,
        fallback_fn=fallback,
    )

    assert output.status == "engine_unavailable"
    assert output.degradation_reason == "fallback_kb_error"
    assert output.fallback_hit_count == 0


async def test_knowledge_base_fallback_top_k_clamped_to_five():
    execute = _load_execute_with_context()
    assert execute is not None

    called_top_k = None

    async def search(_):
        raise httpx.TimeoutException("timeout")

    async def fallback(*, query, scope, top_k, session, workspace_id):
        nonlocal called_top_k
        called_top_k = top_k
        return [_make_hit(1, 1)]

    ctx = CapabilityContext(session=AsyncMock(), workspace_id=1)
    await execute(
        ResearchInput(query="hello"),
        ctx,
        search_fn=search,
        fallback_fn=fallback,
        top_k=100,
    )

    assert called_top_k == 5


async def test_knowledge_base_fallback_uses_authorized_workspace_id():
    execute = _load_execute_with_context()
    assert execute is not None

    seen_workspace_id = None

    async def search(_):
        raise httpx.TimeoutException("timeout")

    async def fallback(*, query, scope, top_k, session, workspace_id):
        nonlocal seen_workspace_id
        seen_workspace_id = workspace_id
        return []

    ctx = CapabilityContext(session=AsyncMock(), workspace_id=42)
    await execute(
        ResearchInput(query="hello"),
        ctx,
        search_fn=search,
        fallback_fn=fallback,
    )

    assert seen_workspace_id == 42


async def test_missing_context_skips_fallback():
    execute = _load_execute_with_context()
    assert execute is not None

    fallback_called = False

    async def search(_):
        raise httpx.TimeoutException("timeout")

    async def fallback(*, query, scope, top_k, session, workspace_id):
        nonlocal fallback_called
        fallback_called = True
        return []

    output = await execute(
        ResearchInput(query="hello"),
        None,
        search_fn=search,
        fallback_fn=fallback,
    )

    assert fallback_called is False
    assert output.status == "engine_unavailable"


async def test_degraded_output_does_not_fabricate_answer():
    execute = _load_execute_with_context()
    assert execute is not None

    async def search(_):
        raise httpx.TimeoutException("timeout")

    async def fallback(*, query, scope, top_k, session, workspace_id):
        return []

    ctx = CapabilityContext(session=AsyncMock(), workspace_id=1)
    output = await execute(
        ResearchInput(query="hello"),
        ctx,
        search_fn=search,
        fallback_fn=fallback,
    )

    assert output.status == "engine_unavailable"
    assert not output.answer
    assert not output.sources
    assert output.next_action is not None


async def test_knowledge_base_fallback_is_tenant_isolated():
    """Negative tenant test: fallback only keeps hits for the authorized workspace.

    The mock ``search_chunks`` pool contains documents from two workspaces. The
    fallback function is invoked with the authorized ``workspace_id`` and must
    only return hits for that workspace; the executor then surfaces only those
    chunks in the final answer.
    """
    from types import SimpleNamespace

    execute = _load_execute_with_context()
    assert execute is not None

    async def search(_):
        raise httpx.TimeoutException("timeout")

    authorized_workspace = 7
    unauthorized_workspace = 99

    def _make_workspace_hit(workspace_id: int, doc_id: int, chunk_id: int):
        base = _make_hit(doc_id, chunk_id)
        # Add a workspace tag so the mock search_chunks can filter by tenant.
        return SimpleNamespace(
            workspace_id=workspace_id,
            document_id=base.document_id,
            title=base.title,
            document_type=base.document_type,
            metadata=base.metadata,
            score=base.score,
            chunks=base.chunks,
        )

    pool = [
        _make_workspace_hit(authorized_workspace, 10, 100),
        _make_workspace_hit(unauthorized_workspace, 20, 200),
    ]

    async def fallback(*, query, scope, top_k, session, workspace_id):
        # Simulates the real search_chunks contract: filter by workspace_id.
        return [h for h in pool if h.workspace_id == workspace_id]

    ctx = CapabilityContext(session=AsyncMock(), workspace_id=authorized_workspace)
    output = await execute(
        ResearchInput(query="hello"),
        ctx,
        search_fn=search,
        fallback_fn=fallback,
    )

    assert output.status == "partial"
    assert output.fallback_hit_count == 1
    assert output.sources[0].document_id == 10
    assert output.sources[0].content == "relevant chunk"
    assert all(s.document_id != 20 for s in output.sources)
