"""Vietstock → Chunk[] normalization tests."""

from __future__ import annotations

import pytest

from app.proprietary.platforms.vietstock.schemas import VietstockQuote
from app.services.scraper_chunks.serializer import to_chunks

pytestmark = pytest.mark.unit


def test_quote_to_chunks_has_canonical_source_id() -> None:
    """Mirror: chunk metadata must include stable sourceId."""
    quote = VietstockQuote(
        symbol="VNM",
        current_price=75000.0,
    )
    chunks = to_chunks(
        domain="vietstock",
        data=quote.model_dump(),
        fetched_at="2026-08-15T00:00:00Z",
        content_type="text/markdown",
        category="quote",
    )
    assert len(chunks) > 0
    assert chunks[0].metadata.sourceId.startswith("vietstock:sha256:")
    assert chunks[0].metadata.domain == "vietstock"
    assert chunks[0].metadata.source == "nowing_scraper"


def test_quote_to_chunks_includes_ratios() -> None:
    """Mirror: chunk metadata.ratios contains pe, pb, roe, roa."""
    quote = VietstockQuote(
        symbol="VNM",
        current_price=75000.0,
        key_ratios={"pe": 15.2, "pb": 2.1, "roe": 18.5, "roa": 10.2},
    )
    chunks = to_chunks(
        domain="vietstock",
        data=quote.model_dump(),
        fetched_at="2026-08-15T00:00:00Z",
        content_type="text/markdown",
        category="quote",
    )
    assert chunks[0].metadata.ratios == {"pe": 15.2, "pb": 2.1, "roe": 18.5, "roa": 10.2}


def test_financial_to_chunks_sets_conflict_and_source_count() -> None:
    """Mirror: chunk metadata contains conflict_flags and source_count."""
    record = {
        "symbol": "VNM",
        "statement_type": "balance_sheet",
        "period": "Q4-2025",
        "content": "...",
        "conflict_flags": True,
        "source_count": 2,
    }
    chunks = to_chunks(
        domain="vietstock",
        data=record,
        fetched_at="2026-08-15T00:00:00Z",
        content_type="text/markdown",
        category="financial_statement",
    )
    assert chunks[0].metadata.conflict_flags is True
    assert chunks[0].metadata.source_count == 2


def test_cross_source_source_id_matches_cafef() -> None:
    """Arithmetic: same (symbol, statement_type, period) produces same hash for both sources."""
    record = {
        "symbol": "VNM",
        "statement_type": "balance_sheet",
        "period": "Q4-2025",
    }
    vietstock_chunks = to_chunks(
        domain="vietstock",
        data=record,
        fetched_at="2026-08-15T00:00:00Z",
        content_type="text/markdown",
        category="financial_statement",
    )
    cafef_chunks = to_chunks(
        domain="cafef",
        data=record,
        fetched_at="2026-08-15T00:00:00Z",
        content_type="text/markdown",
        category="financial_statement",
    )
    v_id = vietstock_chunks[0].metadata.sourceId
    c_id = cafef_chunks[0].metadata.sourceId
    assert v_id.split(":")[2] == c_id.split(":")[2]
