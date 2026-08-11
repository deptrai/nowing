"""Nowing -> chainlens-research scraper ingest adapter."""

from __future__ import annotations

import inspect
import json
import logging
import uuid
from collections.abc import Sequence
from typing import Any

import httpx
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.connectors.exceptions import (
    ConnectorAPIError,
    ConnectorAuthError,
    ConnectorRateLimitError,
    ConnectorTimeoutError,
)
from app.observability import metrics
from app.utils.async_retry import build_retry

from .auth import ChainLensServiceAuth

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


def _positive_int(value: Any, default: int) -> int:
    """Coerce ``value`` to a positive int, falling back to ``default``."""
    try:
        v = int(value)
    except (TypeError, ValueError):
        v = default
    return max(1, v)


def _positive_float(value: Any, default: float) -> float:
    """Coerce ``value`` to a non-negative float, falling back to ``default``."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = default
    return max(0.0, v)


def _cfg(config_obj: Any, name: str, default: Any) -> Any:
    """Safely read a config attribute, falling back to ``default``."""
    return getattr(config_obj, name, default)


def _ingest_url(config_obj: Any) -> str:
    """Return the chainlens-research ingest endpoint."""
    base = _cfg(config_obj, "CHAINLENS_API_URL", "http://localhost:3001").rstrip("/")
    return f"{base}/v1/ingest/scraper"


def _coerce_response_json(response: httpx.Response) -> dict[str, Any]:
    """Best-effort JSON decode; return empty dict for empty bodies."""
    if response.status_code == 204:
        return {}
    if getattr(response, "_json", None) is not None and not response.content:
        if isinstance(response._json, dict):  # type: ignore[union-attr]
            return response._json  # type: ignore[union-attr]
        return {}
    if not response.content:
        return {}
    try:
        return response.json()
    except Exception as exc:
        logger.warning("Failed to decode chainlens ingest response as JSON: %s", exc)
        return {}


def _extract_job_id(body: dict[str, Any]) -> str | None:
    """Return the ingest job id from a chainlens response body."""
    return body.get("ingestJobId") or body.get("ingest_job_id")


def _noop_source_ids(body: dict[str, Any]) -> list[str]:
    """Read noop source ids from a ChainLens response (camel or snake case)."""
    return body.get("noopSourceIds") or body.get("noop_source_ids") or []


def _ingested_source_ids(body: dict[str, Any]) -> list[str]:
    """Read ingested source ids from a ChainLens response (camel or snake case)."""
    return body.get("ingestedSourceIds") or body.get("ingested_source_ids") or []


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
        else:
            logger.warning("Skipping chunk without sourceId in batch")
    return source_ids


async def _post_batch_core(
    scraper_id: str,
    workspace_id: int,
    batch: list[Any],
    config_obj: Any,
) -> dict[str, Any]:
    """POST one batch and map the HTTP status to a retry-aware exception.

    200/202 return the parsed body. 400, 401/403 are non-retryable client errors.
    429, 5xx and 504 are retryable. 409 is not expected by the current ChainLens
    contract (duplicates are handled idempotently via 200/202), but is mapped
    to a non-retryable error defensively.
    """
    url = _ingest_url(config_obj)
    auth = ChainLensServiceAuth(config_obj=config_obj)
    if not auth.configured:
        raise ConnectorAuthError(
            "chainlens service token not configured",
            service="chainlens_ingest",
            status_code=401,
        )
    timeout = _positive_float(
        _cfg(config_obj, "CHAINLENS_INGEST_TIMEOUT_SECONDS", 5.0), 5.0
    )

    body: dict[str, Any] = {
        "source": "nowing_scraper",
        "scraperId": scraper_id,
        "workspaceId": workspace_id,
        "chunks": [_chunk_to_dict(chunk) for chunk in batch],
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        headers = auth.get_outbound_headers(
            workspace_id, content_type="application/json"
        )
        response = await client.post(
            url,
            json=body,
            headers=headers,
        )
        # On 401, rotate token once and retry the same request in-flight.
        if response.status_code == 401:
            rotated = auth.rotate(workspace_id=workspace_id, reason="401_response")
            if rotated:
                headers = auth.get_outbound_headers(
                    workspace_id, content_type="application/json"
                )
                response = await client.post(
                    url,
                    json=body,
                    headers=headers,
                )

    parsed = _coerce_response_json(response)

    if response.status_code in (200, 202):
        return parsed
    if response.status_code == 409:
        raise ConnectorAPIError(
            "chainlens ingest conflict (409)",
            service="chainlens_ingest",
            status_code=409,
            response_body=parsed,
        )
    if response.status_code == 429:
        raise ConnectorRateLimitError(
            "chainlens ingest rate limited (429)",
            service="chainlens_ingest",
            response_body=parsed,
        )
    if response.status_code in (401, 403):
        raise ConnectorAuthError(
            f"chainlens ingest authentication failed ({response.status_code})",
            service="chainlens_ingest",
            status_code=response.status_code,
            response_body=parsed,
        )
    if response.status_code == 504:
        raise ConnectorTimeoutError(
            "chainlens ingest gateway timeout (504)",
            service="chainlens_ingest",
            status_code=504,
            response_body=parsed,
        )
    if response.status_code >= 500:
        raise ConnectorAPIError(
            f"chainlens ingest server error ({response.status_code})",
            service="chainlens_ingest",
            status_code=response.status_code,
            response_body=parsed,
        )
    raise ConnectorAPIError(
        f"chainlens ingest client error ({response.status_code})",
        service="chainlens_ingest",
        status_code=response.status_code,
        response_body=parsed,
    )


async def _post_batch(
    scraper_id: str,
    workspace_id: int,
    batch: list[Any],
    config_obj: Any,
) -> dict[str, Any]:
    """POST one batch with retries on 5xx, 504, 429, network/timeout errors."""
    max_attempts = _positive_int(
        _cfg(config_obj, "CHAINLENS_INGEST_RETRY_MAX_ATTEMPTS", 3), 3
    )
    initial_delay = _positive_float(
        _cfg(config_obj, "CHAINLENS_INGEST_RETRY_BACKOFF_SECONDS", 1.0), 1.0
    )

    return await build_retry(
        max_attempts=max_attempts,
        service="chainlens_ingest",
        initial_delay=initial_delay,
        max_delay=60.0,
    )(_post_batch_core)(scraper_id, workspace_id, batch, config_obj)


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
        ``200`` (idempotent duplicate) and ``202`` (accepted) responses carry
        ``ingestedSourceIds`` / ``noopSourceIds`` that drive the result status.
        ``429`` / ``5xx`` / network / timeout errors are retried with
        exponential backoff up to ``CHAINLENS_INGEST_RETRY_MAX_ATTEMPTS``.
        """
        if not chunks:
            return IngestResult(
                ingest_job_id=None,
                status="noop",
                error="no chunks to ingest",
            )

        if len(scraper_id) > 100:
            raise ValueError("scraper_id exceeds 100 character limit")

        auth = ChainLensServiceAuth(config_obj=config)
        if not auth.configured:
            return IngestResult(
                ingest_job_id=None,
                status="service_auth_unavailable",
                error="CHAINLENS_SERVICE_TOKEN not configured",
            )

        batch_size = _positive_int(
            _cfg(config, "CHAINLENS_INGEST_MAX_BATCH_SIZE", 1000), 1000
        )
        batches = _iter_batches(chunks, batch_size)

        child_job_ids: list[str] = []
        noop_source_ids: list[str] = []
        ingested_source_ids: list[str] = []
        failed_batches: list[dict[str, Any]] = []
        parent_job_id: str | None = None
        overall_status = "ok"

        if len(batches) > 1:
            parent_job_id = f"parent:{uuid.uuid4().hex}"

        for batch in batches:
            try:
                body = await _post_batch(
                    scraper_id,
                    workspace_id,
                    batch,
                    config,
                )
                job_id = _extract_job_id(body)
                if job_id:
                    child_job_ids.append(job_id)
                batch_ingested = _ingested_source_ids(body)
                batch_noop = _noop_source_ids(body)
                if not batch_ingested and not batch_noop:
                    # Fallback for older/noisy responses that omit source id lists.
                    batch_ingested = _source_ids_from_batch(batch)
                ingested_source_ids.extend(batch_ingested)
                noop_source_ids.extend(batch_noop)
            except ConnectorAuthError as exc:
                overall_status = "service_auth_unavailable"
                auth_reason = (
                    "not_configured"
                    if "not configured" in str(exc).lower()
                    else "invalid_token"
                )
                metrics.record_chainlens_auth_failed(
                    workspace_id=workspace_id,
                    reason=auth_reason,
                )
                failed_batches.append(
                    {
                        "batch": [_chunk_to_dict(chunk) for chunk in batch],
                        "status_code": exc.status_code,
                        "error": str(exc),
                    }
                )
                break
            except ConnectorAPIError as exc:
                if exc.status_code == 409:
                    # Defensive: current ChainLens contract handles duplicates
                    # idempotently via 200/202, but support 409 if it appears.
                    job_id = _extract_job_id(exc.response_body or {})
                    if job_id:
                        child_job_ids.append(job_id)
                    noop_source_ids.extend(_noop_source_ids(exc.response_body or {}))
                    ingested_source_ids.extend(
                        _ingested_source_ids(exc.response_body or {})
                    )
                    continue

                overall_status = "failed"
                metrics.record_chainlens_ingest_failed(
                    scraper_id=scraper_id,
                    workspace_id=workspace_id,
                    status_code=exc.status_code or 0,
                    error=str(exc),
                )
                failed_batches.append(
                    {
                        "batch": [_chunk_to_dict(chunk) for chunk in batch],
                        "status_code": exc.status_code,
                        "error": str(exc),
                    }
                )
                logger.error(
                    "chainlens ingest failed after retries",
                    extra={
                        "scraper_id": scraper_id,
                        "workspace_id": workspace_id,
                        "status_code": exc.status_code,
                        "batch_size": len(batch),
                    },
                )
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                overall_status = "failed"
                metrics.record_chainlens_ingest_failed(
                    scraper_id=scraper_id,
                    workspace_id=workspace_id,
                    status_code=0,
                    error=str(exc),
                )
                failed_batches.append(
                    {
                        "batch": [_chunk_to_dict(chunk) for chunk in batch],
                        "status_code": 0,
                        "error": str(exc),
                    }
                )
                logger.error(
                    "chainlens ingest timed out or disconnected after retries",
                    extra={
                        "scraper_id": scraper_id,
                        "workspace_id": workspace_id,
                        "batch_size": len(batch),
                    },
                )

        has_success = bool(ingested_source_ids)

        if overall_status == "ok":
            if noop_source_ids and not has_success:
                overall_status = "noop"
            elif noop_source_ids and has_success:
                overall_status = "partial"
        elif overall_status == "failed" and has_success:
            overall_status = "partial"

        result = IngestResult(
            ingest_job_id=parent_job_id
            or (child_job_ids[0] if child_job_ids else None),
            parent_ingest_job_id=parent_job_id,
            child_ingest_job_ids=child_job_ids,
            noop_source_ids=noop_source_ids,
            ingested_source_ids=ingested_source_ids,
            status=overall_status,
        )

        if failed_batches:
            result.error = json.dumps(
                {
                    "failed_batches": failed_batches,
                    "summary": f"{len(failed_batches)} batch(es) failed",
                },
                ensure_ascii=False,
                default=str,
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
                dead_letter_payload=failed_batches if failed_batches else None,
                run_id=run_id,
            )
            try:
                add_result = session.add(job)
                if inspect.isawaitable(add_result):
                    await add_result
                await session.commit()
            except Exception as exc:
                await session.rollback()
                result.error = f"{result.error or ''}; persistence failed: {exc}".strip(
                    "; "
                )

        return result
