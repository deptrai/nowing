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
from sqlalchemy import Select

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

    def __init__(
        self,
        *,
        scalar: Any = None,
        rows: list[Any] | None = None,
        table_rows: list[Any] | None = None,
    ) -> None:
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False
        self.flushed = False
        self.executed: list[Any] = []
        self._scalar = scalar
        self._rows = rows or []
        self._table_rows = table_rows or []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, stmt: Any, _params: Any | None = None) -> _FakeResult:
        self.executed.append(stmt)
        # Plain SELECTs (e.g. the verified_contacts client_id FK guard) see
        # no rows; the leads upsert RETURNING keeps the fixture rows.
        if isinstance(stmt, Select):
            return _FakeResult(self._scalar, [])
        if getattr(getattr(stmt, "table", None), "name", None) == "workspace_tables":
            # Story 42.7 get-or-create INSERT: default = no row created (race
            # simulation); tests override via ``table_rows`` when needed.
            return _FakeResult(None, self._table_rows)
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
    async def test_batch_ingest_returns_summary_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """should return BatchLeadIngestResponse with summary fields."""
        from app.config import config

        monkeypatch.setattr(config, "SECRET_KEY", "test-secret-key")
        dnc_mock = AsyncMock(return_value=[{"blocked_by_dnc": False}])
        monkeypatch.setattr(
            lead_batch_service.DncComplianceService, "batch_filter_leads", dnc_mock
        )

        lead_id = uuid4()
        value_hmac = "hmac1"
        session = _FakeSession(
            rows=[SimpleNamespace(id=lead_id, value_hmac=value_hmac)]
        )
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
    async def test_batch_ingest_does_not_leak_pii(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """should NOT return phone, email, or value_hmac in response."""
        from app.config import config

        monkeypatch.setattr(config, "SECRET_KEY", "test-secret-key")
        dnc_mock = AsyncMock(return_value=[{"blocked_by_dnc": False}])
        monkeypatch.setattr(
            lead_batch_service.DncComplianceService, "batch_filter_leads", dnc_mock
        )

        lead_id = uuid4()
        value_hmac = "hmac1"
        session = _FakeSession(
            rows=[SimpleNamespace(id=lead_id, value_hmac=value_hmac)]
        )
        service = lead_batch_service.LeadBatchService()

        result = await service.ingest_batch(
            session,
            workspace_id=1,
            leads=[
                _make_lead(value_hmac=value_hmac, phone="+1234567890", email="a@b.com")
            ],
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
    async def test_batch_ingest_accepts_domain_only_lead(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """should accept a lead with only domain and store without verified_contacts."""
        from app.config import config

        monkeypatch.setattr(config, "SECRET_KEY", "test-secret-key")
        dnc_mock = AsyncMock(return_value=[{"blocked_by_dnc": False}])
        monkeypatch.setattr(
            lead_batch_service.DncComplianceService, "batch_filter_leads", dnc_mock
        )

        lead_id = uuid4()
        value_hmac = "domain_only_hmac"
        session = _FakeSession(
            rows=[SimpleNamespace(id=lead_id, value_hmac=value_hmac)]
        )
        service = lead_batch_service.LeadBatchService()

        result = await service.ingest_batch(
            session,
            workspace_id=1,
            leads=[{"domain": "example.com", "value_hmac": value_hmac}],
        )

        assert result["ingested_count"] == 1
        assert result["lead_ids"] == [lead_id]
        # Story 42.7: ingest now also issues workspace_tables statements before
        # the leads upsert — assert by intent, not by statement count.
        executed_sql = [str(stmt).lower() for stmt in session.executed]
        assert not any("verified_contacts" in s for s in executed_sql)
        assert any("workspace_tables" in s for s in executed_sql)

    @pytest.mark.asyncio
    async def test_batch_ingest_uses_dnc_service_fail_closed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
    async def test_embedding_uses_configured_model_instance(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """should call config.embedding_model_instance.embed_texts with 1536-dim fake."""
        from app.config import config

        fake = _FakeEmbeddingModel()
        monkeypatch.setattr(config, "embedding_model_instance", fake)

        vectors = await config.embedding_model_instance.embed_texts(["hello"])

        assert len(vectors) == 1
        assert len(vectors[0]) == 1536
        assert config.embedding_model_instance.dimension == 1536

    @pytest.mark.asyncio
    async def test_no_external_api_calls_made(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
        session = _FakeSession(
            rows=[SimpleNamespace(id=lead_id, value_hmac=value_hmac)]
        )
        service = lead_batch_service.LeadBatchService()

        await service.ingest_batch(
            session,
            workspace_id=1,
            leads=[_make_lead(value_hmac=value_hmac, phone="+1234567890")],
        )

        assert httpx_client_mock.call_count == 0
        assert embed_mock.call_count == 0


class TestExtraMetadataForwarding:
    """Story 41.2: ``extra_metadata`` (leads.metadata JSONB) survives ingest."""

    def test_prepare_lead_record_forwards_extra_metadata(self) -> None:
        record = lead_batch_service._prepare_lead_record(
            1,
            {
                "company_name": "Acme",
                "extra_metadata": {"websets": {"opening_hours": {"value": "9-18"}}},
            },
            "test-secret",
        )
        assert record["extra_metadata"] == {
            "websets": {"opening_hours": {"value": "9-18"}}
        }

    def test_prepare_lead_record_metadata_fallback(self) -> None:
        record = lead_batch_service._prepare_lead_record(
            1,
            {"company_name": "Acme", "metadata": {"websets": {"col": "v"}}},
            "test-secret",
        )
        assert record["extra_metadata"] == {"websets": {"col": "v"}}

    def test_upsert_set_includes_extra_metadata(self) -> None:
        leads = [_make_lead(value_hmac="h", extra_metadata={"websets": {"c": 1}})]
        stmt = lead_batch_service._build_batch_upsert_stmt(leads)
        sql = str(stmt.compile())
        # JSONB merge (existing || excluded): excluded keys win, existing keys
        # survive — a bare coalesce(excluded, existing) would wipe old metadata.
        assert "coalesce(leads.metadata" in sql
        assert "coalesce(excluded.metadata" in sql
        assert "||" in sql

    @pytest.mark.asyncio
    async def test_batch_ingest_degenerate_collects_all_indexes(self) -> None:
        """422 payload lists every degenerate index, not just the first."""
        service = lead_batch_service.LeadBatchService()

        with pytest.raises(lead_batch_service.LeadItemValidationError) as exc_info:
            await service.ingest_batch(
                _FakeSession(),
                workspace_id=1,
                leads=[{"domain": "ok.com"}, {}, {"domain": "ok2.com"}, {}],
            )

        err = exc_info.value
        assert err.rejected_indexes == [1, 3]
        assert set(err.reason_map) == {1, 3}
        payload = err.as_payload()
        assert payload["status"] == "failed"
        assert payload["rejected_indexes"] == [1, 3]
        assert set(payload["reason_map"]) == {"1", "3"}


# ============================================================================
# Story 42.7: auto-table resolution in ingest_batch
# ============================================================================


def _stub_dnc(monkeypatch: pytest.MonkeyPatch, count: int = 1) -> None:
    from app.config import config

    monkeypatch.setattr(config, "SECRET_KEY", "test-secret-key")
    dnc_mock = AsyncMock(return_value=[{"blocked_by_dnc": False}] * count)
    monkeypatch.setattr(
        lead_batch_service.DncComplianceService, "batch_filter_leads", dnc_mock
    )


class _AutoTableFakeSession(_FakeSession):
    """Fake session aware of the three workspace_tables SELECTs (42.7).

    Distinguishes statements by their compiled SQL:
    - existence check:   SELECT workspace_tables.id ... id IN (...)
    - keys check:        SELECT workspace_tables.key ... key IN (...)  (scalars)
    - race re-SELECT:    SELECT workspace_tables.key, workspace_tables.id (rows)
    Non-Select workspace_tables statements are the ON CONFLICT INSERT →
    returns ``insert_returning`` rows; the leads upsert gets ``lead_rows``.
    """

    def __init__(
        self,
        *,
        existing_ids: list[UUID] | None = None,
        existing_keys: list[str] | None = None,
        reselect_rows: list[SimpleNamespace] | None = None,
        insert_returning: list[SimpleNamespace] | None = None,
        lead_rows: list[SimpleNamespace] | None = None,
    ) -> None:
        super().__init__(rows=lead_rows or [])
        self._existing_ids = existing_ids or []
        self._existing_keys = existing_keys or []
        self._reselect_rows = reselect_rows or []
        self._insert_returning = insert_returning or []
        self._lead_rows = lead_rows or []

    async def execute(self, stmt: Any, _params: Any | None = None) -> _FakeResult:
        self.executed.append(stmt)
        if isinstance(stmt, Select):
            sql = str(stmt)
            if "workspace_tables" not in sql:
                return _FakeResult(None, [])
            if "workspace_tables.key, workspace_tables.id" in sql:
                return _FakeResult(None, self._reselect_rows)
            if "workspace_tables.key" in sql:
                return _FakeResult(None, self._existing_keys)  # scalars().all()
            return _FakeResult(None, self._existing_ids)  # scalars().all()
        if getattr(getattr(stmt, "table", None), "name", None) == "workspace_tables":
            return _FakeResult(None, self._insert_returning)
        return _FakeResult(None, self._lead_rows)


class TestAutoTableResolution:
    """Story 42.7: absent/stale table_id → default WorkspaceTable per client_id."""

    @pytest.mark.asyncio
    async def test_absent_table_id_creates_default_table(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ingest with no table_id issues an ON CONFLICT DO NOTHING insert."""
        _stub_dnc(monkeypatch)
        new_table_id = uuid4()
        lead_id = uuid4()
        session = _AutoTableFakeSession(
            insert_returning=[SimpleNamespace(id=new_table_id, key="default")],
            lead_rows=[SimpleNamespace(id=lead_id, value_hmac="hmac1")],
        )
        service = lead_batch_service.LeadBatchService()

        await service.ingest_batch(session, workspace_id=1, leads=[_make_lead()])

        table_inserts = [
            s
            for s in session.executed
            if not isinstance(s, Select)
            and getattr(getattr(s, "table", None), "name", None) == "workspace_tables"
        ]
        assert len(table_inserts) == 1
        sql = str(table_inserts[0]).upper()
        assert "ON CONFLICT" in sql and "DO NOTHING" in sql
        # The leads upsert carries the freshly created table id.
        upsert = [
            s for s in session.executed
            if not isinstance(s, Select) and getattr(s, "table", None) is not None and s.table.name == "leads"
        ]
        assert upsert, "leads upsert must run"
        lead_rows = upsert[0]._multi_values[0]
        assert lead_rows[0][upsert[0].table.c.table_id] == new_table_id

    @pytest.mark.asyncio
    async def test_existing_key_reuses_table_without_insert(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """key already present in the keys SELECT → no workspace_tables INSERT."""
        _stub_dnc(monkeypatch)
        default_table_id = uuid4()
        lead_id = uuid4()
        session = _AutoTableFakeSession(
            existing_keys=["default"],
            # Race re-SELECT seeds the key → id mapping used for assignment.
            reselect_rows=[SimpleNamespace(key="default", id=default_table_id)],
            lead_rows=[SimpleNamespace(id=lead_id, value_hmac="hmac1")],
        )
        service = lead_batch_service.LeadBatchService()

        await service.ingest_batch(session, workspace_id=1, leads=[_make_lead()])

        assert not any(
            not isinstance(s, Select)
            and getattr(getattr(s, "table", None), "name", None) == "workspace_tables"
            for s in session.executed
        ), "no workspace_tables INSERT when the key already exists"

        upsert = [
            s for s in session.executed
            if not isinstance(s, Select) and getattr(s, "table", None) is not None and s.table.name == "leads"
        ]
        assert upsert, "leads upsert must run"
        lead_rows = upsert[0]._multi_values[0]
        assert lead_rows[0][upsert[0].table.c.table_id] == default_table_id

    @pytest.mark.asyncio
    async def test_race_lost_insert_reselects(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """INSERT returning no rows (concurrent winner) → re-SELECT resolves."""
        _stub_dnc(monkeypatch)
        winner_table_id = uuid4()
        lead_id = uuid4()
        session = _AutoTableFakeSession(
            reselect_rows=[
                SimpleNamespace(key="default", id=winner_table_id)
            ],
            lead_rows=[SimpleNamespace(id=lead_id, value_hmac="hmac1")],
        )
        service = lead_batch_service.LeadBatchService()

        await service.ingest_batch(session, workspace_id=1, leads=[_make_lead()])

        upsert = [
            s for s in session.executed
            if not isinstance(s, Select) and getattr(s, "table", None) is not None and s.table.name == "leads"
        ]
        assert upsert, "leads upsert must still run"
        lead_rows = upsert[0]._multi_values[0]
        assert lead_rows[0][upsert[0].table.c.table_id] == winner_table_id

    @pytest.mark.asyncio
    async def test_valid_caller_table_id_preserved(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A caller-passed table_id that exists is never overwritten."""
        _stub_dnc(monkeypatch)
        caller_table_id = uuid4()
        lead_id = uuid4()
        session = _AutoTableFakeSession(
            existing_ids=[caller_table_id],
            lead_rows=[SimpleNamespace(id=lead_id, value_hmac="hmac1")],
        )
        service = lead_batch_service.LeadBatchService()

        await service.ingest_batch(
            session, workspace_id=1, leads=[_make_lead(table_id=caller_table_id)]
        )

        assert not any(
            not isinstance(s, Select)
            and getattr(getattr(s, "table", None), "name", None) == "workspace_tables"
            for s in session.executed
        ), "no workspace_tables INSERT when all table_ids are valid"

    @pytest.mark.asyncio
    async def test_str_table_id_from_save_leads_preserved(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """save_leads passes table_id as a str UUID — valid str is coerced and kept."""
        _stub_dnc(monkeypatch)
        caller_table_id = uuid4()
        lead_id = uuid4()
        session = _AutoTableFakeSession(
            existing_ids=[caller_table_id],
            lead_rows=[SimpleNamespace(id=lead_id, value_hmac="hmac1")],
        )
        service = lead_batch_service.LeadBatchService()

        await service.ingest_batch(
            session,
            workspace_id=1,
            leads=[_make_lead(table_id=str(caller_table_id))],
        )

        assert not any(
            not isinstance(s, Select)
            and getattr(getattr(s, "table", None), "name", None) == "workspace_tables"
            for s in session.executed
        ), "valid str table_id must be coerced and preserved"

    @pytest.mark.asyncio
    async def test_invalid_str_table_id_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A non-UUID str table_id is treated as absent → default table."""
        _stub_dnc(monkeypatch)
        default_table_id = uuid4()
        lead_id = uuid4()
        session = _AutoTableFakeSession(
            existing_keys=["default"],
            reselect_rows=[SimpleNamespace(key="default", id=default_table_id)],
            lead_rows=[SimpleNamespace(id=lead_id, value_hmac="hmac1")],
        )
        service = lead_batch_service.LeadBatchService()

        await service.ingest_batch(
            session, workspace_id=1, leads=[_make_lead(table_id="not-a-uuid")]
        )

        upsert = [
            s for s in session.executed
            if not isinstance(s, Select) and getattr(s, "table", None) is not None and s.table.name == "leads"
        ]
        assert upsert, "leads upsert must still run"
        lead_rows = upsert[0]._multi_values[0]
        assert lead_rows[0][upsert[0].table.c.table_id] == default_table_id

    @pytest.mark.asyncio
    async def test_stale_table_id_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """table_id pointing at a deleted row → default table, no FK crash."""
        _stub_dnc(monkeypatch)
        default_table_id = uuid4()
        stale_id = uuid4()
        lead_id = uuid4()
        session = _AutoTableFakeSession(
            existing_keys=["default"],
            reselect_rows=[
                SimpleNamespace(key="default", id=default_table_id)
            ],
            lead_rows=[SimpleNamespace(id=lead_id, value_hmac="hmac1")],
        )
        service = lead_batch_service.LeadBatchService()

        await service.ingest_batch(
            session, workspace_id=1, leads=[_make_lead(table_id=stale_id)]
        )

        upsert = [
            s for s in session.executed
            if not isinstance(s, Select) and getattr(s, "table", None) is not None and s.table.name == "leads"
        ]
        assert upsert, "leads upsert must still run"
        lead_rows = upsert[0]._multi_values[0]
        assert lead_rows[0][upsert[0].table.c.table_id] == default_table_id

    @pytest.mark.asyncio
    async def test_client_id_groups_get_distinct_keys(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two client_ids → two keys in one ON CONFLICT INSERT."""
        _stub_dnc(monkeypatch, count=2)
        lead_id = uuid4()
        session = _AutoTableFakeSession(
            insert_returning=[
                SimpleNamespace(id=uuid4(), key="campaign-a"),
                SimpleNamespace(id=uuid4(), key="campaign-b"),
            ],
            lead_rows=[SimpleNamespace(id=lead_id, value_hmac="hmac1")],
        )
        service = lead_batch_service.LeadBatchService()

        await service.ingest_batch(
            session,
            workspace_id=1,
            leads=[
                _make_lead(value_hmac="hmac1", client_id="campaign-a"),
                _make_lead(value_hmac="hmac2", client_id="campaign-b"),
            ],
        )

        inserts = [
            s
            for s in session.executed
            if not isinstance(s, Select)
            and getattr(getattr(s, "table", None), "name", None) == "workspace_tables"
        ]
        assert len(inserts) == 1
        keys = {row[inserts[0].table.c.key] for row in inserts[0]._multi_values[0]}
        assert keys == {"campaign-a", "campaign-b"}
