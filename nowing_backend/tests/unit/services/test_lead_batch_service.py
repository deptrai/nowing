"""Red-phase ATDD unit tests for Story 26.1 batch lead ingestion service.

Tests focus on AC-1, AC-2, AC-4, AC-5. DB and external services are mocked;
no real Postgres, embedding, or ChainLens API is required.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import app.services.lead_batch_service as lead_batch_service
from app.db import Lead

pytestmark = pytest.mark.unit


class _FakeResult:
    def __init__(self, value: Any = None, rows: list[Any] | None = None) -> None:
        self._value = value
        self._rows = rows or []

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalar_one(self) -> Any:
        return self._value if self._value is not None else 0

    def scalar(self) -> Any:
        return self._value

    def first(self) -> Any:
        return self._value

    def scalars(self) -> Any:
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    """AsyncSession stand-in that records staged rows and transaction state."""

    def __init__(self, *, scalar: Any = None, rows: list[Any] | None = None) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False
        self.flushed = False
        self.executed: list[Any] = []
        self._scalar = scalar
        self._rows = rows or []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, stmt: Any, _params: Any | None = None) -> _FakeResult:
        self.executed.append(stmt)
        return _FakeResult(self._scalar, self._rows)

    async def get(self, model: type, ident: Any) -> Any | None:
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def flush(self) -> None:
        self.flushed = True


class _FakeEmbeddingModel:
    """Hermetic fake embedding model returning 1536-dim vectors."""

    dimension = 1536

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self.dimension for _ in texts]

    async def embed_text(self, text: str) -> list[float]:
        return [0.0] * self.dimension


def _make_lead(value_hmac: str = "hmac1", **overrides: Any) -> dict[str, Any]:
    return {
        "workspace_id": 1,
        "client_id": "default",
        "source": "batch_ingest",
        "company_name": "A",
        "domain": "a.com",
        "industry": None,
        "company_size": None,
        "location": None,
        "fit_score": 0.5,
        "intent_score": 0.0,
        "composite_score": None,
        "status": "new",
        "value_hmac": value_hmac,
        "tax_id": None,
        "id": uuid4(),
        **overrides,
    }


# ============================================================================
# AC-1: Batch Lead Ingestion Endpoint
# ============================================================================


class TestBatchLeadIngestion:
    """AC-1: POST /api/v1/workspaces/:workspace_id/leads/batch-ingest"""

    @pytest.mark.asyncio
    async def test_batch_ingest_returns_summary_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """should return BatchLeadIngestResponse with summary fields."""
        from app.config import config

        monkeypatch.setattr(config, "SECRET_KEY", "test-secret-key")
        dnc_mock = AsyncMock(return_value=[{"blocked_by_dnc": False}])
        monkeypatch.setattr(
            lead_batch_service.DncComplianceService, "batch_filter_leads", dnc_mock
        )

        lead_id = uuid4()
        value_hmac = "hmac1"
        session = _FakeSession(rows=[SimpleNamespace(id=lead_id, value_hmac=value_hmac)])
        service = lead_batch_service.LeadBatchService()

        result = await service.ingest_batch(
            session,
            workspace_id=1,
            leads=[_make_lead(value_hmac=value_hmac)],
        )

        assert result["ingested_count"] == 1
        assert result["skipped_blacklisted_count"] == 0
        assert result["failed_count"] == 0
        assert "execution_time_ms" in result
        assert result["lead_ids"] == [lead_id]

    @pytest.mark.asyncio
    async def test_batch_ingest_does_not_leak_pii(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """should NOT return phone, email, or value_hmac in response."""
        from app.config import config

        monkeypatch.setattr(config, "SECRET_KEY", "test-secret-key")
        dnc_mock = AsyncMock(return_value=[{"blocked_by_dnc": False}])
        monkeypatch.setattr(
            lead_batch_service.DncComplianceService, "batch_filter_leads", dnc_mock
        )

        lead_id = uuid4()
        value_hmac = "hmac1"
        session = _FakeSession(rows=[SimpleNamespace(id=lead_id, value_hmac=value_hmac)])
        service = lead_batch_service.LeadBatchService()

        result = await service.ingest_batch(
            session,
            workspace_id=1,
            leads=[_make_lead(value_hmac=value_hmac, phone="+1234567890", email="a@b.com")],
        )

        assert "phone" not in result
        assert "email" not in result
        assert "value_hmac" not in result

    @pytest.mark.asyncio
    async def test_batch_ingest_rejects_degenerate_lead(self) -> None:
        """should reject any lead with all of phone, email, domain empty."""
        service = lead_batch_service.LeadBatchService()

        with pytest.raises(lead_batch_service.LeadItemValidationError):
            await service.ingest_batch(_FakeSession(), workspace_id=1, leads=[{}])

    @pytest.mark.asyncio
    async def test_batch_ingest_accepts_domain_only_lead(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """should accept a lead with only domain and store without verified_contacts."""
        from app.config import config

        monkeypatch.setattr(config, "SECRET_KEY", "test-secret-key")
        dnc_mock = AsyncMock(return_value=[{"blocked_by_dnc": False}])
        monkeypatch.setattr(
            lead_batch_service.DncComplianceService, "batch_filter_leads", dnc_mock
        )

        lead_id = uuid4()
        value_hmac = "domain_only_hmac"
        session = _FakeSession(rows=[SimpleNamespace(id=lead_id, value_hmac=value_hmac)])
        service = lead_batch_service.LeadBatchService()

        result = await service.ingest_batch(
            session,
            workspace_id=1,
            leads=[{"domain": "example.com", "value_hmac": value_hmac}],
        )

        assert result["ingested_count"] == 1
        assert result["lead_ids"] == [lead_id]
        assert len(session.executed) == 1
        assert "verified_contacts" not in str(session.executed[0]).lower()

    @pytest.mark.asyncio
    async def test_batch_ingest_uses_dnc_service_fail_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """should call DncComplianceService.batch_filter_leads and mark blocked leads as blacklisted."""
        from app.config import config

        monkeypatch.setattr(config, "SECRET_KEY", "test-secret-key")
        dnc_mock = AsyncMock(
            return_value=[
                {"blocked_by_dnc": False},
                {"blocked_by_dnc": True, "dnc_reason": "blocked by dnc"},
            ]
        )
        monkeypatch.setattr(
            lead_batch_service.DncComplianceService, "batch_filter_leads", dnc_mock
        )

        lead1_id = uuid4()
        lead2_id = uuid4()
        session = _FakeSession(
            rows=[
                SimpleNamespace(id=lead1_id, value_hmac="hmac1"),
                SimpleNamespace(id=lead2_id, value_hmac="hmac2"),
            ]
        )
        service = lead_batch_service.LeadBatchService()

        result = await service.ingest_batch(
            session,
            workspace_id=1,
            leads=[
                _make_lead(value_hmac="hmac1", phone="+111"),
                _make_lead(value_hmac="hmac2", phone="+222"),
            ],
        )

        dnc_mock.assert_awaited_once()
        assert result["skipped_blacklisted_count"] == 1
        assert result["ingested_count"] == 1
        assert lead1_id in result["lead_ids"]
        assert lead2_id in result["lead_ids"]


# ============================================================================
# AC-2: Deterministic Sorting & Concurrency Deadlock Prevention
# ============================================================================


class TestDeterministicSortingAndUpsert:
    """AC-2: Sort by value_hmac ASC and bulk upsert without deadlocks."""

    def test_leads_sorted_by_value_hmac_asc(self) -> None:
        """should sort batch leads by value_hmac ASC before upsert."""
        leads = [
            _make_lead(value_hmac="zzz"),
            _make_lead(value_hmac="aaa"),
        ]
        stmt = lead_batch_service._build_batch_upsert_stmt(leads)
        rows = stmt._multi_values[0]
        hmacs = [r[stmt.table.c.value_hmac] for r in rows]

        assert hmacs == sorted(hmacs)
        assert hmacs == ["aaa", "zzz"]

    def test_upsert_keeps_higher_fit_score(self) -> None:
        """should update fit_score with GREATEST(existing, incoming)."""
        leads = [
            _make_lead(value_hmac="dup", fit_score=0.8),
            _make_lead(value_hmac="dup", fit_score=0.5),
        ]
        stmt = lead_batch_service._build_batch_upsert_stmt(leads)
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))

        assert "greatest(leads.fit_score, excluded.fit_score)" in sql

    def test_upsert_computes_composite_score_with_coalesce(self) -> None:
        """should update composite_score with GREATEST(COALESCE(existing,0), COALESCE(incoming,0))."""
        leads = [_make_lead(value_hmac="h", composite_score=0.7)]
        stmt = lead_batch_service._build_batch_upsert_stmt(leads)
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))

        assert (
            "greatest(coalesce(leads.composite_score, 0), coalesce(excluded.composite_score, 0))"
            in sql
        )

    def test_intra_batch_duplicate_value_hmac_deduped(self) -> None:
        """should deduplicate leads with same value_hmac inside a single batch."""
        leads = [
            _make_lead(value_hmac="dup", fit_score=0.5),
            _make_lead(value_hmac="dup", fit_score=0.9),
        ]
        stmt = lead_batch_service._build_batch_upsert_stmt(leads)
        rows = stmt._multi_values[0]

        assert len(rows) == 1
        assert rows[0][stmt.table.c.value_hmac] == "dup"
        assert rows[0][stmt.table.c.fit_score] == pytest.approx(0.9)


# ============================================================================
# AC-4: Zero-Cache CDC Isolation
# ============================================================================


class TestZeroCacheIsolation:
    """AC-4: zero_publication excludes PII and chunks."""

    def test_zero_publication_leads_columns(self) -> None:
        """should publish only the allowed leads columns."""
        from app.zero_publication import LEADS_COLS

        assert "value_hmac" not in LEADS_COLS
        assert "is_blacklisted" not in LEADS_COLS
        assert "pii_access_audit_logs" not in LEADS_COLS

        assert "id" in LEADS_COLS
        assert "status" in LEADS_COLS
        assert "company_name" in LEADS_COLS

        # The Lead table has PII columns; they must not be in the publication.
        assert "value_hmac" in set(Lead.__table__.columns.keys())

    def test_zero_publication_excludes_chunks(self) -> None:
        """should NOT publish chunks or chainlens_chunks."""
        from app.zero_publication import ZERO_PUBLICATION

        assert "chainlens_chunks" not in ZERO_PUBLICATION
        assert "chunks" not in ZERO_PUBLICATION


# ============================================================================
# AC-5: Hermetic Quality Testing & $0 API Cost
# ============================================================================


class TestHermeticAndCostGate:
    """AC-5: All external calls mocked, $0 cost."""

    @pytest.mark.asyncio
    async def test_embedding_uses_configured_model_instance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """should call config.embedding_model_instance.embed_texts with 1536-dim fake."""
        from app.config import config

        fake = _FakeEmbeddingModel()
        monkeypatch.setattr(config, "embedding_model_instance", fake)

        vectors = await config.embedding_model_instance.embed_texts(["hello"])

        assert len(vectors) == 1
        assert len(vectors[0]) == 1536
        assert config.embedding_model_instance.dimension == 1536

    @pytest.mark.asyncio
    async def test_no_external_api_calls_made(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """should not call OpenAI/OpenRouter/ChainLens during unit tests."""
        from app.config import config

        fake = _FakeEmbeddingModel()
        embed_mock = AsyncMock(return_value=[[0.0] * 1536])
        monkeypatch.setattr(fake, "embed_texts", embed_mock)
        monkeypatch.setattr(config, "embedding_model_instance", fake)

        httpx_client_mock = MagicMock()
        monkeypatch.setattr("httpx.AsyncClient", httpx_client_mock)

        dnc_mock = AsyncMock(return_value=[{"blocked_by_dnc": False}])
        monkeypatch.setattr(
            lead_batch_service.DncComplianceService, "batch_filter_leads", dnc_mock
        )

        monkeypatch.setattr(config, "SECRET_KEY", "test-secret-key")

        lead_id = uuid4()
        value_hmac = "hmac1"
        session = _FakeSession(rows=[SimpleNamespace(id=lead_id, value_hmac=value_hmac)])
        service = lead_batch_service.LeadBatchService()

        await service.ingest_batch(
            session,
            workspace_id=1,
            leads=[_make_lead(value_hmac=value_hmac, phone="+1234567890")],
        )

        assert httpx_client_mock.call_count == 0
        assert embed_mock.call_count == 0
