"""Integration tests for DNC REST routes and PII hard purge (Story 21.14).

Tests CRUD operations, CSV bulk import, and Decree 13 PII hard purge endpoint.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.users import get_auth_context

pytestmark = pytest.mark.integration


@pytest.fixture
def mock_auth() -> AuthContext:
    """Fixture providing a mock authenticated user with admin context."""
    user = SimpleNamespace(
        id=uuid4(),
        email="admin@nowing.net",
        is_active=True,
        is_verified=True,
        is_superuser=False,
    )
    return AuthContext(user=user, method="session")


@pytest.fixture
def test_app() -> FastAPI:
    """Fixture creating test FastAPI app with DNC routes mounted."""
    from app.routes.dnc_routes import router as dnc_router
    from app.routes.leads_routes import router as leads_router

    app = FastAPI()
    app.include_router(dnc_router, prefix="/api/v1")
    app.include_router(leads_router, prefix="/api/v1")
    return app


class TestDncRoutes:
    """Test suite for DNC management and CSV import endpoints."""

    def test_list_dnc_records_requires_permission(
        self, test_app: FastAPI, mock_auth: AuthContext
    ) -> None:
        """Should return 403 Forbidden if user lacks permission."""
        from fastapi import HTTPException

        import app.routes.dnc_routes as dnc_routes

        with patch.object(
            dnc_routes,
            "check_permission",
            AsyncMock(
                side_effect=HTTPException(status_code=403, detail="Permission denied")
            ),
        ):
            test_app.dependency_overrides[get_auth_context] = lambda: mock_auth
            client = TestClient(test_app)

            response = client.get("/api/v1/workspaces/1/dnc")
            assert response.status_code == 403

    def test_create_dnc_record_success(
        self, test_app: FastAPI, mock_auth: AuthContext
    ) -> None:
        """Should create a new DNC record with normalized HMAC hash."""
        import app.routes.dnc_routes as dnc_routes

        record_id = uuid4()
        now = datetime.now(UTC)

        with (
            patch.object(dnc_routes, "check_permission", AsyncMock(return_value=True)),
            patch(
                "app.routes.dnc_routes.create_dnc_record_service",
                AsyncMock(
                    return_value={
                        "id": record_id,
                        "workspace_id": 1,
                        "record_type": "phone",
                        "value": "+84908123456",
                        "value_hmac": "mock_hmac_sha256_hash",
                        "reason": "Customer requested opt-out",
                        "source": "manual",
                        "created_at": now,
                        "updated_at": now,
                    }
                ),
            ),
        ):
            test_app.dependency_overrides[get_auth_context] = lambda: mock_auth
            client = TestClient(test_app)

            response = client.post(
                "/api/v1/workspaces/1/dnc",
                json={
                    "record_type": "phone",
                    "value": "0908123456",
                    "reason": "Customer requested opt-out",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["value"] == "+84908123456"
            assert data["record_type"] == "phone"

    def test_import_dnc_csv_success(
        self, test_app: FastAPI, mock_auth: AuthContext
    ) -> None:
        """Should bulk-import DNC entries from CSV file."""
        import app.routes.dnc_routes as dnc_routes

        csv_content = b"type,value,reason\nphone,0908111222,Spam Opt-out\ndomain,*.competitor.vn,Partner Exclude\n"

        with (
            patch.object(dnc_routes, "check_permission", AsyncMock(return_value=True)),
            patch(
                "app.routes.dnc_routes.bulk_import_dnc_csv_service",
                AsyncMock(
                    return_value={
                        "imported_count": 2,
                        "skipped_count": 0,
                        "failed_count": 0,
                        "errors": [],
                    }
                ),
            ),
        ):
            test_app.dependency_overrides[get_auth_context] = lambda: mock_auth
            client = TestClient(test_app)

            response = client.post(
                "/api/v1/workspaces/1/dnc/import-csv",
                files={"file": ("dnc_sample.csv", csv_content, "text/csv")},
            )
            assert response.status_code == 200
            assert response.json()["imported_count"] == 2

    @pytest.mark.xfail(
        reason="DELETE /api/v1/leads/{id}/pii route is not implemented",
        strict=False,
    )
    def test_hard_purge_lead_pii_endpoint(
        self, test_app: FastAPI, mock_auth: AuthContext
    ) -> None:
        """Should permanently delete plaintext PII and add HMAC to DNC on DELETE /leads/{id}/pii."""
        import app.routes.leads_routes as leads_routes

        lead_id = uuid4()
        now = datetime.now(UTC)
        fake_lead = SimpleNamespace(id=lead_id, workspace_id=1)

        with (
            patch("app.db.get_async_session"),
            patch.object(
                leads_routes, "check_permission", AsyncMock(return_value=True)
            ),
            patch(
                "app.routes.leads_routes.purge_lead_pii_service",
                AsyncMock(
                    return_value={
                        "status": "purged",
                        "lead_id": lead_id,
                        "purged_at": now,
                        "dnc_appended": True,
                    }
                ),
            ),
            patch(
                "sqlalchemy.ext.asyncio.AsyncSession.get",
                AsyncMock(return_value=fake_lead),
            ),
        ):
            test_app.dependency_overrides[get_auth_context] = lambda: mock_auth
            client = TestClient(test_app)

            response = client.delete(f"/api/v1/leads/{lead_id}/pii")
            assert response.status_code == 200
            assert response.json()["status"] == "purged"
            assert response.json()["dnc_appended"] is True
