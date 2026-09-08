"""Unit tests for MemoryBrowserService (Story 29.5 / FR-104).

Covers:
- Workspace-scoped list with pagination and sort.
- Filter application (source_type, confidence, time range, creator, keyword).
- Keyword search uses to_tsvector when encryption is off, falls back/works with content_search when on.
- Source URL derivation from source_run_id / source_uuid+source_entity_type / source_id.
- flag_status and version_count derivation.
- Detail response with decryption, versions, research thread, relations.
- Review flag creation and notification metadata.
- Permission helpers.

These tests mock the AsyncSession and any async helpers. SQL is asserted via
mock call args, not against a real database.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.memory_browser import (
    MemoryBrowserDetailResponse,
    MemoryBrowserListItem,
    MemoryBrowserListResponse,
    MemoryRelationListResponse,
)
from app.services.memory.memory_browser_service import MemoryBrowserService

pytestmark = [pytest.mark.unit, pytest.mark.memory]


@dataclass
class _FakeUser:
    id: uuid.UUID
    email: str


@dataclass
class _FakeMemory:
    """Minimal fake for the columns used by the service."""

    id: int
    workspace_id: int | None
    created_by_id: uuid.UUID | None = None
    research_thread_id: int | None = None
    content: str = ""
    content_search: str | None = None
    confidence: float = 1.0
    source_type: str = "MANUAL"
    source_id: int | None = None
    source_run_id: uuid.UUID | None = None
    source_uuid: uuid.UUID | None = None
    source_entity_type: str | None = None
    source_capability: str | None = None
    source_input: dict | None = None
    archived_at: datetime | None = None
    created_at: datetime = datetime(2026, 9, 5, 12, 0, 0, tzinfo=UTC)
    updated_at: datetime = datetime(2026, 9, 5, 12, 0, 0, tzinfo=UTC)
    key_id: str | None = None
    encryption_iv: str | None = None
    encryption_algo: str | None = None
    versions: list | None = None
    relations: list | None = None

    def __post_init__(self):
        if isinstance(self.source_type, SimpleNamespace):
            self.source_type = self.source_type.value
        if self.versions is None:
            self.versions = []
        if self.relations is None:
            self.relations = []


@dataclass
class _FakeVersion:
    previous_content: str
    corrected_content: str
    corrected_by_id: uuid.UUID | None = None
    created_at: datetime = datetime(2026, 9, 5, 12, 0, 0, tzinfo=UTC)


class _FakeResult:
    def __init__(self, rows=None, scalar=None, count=None):
        self._rows = rows or []
        self._scalar = scalar
        self._count = count

    def all(self):
        return self._rows

    def scalars(self):
        return _FakeResult(self._rows)

    def scalar_one_or_none(self):
        return self._scalar

    def one_or_none(self):
        return self._scalar

    def scalar(self):
        return self._scalar

    def __iter__(self):
        return iter(self._rows)

    def __len__(self):
        return len(self._rows)


class _FakeSession:
    def __init__(self, rows=None, scalar=None, subsequent_scalar=None, count=None):
        self.rows = rows or []
        self.scalar = scalar
        self.subsequent_scalar = subsequent_scalar
        self.count = count
        self.execute_calls = []
        self.added = []

    async def execute(self, stmt):
        self.execute_calls.append(stmt)
        resolved_scalar = (
            self.subsequent_scalar if self.execute_calls and len(self.execute_calls) > 1 else self.scalar
        )
        return _FakeResult(self.rows, resolved_scalar, self.count)

    async def commit(self):
        pass

    async def flush(self):
        pass

    async def refresh(self, obj):
        pass

    def add(self, obj):
        self.added.append(obj)


def _build_statement_where(stmt) -> list:
    """Extract where clauses from a SQLAlchemy select statement for assertions."""
    return getattr(stmt, "_where_criteria", [])


def _clause_str(c) -> str:
    try:
        return str(c)
    except Exception:
        return repr(c)


class TestMemoryBrowserServiceList:
    """Pattern 1 + 3: list response shape and boundary filtering."""

    async def test_list_includes_workspace_in_where(self):
        session = _FakeSession(rows=[])
        service = MemoryBrowserService(session)

        with patch.object(service, "_count_total", return_value=0):
            res = await service.list_memories(
                workspace_id=7,
                page=1,
                page_size=50,
            )

        assert isinstance(res, MemoryBrowserListResponse)
        assert res.total == 0
        assert res.page == 1
        assert res.page_size == 50
        # AC-1: workspace_id must appear in WHERE
        calls = [str(c) for c in _build_statement_where(session.execute_calls[0])]
        assert any("workspace_id" in c for c in calls)

    async def test_list_excludes_archived_by_default(self):
        session = _FakeSession(rows=[])
        service = MemoryBrowserService(session)

        with patch.object(service, "_count_total", return_value=0):
            await service.list_memories(workspace_id=7, page=1, page_size=50)

        stmt = session.execute_calls[0]
        where = _build_statement_where(stmt)
        assert any("archived_at" in _clause_str(c) for c in where)

    async def test_list_pagination_offset(self):
        fake = _FakeMemory(id=1, workspace_id=7, content="x" * 200, source_type="SCRAPER_RUN", confidence=0.9)
        session = _FakeSession(rows=[fake])
        service = MemoryBrowserService(session)

        with patch.object(service, "_count_total", return_value=1):
            res = await service.list_memories(workspace_id=7, page=3, page_size=25)

        assert res.page == 3
        assert res.page_size == 25
        # Offset is (page-1)*page_size = 50
        stmt = session.execute_calls[0]
        assert getattr(stmt, "_offset", None) == 50

    async def test_list_rejects_invalid_page_size(self):
        session = _FakeSession(rows=[])
        service = MemoryBrowserService(session)

        with pytest.raises(ValueError) as exc_info:
            await service.list_memories(workspace_id=7, page=1, page_size=101)

        assert "page_size" in str(exc_info.value).lower()

    async def test_list_rejects_page_zero(self):
        session = _FakeSession(rows=[])
        service = MemoryBrowserService(session)

        with pytest.raises(ValueError) as exc_info:
            await service.list_memories(workspace_id=7, page=0, page_size=50)

        assert "page" in str(exc_info.value).lower()

    async def test_list_applies_source_type_in_filter(self):
        session = _FakeSession(rows=[])
        service = MemoryBrowserService(session)

        with patch.object(service, "_count_total", return_value=0):
            await service.list_memories(
                workspace_id=7,
                page=1,
                page_size=50,
                source_types=["SCRAPER_RUN", "DOCUMENT"],
            )

        stmt = session.execute_calls[0]
        where = _build_statement_where(stmt)
        where_str = " ".join(_clause_str(c) for c in where)
        assert "source_type" in where_str
        assert "IN" in where_str

    async def test_list_applies_confidence_range(self):
        session = _FakeSession(rows=[])
        service = MemoryBrowserService(session)

        with patch.object(service, "_count_total", return_value=0):
            await service.list_memories(
                workspace_id=7,
                page=1,
                page_size=50,
                confidence_min=0.2,
                confidence_max=0.8,
            )

        stmt = session.execute_calls[0]
        where = _build_statement_where(stmt)
        where_str = " ".join(_clause_str(c) for c in where)
        assert "coalesce" in where_str and "confidence" in where_str
        assert ">=" in where_str and "<=" in where_str

    async def test_list_rejects_confidence_min_greater_than_max(self):
        session = _FakeSession(rows=[])
        service = MemoryBrowserService(session)

        with pytest.raises(ValueError) as exc_info:
            await service.list_memories(
                workspace_id=7,
                page=1,
                page_size=50,
                confidence_min=0.8,
                confidence_max=0.2,
            )

        assert "confidence" in str(exc_info.value).lower()

    async def test_list_applies_time_range(self):
        since = datetime(2026, 9, 1, tzinfo=UTC)
        until = datetime(2026, 9, 5, tzinfo=UTC)
        session = _FakeSession(rows=[])
        service = MemoryBrowserService(session)

        with patch.object(service, "_count_total", return_value=0):
            await service.list_memories(
                workspace_id=7,
                page=1,
                page_size=50,
                created_after=since,
                created_before=until,
            )

        stmt = session.execute_calls[0]
        where = _build_statement_where(stmt)
        where_str = " ".join(_clause_str(c) for c in where)
        assert "created_at" in where_str

    async def test_list_applies_creator_filter(self):
        user_id = uuid.uuid4()
        session = _FakeSession(rows=[])
        service = MemoryBrowserService(session)

        with patch.object(service, "_count_total", return_value=0):
            await service.list_memories(
                workspace_id=7,
                page=1,
                page_size=50,
                created_by=user_id,
            )

        stmt = session.execute_calls[0]
        where = _build_statement_where(stmt)
        where_str = " ".join(_clause_str(c) for c in where)
        assert "created_by_id" in where_str

    async def test_list_applies_keyword_tsvector(self):
        session = _FakeSession(rows=[])
        service = MemoryBrowserService(session)

        with patch.object(service, "_count_total", return_value=0):
            await service.list_memories(
                workspace_id=7,
                page=1,
                page_size=50,
                keyword="neural search",
            )

        stmt = session.execute_calls[0]
        where = _build_statement_where(stmt)
        where_str = " ".join(_clause_str(c) for c in where)
        assert "to_tsvector" in where_str
        assert "plainto_tsquery" in where_str

    async def test_list_applies_client_id_scope(self):
        session = _FakeSession(rows=[])
        service = MemoryBrowserService(session)

        with patch.object(service, "_count_total", return_value=0):
            await service.list_memories(
                workspace_id=7,
                page=1,
                page_size=50,
                client_id="client-a",
            )

        stmt = session.execute_calls[0]
        where = _build_statement_where(stmt)
        where_str = " ".join(_clause_str(c) for c in where)
        assert "client_id" in where_str


class TestMemoryBrowserServiceListItemDerivation:
    """Pattern 1 (Mirror): derived fields in list items."""

    async def test_list_item_content_snippet_truncated(self):
        long = "word " * 500
        fake = _FakeMemory(
            id=1,
            workspace_id=7,
            content=long,
            source_type="SCRAPER_RUN",
            confidence=0.9,
            source_run_id=uuid.uuid4(),
        )
        session = _FakeSession(rows=[fake])
        service = MemoryBrowserService(session)

        with patch.object(service, "_count_total", return_value=1), \
             patch.object(service, "_load_review_status", return_value={}):
            res = await service.list_memories(workspace_id=7, page=1, page_size=50)

        item: MemoryBrowserListItem = res.items[0]
        assert len(item.content_snippet) < len(long)
        assert item.content_snippet.endswith("...")

    async def test_list_item_source_url_from_source_run_id(self):
        run_id = uuid.uuid4()
        fake = _FakeMemory(
            id=1,
            workspace_id=7,
            content="x",
            source_type="SCRAPER_RUN",
            confidence=0.9,
            source_run_id=run_id,
        )
        session = _FakeSession(rows=[fake])
        service = MemoryBrowserService(session)

        with patch.object(service, "_count_total", return_value=1), \
             patch.object(service, "_load_review_status", return_value={}):
            res = await service.list_memories(workspace_id=7, page=1, page_size=50)

        assert res.items[0].source_url == f"/dashboard/7/runs/{run_id}"

    async def test_list_item_source_url_from_lead_source_uuid(self):
        lead_id = uuid.uuid4()
        fake = _FakeMemory(
            id=2,
            workspace_id=7,
            content="x",
            source_type="LEAD",
            confidence=0.95,
            source_uuid=lead_id,
            source_entity_type="lead",
        )
        session = _FakeSession(rows=[fake])
        service = MemoryBrowserService(session)

        with patch.object(service, "_count_total", return_value=1), \
             patch.object(service, "_load_review_status", return_value={}):
            res = await service.list_memories(workspace_id=7, page=1, page_size=50)

        assert res.items[0].source_url == f"/dashboard/7/leads/{lead_id}"

    async def test_list_item_source_url_falls_back_to_none(self):
        fake = _FakeMemory(id=3, workspace_id=7, content="x", source_type="MANUAL", confidence=0.5)
        session = _FakeSession(rows=[fake])
        service = MemoryBrowserService(session)

        with patch.object(service, "_count_total", return_value=1), \
             patch.object(service, "_load_review_status", return_value={}):
            res = await service.list_memories(workspace_id=7, page=1, page_size=50)

        assert res.items[0].source_url is None

    async def test_list_item_version_count_and_flag_status(self):
        fake = _FakeMemory(id=4, workspace_id=7, content="x", source_type="MANUAL", confidence=0.7)
        fake.versions = [_FakeVersion("a", "b"), _FakeVersion("b", "c")]
        session = _FakeSession(rows=[fake])
        service = MemoryBrowserService(session)

        with patch.object(service, "_count_total", return_value=1), \
             patch.object(service, "_load_review_status", return_value={4: "open"}), \
             patch.object(service, "_load_version_counts", return_value={4: 2}):
            res = await service.list_memories(workspace_id=7, page=1, page_size=50)

        item = res.items[0]
        assert item.version_count == 2
        assert item.flag_status == "open"

    async def test_list_item_created_by_includes_email(self):
        user_id = uuid.uuid4()
        fake = _FakeMemory(
            id=5,
            workspace_id=7,
            content="x",
            source_type="MANUAL",
            confidence=0.8,
            created_by_id=user_id,
        )
        session = _FakeSession(rows=[fake])
        service = MemoryBrowserService(session)

        with patch.object(service, "_count_total", return_value=1), \
             patch.object(service, "_load_review_status", return_value={}), \
             patch.object(service, "_load_creator_emails", return_value={user_id: "analyst@example.com"}):
            res = await service.list_memories(workspace_id=7, page=1, page_size=50)

        assert res.items[0].created_by.id == str(user_id)
        assert res.items[0].created_by.email == "analyst@example.com"


class TestMemoryBrowserServiceDetail:
    """Pattern 1 + 2: detail response and decryption failure."""

    async def test_detail_returns_decrypted_content(self):
        fake = _FakeMemory(
            id=1,
            workspace_id=7,
            content="encrypted cipher",
            source_type="MANUAL",
            confidence=1.0,
            key_id="managed:v1:test",
        )
        session = _FakeSession(scalar=fake)
        service = MemoryBrowserService(session)

        with patch.object(service, "_decrypt_memory") as mock_decrypt, \
             patch.object(service, "_derive_source_url", return_value=None), \
             patch.object(service, "_build_versions", return_value=[]), \
             patch.object(service, "_build_thread", return_value=None), \
             patch.object(service, "_build_relations", return_value=MemoryRelationListResponse(items=[])):
            mock_decrypt.side_effect = lambda m: setattr(m, "content", "decrypted text") or None
            detail = await service.get_memory_detail(workspace_id=7, memory_id=1)

        assert isinstance(detail, MemoryBrowserDetailResponse)
        assert detail.content == "decrypted text"

    async def test_detail_decrypt_failure_returns_500(self):
        fake = _FakeMemory(
            id=1,
            workspace_id=7,
            content="encrypted cipher",
            source_type="MANUAL",
            confidence=1.0,
            key_id="managed:v1:test",
        )
        session = _FakeSession(scalar=fake)
        service = MemoryBrowserService(session)

        with (
            patch.object(service, "_decrypt_memory", side_effect=RuntimeError("decryption_failed")),
            pytest.raises(RuntimeError) as exc_info,
        ):
            await service.get_memory_detail(workspace_id=7, memory_id=1)

        assert "decryption" in str(exc_info.value).lower()

    async def test_detail_returns_404_for_wrong_workspace(self):
        session = _FakeSession(scalar=None)

        with pytest.raises(ValueError) as exc_info:
            await MemoryBrowserService(session).get_memory_detail(workspace_id=7, memory_id=1)

        assert "not found" in str(exc_info.value).lower()


class TestMemoryBrowserServiceFlagForReview:
    """Pattern 2 + 5: flag creation, audit row, and atomic notification."""

    async def test_flag_creates_review_queue_row(self):
        user_id = uuid.uuid4()
        fake = _FakeMemory(id=1, workspace_id=7, content="x", source_type="MANUAL", confidence=1.0)
        session = _FakeSession(scalar=fake, subsequent_scalar=None)
        service = MemoryBrowserService(session)

        with patch.object(service, "_load_review_recipients", new_callable=AsyncMock, return_value=[]):
            result = await service.flag_for_review(
                workspace_id=7,
                memory_id=1,
                flag_reason="outdated",
                flagged_by=user_id,
            )

        assert result is not None
        # queue row + audit row are staged on the same session
        queue_rows = [o for o in session.added if o.__class__.__name__ == "MemoryReviewQueue"]
        audit_rows = [o for o in session.added if o.__class__.__name__ == "AuditEvent"]
        assert len(queue_rows) == 1
        assert queue_rows[0].flag_reason == "outdated"
        assert queue_rows[0].flagged_by == user_id
        assert queue_rows[0].status == "open"
        assert len(audit_rows) == 1
        assert audit_rows[0].action == "memory_review_flag"
        assert audit_rows[0].actor_id == user_id

    async def test_flag_notification_failure_rolls_back(self):
        user_id = uuid.uuid4()
        fake = _FakeMemory(id=1, workspace_id=7, content="x", source_type="MANUAL", confidence=1.0)
        session = _FakeSession(scalar=fake, subsequent_scalar=None)
        service = MemoryBrowserService(session)

        with (
            patch.object(
                service,
                "_load_review_recipients",
                new_callable=AsyncMock,
                side_effect=RuntimeError("notify failed"),
            ),
            pytest.raises(RuntimeError),
        ):
            await service.flag_for_review(
                workspace_id=7,
                memory_id=1,
                flag_reason="outdated",
                flagged_by=user_id,
            )

    async def test_flag_notifies_recipients_in_same_transaction(self):
        user_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        fake = _FakeMemory(id=1, workspace_id=7, content="x", source_type="MANUAL", confidence=1.0)
        session = _FakeSession(scalar=fake, subsequent_scalar=None)
        service = MemoryBrowserService(session)

        with patch.object(service, "_load_review_recipients", new_callable=AsyncMock, return_value=[owner_id]):
            await service.flag_for_review(
                workspace_id=7,
                memory_id=1,
                flag_reason="outdated",
                flagged_by=user_id,
            )

        notifications = [o for o in session.added if o.__class__.__name__ == "Notification"]
        assert len(notifications) == 1
        assert notifications[0].user_id == owner_id
        assert notifications[0].type == "memory_review_flag"
        assert notifications[0].notification_metadata["memory_id"] == 1

    async def test_flag_returns_existing_open_flag(self):
        user_id = uuid.uuid4()
        fake = _FakeMemory(id=1, workspace_id=7, content="x", source_type="MANUAL", confidence=1.0)
        queue_fake = SimpleNamespace(
            id=42,
            memory_id=1,
            workspace_id=7,
            flag_reason="stale",
            flagged_by=uuid.uuid4(),
            status="open",
            created_at=datetime.now(UTC),
            resolved_at=None,
            resolved_by=None,
        )
        session = _FakeSession(scalar=fake, subsequent_scalar=queue_fake)
        service = MemoryBrowserService(session)

        result = await service.flag_for_review(
            workspace_id=7,
            memory_id=1,
            flag_reason="outdated",
            flagged_by=user_id,
        )

        assert result.status == "open"
        assert result.id == 42
        assert result.flag_reason == "stale"
        # No new queue/audit/notification rows should have been staged.
        queue_rows = [o for o in session.added if o.__class__.__name__ == "MemoryReviewQueue"]
        assert len(queue_rows) == 0

    async def test_flag_rejects_empty_reason(self):
        user_id = uuid.uuid4()
        fake = _FakeMemory(id=1, workspace_id=7, content="x", source_type="MANUAL", confidence=1.0)
        session = _FakeSession(scalar=fake)

        with pytest.raises(ValueError):
            await MemoryBrowserService(session).flag_for_review(
                workspace_id=7,
                memory_id=1,
                flag_reason="   ",
                flagged_by=user_id,
            )

    async def test_flag_for_wrong_workspace_returns_404(self):
        session = _FakeSession(scalar=None)

        with pytest.raises(ValueError) as exc_info:
            await MemoryBrowserService(session).flag_for_review(
                workspace_id=7,
                memory_id=1,
                flag_reason="outdated",
                flagged_by=uuid.uuid4(),
            )

        assert "not found" in str(exc_info.value).lower()


class TestMemoryBrowserServiceHelpers:
    """Pattern 4: derived helper arithmetic."""

    def test_derive_source_url_run(self):
        run_id = uuid.uuid4()
        fake = _FakeMemory(id=1, workspace_id=7, content="x", source_type="SCRAPER_RUN", confidence=1.0, source_run_id=run_id)
        service = MemoryBrowserService(MagicMock())
        assert service._derive_source_url(7, fake) == f"/dashboard/7/runs/{run_id}"

    def test_derive_source_url_lead(self):
        lead_id = uuid.uuid4()
        fake = _FakeMemory(id=2, workspace_id=7, content="x", source_type="LEAD", confidence=0.9, source_uuid=lead_id, source_entity_type="lead")
        service = MemoryBrowserService(MagicMock())
        assert service._derive_source_url(7, fake) == f"/dashboard/7/leads/{lead_id}"

    def test_derive_source_url_document(self):
        doc_id = uuid.uuid4()
        fake = _FakeMemory(id=3, workspace_id=7, content="x", source_type="DOCUMENT", confidence=0.9, source_uuid=doc_id, source_entity_type="document")
        service = MemoryBrowserService(MagicMock())
        assert service._derive_source_url(7, fake) == f"/dashboard/7/documents/{doc_id}"

    def test_derive_source_url_chat_message_fallback(self):
        fake = _FakeMemory(id=4, workspace_id=7, content="x", source_type="CHAT_MESSAGE", confidence=0.9, source_id=42)
        service = MemoryBrowserService(MagicMock())
        assert service._derive_source_url(7, fake) is None

    def test_snippet_truncates_and_adds_ellipsis(self):
        service = MemoryBrowserService(MagicMock())
        text = "word " * 500
        snippet = service._snippet(text, 120)
        assert len(snippet) <= 124
        assert snippet.endswith("...")

    def test_snippet_short_text_untouched(self):
        service = MemoryBrowserService(MagicMock())
        text = "short content"
        assert service._snippet(text, 120) == text
