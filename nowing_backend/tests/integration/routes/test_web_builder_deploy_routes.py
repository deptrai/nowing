"""Integration tests for Web Builder Deploy & Custom Domain Routes (Story 27.1c).

Acceptance Criteria:
- AC-1: POST /apps/{app_id}/publish (1-Click publish to https://{slug}.apps.nowing.net).
- AC-2: POST /apps/{app_id}/custom-domain (Custom CNAME & DNS proof-of-control).
- AC-3: Workspace-Scoped App Registry & Deploy Cost (TokenUsage recording).
- AC-4: Workspace Feature Gating (403 Forbidden when disabled).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.db import get_async_session
from app.routes.web_builder_routes import router as web_builder_router
from app.services.web_builder.schemas import CustomDomainOutput, WebAppDeployOutput
from app.users import get_auth_context

pytestmark = pytest.mark.integration


@pytest.fixture
def mock_auth() -> AuthContext:
    user = SimpleNamespace(
        id=uuid4(),
        email="developer@nowing.net",
        is_active=True,
        is_verified=True,
        is_superuser=False,
    )
    return AuthContext(user=user, method="session")


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = MagicMock()
    session.execute.return_value = mock_result
    return session


@pytest.fixture
def client(mock_auth: AuthContext, mock_db_session: AsyncMock) -> TestClient:
    import app.routes.web_builder_routes as routes

    app = FastAPI()
    app.include_router(web_builder_router)

    app.dependency_overrides[get_auth_context] = lambda: mock_auth
    app.dependency_overrides[get_async_session] = lambda: mock_db_session
    app.dependency_overrides[routes.get_async_session] = lambda: mock_db_session

    return TestClient(app)


class TestWebBuilderDeployRoutes:
    def test_publish_endpoint_success(self, client: TestClient):
        with patch(
            "app.services.web_builder.deploy_service.WebAppDeployService.deploy_app",
            new_callable=AsyncMock,
        ) as mock_deploy:
            mock_deploy.return_value = WebAppDeployOutput(
                app_id="app-123",
                workspace_id=1,
                status="published",
                public_url="https://pulse-ai-landing.apps.nowing.net",
                slug="pulse-ai-landing",
                message="Application deployed successfully",
            )

            res = client.post(
                "/api/v1/web-builder/apps/app-123/publish",
                params={"workspace_id": 1},
                json={"workspace_id": 1, "slug": "pulse-ai-landing"},
            )

            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "published"
            assert data["public_url"] == "https://pulse-ai-landing.apps.nowing.net"
            assert data["slug"] == "pulse-ai-landing"

    def test_custom_domain_endpoint_success(self, client: TestClient):
        with patch(
            "app.services.web_builder.deploy_service.WebAppDeployService.verify_and_bind_custom_domain",
            new_callable=AsyncMock,
        ) as mock_bind:
            mock_bind.return_value = CustomDomainOutput(
                app_id="app-123",
                workspace_id=1,
                custom_domain="landing.mycompany.com",
                status="active",
                cname_target="cname-ingress.apps.nowing.net",
                message="Custom domain verified",
            )

            res = client.post(
                "/api/v1/web-builder/apps/app-123/custom-domain",
                params={"workspace_id": 1},
                json={"workspace_id": 1, "custom_domain": "landing.mycompany.com"},
            )

            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "active"
            assert data["custom_domain"] == "landing.mycompany.com"
            assert data["cname_target"] == "cname-ingress.apps.nowing.net"

    def test_feature_gate_403_when_disabled(
        self, client: TestClient, mock_db_session: AsyncMock
    ):
        with patch(
            "app.services.web_builder.deploy_service.WebAppDeployService.deploy_app",
            new_callable=AsyncMock,
        ) as mock_deploy:
            mock_deploy.return_value = WebAppDeployOutput(
                app_id="app-123",
                workspace_id=1,
                status="deploy_failed",
                slug="",
                message="Web Builder is not enabled on this workspace plan",
            )

            with patch(
                "app.routes.web_builder_routes.check_web_builder_enabled",
                side_effect=lambda: None,
            ):
                res = client.post(
                    "/api/v1/web-builder/apps/app-123/publish",
                    params={"workspace_id": 1},
                    json={"workspace_id": 1},
                )

                assert res.status_code == 403
                data = res.json()
                assert "Web Builder is not enabled" in data["detail"]
