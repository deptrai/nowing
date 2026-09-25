"""Unit tests for ChainLens S2S Hardening (Story 40.5)."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from app.routes.chainlens_internal import search_private_data
from app.services.chainlens.auth import ChainLensAuthContext
from app.services.chainlens.schemas import PrivateDataSearchRequest


@pytest.mark.asyncio
async def test_search_private_data_enforces_5s_timeout():
    """Verify search_private_data raises HTTP 504 when search exceeds 5.0s."""
    req = MagicMock()
    body = PrivateDataSearchRequest(
        workspaceId=1,
        query="test query",
    )
    session = AsyncMock()
    session.get = AsyncMock(return_value=MagicMock(id=1))
    auth_ctx = ChainLensAuthContext(
        workspace_id=1,
        correlation_id="corr-123",
        token="valid-token",
    )

    async def _slow_search(**kwargs):
        await asyncio.sleep(5.5)

    with patch("app.routes.chainlens_internal.PrivateProviderService") as MockService:
        instance = MockService.return_value
        instance.search = _slow_search

        with pytest.raises(HTTPException) as exc_info:
            await search_private_data(
                request=req,
                body=body,
                session=session,
                auth_ctx=auth_ctx,
            )

        assert exc_info.value.status_code == 504
        assert "5.0s" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_search_private_data_workspace_mismatch():
    """Verify search_private_data rejects mismatch with HTTP 403."""
    req = MagicMock()
    body = PrivateDataSearchRequest(
        workspaceId=2,  # mismatch with auth_ctx workspace_id=1
        query="test",
    )
    session = AsyncMock()
    auth_ctx = ChainLensAuthContext(
        workspace_id=1,
        correlation_id="corr-123",
        token="valid-token",
    )

    with pytest.raises(HTTPException) as exc_info:
        await search_private_data(
            request=req,
            body=body,
            session=session,
            auth_ctx=auth_ctx,
        )

    assert exc_info.value.status_code == 403
