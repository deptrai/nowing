"""Test-only entity extraction route for hermetic benchmarks (AC-1 / AD-107)."""

from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.rate_limiter import limiter
from app.schemas.extract_entities import (
    ExtractEntitiesRequest,
    ExtractEntitiesResponse,
)
from app.services.lead_extraction_service import LeadExtractionService

_MAX_SOURCE_TEXT_LEN = 100_000
_MAX_CONCURRENT_EXTRACTIONS = 4

_extraction_semaphore: asyncio.Semaphore | None = None
_extraction_service = LeadExtractionService()

router = APIRouter(prefix="/test", include_in_schema=False)


def _get_extraction_semaphore() -> asyncio.Semaphore:
    """Lazy per-process concurrency guard for extraction calls.

    ponytail: created on first request inside the running event loop to avoid
    ``asyncio.Semaphore`` construction outside a loop at import time.
    """
    global _extraction_semaphore
    if _extraction_semaphore is None:
        _extraction_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_EXTRACTIONS)
    return _extraction_semaphore


@router.post(
    "/extract-entities",
    response_model=ExtractEntitiesResponse,
    summary="Hermetic local extraction of phones and tax codes (test-only)",
    include_in_schema=False,
)
@limiter.limit("30/minute")
async def extract_entities(
    body: ExtractEntitiesRequest,
    request: Request,
    x_internal_test: str | None = Header(default=None, alias="X-Internal-Test"),
) -> ExtractEntitiesResponse:
    """Extract phones and tax codes from unstructured text without DB or external API calls."""
    expected_secret = os.getenv("TEST_EXTRACTION_SECRET")
    if not expected_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Test extraction endpoint is not configured",
        )

    if not x_internal_test or x_internal_test != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: missing or invalid X-Internal-Test header",
        )

    if len(body.source_text) > _MAX_SOURCE_TEXT_LEN:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"source_text exceeds {_MAX_SOURCE_TEXT_LEN} characters",
        )

    semaphore = _get_extraction_semaphore()
    async with semaphore:
        result = await _extraction_service.extract_from_text(body.source_text)

    return ExtractEntitiesResponse(
        phones=result.phones,
        tax_ids=result.tax_ids,
        tax_ids_valid=result.tax_ids_valid,
        company_name=result.company_name,
    )
