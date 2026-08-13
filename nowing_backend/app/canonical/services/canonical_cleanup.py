"""Cleanup helpers for canonical entities orphaned by connector lifecycle.

Two flows remove documents outside the canonical persistence service:

* connector deletion (``search_source_connectors_routes``) deletes every
  document belonging to the connector;
* RSS feed pruning (``rss_indexer``) removes articles that left the feed's
  rolling window.

Both flows must also remove the corresponding canonical provenance rows and
any canonical entities that are left without sources, otherwise
``canonical_entities`` accumulates stale entries forever.
"""

from __future__ import annotations

import logging

from sqlalchemy import delete as sa_delete, exists
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import CanonicalEntity, CanonicalEntitySource

logger = logging.getLogger(__name__)

_DEFAULT_BATCH_SIZE = 500


async def delete_canonical_sources_by_record_ids(
    session: AsyncSession,
    workspace_id: int,
    record_ids: list[str],
    *,
    batch_size: int = _DEFAULT_BATCH_SIZE,
) -> int:
    """Delete canonical entity sources by their ``source_record_id`` values.

    ``source_record_id`` equals the document ``unique_id`` (the article link)
    for RSS connectors, so the links of deleted documents map 1:1 to the
    provenance rows that referenced them.
    """
    total = 0
    for start in range(0, len(record_ids), batch_size):
        batch = record_ids[start : start + batch_size]
        result = await session.execute(
            sa_delete(CanonicalEntitySource).where(
                CanonicalEntitySource.workspace_id == workspace_id,
                CanonicalEntitySource.source_record_id.in_(batch),
            )
        )
        total += result.rowcount or 0
    return total


async def delete_orphaned_canonical_entities(
    session: AsyncSession,
    workspace_id: int,
    entity_types: list[str] | None = None,
) -> int:
    """Delete canonical entities that no longer have any source records.

    ``entity_types`` optionally scopes the sweep (e.g. connector cleanup
    should only touch the domains it indexes, like ``news_article``).
    """
    stmt = sa_delete(CanonicalEntity).where(
        CanonicalEntity.workspace_id == workspace_id,
    )
    if entity_types is not None:
        stmt = stmt.where(CanonicalEntity.entity_type.in_(entity_types))
    stmt = stmt.where(
        ~exists().where(CanonicalEntitySource.canonical_entity_id == CanonicalEntity.id)
    )
    result = await session.execute(stmt)
    return result.rowcount or 0
