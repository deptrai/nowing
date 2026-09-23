"""_guardrail_filter_chunks + private_provider filter wiring (Story 39.4)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.services.chainlens.ingest as ingest_mod
import app.services.chainlens.private_provider as pp
from app.services.chainlens.private_provider import PrivateProviderService
from app.services.chainlens.schemas import (
    PrivateDataSearchRequest,
    PrivateProviderChunk,
    PrivateProviderChunkMetadata,
)
from app.services.content_guardrails import GuardrailAction, PassageVerdict
from app.services.scraper_chunks.schemas import Chunk, ChunkMetadata

pytestmark = pytest.mark.unit


def _chunk(content: str, source_id: str = "s1") -> Chunk:
    return Chunk(
        content=content,
        metadata=ChunkMetadata(
            source="nowing_scraper",
            sourceId=source_id,
            domain="bds",
            fetchedAt="2026-09-22T00:00:00",
            contentType="text/markdown",
        ),
    )


def _verdict(action: GuardrailAction, masked: str | None = None):
    return PassageVerdict(
        action=action,
        reasons=("sensitive",) if action is GuardrailAction.MASK else (),
        masked_text=masked,
    )


@pytest.fixture
def _enabled(monkeypatch):
    monkeypatch.setenv("DECISION_ENABLED", "true")
    monkeypatch.setenv("DECISION_FILTER_ENABLED", "true")


def _patch_filter(module, monkeypatch, route):
    async def _fake(items, **_kwargs):
        return (
            [(item, route(item, text)) for item, text in items],
            None,
        )

    monkeypatch.setattr(module, "filter_passages", _fake)


# ---------------------------------------------------------------------------
# ingest._guardrail_filter_chunks
# ---------------------------------------------------------------------------


async def test_ingest_flags_off_returns_input(monkeypatch):
    monkeypatch.setenv("DECISION_ENABLED", "false")

    async def _boom(*_a, **_k):
        raise AssertionError("filter must not run when flags off")

    monkeypatch.setattr(ingest_mod, "filter_passages", _boom)
    chunks = [_chunk("a"), _chunk("b", "s2")]
    out = await ingest_mod._guardrail_filter_chunks(
        chunks, scraper_id="bds", workspace_id=1
    )
    assert out == chunks


async def test_ingest_drop_excludes_chunk(_enabled, monkeypatch):
    _patch_filter(
        ingest_mod,
        monkeypatch,
        lambda _c, _t: _verdict(GuardrailAction.DROP),
    )
    out = await ingest_mod._guardrail_filter_chunks(
        [_chunk("bad"), _chunk("bad2", "s2")],
        scraper_id="bds",
        workspace_id=1,
    )
    assert out == []


async def test_ingest_mask_mutates_chunk_content(_enabled, monkeypatch):
    _patch_filter(
        ingest_mod,
        monkeypatch,
        lambda _c, _t: _verdict(GuardrailAction.MASK, masked="MASKED"),
    )
    chunk = _chunk("SĐT 0901234567")
    out = await ingest_mod._guardrail_filter_chunks(
        [chunk], scraper_id="bds", workspace_id=1
    )
    assert len(out) == 1
    assert out[0].content == "MASKED"
    assert out[0] is chunk  # in-place mutation, identity preserved


async def test_ingest_mask_dict_chunk(_enabled, monkeypatch):
    _patch_filter(
        ingest_mod,
        monkeypatch,
        lambda _c, _t: _verdict(GuardrailAction.MASK, masked="MASKED"),
    )
    chunk = {"content": "raw", "metadata": {}}
    out = await ingest_mod._guardrail_filter_chunks(
        [chunk], scraper_id="bds", workspace_id=1
    )
    assert out[0]["content"] == "MASKED"


async def test_ingest_query_uses_scraper_id(_enabled, monkeypatch):
    seen: dict = {}

    async def _fake(items, *, query, surface, max_calls, **_kwargs):
        seen.update(query=query, surface=surface, max_calls=max_calls)
        return ([(i, _verdict(GuardrailAction.PASS)) for i, _ in items], None)

    monkeypatch.setattr(ingest_mod, "filter_passages", _fake)
    await ingest_mod._guardrail_filter_chunks(
        [_chunk("x")], scraper_id="muaban_bds", workspace_id=1
    )
    assert seen["query"] == "scraped muaban_bds content"
    assert seen["surface"] == "ingest"
    assert seen["max_calls"] == ingest_mod.MAX_INGEST_FILTER_CALLS


async def test_ingest_immutable_sensitive_chunk_dropped(
    _enabled, monkeypatch
):
    """A MASK verdict on an object with no content field → drop, not pass."""
    _patch_filter(
        ingest_mod,
        monkeypatch,
        lambda _c, _t: _verdict(GuardrailAction.MASK, masked="MASKED"),
    )
    weird = object()  # neither BaseModel nor dict — no content to rewrite
    out = await ingest_mod._guardrail_filter_chunks(
        [weird], scraper_id="bds", workspace_id=1
    )
    assert out == []


async def test_ingest_mask_without_masked_text_drops(_enabled, monkeypatch):
    """MASK verdict with empty masked_text → drop, never store raw."""
    _patch_filter(
        ingest_mod,
        monkeypatch,
        lambda _c, _t: _verdict(GuardrailAction.MASK, masked=None),
    )
    out = await ingest_mod._guardrail_filter_chunks(
        [_chunk("raw")], scraper_id="bds", workspace_id=1
    )
    assert out == []


async def test_ingest_filter_raise_returns_input(_enabled, monkeypatch):
    """Fail-open: filter_passages raising must not break ingest."""

    async def _boom(*_a, **_k):
        raise RuntimeError("guardrail exploded")

    monkeypatch.setattr(ingest_mod, "filter_passages", _boom)
    chunks = [_chunk("a"), _chunk("b", "s2")]
    out = await ingest_mod._guardrail_filter_chunks(
        chunks, scraper_id="bds", workspace_id=1
    )
    assert out == chunks


async def test_ingest_end_to_end_all_dropped_returns_noop(
    _enabled, monkeypatch
):
    """Wire check: ingest() must reach _guardrail_filter_chunks — all DROP
    short-circuits to the same noop result as empty input."""
    _patch_filter(
        ingest_mod,
        monkeypatch,
        lambda _c, _t: _verdict(GuardrailAction.DROP),
    )
    monkeypatch.setattr(
        ingest_mod,
        "ChainLensServiceAuth",
        lambda **_kw: SimpleNamespace(configured=True),
    )

    async def _no_post(*_a, **_k):
        raise AssertionError("must not POST when all chunks dropped")

    monkeypatch.setattr(ingest_mod, "_post_batch", _no_post)
    service = ingest_mod.NowingIngestService()
    result = await service.ingest(
        "bds", [_chunk("bad")], workspace_id=1
    )
    assert result.status == "noop"


async def test_ingest_end_to_end_pass_posts_masked_content(
    _enabled, monkeypatch
):
    """Wire check: surviving masked chunks reach the batch POST."""
    _patch_filter(
        ingest_mod,
        monkeypatch,
        lambda _c, _t: _verdict(GuardrailAction.MASK, masked="MASKED"),
    )
    monkeypatch.setattr(
        ingest_mod,
        "ChainLensServiceAuth",
        lambda **_kw: SimpleNamespace(configured=True),
    )
    posted: list = []

    async def _fake_post(_sid, _ws, batch, _cfg, _cid):
        posted.extend(batch)
        return {"ingestedSourceIds": ["s1"]}

    monkeypatch.setattr(ingest_mod, "_post_batch", _fake_post)
    service = ingest_mod.NowingIngestService()
    result = await service.ingest(
        "bds", [_chunk("raw")], workspace_id=1
    )
    assert result.status == "ok"
    assert posted and posted[0].content == "MASKED"


# ---------------------------------------------------------------------------
# private_provider.search — filter wiring
# ---------------------------------------------------------------------------


def _make_request(**overrides) -> PrivateDataSearchRequest:
    defaults = {
        "query": "private search query",
        "workspaceId": 7,
        "userId": None,
        "connectorId": None,
        "sources": None,
        "topK": 20,
    }
    defaults.update(overrides)
    return PrivateDataSearchRequest(**defaults)


def _provider_chunk(content: str, chunk_id: int) -> PrivateProviderChunk:
    return PrivateProviderChunk(
        content=content,
        metadata=PrivateProviderChunkMetadata(
            source="private_provider",
            sourceId=f"src-{chunk_id}",
            domain="nowing",
            fetchedAt="2026-09-22T00:00:00",
            contentType="FILE",
            title="Doc",
            url=f"nowing://documents/1/chunks/{chunk_id}",
            document_id=1,
            chunk_id=chunk_id,
            connector_id=None,
            workspace_id=7,
        ),
    )


def _stubbed_search_service(fake_session, chunks):
    """Provider whose search() internals are all stubbed to return ``chunks``."""
    service = PrivateProviderService(fake_session)
    service._is_workspace_member = AsyncMock(return_value=True)
    service._resolve_document_type = AsyncMock(return_value=None)
    service._run_retrievers = AsyncMock(return_value=([], []))
    service._search_memory = AsyncMock(return_value=[])
    service._load_document_meta = AsyncMock(return_value={})
    service._record_usage = AsyncMock()
    service._build_chunks = lambda **_kw: list(chunks)
    return service


async def test_provider_drop_removes_chunks(_enabled, monkeypatch):
    fake_session = MagicMock()
    fake_session.scalar = AsyncMock(return_value=None)
    workspace = SimpleNamespace(id=7, user_id=None)
    chunks = [_provider_chunk("keep", 1), _provider_chunk("drop me", 2)]
    service = _stubbed_search_service(fake_session, chunks)

    async def _fake_filter(items, **_kwargs):
        return (
            [
                (
                    c,
                    _verdict(
                        GuardrailAction.DROP
                        if "drop" in t
                        else GuardrailAction.PASS
                    ),
                )
                for c, t in items
            ],
            None,
        )

    monkeypatch.setattr(pp, "filter_passages", _fake_filter)
    monkeypatch.setattr(pp, "embed_text", lambda _t: [0.1] * 8)
    monkeypatch.setattr(
        pp, "set_request_tenant_context", AsyncMock()
    )

    response = await service.search(_make_request(), workspace)
    assert [c.content for c in response.chunks] == ["keep"]


async def test_provider_mask_rewrites_chunk_content(_enabled, monkeypatch):
    fake_session = MagicMock()
    workspace = SimpleNamespace(id=7, user_id=None)
    chunks = [_provider_chunk("sensitive", 1)]
    service = _stubbed_search_service(fake_session, chunks)

    _patch_filter(
        pp,
        monkeypatch,
        lambda _c, _t: _verdict(GuardrailAction.MASK, masked="MASKED"),
    )
    monkeypatch.setattr(pp, "embed_text", lambda _t: [0.1] * 8)
    monkeypatch.setattr(pp, "set_request_tenant_context", AsyncMock())

    response = await service.search(_make_request(), workspace)
    assert response.chunks[0].content == "MASKED"


async def test_provider_flags_off_skips_filter(monkeypatch):
    monkeypatch.setenv("DECISION_ENABLED", "false")
    fake_session = MagicMock()
    workspace = SimpleNamespace(id=7, user_id=None)
    chunks = [_provider_chunk("raw", 1)]
    service = _stubbed_search_service(fake_session, chunks)

    async def _boom(*_a, **_k):
        raise AssertionError("filter must not run when flags off")

    monkeypatch.setattr(pp, "filter_passages", _boom)
    monkeypatch.setattr(pp, "embed_text", lambda _t: [0.1] * 8)
    monkeypatch.setattr(pp, "set_request_tenant_context", AsyncMock())

    response = await service.search(_make_request(), workspace)
    assert [c.content for c in response.chunks] == ["raw"]


async def test_provider_irrelevant_demotes_not_drops(_enabled, monkeypatch):
    """Relevance-negative chunk sinks to the tail; injection still drops."""
    fake_session = MagicMock()
    workspace = SimpleNamespace(id=7, user_id=None)
    chunks = [
        _provider_chunk("inject this", 1),
        _provider_chunk("good hit", 2),
        _provider_chunk("weak match", 3),
    ]
    service = _stubbed_search_service(fake_session, chunks)

    async def _fake_filter(items, **_kwargs):
        def _route(_c, text):
            if "inject" in text:
                return _verdict(GuardrailAction.DROP)
            if "weak" in text:
                return PassageVerdict(
                    action=GuardrailAction.DROP, reasons=("irrelevant",)
                )
            return _verdict(GuardrailAction.PASS)

        return ([(c, _route(c, t)) for c, t in items], None)

    monkeypatch.setattr(pp, "filter_passages", _fake_filter)
    monkeypatch.setattr(pp, "embed_text", lambda _t: [0.1] * 8)
    monkeypatch.setattr(pp, "set_request_tenant_context", AsyncMock())

    response = await service.search(_make_request(), workspace)
    assert [c.content for c in response.chunks] == ["good hit", "weak match"]


async def test_provider_filter_raise_returns_chunks(_enabled, monkeypatch):
    """Fail-open: filter_passages raising must not 500 the search."""
    fake_session = MagicMock()
    workspace = SimpleNamespace(id=7, user_id=None)
    chunks = [_provider_chunk("a", 1), _provider_chunk("b", 2)]
    service = _stubbed_search_service(fake_session, chunks)

    async def _boom(*_a, **_k):
        raise RuntimeError("guardrail exploded")

    monkeypatch.setattr(pp, "filter_passages", _boom)
    monkeypatch.setattr(pp, "embed_text", lambda _t: [0.1] * 8)
    monkeypatch.setattr(pp, "set_request_tenant_context", AsyncMock())

    response = await service.search(_make_request(), workspace)
    assert [c.content for c in response.chunks] == ["a", "b"]
