"""_filter_rag_results — RAG doc guardrail wiring (Story 39.4)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.services.connectors.search.core as core
from app.services.content_guardrails import GuardrailAction, PassageVerdict

pytestmark = pytest.mark.unit


def _doc(content: str, chunks: list[str] | None = None) -> dict:
    return {
        "content": content,
        "chunks": [{"content": c} for c in (chunks or [])],
        "document_id": 1,
    }


@pytest.fixture
def _enabled(monkeypatch):
    monkeypatch.setenv("DECISION_ENABLED", "true")
    monkeypatch.setenv("DECISION_FILTER_ENABLED", "true")


def _patch_filter(monkeypatch, route):
    """Stub filter_passages: route(item, text) -> PassageVerdict."""

    async def _fake(items, **_kwargs):
        return (
            [(item, route(item, text)) for item, text in items],
            None,
        )

    monkeypatch.setattr(core, "filter_passages", _fake)


async def test_flags_off_returns_input_untouched(monkeypatch):
    monkeypatch.setenv("DECISION_ENABLED", "false")
    docs = [_doc("a"), _doc("b")]

    async def _boom(*_a, **_k):
        raise AssertionError("filter_passages must not run when flags off")

    monkeypatch.setattr(core, "filter_passages", _boom)
    out = await core._filter_rag_results(
        docs, query_text="q", workspace_id=1
    )
    assert out == docs


async def test_drop_removes_doc(_enabled, monkeypatch):
    def _route(_doc, _text):
        return PassageVerdict(
            action=GuardrailAction.DROP, reasons=("prompt_injection",)
        )

    _patch_filter(monkeypatch, _route)
    out = await core._filter_rag_results(
        [_doc("bad"), _doc("also dropped")], query_text="q", workspace_id=1
    )
    assert out == []


async def test_irrelevant_drop_demotes_to_tail(_enabled, monkeypatch):
    """Relevance-negative demotes instead of dropping — recall-safe fix
    for Jev over-dropping VN content lacking literal query geo terms."""

    def _route(_doc, text):
        if "off-topic" in text:
            return PassageVerdict(
                action=GuardrailAction.DROP, reasons=("irrelevant",)
            )
        return PassageVerdict(action=GuardrailAction.PASS)

    _patch_filter(monkeypatch, _route)
    docs = [_doc("keep one"), _doc("off-topic"), _doc("keep two")]
    out = await core._filter_rag_results(docs, query_text="q", workspace_id=1)
    assert [d["content"] for d in out] == [
        "keep one",
        "keep two",
        "off-topic",
    ]


async def test_injection_still_hard_drops_when_mixed(_enabled, monkeypatch):
    """Mixed batch: injection removed entirely, irrelevant demoted."""

    def _route(_doc, text):
        if "inject" in text:
            return PassageVerdict(
                action=GuardrailAction.DROP, reasons=("prompt_injection",)
            )
        if "weak" in text:
            return PassageVerdict(
                action=GuardrailAction.DROP, reasons=("irrelevant",)
            )
        return PassageVerdict(action=GuardrailAction.PASS)

    _patch_filter(monkeypatch, _route)
    docs = [_doc("inject me"), _doc("good"), _doc("weak match")]
    out = await core._filter_rag_results(docs, query_text="q", workspace_id=1)
    assert [d["content"] for d in out] == ["good", "weak match"]


async def test_mask_rewrites_doc_and_chunk_fields_separately(
    _enabled, monkeypatch
):
    """MASK: parent content gets masked_text; each chunk masked per-field."""

    def _route(_doc, _text):
        return PassageVerdict(
            action=GuardrailAction.MASK,
            reasons=("sensitive",),
            masked_text="MASKED-PARENT",
        )

    _patch_filter(monkeypatch, _route)
    doc = _doc("call 0901234567 now", chunks=["phone 0901234567"])
    out = await core._filter_rag_results(
        [doc], query_text="q", workspace_id=1
    )
    assert len(out) == 1
    assert out[0]["content"] == "MASKED-PARENT"
    # Nested chunk masked via redact_pii — NOT the concatenated masked_text.
    assert "0901234567" not in out[0]["chunks"][0]["content"]
    assert out[0]["chunks"][0]["content"] != "MASKED-PARENT"


async def test_pass_keeps_doc(_enabled, monkeypatch):
    _patch_filter(
        monkeypatch, lambda _d, _t: PassageVerdict(action=GuardrailAction.PASS)
    )
    docs = [_doc("fine")]
    out = await core._filter_rag_results(docs, query_text="q", workspace_id=1)
    assert out == docs


async def test_query_and_surface_forwarded(_enabled, monkeypatch):
    seen: dict = {}

    async def _fake(items, *, query, surface, **_kwargs):
        seen["query"] = query
        seen["surface"] = surface
        return ([(i, PassageVerdict(action=GuardrailAction.PASS)) for i, _ in items], None)

    monkeypatch.setattr(core, "filter_passages", _fake)
    await core._filter_rag_results(
        [_doc("x")], query_text="nhà Q7", workspace_id=1
    )
    assert seen == {"query": "nhà Q7", "surface": "rag"}


async def test_filter_failure_returns_unfiltered(_enabled, monkeypatch):
    """Fail-open: an exception inside the filter must not 500 the search."""

    async def _boom(*_a, **_k):
        raise RuntimeError("guardrail exploded")

    monkeypatch.setattr(core, "filter_passages", _boom)
    docs = [_doc("a"), _doc("b")]
    out = await core._filter_rag_results(docs, query_text="q", workspace_id=1)
    assert out == docs


async def test_mask_without_masked_text_drops_doc(_enabled, monkeypatch):
    """MASK + empty masked_text → drop, never pass unmasked (mask_failed parity)."""
    _patch_filter(
        monkeypatch,
        lambda _d, _t: PassageVerdict(
            action=GuardrailAction.MASK, masked_text=None
        ),
    )
    out = await core._filter_rag_results(
        [_doc("sensitive")], query_text="q", workspace_id=1
    )
    assert out == []


async def test_combined_rrf_search_invokes_guardrail_filter(
    _enabled, monkeypatch
):
    """Wire check: deleting the _filter_rag_results call must fail this."""
    seen: dict = {}

    async def _spy(results, *, query_text, workspace_id):
        seen.update(query_text=query_text, n=len(results))
        return results[:-1]  # pretend the last doc was dropped

    monkeypatch.setattr(core, "_filter_rag_results", _spy)

    chunk_results = [
        {"document": {"id": 1}, "chunks": [{"content": "a"}]}
    ]
    doc_results = [{"document": {"id": 2}, "chunks": [{"content": "b"}]}]

    class _CM:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, *_exc):
            return False

    monkeypatch.setattr(core, "async_session_maker", lambda: _CM())
    monkeypatch.setattr(
        core,
        "ChunksHybridSearchRetriever",
        lambda _s: SimpleNamespace(
            hybrid_search=AsyncMock(return_value=chunk_results)
        ),
    )
    monkeypatch.setattr(
        core,
        "DocumentHybridSearchRetriever",
        lambda _s: SimpleNamespace(
            hybrid_search=AsyncMock(return_value=doc_results)
        ),
    )

    service = core.ConnectorSearchCore(MagicMock())
    out = await service._combined_rrf_search(
        query_text="nhà Q7",
        workspace_id=1,
        document_type="FILE",
        top_k=10,
        query_embedding=[0.1] * 8,
    )
    assert seen == {"query_text": "nhà Q7", "n": 2}
    assert len(out) == 1
