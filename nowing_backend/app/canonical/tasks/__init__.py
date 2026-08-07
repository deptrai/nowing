"""Canonical entity background tasks."""

from __future__ import annotations

from .backfill_canonical_embedding import backfill_canonical_embedding
from .process_canonical_persist_outbox import process_canonical_persist_outbox

__all__ = [
    "backfill_canonical_embedding",
    "process_canonical_persist_outbox",
]
