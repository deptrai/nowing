"""Nowing -> chainlens-research scraper ingest adapter."""

from __future__ import annotations

import asyncio
import inspect
import logging
import uuid
from collections.abc import Sequence
from typing import Any

import httpx
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.observability import metrics

from .auth_stub import get_chainlens_auth_header

logger = logging.getLogger(__name__)


class IngestResult(BaseModel):
    """Result of a ``NowingIngestService.ingest`` call."""

    ingest_job_id: str | None = None
    parent_ingest_job_id: str | None = None
    child_ingest_job_ids: list[str] = Field(default_factory=list)
    noop_source_ids: list[str] = Field(default_factory=list)
    ingested_source_ids: list[str] = Field(default_factory=list)
    status: str = "pending"
    error: str | None = None


def _chunk_to_dict(chunk: Any) -> dict[str, Any]:
    """Serialize a Chunk model or dict for JSON transport."""
    if isinstance(chunk, BaseModel):
        return chunk.model_dump()
    return dict(chunk)


def _iter_batches(items: Sequence[Any], batch_size: int) -> list[list[Any]]:
    """Split ``items`` into chunks of at most ``batch_size``."""
    return [list(items[i : i + batch_size]) for i in range(0, len(items), batch_size)]


def _ingest_url(config_obj: Any) -> str:
    """Return the chainlens-research ingest endpoint."""
    base = getattr(config_obj, "CHAINLENS_API_URL", "http://localhost:3001").rstrip("/")
    return f"{base}/v1/ingest/scraper"


def _coerce_response_json(response: httpx.Response) -> dict[str, Any]:
    """Best-effort JSON decode; return empty dict for empty bodies."""
    if response.status_code == 204 or not response.content:
        # Some test doubles set content to b"" even when json_data is present.
        # httpx.Response.json() prefers content, so explicitly fall back to
        # _json if it was populated (e.g., test fixtures).
        if isinstance(getattr(response, "_json", None), dict):
            return response._json  # type: ignore[union-attr]
        return {}
    try:
        return response.json()
    except Exception:
        return {}


async def _post_batch(
    scraper_id: str,
    workspace_id: int,
    batch: list[Any],
    config_obj: Any,
) -> tuple[int, dict[str, Any]]:
    """POST one batch to chainlens-research with retries on 5xx / timeout.

    Returns ``(status_code, response_body)`` for 200, 409, or terminal failure.
    """
    url = _ingest_url(config_obj)
    auth_header = get_chainlens_auth_header(config_obj)
    timeout = float(getattr(config_obj, "CHAINLENS_INGEST_TIMEOUT_SECONDS", 5))
    max_attempts = int(getattr(config_obj, "CHAINLENS_INGEST_RETRY_MAX_ATTEMPTS", 3))
    backoff = float(getattr(config_obj, "CHAINLENS_INGEST_RETRY_BACKOFF_SECONDS", 0.0))

    body: dict[str, Any] = {
        "scraper_id": scraper_id,
        "workspace_id": workspace_id,
        "source": "nowing_scraper",
        "chunks": [_chunk_to_dict(chunk) for chunk in batch],
    }

    last_status = 0
    last_body: dict[str, Any] = {}

    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    url,
                    json=body,
                    headers=auth_header,
                )
                last_status = response.status_code
                last_body = _coerce_response_json(response)

                if response.status_code == 200:
                    return 200, last_body
                if response.status_code == 409:
                    return 409, last_body
                if response.status_code >= 500:
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(backoff * (2**attempt))
                        continue
                    return last_status, last_body
                # Non-retryable 4xx
                return last_status, last_body
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
            if attempt < max_attempts - 1:
                await asyncio.sleep(backoff * (2**attempt))
                continue
            raise exc

    return last_status, last_body


def _extract_job_id(body: dict[str, Any]) -> str | None:
    """Return the ingest job id from a chainlens response body."""
    return body.get("ingestJobId") or body.get("ingest_job_id")


