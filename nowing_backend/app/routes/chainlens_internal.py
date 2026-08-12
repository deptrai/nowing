"""Internal routes called by ``chainlens-research`` (Story 20.2).

These endpoints are NOT part of the public workspace API; they are
service-to-service callbacks authenticated with ``ChainLensServiceAuth``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.core import execute_with_context
from app.capabilities.core.store import get_capability
from app.capabilities.core.types import CapabilityContext
from app.db import Workspace, get_async_session
from app.services.chainlens.auth import ChainLensAuthContext, ChainLensServiceAuth
from app.services.chainlens.ingest import NowingIngestService
from app.services.chainlens.private_provider import PrivateProviderService
from app.services.chainlens.schemas import (
    PrivateDataSearchRequest,
    PrivateDataSearchResponse,
)
from app.services.scraper_chunks.schemas import Chunk
from app.services.scraper_chunks.serializer import to_chunks

router = APIRouter(tags=["chainlens-internal"])

logger = logging.getLogger(__name__)

# Domain slug -> fully qualified capability name.
_DOMAIN_CAPABILITY_MAP: dict[str, str] = {
    "batdongsan": "batdongsan.scrape",
    "vn_jobs": "vn_jobs.aggregate",
}


def _resolve_scraper_id(scraper_id: str) -> str:
    """Allow callers to use either a domain slug or a full capability name."""
    try:
        get_capability(scraper_id)
        return scraper_id
    except KeyError:
        pass
    if scraper_id in _DOMAIN_CAPABILITY_MAP:
        mapped = _DOMAIN_CAPABILITY_MAP[scraper_id]
        try:
            get_capability(mapped)
            return mapped
        except KeyError:
            pass
    # Also try the domain with a ``.scrape`` suffix as a fallback.
    candidate = f"{scraper_id}.scrape"
    try:
        get_capability(candidate)
        return candidate
    except KeyError:
        pass
    return scraper_id


class _ScraperRunRequest(BaseModel):
    """Payload for ``POST /v1/scraper/{scraper_id}/run``."""

    query: str | None = Field(default=None)
    params: dict[str, Any] = Field(default_factory=dict)
    workspace_id: int | None = Field(default=None, gt=0)


class _ScraperRunResponse(BaseModel):
    """Response returned to chainlens-research after a scraper callback."""

    scraper_id: str
    ingest_job_id: str | None = None
    status: str
    ingested_count: int = 0
    noop_count: int = 0
    error: str | None = None


def chainlens_auth_dependency(request: Request) -> ChainLensAuthContext:
    """FastAPI dependency to validate an inbound chainlens-research request."""
    auth = ChainLensServiceAuth()
    return auth.validate_inbound_token(request)


@router.post("/scraper/{scraper_id}/run")
async def run_scraper_for_chainlens(
    scraper_id: str,
    body: _ScraperRunRequest = Body(default=_ScraperRunRequest()),
    session: AsyncSession = Depends(get_async_session),
    auth_ctx: ChainLensAuthContext = Depends(chainlens_auth_dependency),
) -> _ScraperRunResponse:
    """Run a Nowing scraper and push the results back to chainlens-research."""
    if auth_ctx is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing ChainLens service token",
        )

    # Trust the authenticated service context, not the request body.
    workspace_id = auth_ctx.workspace_id
    correlation_id = auth_ctx.correlation_id
    capability_name = _resolve_scraper_id(scraper_id)
    logger.info(
        "chainlens scraper run requested",
        extra={
            "scraper_id": scraper_id,
            "capability_name": capability_name,
            "workspace_id": workspace_id,
            "correlation_id": correlation_id,
        },
    )
    try:
        capability = get_capability(capability_name)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown scraper capability: {scraper_id}",
        ) from None

    # Auth-only probes (e.g. service-token tests) return accepted immediately.
    if not body.query and not body.params:
        return _ScraperRunResponse(
            scraper_id=scraper_id,
            status="accepted",
        )

    # Build scraper input from the provided params, defaulting the query to
    # a keyword/city where the scraper schema expects one.
    input_data = dict(body.params) if body.params else {}
    if body.query and "query" not in input_data:
        input_data["query"] = body.query
    if (
        body.query
        and capability_name == "batdongsan.scrape"
        and "city" not in input_data
    ):
        # ponytail: city-level gap-fill defaults to HN; the caller should
        # supply a city in ``params`` for precise targeting.
        input_data.setdefault("city", "HN")
    if (
        body.query
        and capability_name == "vn_jobs.aggregate"
        and "keyword" not in input_data
    ):
        input_data.setdefault("keyword", body.query)

    try:
        payload = capability.input_schema(**input_data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid scraper parameters for {scraper_id}: {exc}",
        ) from exc

    ctx = CapabilityContext(session=session, workspace_id=workspace_id)
    output = await execute_with_context(capability.executor, payload=payload, ctx=ctx)

    # AC-6: the vn_jobs.aggregate executor already chunks and ingests the
    # listings. Avoid double-ingest by using its output directly.
    if capability_name == "vn_jobs.aggregate" and hasattr(output, "ingest_status"):
        response = _ScraperRunResponse(
            scraper_id=scraper_id,
            ingest_job_id=getattr(output, "ingest_job_id", None),
            status=getattr(output, "ingest_status", "no_items") or "no_items",
            ingested_count=getattr(output, "ingested_count", 0),
            noop_count=getattr(output, "noop_count", 0),
        )
        logger.info(
            "chainlens scraper run completed (vn_jobs.aggregate executor ingest)",
            extra={
                "scraper_id": scraper_id,
                "workspace_id": workspace_id,
                "correlation_id": correlation_id,
                "status": response.status,
                "ingest_job_id": response.ingest_job_id,
                "ingested_count": response.ingested_count,
                "noop_count": response.noop_count,
            },
        )
        return response

    items: list[Any] = []
    if hasattr(output, "items") and isinstance(output.items, list):
        items = output.items

    if not items:
        return _ScraperRunResponse(
            scraper_id=scraper_id,
            status="no_items",
            ingested_count=0,
        )

    # Normalize items to the canonical ``Chunk[]`` shape expected by
    # chainlens-research ingest.
    domain = scraper_id.split(".")[0]
    fetched_at = datetime.now(UTC).isoformat()
    chunks: list[Chunk] = []
    for item in items:
        try:
            chunks.extend(
                to_chunks(
                    domain=domain,
                    data=item,
                    fetched_at=fetched_at,
                    content_type="text/markdown",
                    category=None,
                )
            )
        except Exception:
            # Skip records that cannot be normalized; the ingestion still
            # proceeds with the rest.
            continue

    if not chunks:
        return _ScraperRunResponse(
            scraper_id=scraper_id,
            status="no_chunks",
            ingested_count=0,
            error="Scraper produced items but none could be serialized to chunks",
        )

    ingest_service = NowingIngestService()
    result = await ingest_service.ingest(
        scraper_id=scraper_id,
        chunks=chunks,
        workspace_id=workspace_id,
        session=session,
        correlation_id=correlation_id,
    )

    # Propagate the ingest job id back to the capability output so REST/MCP/chat
    # consumers of VnJobAggregateOutput see it (AC-6, Story 12.4e).
    if hasattr(output, "ingest_job_id"):
        output.ingest_job_id = result.ingest_job_id or result.parent_ingest_job_id

    response = _ScraperRunResponse(
        scraper_id=scraper_id,
        ingest_job_id=result.ingest_job_id or result.parent_ingest_job_id,
        status=result.status,
        ingested_count=len(result.ingested_source_ids or []),
        noop_count=len(result.noop_source_ids or []),
    )

    logger.info(
        "chainlens scraper run completed",
        extra={
            "scraper_id": scraper_id,
            "workspace_id": workspace_id,
            "correlation_id": correlation_id,
            "status": response.status,
            "ingest_job_id": response.ingest_job_id,
            "ingested_count": response.ingested_count,
            "noop_count": response.noop_count,
        },
    )
    return response


@router.post("/private-data/search")
async def search_private_data(
    request: Request,
    body: PrivateDataSearchRequest,
    session: AsyncSession = Depends(get_async_session),
    auth_ctx: ChainLensAuthContext = Depends(chainlens_auth_dependency),
) -> PrivateDataSearchResponse:
    """Search a workspace's private knowledge base on behalf of chainlens-research."""
    if body.workspaceId != auth_ctx.workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace mismatch",
        )

    workspace = await session.get(Workspace, body.workspaceId)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unknown workspace",
        )

    service = PrivateProviderService(session)
    return await service.search(
        request=body,
        workspace=workspace,
        correlation_id=auth_ctx.correlation_id,
    )
