"""Integration tests for Sequence REST API Routes (Story 24.1)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.auth.context import AuthContext
from app.db import SequenceEnrollment, SequenceEvent, get_async_session
from app.routes.sequence_routes import router as sequence_router
from app.schemas.sequence import SequenceAnalyticsResponse
from app.users import get_auth_context

pytestmark = pytest.mark.integration


@pytest.fixture
def test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(sequence_router, prefix="/api/v1")
    return app


@pytest.fixture
def mock_auth() -> AuthContext:
    user = MagicMock()
    user.id = uuid4()
    user.client_id = "default"
    user.email = "test_user@example.com"
    user.is_active = True
    return AuthContext.session(user=user)


@pytest.fixture
def mock_db_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_create_sequence_endpoint(
    test_app: FastAPI, mock_auth: AuthContext, mock_db_session: AsyncMock
) -> None:
    """AC-1/AC-2: POST /api/v1/workspaces/{workspace_id}/sequences creates sequence."""
    test_app.dependency_overrides[get_auth_context] = lambda: mock_auth
    test_app.dependency_overrides[get_async_session] = lambda: mock_db_session

    workspace_id = 1

    with (
        patch("app.routes.sequence_routes.check_workspace_access", AsyncMock()),
        patch("app.routes.sequence_routes.set_request_tenant_context", AsyncMock()),
        patch("app.routes.sequence_routes.SequencerService") as mock_seq_cls,
    ):
        mock_svc = mock_seq_cls.return_value
        mock_svc.validate_step_channel = AsyncMock(return_value=None)

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v1/workspaces/{workspace_id}/sequences",
                json={
                    "name": "Outreach VIP",
                    "description": "Drip sequence for VIP leads",
                    "status": "active",
                    "steps": [
                        {
                            "step_order": 1,
                            "step_type": "send_email",
                            "channel": "email",
                            "template": {"subject": "Hi {{name}}"},
                        }
                    ],
                },
            )

            assert resp.status_code == 201
            data = resp.json()
            assert data["name"] == "Outreach VIP"
            assert data["workspace_id"] == workspace_id
            assert len(data["steps"]) == 1


@pytest.mark.asyncio
async def test_enroll_leads_endpoint(
    test_app: FastAPI, mock_auth: AuthContext, mock_db_session: AsyncMock
) -> None:
    """AC-4: POST /api/v1/workspaces/{workspace_id}/sequences/{sequence_id}/enroll."""
    test_app.dependency_overrides[get_auth_context] = lambda: mock_auth
    test_app.dependency_overrides[get_async_session] = lambda: mock_db_session

    workspace_id = 1
    seq_id = str(uuid4())
    lead_id = str(uuid4())

    enr = SequenceEnrollment(
        id=uuid4(),
        workspace_id=workspace_id,
        sequence_id=UUID(seq_id),
        lead_id=UUID(lead_id),
        current_step=1,
        status="scheduled",
        version=0,
        scheduled_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )

    with (
        patch("app.routes.sequence_routes.check_workspace_access", AsyncMock()),
        patch("app.routes.sequence_routes.set_request_tenant_context", AsyncMock()),
        patch("app.routes.sequence_routes.SequencerService") as mock_seq_cls,
    ):
        mock_svc = mock_seq_cls.return_value
        mock_svc.enroll_leads = AsyncMock(return_value=[enr])

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v1/workspaces/{workspace_id}/sequences/{seq_id}/enroll",
                json={"lead_ids": [lead_id]},
            )

            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["status"] == "scheduled"


@pytest.mark.asyncio
async def test_get_sequence_analytics_endpoint(
    test_app: FastAPI, mock_auth: AuthContext, mock_db_session: AsyncMock
) -> None:
    """AC-8: GET /api/v1/workspaces/{workspace_id}/sequences/{sequence_id}/analytics."""
    test_app.dependency_overrides[get_auth_context] = lambda: mock_auth
    test_app.dependency_overrides[get_async_session] = lambda: mock_db_session

    workspace_id = 1
    seq_id = str(uuid4())

    analytics_data = SequenceAnalyticsResponse(
        sequence_id=UUID(seq_id),
        total_enrolled=15,
        active_scheduled=8,
        delivered_count=12,
        responded_count=4,
        unsubscribed_count=1,
        failed_count=0,
        total_cost_micros=60000,
    )

    with (
        patch("app.routes.sequence_routes.check_workspace_access", AsyncMock()),
        patch("app.routes.sequence_routes.set_request_tenant_context", AsyncMock()),
        patch("app.routes.sequence_routes.SequencerService") as mock_seq_cls,
    ):
        mock_svc = mock_seq_cls.return_value
        mock_svc.get_sequence_analytics = AsyncMock(return_value=analytics_data)

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/api/v1/workspaces/{workspace_id}/sequences/{seq_id}/analytics"
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["total_enrolled"] == 15
            assert data["responded_count"] == 4
            assert data["total_cost_micros"] == 60000


@pytest.mark.asyncio
async def test_list_sequence_events_endpoint(
    test_app: FastAPI, mock_auth: AuthContext, mock_db_session: AsyncMock
) -> None:
    """AC-8: GET /api/v1/workspaces/{workspace_id}/sequences/{sequence_id}/events."""
    test_app.dependency_overrides[get_auth_context] = lambda: mock_auth
    test_app.dependency_overrides[get_async_session] = lambda: mock_db_session

    workspace_id = 1
    seq_id = str(uuid4())

    ev = SequenceEvent(
        id=uuid4(),
        workspace_id=workspace_id,
        enrollment_id=uuid4(),
        sequence_id=UUID(seq_id),
        event_type="sent",
        channel="email",
        cost_micros=5000,
        event_metadata={},
        created_at=datetime.now(UTC),
    )

    mock_db_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[ev])))
    )

    with (
        patch("app.routes.sequence_routes.check_workspace_access", AsyncMock()),
        patch("app.routes.sequence_routes.set_request_tenant_context", AsyncMock()),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/api/v1/workspaces/{workspace_id}/sequences/{seq_id}/events"
            )

            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["event_type"] == "sent"
            assert data[0]["cost_micros"] == 5000
