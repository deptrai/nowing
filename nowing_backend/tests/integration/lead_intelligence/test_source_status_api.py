"""Integration tests for Story 26.28: Source Status & Location Coverage API."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app
from app.auth.context import AuthContext
from app.db import User, Workspace, get_async_session
from app.users import get_auth_context, require_session_context

pytestmark = [pytest.mark.integration]


@pytest.fixture
def override_auth_owner(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
):
    """Provide authenticated workspace owner context."""
    auth = AuthContext.session(user=db_user)

    async def _mock_auth():
        return auth

    async def _mock_session():
        yield db_session

    app.dependency_overrides[require_session_context] = _mock_auth
    # RequirePermission depends on get_auth_context — without this override
    # the real cookie auth runs and returns 401.
    app.dependency_overrides[get_auth_context] = _mock_auth
    app.dependency_overrides[get_async_session] = _mock_session
    yield auth
    app.dependency_overrides.pop(require_session_context, None)
    app.dependency_overrides.pop(get_auth_context, None)


class TestSourceStatusApi:
    """Validate GET /workspaces/{id}/campaigns/sources/status endpoint."""

    @pytest.mark.asyncio
    async def test_get_all_source_statuses_idle(
        self,
        db_workspace: Workspace,
        override_auth_owner: AuthContext,
    ) -> None:
        """AC-4: Endpoint returns all canonical scraper adapters (10+ registered) with health and default coverage."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/api/v1/workspaces/{db_workspace.id}/campaigns/sources/status"
            )
            assert resp.status_code == 200, resp.text
            items = resp.json()
            assert isinstance(items, list)
            # Registry now also registers shopee/tiktok_shop/news (13 total);
            # AC-4 requires the 10 canonical names below, extra ones are fine.
            assert len(items) >= 10

            source_names = {s["source_name"] for s in items}
            expected = {
                "batdongsan",
                "chotot",
                "muaban_bds",
                "vn_jobs",
                "job_market",
                "vietnamworks",
                "enterprise",
                "muasamcong",
                "social",
                "telegram",
            }
            assert expected.issubset(source_names)

            for s in items:
                assert "source_name" in s
                assert "category" in s
                assert "status" in s
                assert s["status"] in ("ready", "degraded", "offline")
                assert "location_coverage_quality" in s
                assert s["location_coverage_quality"] in (
                    "high",
                    "medium",
                    "low",
                    "none",
                )
                assert isinstance(s["supported_provinces"], list)

    @pytest.mark.asyncio
    async def test_get_source_statuses_with_location_query(
        self,
        db_workspace: Workspace,
        override_auth_owner: AuthContext,
    ) -> None:
        """AC-1 & AC-4: Endpoint calculates contextual coverage quality when province_code is provided."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/api/v1/workspaces/{db_workspace.id}/campaigns/sources/status",
                params={"province_code": "HN", "district_codes": ["001"]},
            )
            assert resp.status_code == 200, resp.text
            items = resp.json()
            assert len(items) >= 10

            by_name = {s["source_name"]: s for s in items}
            # Batdongsan has explicit HN coverage -> high
            assert by_name["batdongsan"]["location_coverage_quality"] == "high"
            assert by_name["batdongsan"]["location_coverage_score"] >= 0.9
