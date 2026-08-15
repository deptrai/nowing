"""Pattern 6 (SQL) integration tests for Story 21.1 signal detection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Memory, MemorySourceType, MemoryType, SignalEvent, User, Workspace
from app.lead_intelligence.signals.schemas import (
    SignalEventRead,
    SignalInput,
    SignalOutput,
)
from app.lead_intelligence.signals.service import SignalDetectionService

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_signal_event_insert_and_select(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> None:
    """SignalEvent rows persist with the exact contract fields."""
    detected_at = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
    chunk_id = uuid4()

    event = SignalEvent(
        id=uuid4(),
        workspace_id=db_workspace.id,
        client_id=None,
        company_name="FPT",
        signal_type="funding",
        source_url="https://example.com/funding",
        chunk_id=chunk_id,
        confidence=85.0,
        detected_at=detected_at,
        processed=False,
    )
    db_session.add(event)
    await db_session.flush()

    result = await db_session.execute(
        select(SignalEvent).where(SignalEvent.workspace_id == db_workspace.id)
    )
    rows = list(result.scalars().all())
    assert len(rows) == 1

    row = rows[0]
    assert row.workspace_id == db_workspace.id
    assert row.client_id is None
    assert row.company_name == "FPT"
    assert row.signal_type == "funding"
    assert row.source_url == "https://example.com/funding"
    assert row.chunk_id == chunk_id
    assert row.confidence == 85.0
    assert row.detected_at == detected_at
    assert row.processed is False


async def test_signal_event_unique_constraint(
    db_session: AsyncSession,
    db_workspace: Workspace,
) -> None:
    """The composite unique key rejects duplicate signals."""
    detected_at = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
    common = {
        "workspace_id": db_workspace.id,
        "client_id": "acme",
        "company_name": "FPT",
        "signal_type": "funding",
        "source_url": "https://example.com/funding",
        "detected_at": detected_at,
        "confidence": 80.0,
    }

    event1 = SignalEvent(id=uuid4(), **common)
    db_session.add(event1)
    await db_session.flush()

    event2 = SignalEvent(id=uuid4(), **common)
    db_session.add(event2)

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_memory_insert_with_signal_provenance(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> None:
    """A Memory row is linked to a SignalEvent via source_uuid and redacts content."""
    from app.config import config
    from app.services.pii.redact import redact_pii

    detected_at = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
    signal = SignalEvent(
        id=uuid4(),
        workspace_id=db_workspace.id,
        client_id=None,
        company_name="FPT",
        signal_type="funding",
        source_url="https://example.com/funding",
        chunk_id=None,
        confidence=90.0,
        detected_at=detected_at,
        processed=False,
    )
    db_session.add(signal)
    await db_session.flush()

    raw_summary = "FPT raised $1M. Contact: 0901234567, hr@fpt.com"
    redacted = redact_pii(raw_summary, context="lead_enrichment")

    dim = config.embedding_model_instance.dimension
    memory = Memory(
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
        client_id=None,
        type=MemoryType.SEMANTIC,
        content=redacted.text,
        embedding=[0.0] * dim,
        source_type=MemorySourceType.SIGNAL,
        source_uuid=signal.id,
        source_entity_type="SignalEvent",
        source_capability="funding.signal",
        source_input={"company_name": "FPT", "signal_type": "funding"},
        tags=["lead_signal"],
        confidence=signal.confidence,
    )
    db_session.add(memory)
    await db_session.flush()

    result = await db_session.execute(
        select(Memory).where(Memory.source_uuid == signal.id)
    )
    row = result.scalar_one()

    assert row.source_uuid == signal.id
    assert row.source_entity_type == "SignalEvent"
    assert row.type == MemoryType.SEMANTIC
    assert row.tags == ["lead_signal"]
    assert row.confidence == 90.0
    assert "<PHONE>" in row.content or "0901234567" not in row.content
    assert "<EMAIL>" in row.content or "hr@fpt.com" not in row.content


async def test_signal_detection_service_persists_signal_event_and_memory(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
    patched_embed_texts: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SignalDetectionService writes SignalEvent + Memory in one transaction."""
    from app.capabilities.core.types import CapabilityContext
    from app.config import config

    monkeypatch.setattr(config, "CRUNCHBASE_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(config, "SIGNAL_SCAN_MICROS_PER_SIGNAL", 0, raising=False)
    monkeypatch.setattr(
        httpx.AsyncClient,
        "get",
        AsyncMock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "name": "FPT",
                        "funding_total": 1_000_000,
                        "announced_on": "2026-08-01",
                        "source_url": "https://example.com/funding",
                        "confidence": 85,
                    }
                ],
            )
        ),
    )

    ctx = CapabilityContext(
        session=db_session,
        workspace_id=db_workspace.id,
        run_id="run-integration-signal",
    )
    service = SignalDetectionService()
    output = await service.detect(
        db_session,
        ctx,
        SignalInput(company_name="FPT"),
        "funding",
    )

    assert isinstance(output, SignalOutput)
    assert output.degraded is False
    assert len(output.items) == 1
    assert output.items[0].signal_type == "funding"
    assert output.items[0].company_name == "FPT"
    assert output.items[0].confidence == 85.0

    signal_rows = list(
        (
            await db_session.execute(
                select(SignalEvent).where(SignalEvent.workspace_id == db_workspace.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(signal_rows) == 1

    memory_rows = list(
        (
            await db_session.execute(
                select(Memory).where(Memory.source_entity_type == "SignalEvent")
            )
        )
        .scalars()
        .all()
    )
    assert len(memory_rows) == 1
    assert memory_rows[0].source_uuid == signal_rows[0].id


async def test_get_signals_list_with_filters_and_ordering(
    client: httpx.AsyncClient,
    db_workspace: Workspace,
    seed_signal_event: Any,
) -> None:
    """GET /workspaces/{id}/signals filters and orders by detected_at."""
    now = datetime.now(UTC)
    t1 = now - timedelta(days=2)
    t2 = now - timedelta(days=1)
    t3 = now

    await seed_signal_event(
        signal_type="funding",
        company_name="FPT",
        confidence=85.0,
        detected_at=t3,
        source_url="https://example.com/funding-3",
    )
    await seed_signal_event(
        signal_type="hiring",
        company_name="FPT",
        confidence=30.0,
        detected_at=t2,
        source_url="https://example.com/jobs",
    )
    await seed_signal_event(
        signal_type="funding",
        company_name="FPT",
        confidence=90.0,
        detected_at=t1,
        source_url="https://example.com/funding-1",
    )

    resp = await client.get(
        f"/api/v1/workspaces/{db_workspace.id}/signals",
        params={
            "signal_type": "funding",
            "company_name": "FPT",
            "from_date": (t1 - timedelta(hours=1)).isoformat(),
            "to_date": (t3 + timedelta(hours=1)).isoformat(),
            "confidence_min": 50,
            "sort": "detected_at_desc",
            "limit": 20,
            "offset": 0,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert "limit" in body
    assert "offset" in body

    items = body["items"]
    assert body["total"] == 2
    assert len(items) == 2
    assert items[0]["signal_type"] == "funding"
    assert items[0]["confidence"] == 85.0
    assert items[1]["confidence"] == 90.0
    assert items[0]["detected_at"] >= items[1]["detected_at"]


async def test_post_signals_detect_returns_signal_output(
    client: httpx.AsyncClient,
    db_workspace: Workspace,
    patched_embed_texts: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /workspaces/{id}/signals/detect returns a SignalOutput."""
    now = datetime.now(UTC)

    async def _fake_detect(*args: Any, **kwargs: Any) -> SignalOutput:
        return SignalOutput(
            items=[
                SignalEventRead(
                    id=uuid4(),
                    workspace_id=db_workspace.id,
                    client_id=None,
                    company_name="FPT",
                    signal_type="funding",
                    source_url="https://example.com/funding",
                    chunk_id=None,
                    confidence=85.0,
                    detected_at=now,
                    processed=False,
                )
            ],
            cost_micros=1000,
            degraded=False,
        )

    monkeypatch.setattr(
        "app.lead_intelligence.signals.service.SignalDetectionService.detect",
        _fake_detect,
        raising=False,
    )

    resp = await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/signals/detect",
        json={
            "company_name": "FPT",
            "signal_type": "funding",
            "lookback_days": 30,
            "confidence_threshold": 0.0,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "cost_micros" in body
    assert "degraded" in body
    assert body["degraded"] is False
    assert len(body["items"]) == 1
    assert body["items"][0]["company_name"] == "FPT"
    assert body["items"][0]["signal_type"] == "funding"
