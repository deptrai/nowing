"""Real API Integration tests for Story 26.27: Pre-Flight Lead Plan & AC-4 Smoke Test."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app
from app.auth.context import AuthContext
from app.db import Permission, User, Workspace, get_async_session
from app.lead_intelligence.schemas import LocationProfilePayload
from app.users import require_session_context

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
    app.dependency_overrides[get_async_session] = _mock_session
    yield auth
    app.dependency_overrides.pop(require_session_context, None)
    app.dependency_overrides.pop(get_async_session, None)


class TestPreFlightPlanRealApi:
    """Validate Pre-Flight Lead Plan Summary and Smoke Test execution on real FastAPI endpoints."""

    @pytest.mark.asyncio
    async def test_preflight_plan_with_location_profile_and_coverage(
        self,
        db_workspace: Workspace,
        override_auth_owner: AuthContext,
    ) -> None:
        """AC-1: POST /campaigns/plan returns enriched source allocations, coverage badges, and cost."""
        payload = {
            "name": "Chiến dịch BĐS Hà Nội - Test Real API",
            "workspace_id": db_workspace.id,
            "icp_config": {
                "template": "real_estate_investor",
                "target_industries": ["Bất động sản"],
                "locations": ["Hà Nội"],
                "company_size_range": None,
                "tech_stack": [],
                "intents": ["BÁN"],
                "negative_keywords": [],
                "reverse_icp_url": None,
                "custom_instructions": "Mua bán nhà đất chính chủ",
                "location_profile": {
                    "location_type": "both",
                    "province_code": "HN",
                    "province_name": "Hà Nội",
                    "district_codes": ["001"],
                    "district_names": ["Quận Ba Đình"],
                    "ward_codes": [],
                    "ward_names": [],
                    "location_text": "Hà Nội (Quận Ba Đình)",
                },
            },
            "source_budget_config": {
                "sources": ["batdongsan", "chotot"],
                "expected_leads_target": 100,
                "max_daily_spend_vnd": 500000,
                "min_fit_score": 60,
                "min_intent_score": 50,
                "max_contacts_per_lead": 3,
                "exclude_dnc": True,
                "auto_unlock_verified_phones": False,
            },
            "launch_config": {
                "schedule_type": "once",
                "cron_expression": None,
                "start_time": None,
                "auto_start": True,
                "export_destination": "workspace",
                "notification_webhook": None,
            },
        }

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v1/workspaces/{db_workspace.id}/campaigns/plan",
                json=payload,
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()

            # AC-1 assertions
            assert data["campaign_name"] == "Chiến dịch BĐS Hà Nội - Test Real API"
            assert data["workspace_id"] == db_workspace.id
            assert data["total_planned_sources"] == 2
            assert set(data["expected_sources"]) == {"batdongsan", "chotot"}

            allocations = data["source_allocations"]
            assert len(allocations) == 2
            for alloc in allocations:
                assert "source_name" in alloc
                assert "location_coverage_quality" in alloc
                assert alloc["location_coverage_quality"] in ("high", "medium", "low", "none")
                assert 0.0 <= alloc["location_coverage_score"] <= 1.0
                assert alloc["status"] in ("ready", "degraded", "offline")

            assert data["estimated_reachable_leads"] > 0
            # Base cost: 100 * 1500 VND = 150,000 VND
            assert data["estimated_cost_vnd"] == 150000
            assert data["estimated_cost_micros"] == 150000 * 40

    @pytest.mark.asyncio
    async def test_smoke_test_execution_persist_false(
        self,
        db_workspace: Workspace,
        override_auth_owner: AuthContext,
    ) -> None:
        """AC-4: POST /campaigns/execute?persist=false runs low-cost 5-lead smoke test."""
        payload = {
            "name": "Smoke Test Run (5 Leads)",
            "workspace_id": db_workspace.id,
            "icp_config": {
                "template": "b2b_saas",
                "target_industries": ["Information Technology"],
                "locations": ["Hà Nội"],
                "company_size_range": None,
                "tech_stack": ["Python", "FastAPI"],
                "intents": ["TUYỂN"],
                "negative_keywords": [],
                "reverse_icp_url": None,
                "custom_instructions": "Tuyển dụng kỹ sư",
                "location_profile": None,
            },
            "source_budget_config": {
                "sources": ["vn_jobs"],
                "expected_leads_target": 5,
                "max_daily_spend_vnd": 200000,
                "min_fit_score": 50,
                "min_intent_score": 50,
                "max_contacts_per_lead": 3,
                "exclude_dnc": True,
                "auto_unlock_verified_phones": False,
            },
            "launch_config": {
                "schedule_type": "once",
                "cron_expression": None,
                "start_time": None,
                "auto_start": True,
                "export_destination": "workspace",
                "notification_webhook": None,
            },
        }

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v1/workspaces/{db_workspace.id}/campaigns/execute?persist=false",
                json=payload,
            )
            assert resp.status_code == 200, resp.text
            result = resp.json()

            assert "status" in result
            assert "total_discovered" in result
            assert "subtask_plans" in result
            assert len(result["subtask_plans"]) >= 1
            assert result["subtask_plans"][0]["limit"] == 5
