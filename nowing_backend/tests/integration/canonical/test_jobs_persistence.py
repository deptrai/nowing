"""Integration tests for job aggregator persistence to canonical storage."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.canonical.services.canonical_persist_service import upsert_canonical_entity
from app.capabilities.core.types import CapabilityContext
from app.db import (
    CanonicalEntity,
    CanonicalEntitySource,
    CanonicalPersistOutbox,
    Workspace,
)
from app.services.jobs_aggregator import aggregate_jobs, fingerprint
from app.services.jobs_aggregator.schemas import VnJobAggregateInput

pytestmark = [pytest.mark.integration, pytest.mark.canonical]


def _no_op_apply_async(*args: Any, **kwargs: Any) -> None:
    """Prevent Celery broker round-trips in tests."""
    return None


def _vietnamworks_item() -> dict[str, Any]:
    return {
        "id": "vw:123",
        "title": "Senior Data Engineer",
        "company": "ACB",
        "location": "Hà Nội",
        "salary_raw": "Từ 30 triệu",
        "salary_min": 30000000,
        "salary_max": 0,
        "salary_currency": "VND",
        "salary_period_id": 2,
        "posted_at": "2026-08-05",
        "employment_type": "full_time",
        "source_url": "https://vietnamworks.com/123",
        "job_description": (
            "Contact Nguyễn Văn A at 0901234567 or email test@example.com for details."
        ),
        "job_requirement": "Must have 3 years of Python experience.",
    }


def _topcv_item() -> dict[str, Any]:
    return {
        "id": "tc:456",
        "title": "Senior Data Engineer",
        "company": "ACB",
        "location": "Hà Nội",
        "salary_raw": "30-40 triệu",
        "salary_min": 30000000,
        "salary_max": 40000000,
        "salary_currency": "VND",
        "salary_period_id": 2,
        "posted_at": "2026-08-05",
        "employment_type": "full_time",
        "source_url": "https://topcv.com/456",
        "job_description": "Join our data team in Hanoi.",
        "job_requirement": "Python, SQL.",
    }


def _make_fake_call_source(
    *, degraded: dict[str, str] | None = None
) -> Callable[..., Awaitable[dict[str, Any]]]:
    degraded = degraded or {}

    async def _call_source(
        source: str, payload: dict[str, Any], ctx: Any
    ) -> dict[str, Any]:
        if source in degraded:
            return {
                "items": [],
                "degraded": True,
                "degradation_reason": degraded[source],
            }
        if source == "vietnamworks":
            return {
                "items": [_vietnamworks_item()],
                "cost_micros": 3500,
                "degraded": False,
            }
        if source == "topcv":
            return {"items": [_topcv_item()], "cost_micros": 3500, "degraded": False}
        return {
            "items": [],
            "degraded": True,
            "degradation_reason": f"{source}: not_found",
        }

    return _call_source


async def test_aggregate_persists_multi_source_jobs(
    db_session: AsyncSession,
    db_workspace: Workspace,
    monkeypatch: Any,
) -> None:
    """A merged job listing from two sources gets source_count=2 and redacted snapshots."""
    monkeypatch.setattr(
        "app.canonical.services.canonical_persist_service.backfill_canonical_embedding.apply_async",
        _no_op_apply_async,
    )
    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source",
        _make_fake_call_source(),
    )

    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)
    input = VnJobAggregateInput(
        keyword="data engineer",
        sources=["vietnamworks", "topcv"],
        max_items_per_source=1,
    )
    output = await aggregate_jobs(input, ctx)

    assert output.persistence_status == "ok"
    assert output.persistence_message is None
    assert output.total_items == 1

    listing = output.items[0]
    assert listing.source == "multiple"

    fp = fingerprint(listing.model_dump())
    entity = await db_session.scalar(
        select(CanonicalEntity).where(
            CanonicalEntity.workspace_id == db_workspace.id,
            CanonicalEntity.entity_type == "vn_job",
            CanonicalEntity.fingerprint == fp,
        )
    )
    assert entity is not None
    assert entity.fingerprint == fp
    assert entity.source_count == 2
    assert entity.search_text
    # Location is normalized to city code.
    assert entity.canonical_data.get("location") == "HN"
    # Salary 30M vs 30-40M triggers SALARY_MISMATCH and lowered confidence.
    assert "SALARY_MISMATCH" in [f["type"] for f in entity.conflict_flags]

    sources_result = await db_session.execute(
        select(CanonicalEntitySource).where(
            CanonicalEntitySource.canonical_entity_id == entity.id
        )
    )
    sources = sources_result.scalars().all()
    assert len(sources) == 2
    source_names = {s.source_name for s in sources}
    assert source_names == {"vietnamworks", "topcv"}

    record_ids = {s.source_record_id for s in sources}
    assert record_ids == {"vw:123", "tc:456"}

    for source in sources:
        assert source.source_url
        snapshot_text = " ".join(
            str(v) for v in _flatten_values(source.source_snapshot)
        )
        assert "0901234567" not in snapshot_text
        assert "test@example.com" not in snapshot_text
        assert "Nguyễn Văn A" not in snapshot_text


async def test_aggregate_persistence_is_idempotent(
    db_session: AsyncSession,
    db_workspace: Workspace,
    monkeypatch: Any,
) -> None:
    """Calling aggregate twice with the same source records does not duplicate rows."""
    monkeypatch.setattr(
        "app.canonical.services.canonical_persist_service.backfill_canonical_embedding.apply_async",
        _no_op_apply_async,
    )
    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source",
        _make_fake_call_source(),
    )

    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)
    input = VnJobAggregateInput(
        keyword="data engineer",
        sources=["vietnamworks", "topcv"],
        max_items_per_source=1,
    )

    for _ in range(2):
        output = await aggregate_jobs(input, ctx)
        assert output.persistence_status == "ok"

    entity_count_result = await db_session.execute(
        select(CanonicalEntity).where(
            CanonicalEntity.workspace_id == db_workspace.id,
            CanonicalEntity.entity_type == "vn_job",
        )
    )
    entities = entity_count_result.scalars().all()
    assert len(entities) == 1
    assert entities[0].source_count == 2

    source_count_result = await db_session.execute(
        select(CanonicalEntitySource).where(
            CanonicalEntitySource.canonical_entity_id == entities[0].id
        )
    )
    assert len(source_count_result.scalars().all()) == 2


async def test_aggregate_persists_successful_source_when_other_degraded(
    db_session: AsyncSession,
    db_workspace: Workspace,
    monkeypatch: Any,
) -> None:
    """When one source is degraded, the successful source is still persisted."""
    monkeypatch.setattr(
        "app.canonical.services.canonical_persist_service.backfill_canonical_embedding.apply_async",
        _no_op_apply_async,
    )
    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source",
        _make_fake_call_source(degraded={"topcv": "tos_pending"}),
    )

    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)
    input = VnJobAggregateInput(
        keyword="data engineer",
        sources=["vietnamworks", "topcv"],
        max_items_per_source=1,
    )
    output = await aggregate_jobs(input, ctx)

    assert output.persistence_status == "ok"
    assert output.degraded is True
    assert output.degraded_source_ids == ["topcv"]
    assert output.source_breakdown["topcv"]["degraded"] is True
    assert output.total_items == 1

    listing = output.items[0]
    fp = fingerprint(listing.model_dump())
    entity = await db_session.scalar(
        select(CanonicalEntity).where(
            CanonicalEntity.workspace_id == db_workspace.id,
            CanonicalEntity.entity_type == "vn_job",
            CanonicalEntity.fingerprint == fp,
        )
    )
    assert entity is not None
    assert entity.source_count == 1

    source = await db_session.scalar(
        select(CanonicalEntitySource).where(
            CanonicalEntitySource.canonical_entity_id == entity.id,
            CanonicalEntitySource.source_name == "vietnamworks",
        )
    )
    assert source is not None
    assert source.source_record_id == "vw:123"


async def test_aggregate_partial_persistence_failure_stages_outbox_and_metric(
    db_session: AsyncSession,
    db_workspace: Workspace,
    monkeypatch: Any,
) -> None:
    """A per-source persistence failure returns partial, stages an outbox row and emits a metric."""
    monkeypatch.setattr(
        "app.canonical.services.canonical_persist_service.backfill_canonical_embedding.apply_async",
        _no_op_apply_async,
    )
    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source",
        _make_fake_call_source(),
    )

    recorded_failures: list[tuple[str, str]] = []

    def _capture_metric(*, domain: str, reason: str) -> None:
        recorded_failures.append((domain, reason))

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator.record_canonical_persist_failure",
        _capture_metric,
    )

    real_upsert = upsert_canonical_entity

    async def _failing_upsert(*args: Any, **kwargs: Any) -> CanonicalEntity:
        if kwargs.get("source_name") == "topcv":
            raise RuntimeError("simulated topcv failure")
        return await real_upsert(*args, **kwargs)

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator.upsert_canonical_entity",
        _failing_upsert,
    )

    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)
    input = VnJobAggregateInput(
        keyword="data engineer",
        sources=["vietnamworks", "topcv"],
        max_items_per_source=1,
    )
    output = await aggregate_jobs(input, ctx)

    assert output.persistence_status == "partial"
    assert output.persistence_message is not None
    assert output.total_items == 1

    listing = output.items[0]
    fp = fingerprint(listing.model_dump())
    entity = await db_session.scalar(
        select(CanonicalEntity).where(
            CanonicalEntity.workspace_id == db_workspace.id,
            CanonicalEntity.entity_type == "vn_job",
            CanonicalEntity.fingerprint == fp,
        )
    )
    assert entity is not None
    # VietnamWorks source succeeded before TopCV failed.
    assert entity.source_count == 1

    outbox = await db_session.scalar(
        select(CanonicalPersistOutbox).where(
            CanonicalPersistOutbox.workspace_id == db_workspace.id,
            CanonicalPersistOutbox.entity_type == "vn_job",
        )
    )
    assert outbox is not None
    assert outbox.status == "pending"
    assert "simulated topcv failure" in (outbox.error or "")
    assert outbox.payload["fingerprint"] == fp
    assert any(s["source_name"] == "topcv" for s in outbox.payload["sources"])

    assert recorded_failures
    assert any(domain == "vn_job" for domain, _ in recorded_failures)


async def test_aggregate_conflict_flags_and_source_count_persisted(
    db_session: AsyncSession,
    db_workspace: Workspace,
    monkeypatch: Any,
) -> None:
    """Conflict flags (SALARY_MISMATCH, LOCATION_MISMATCH) and source_count are written to canonical data."""
    monkeypatch.setattr(
        "app.canonical.services.canonical_persist_service.backfill_canonical_embedding.apply_async",
        _no_op_apply_async,
    )

    async def _fake_call_source(
        source: str, payload: dict[str, Any], ctx: Any
    ) -> dict[str, Any]:
        items = {
            "vietnamworks": {
                "id": "vw:789",
                "title": "Python Backend",
                "company": "FPT",
                "location": "Hà Nội",
                "salary_min": 30_000_000,
                "salary_max": 30_000_000,
                "posted_at": "2026-08-05",
                "employment_type": "full_time",
            },
            "topcv": {
                "id": "tc:789",
                "title": "Python Backend",
                "company": "FPT",
                "location": "Hà Nội",
                "salary_min": 60_000_000,
                "salary_max": 60_000_000,
                "posted_at": "2026-08-05",
                "employment_type": "full_time",
            },
        }
        return {
            "items": [items[source]],
            "cost_micros": 1000,
            "degraded": False,
        }

    monkeypatch.setattr(
        "app.services.jobs_aggregator.orchestrator._call_source",
        _fake_call_source,
    )

    ctx = CapabilityContext(session=db_session, workspace_id=db_workspace.id)
    input = VnJobAggregateInput(
        keyword="python",
        sources=["vietnamworks", "topcv"],
        max_items_per_source=1,
    )
    output = await aggregate_jobs(input, ctx)

    assert output.persistence_status == "ok"
    assert output.total_items == 1

    listing = output.items[0]
    assert listing.source_count == 2
    assert "SALARY_MISMATCH" in listing.conflict_flags
    assert "LOCATION_MISMATCH" not in listing.conflict_flags

    fp = fingerprint(listing.model_dump())
    entity = await db_session.scalar(
        select(CanonicalEntity).where(
            CanonicalEntity.workspace_id == db_workspace.id,
            CanonicalEntity.entity_type == "vn_job",
            CanonicalEntity.fingerprint == fp,
        )
    )
    assert entity is not None
    assert entity.source_count == 2
    flag_types = {f["type"] for f in entity.conflict_flags}
    assert "SALARY_MISMATCH" in flag_types
    assert "LOCATION_MISMATCH" not in flag_types
    assert 0.5 <= listing.confidence_score <= 0.7


def _flatten_values(value: Any) -> list[Any]:
    """Flatten a JSON-like structure to a flat list of primitive values."""
    result: list[Any] = []
    if isinstance(value, dict):
        for v in value.values():
            result.extend(_flatten_values(v))
    elif isinstance(value, list):
        for v in value:
            result.extend(_flatten_values(v))
    else:
        result.append(value)
    return result