def _source_ids_from_batch(batch: list[Any]) -> list[str]:
    """Extract sourceId values from a batch of chunks for bookkeeping."""
    source_ids: list[str] = []
    for chunk in batch:
        if isinstance(chunk, BaseModel):
            source_id = chunk.metadata.sourceId if hasattr(chunk, "metadata") else None
        elif isinstance(chunk, dict):
            meta = chunk.get("metadata") or {}
            source_id = meta.get("sourceId")
        else:
            source_id = None
        if source_id:
            source_ids.append(str(source_id))
    return source_ids


class NowingIngestService:
    """Send ``Chunk[]`` payloads to chainlens-research ``POST /v1/ingest/scraper``."""

    async def ingest(
        self,
        scraper_id: str,
        chunks: Sequence[Any],
        workspace_id: int,
        session: AsyncSession | None = None,
        run_id: str | None = None,
    ) -> IngestResult:
        """Ingest ``chunks`` and return a stable ``IngestResult``.

        Batches larger than ``CHAINLENS_INGEST_MAX_BATCH_SIZE`` are paginated.
        ``409`` duplicate sourceIds are mapped to ``noop`` and the remaining
        batch continues. ``5xx`` / network / timeout errors are retried with
        exponential backoff up to ``CHAINLENS_INGEST_RETRY_MAX_ATTEMPTS``.
        """
        if not chunks:
            return IngestResult(
                ingest_job_id=None,
                status="noop",
                error="no chunks to ingest",
            )

        batch_size = int(getattr(config, "CHAINLENS_INGEST_MAX_BATCH_SIZE", 1000))
        batches = _iter_batches(chunks, batch_size)

        child_job_ids: list[str] = []
        noop_source_ids: list[str] = []
        ingested_source_ids: list[str] = []
        parent_job_id: str | None = None
        overall_status = "ok"

        if len(batches) > 1:
            parent_job_id = f"parent:{uuid.uuid4().hex}"

        for batch in batches:
            status_code, body = await _post_batch(
                scraper_id,
                workspace_id,
                batch,
                config,
            )

            if status_code == 200:
                job_id = _extract_job_id(body)
                child_job_ids.append(job_id) if job_id else None
                ingested_source_ids.extend(_source_ids_from_batch(batch))
            elif status_code == 409:
                job_id = _extract_job_id(body)
                if job_id:
                    child_job_ids.append(job_id)
                noop_source_ids.extend(body.get("noop_source_ids", []))
                ingested_source_ids.extend(body.get("ingested_source_ids", []))
            else:
                overall_status = "failed"
                metrics.record_chainlens_ingest_failed(
                    scraper_id=scraper_id,
                    workspace_id=workspace_id,
                    status_code=status_code,
                    error=body.get("error") or "unknown",
                )
                # Dead-letter: log the failed batch for an outbox worker to replay.
                logger.error(
                    "chainlens ingest failed after retries",
                    extra={
                        "scraper_id": scraper_id,
                        "workspace_id": workspace_id,
                        "status_code": status_code,
                        "batch_size": len(batch),
                    },
                )

        result = IngestResult(
            ingest_job_id=parent_job_id
            or (child_job_ids[0] if child_job_ids else None),
            parent_ingest_job_id=parent_job_id,
            child_ingest_job_ids=child_job_ids,
            noop_source_ids=noop_source_ids,
            ingested_source_ids=ingested_source_ids,
            status=overall_status,
        )

        if session is not None:
            from app.db import ChainLensIngestJob

            job = ChainLensIngestJob(
                workspace_id=workspace_id,
                scraper_id=scraper_id,
                parent_ingest_job_id=result.parent_ingest_job_id,
                child_ingest_job_ids=result.child_ingest_job_ids,
                noop_source_ids=result.noop_source_ids,
                ingested_source_ids=result.ingested_source_ids,
                status=result.status,
                error=result.error,
                run_id=run_id,
            )
            add_result = session.add(job)
            if inspect.isawaitable(add_result):
                await add_result
            await session.commit()

        return result
