"""Internal chainlens-research callback routes.

These endpoints are called by the chainlens-research engine, not by the
Nowing web client. Authentication is service-to-service via a shared
``Authorization: Bearer <CHAINLENS_SERVICE_TOKEN>`` header plus
``X-Workspace-Id`` for workspace scoping.

The actual scraper dispatch lives in Story 20.2 and private-data search in
Story 20.3; this module provides the auth-guarded door and minimal stubs
that return accepted status so callers can validate the contract.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from app.services.chainlens.auth import (
    ChainLensAuthContext,
    get_chainlens_auth,
)

router = APIRouter()


def _chainlens_auth_dependency(request: Request) -> ChainLensAuthContext:
    """FastAPI dependency that validates an inbound chainlens-research request."""
    return get_chainlens_auth().validate_inbound_token(request)


async def chainlens_auth_dependency(
    request: Request,
) -> ChainLensAuthContext:
    """Async wrapper for FastAPI Depends."""
    return _chainlens_auth_dependency(request)


@router.post("/scraper/{scraper_id}/run")
async def run_scraper_for_chainlens(
    scraper_id: str,
    context: ChainLensAuthContext = Depends(chainlens_auth_dependency),
) -> dict[str, Any]:
    """Trigger a Nowing scraper on behalf of chainlens-research.

    ponytail: Full dispatch is implemented in Story 20.2. This endpoint
    validates the service token and returns accepted so the contract can be
    exercised before the capability wiring lands.
    """
    return {
        "status": "accepted",
        "scraper_id": scraper_id,
        "workspace_id": context.workspace_id,
    }


@router.post("/private-data/search")
async def private_data_search_for_chainlens(
    context: ChainLensAuthContext = Depends(chainlens_auth_dependency),
) -> dict[str, Any]:
    """Search Nowing private data on behalf of chainlens-research.

    ponytail: Full search implementation is in Story 20.3. This endpoint
    validates the service token and returns accepted.
    """
    return {
        "status": "accepted",
        "workspace_id": context.workspace_id,
    }
