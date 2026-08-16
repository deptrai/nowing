"""Redis Stream Transit Buffer & Ingestion Service (Story 23.1 / AC-2).

Governed by:
- AC-2: Redis Stream Transit Buffer & Dual-Trigger Flush Window
- INV-23.2: Bounded Redis Streams (MAXLEN ~ 10000 approximate cap)
- Architecture Spine: architecture-epic23-lead-infrastructure.md
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import Lead, async_session_maker
from app.redis_client import get_redis_client

logger = logging.getLogger(__name__)

FLUSH_BATCH_SIZE: int = 5
FLUSH_TIME_WINDOW_SECONDS: float = 3.0
REDIS_STREAM_MAXLEN: int = 10000


class LeadRecordPayload(BaseModel):
    """Payload schema for leads stored in Redis Stream transit buffer."""

    workspace_id: int
    client_id: str
    source: str
    company_name: str | None = None
    domain: str | None = None
    value_hmac: str
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    fit_score: float = 0.0
    intent_score: float = 0.0
    status: str = "new"


def generate_lead_hmac(
    workspace_id: int, company_name: str, domain: str | None = None
) -> str:
    """Generate SHA-256 HMAC for lead deduplication."""
    key = f"{workspace_id}:{domain or ''}:{company_name.strip().lower()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def build_lead_upsert_stmt(leads: list[dict[str, Any]]) -> Any:
    """Build PostgreSQL idempotent upsert statement for partitioned leads table."""
    if not leads:
        return None

    # Deduplicate in-memory by (workspace_id, value_hmac) to prevent CardinalityViolation
    unique_records: dict[tuple[int, str], dict[str, Any]] = {}
    for lead in leads:
        ws_id = lead["workspace_id"]
        company = lead.get("company_name") or lead.get("title") or "Doanh nghiệp"
        domain = lead.get("domain") or lead.get("canonical_domain")
        hmac = lead.get("value_hmac") or generate_lead_hmac(ws_id, company, domain)

        rec = {
            "id": lead.get("id") or uuid4(),
            "workspace_id": ws_id,
            "client_id": lead.get("client_id", "default"),
            "source": lead.get("source", "unknown"),
            "company_name": company,
            "domain": domain,
            "value_hmac": hmac,
            "fit_score": lead.get("fit_score", 0.0),
            "intent_score": lead.get("intent_score", 0.0),
            "status": lead.get("status", "new"),
        }
        unique_records[(ws_id, hmac)] = rec

    stmt = pg_insert(Lead).values(list(unique_records.values()))
    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=["workspace_id", "value_hmac"],
        set_={
            "fit_score": stmt.excluded.fit_score,
            "intent_score": stmt.excluded.intent_score,
            "status": stmt.excluded.status,
            "company_name": stmt.excluded.company_name,
        },
    )
    return upsert_stmt


class LeadStreamBuffer:
    """Buffer collecting lead records and flushing to Redis Stream via dual triggers."""

    def __init__(
        self,
        workspace_id: int,
        redis_client: Any = None,
        flush_batch_size: int = FLUSH_BATCH_SIZE,
        flush_time_seconds: float = FLUSH_TIME_WINDOW_SECONDS,
        maxlen: int = REDIS_STREAM_MAXLEN,
    ) -> None:
        self.workspace_id = workspace_id
        self._redis = redis_client
        self.flush_batch_size = flush_batch_size
        self.flush_time_seconds = flush_time_seconds
        self.maxlen = maxlen
        self._buffer: list[dict[str, Any]] = []
        self._last_flush_time = time.time()
        self.stream_key = f"workspace:{workspace_id}:leads_stream"
        self._lock = asyncio.Lock()

    async def _get_redis(self) -> Any:
        if self._redis is not None:
            return self._redis
        return await get_redis_client()

    def get_buffered_count(self) -> int:
        """Return number of currently buffered leads."""
        return len(self._buffer)

    def should_flush_by_timeout(self, current_time: float | None = None) -> bool:
        """Check if time window trigger has elapsed with buffered items."""
        if not self._buffer:
            return False
        now = current_time if current_time is not None else time.time()
        return (now - self._last_flush_time) >= self.flush_time_seconds

    async def add_lead(self, lead_record: dict[str, Any]) -> bool:
        """
        Add a lead to the buffer safely under lock.
        Returns True if batch size flush was triggered, False otherwise.
        """
        async with self._lock:
            lead = dict(lead_record)
            lead.setdefault("workspace_id", self.workspace_id)
            if not lead.get("value_hmac"):
                company = (
                    lead.get("company_name") or lead.get("title") or "Doanh nghiệp"
                )
                domain = lead.get("domain") or lead.get("canonical_domain")
                lead["value_hmac"] = generate_lead_hmac(
                    self.workspace_id, company, domain
                )
            self._buffer.append(lead)

            if len(self._buffer) >= self.flush_batch_size:
                await self._flush_internal()
                return True
            return False

    async def flush(self) -> int:
        """Flush all buffered leads into Redis Stream safely under lock."""
        async with self._lock:
            return await self._flush_internal()

    async def _flush_internal(self) -> int:
        """Internal flush implementation executing under lock."""
        if not self._buffer:
            return 0

        redis = await self._get_redis()
        flushed_leads = list(self._buffer)

        for lead in flushed_leads:
            payload = json.dumps(lead, default=str)
            await redis.xadd(
                self.stream_key,
                {"payload": payload},
                maxlen=self.maxlen,
                approximate=True,
            )

        # Delete only flushed records after Redis confirms write
        del self._buffer[: len(flushed_leads)]
        self._last_flush_time = time.time()

        logger.debug(
            "Flushed %d leads to Redis Stream %s",
            len(flushed_leads),
            self.stream_key,
        )
        return len(flushed_leads)

    async def flush_if_due(self, current_time: float | None = None) -> int:
        """Flush buffer if time window trigger is satisfied."""
        if self.should_flush_by_timeout(current_time):
            return await self.flush()
        return 0


async def ingest_stream_leads_to_db(
    workspace_id: int,
    leads: list[dict[str, Any]],
) -> int:
    """Bulk upsert flushed stream leads into partitioned PostgreSQL leads table."""
    if not leads:
        return 0

    stmt = build_lead_upsert_stmt(leads)
    if stmt is None:
        return 0

    async with async_session_maker() as session, session.begin():
        await session.execute(stmt)

    return len(leads)
