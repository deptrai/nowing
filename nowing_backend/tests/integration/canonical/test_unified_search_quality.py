"""Lightweight quality benchmark for the unified canonical search."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.canonical.services.unified_search_service import UnifiedSearchService
from app.config import config as app_config
from app.db import CanonicalEntity, CanonicalEntitySource

pytestmark = [pytest.mark.integration, pytest.mark.canonical]


_EMBEDDING_DIM = app_config.embedding_model_instance.dimension
_DUMMY_EMBEDDING = [0.1] * _EMBEDDING_DIM
_CURRENT_MODEL = app_config.EMBEDDING_MODEL or "unknown"
_FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / ".."
    / "nowing_evals"
    / "data"
    / "canonical"
    / "fixtures"
    / "bds-overlap-30.jsonl"
)


def _entity_uuid(raw_id: str) -> uuid.UUID:
    """Deterministic UUID from the fixture canonical_entity_id string."""
    return uuid.uuid5(uuid.NAMESPACE_DNS, raw_id)


async def _seed_fixture(db_session, db_workspace, monkeypatch):
    """Load the bds-overlap-30 fixture into the test workspace."""
    fixture_path = _FIXTURE_PATH.resolve()
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}")

    rows = []
    with fixture_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    # Group fixture rows by canonical entity.
    entity_rows: dict[str, list[dict]] = {}
    for row in rows:
        entity_id = row["canonical_entity_id"]
        entity_rows.setdefault(entity_id, []).append(row)

    created_entities: dict[str, CanonicalEntity] = {}
    for entity_id, sources in entity_rows.items():
        title = sources[0]["title"]
        search_text = " ".join({s["title"] for s in sources})
        entity = CanonicalEntity(
            id=_entity_uuid(entity_id),
            workspace_id=db_workspace.id,
            entity_type="vn_bds.listing",
            canonical_title=title,
            canonical_data={"title": title},
            fingerprint=f"fp-{entity_id}",
            search_text=search_text,
            source_count=len(sources),
            confidence_score=0.85,
            conflict_flags=[],
            version=1,
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
            embedding=_DUMMY_EMBEDDING,
            embedding_model_name=_CURRENT_MODEL,
            embedding_status="ready",
        )
        db_session.add(entity)
        created_entities[entity_id] = entity

    await db_session.flush()

    # Add sources for each fixture row.
    for row in rows:
        source = CanonicalEntitySource(
            id=uuid.uuid4(),
            workspace_id=db_workspace.id,
            canonical_entity_id=_entity_uuid(row["canonical_entity_id"]),
            entity_type="vn_bds.listing",
            source_name=row["source"],
            source_record_id=row["record_id"],
            source_snapshot=row,
        )
        db_session.add(source)

    await db_session.flush()

    # Monkeypatch embedding to a fast, deterministic dummy so the test does not
    # depend on the real sentence-transformers model.
    monkeypatch.setattr(
        app_config.embedding_model_instance,
        "embed",
        lambda _text: _DUMMY_EMBEDDING,
    )

    return {
        "workspace": db_workspace,
        "entity_rows": entity_rows,
        "rows": rows,
    }


@pytest.mark.asyncio
async def test_unified_search_fixture_recall_and_precision(
    db_session, db_workspace, monkeypatch
):
    """Search fixture titles and assert recall@10 >= 0.85 and precision@5 >= 0.80."""
    data = await _seed_fixture(db_session, db_workspace, monkeypatch)
    rows = data["rows"]
    service = UnifiedSearchService(db_session)

    # Use every 5th row as a query to keep the test fast.
    query_rows = rows[::5]
    if not query_rows:
        pytest.skip("No query rows available")

    hits_at_10 = 0
    hits_at_5 = 0

    for row in query_rows:
        query = row["title"]
        expected_entity_id = _entity_uuid(row["canonical_entity_id"])

        results = await service.search(
            workspace_id=db_workspace.id,
            query_text=query,
            top_k=10,
            entity_types=["vn_bds.listing"],
            w_vector=0.3,
            w_fts=0.7,
        )

        top_10_ids = {
            r["entity"]["id"] for r in results if r["type"] == "canonical_entity"
        }
        top_5_ids = {
            r["entity"]["id"] for r in results[:5] if r["type"] == "canonical_entity"
        }

        if expected_entity_id in top_10_ids:
            hits_at_10 += 1
        if expected_entity_id in top_5_ids:
            hits_at_5 += 1

    total = len(query_rows)
    recall_at_10 = hits_at_10 / total
    precision_at_5 = hits_at_5 / total

    assert recall_at_10 >= 0.85, f"recall@10 {recall_at_10} below threshold"
    assert precision_at_5 >= 0.80, f"precision@5 {precision_at_5} below threshold"


@pytest.mark.asyncio
async def test_unified_search_no_duplicate_groups(
    db_session, db_workspace, monkeypatch
):
    """The same canonical entity is never emitted twice at the top level."""
    data = await _seed_fixture(db_session, db_workspace, monkeypatch)
    rows = data["rows"]
    service = UnifiedSearchService(db_session)

    query = rows[0]["title"]
    results = await service.search(
        workspace_id=db_workspace.id,
        query_text=query,
        top_k=10,
        entity_types=["vn_bds.listing"],
    )

    canonical_ids = [
        r["entity"]["id"] for r in results if r["type"] == "canonical_entity"
    ]
    assert len(canonical_ids) == len(set(canonical_ids))
