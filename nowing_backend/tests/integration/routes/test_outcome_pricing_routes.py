"""Integration tests for Outcome Pricing & Meeting Booking Routes (Story 21.7 / AC-7).

Validates REST API endpoints for pricing plan retrieval/updates,
outcome meeting recording, and wallet deduction responses.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.users import get_auth_context

pytestmark = pytest.mark.integration


@pytest.fixture
def test_app() -> FastAPI:
    """Create test FastAPI application with mounted outcome pricing router."""
    from app.routes.outcome_pricing_routes import router as outcome_pricing_router

    app = FastAPI()
    app.include_router(outcome_pricing_router, prefix="/api/v1")
    return app


@pytest.fixture
def mock_auth() -> AuthContext:
    """Create mock authenticated user context."""
    user = MagicMock()
    user.id = uuid4()
    user.email = "founder@nowing.net"
    user.is_active = True
    user.is_superuser = False
    user.credit_micros_balance = 10_000_000

    auth = MagicMock(spec=AuthContext)
    auth.user = user
    auth.workspace_id = 1
    auth.client_id = None
    return auth


def test_get_pricing_plan(test_app: FastAPI, mock_auth: AuthContext) -> None:
    """GET /api/v1/workspaces/{workspace_id}/pricing-plan returns active rate card."""
    test_app.dependency_overrides[get_auth_context] = lambda: mock_auth

    mock_plan = {
        "id": str(uuid4()),
        "workspace_id": 1,
        "plan_type": "outcome",
        "seat_price": 0,
        "outcome_rates_json": {
            "meeting_booked": 2_000_000,
            "phone_unlock": 60_000,
            "lead_enriched": 40_000,
        },
        "is_active": True,
    }

    with (
        patch(
            "app.routes.outcome_pricing_routes.check_workspace_access",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "app.services.outcome_pricing_service.OutcomePricingService.get_or_create_workspace_plan",
            new=AsyncMock(return_value=mock_plan),
        ),
    ):
        client = TestClient(test_app)
        response = client.get("/api/v1/workspaces/1/pricing-plan")
        assert response.status_code == 200
        data = response.json()
        assert data["plan_type"] == "outcome"
        assert data["outcome_rates_json"]["meeting_booked"] == 2_000_000


def test_record_meeting_booked_route_success(
    test_app: FastAPI, mock_auth: AuthContext
) -> None:
    """POST /api/v1/workspaces/{workspace_id}/outcomes/meeting-booked records meeting and debits credits."""
    test_app.dependency_overrides[get_auth_context] = lambda: mock_auth
    lead_id = str(uuid4())

    mock_outcome = MagicMock()
    mock_outcome.id = uuid4()
    mock_outcome.workspace_id = 1
    mock_outcome.event_type = "outcome_meeting_booked"
    mock_outcome.lead_id = lead_id
    mock_outcome.sequence_id = None
    mock_outcome.cost_micros = 2_000_000
    mock_outcome.attribution = "source:batdongsan"
    mock_outcome.outcome_metadata = {"title": "Sales Pitch Demo"}
    mock_outcome.created_at = datetime.now(UTC)

    with (
        patch(
            "app.routes.outcome_pricing_routes.check_workspace_access",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "app.services.outcome_pricing_service.OutcomePricingService.record_meeting_booked",
            new=AsyncMock(return_value=mock_outcome),
        ),
    ):
        client = TestClient(test_app)
        payload = {
            "lead_id": lead_id,
            "metadata": {"title": "Sales Pitch Demo", "channel": "google_meet"},
        }
        response = client.post(
            "/api/v1/workspaces/1/outcomes/meeting-booked", json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["event_type"] == "outcome_meeting_booked"
        assert data["cost_micros"] == 2_000_000


def test_update_pricing_plan(test_app: FastAPI, mock_auth: AuthContext) -> None:
    """PUT /api/v1/workspaces/{workspace_id}/pricing-plan updates plan (Admin/Owner only)."""
    test_app.dependency_overrides[get_auth_context] = lambda: mock_auth

    mock_plan = {
        "id": str(uuid4()),
        "workspace_id": 1,
        "plan_type": "outcome",
        "seat_price": 0,
        "outcome_rates_json": {
            "meeting_booked": 3_000_000,
        },
        "is_active": True,
    }

    with (
        patch(
            "app.routes.outcome_pricing_routes.check_permission",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "app.services.outcome_pricing_service.OutcomePricingService.update_workspace_plan",
            new=AsyncMock(return_value=mock_plan),
        ),
    ):
        client = TestClient(test_app)
        response = client.put(
            "/api/v1/workspaces/1/pricing-plan",
            json={"outcome_rates_json": {"meeting_booked": 3_000_000}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["outcome_rates_json"]["meeting_booked"] == 3_000_000
