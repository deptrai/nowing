"""Integration tests for Web Builder API Routes (Story 27.1).

Acceptance Criteria:
- AC-1: POST /api/v1/web-builder/generate
- AC-2: POST /api/v1/web-builder/apps/{app_id}/publish
- AC-3: POST /api/v1/web-builder/apps/{app_id}/custom-domain
- AC-4: POST /api/v1/web-builder/apps/{app_id}/mark
- AC-5: GET /api/v1/web-builder/apps
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.db import WorkspaceApp, get_async_session
from app.routes.web_builder_routes import router as web_builder_router
from app.services.web_builder.schemas import (
    CustomDomainOutput,
    WebAppBuildOutput,
    WebAppDeployOutput,
)
from app.users import get_auth_context

pytestmark = pytest.mark.integration


@pytest.fixture
def mock_auth() -> AuthContext:
    """Fixture providing a mock authenticated user context."""
    user = SimpleNamespace(
        id=uuid4(),
        email="test@nowing.net",
        is_active=True,
        is_verified=True,
        is_superuser=False,
    )
    return AuthContext(user=user, method="session")


@pytest.fixture
def mock_db_session():
    """Mock async DB session."""
    session = AsyncMock()
    return session


@pytest.fixture
def client(mock_auth: AuthContext, mock_db_session: AsyncMock) -> TestClient:
    """Fixture creating test FastAPI app with Web Builder routes mounted and auth overridden."""
    app = FastAPI()
    app.include_router(web_builder_router)
    app.dependency_overrides[get_auth_context] = lambda: mock_auth
    app.dependency_overrides[get_async_session] = lambda: mock_db_session
    return TestClient(app)


class TestWebBuilderRoutes:
    """REST API route integration tests for Web Builder."""

    def test_generate_web_app_endpoint(self, client: TestClient):
        """AC-1: POST /api/v1/web-builder/generate returns app_id, preview_url, and generated status."""
        payload = {
            "workspace_id": 1,
            "prompt": "Create a real-time cryptocurrency portfolio tracker with Next.js and Tailwind.",
            "language": "en",
        }

        mock_out = WebAppBuildOutput(
            app_id="test-app-123",
            workspace_id=1,
            name="Crypto Tracker",
            slug="crypto-tracker",
            status="generated",
            preview_url="http://localhost:8000/api/v1/web-builder/apps/test-app-123/preview",
            files=["package.json", "app/page.tsx"],
        )

        with patch(
            "app.routes.web_builder_routes.WebBuilderService.generate_project",
            new_callable=AsyncMock,
        ) as mock_gen:
            mock_gen.return_value = mock_out
            response = client.post(
                "/api/v1/web-builder/generate",
                json=payload,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["app_id"] == "test-app-123"
        assert data["status"] == "generated"
        assert "preview_url" in data

    def test_publish_web_app_endpoint(self, client: TestClient):
        """AC-2: POST /api/v1/web-builder/apps/{app_id}/publish returns public_url at *.apps.nowing.net."""
        app_id = "test-app-001"
        payload = {
            "workspace_id": 1,
            "slug": "crypto-tracker",
        }

        mock_out = WebAppDeployOutput(
            app_id=app_id,
            workspace_id=1,
            status="published",
            public_url="https://crypto-tracker.apps.nowing.net",
            slug="crypto-tracker",
        )

        with patch(
            "app.routes.web_builder_routes.WebAppDeployService.deploy_app",
            new_callable=AsyncMock,
        ) as mock_deploy:
            mock_deploy.return_value = mock_out

            response = client.post(
                f"/api/v1/web-builder/apps/{app_id}/publish",
                json=payload,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "published"
        assert data["public_url"] == "https://crypto-tracker.apps.nowing.net"

    def test_custom_domain_validation_and_assignment(self, client: TestClient):
        """AC-3: POST /api/v1/web-builder/apps/{app_id}/custom-domain verifies CNAME and registers route."""
        app_id = "test-app-001"
        payload = {
            "workspace_id": 1,
            "custom_domain": "portfolio.mybrand.io",
        }

        mock_out = CustomDomainOutput(
            app_id=app_id,
            workspace_id=1,
            custom_domain="portfolio.mybrand.io",
            status="active",
            cname_target="cname-ingress.apps.nowing.net",
        )

        with patch(
            "app.routes.web_builder_routes.WebAppDeployService.verify_and_bind_custom_domain",
            new_callable=AsyncMock,
        ) as mock_cname:
            mock_cname.return_value = mock_out

            response = client.post(
                f"/api/v1/web-builder/apps/{app_id}/custom-domain",
                json=payload,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["custom_domain"] == "portfolio.mybrand.io"
        assert data["status"] == "active"

    def test_mark_tool_patch_endpoint(
        self, client: TestClient, mock_db_session: AsyncMock, tmp_path
    ):
        """AC-4: POST /api/v1/web-builder/apps/{app_id}/mark applies visual patch to component AST."""
        app_id = "test-app-001"
        test_dir = tmp_path / "web-app" / "1" / app_id
        test_dir.mkdir(parents=True, exist_ok=True)
        app_page = test_dir / "app" / "page.tsx"
        app_page.parent.mkdir(parents=True, exist_ok=True)
        app_page.write_text(
            'export default function Page() { return <h1 id="main-header">Old Title</h1>; }',
            encoding="utf-8",
        )

        mock_app_entity = WorkspaceApp(
            id=app_id,
            workspace_id=1,
            name="Test App",
            slug="test-app",
            storage_path=str(test_dir),
        )

        payload = {
            "workspace_id": 1,
            "selector": "#main-header",
            "patch": {"type": "text", "value": "Welcome to CryptoTracker Pro"},
            "file_path": "app/page.tsx",
        }

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_app_entity
        mock_db_session.execute.return_value = mock_result

        response = client.post(
            f"/api/v1/web-builder/apps/{app_id}/mark",
            json=payload,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "patched"
        assert "Welcome to CryptoTracker Pro" in app_page.read_text(encoding="utf-8")

    def test_generate_stream_endpoint(self, client: TestClient):
        """POST /api/v1/web-builder/generate/stream returns text/event-stream chunks."""
        payload = {
            "workspace_id": 1,
            "prompt": "Create a modern portfolio tracker",
            "language": "en",
        }

        async def fake_stream(*args, **kwargs):
            yield 'data: {"type": "phase", "phase": "planning", "message": "Planning..."}\n\n'
            yield 'data: {"type": "complete", "app": {"id": "app-stream-1", "name": "Portfolio Tracker"}}\n\n'

        with patch(
            "app.routes.web_builder_routes.WebBuilderService.generate_project_stream",
            side_effect=fake_stream,
        ):
            response = client.post("/api/v1/web-builder/generate/stream", json=payload)

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        assert "planning" in response.text
        assert "app-stream-1" in response.text

    def test_preview_html_endpoint(
        self, client: TestClient, mock_db_session: AsyncMock, tmp_path
    ):
        """GET /api/v1/web-builder/apps/{app_id}/preview returns rich HTML document."""
        app_id = "test-preview-app"
        test_dir = tmp_path / "web-app" / "1" / app_id
        test_dir.mkdir(parents=True, exist_ok=True)
        app_page = test_dir / "app" / "page.tsx"
        app_page.parent.mkdir(parents=True, exist_ok=True)
        app_page.write_text(
            'export default function Page() { return <h1 id="hero-title">Crypto Tracker Live</h1>; }',
            encoding="utf-8",
        )

        mock_app_entity = WorkspaceApp(
            id=app_id,
            workspace_id=1,
            name="Crypto Tracker Live",
            slug="crypto-tracker-live",
            storage_path=str(test_dir),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_app_entity
        mock_db_session.execute.return_value = mock_result

        response = client.get(f"/api/v1/web-builder/apps/{app_id}/preview")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "<!DOCTYPE html>" in response.text
        assert "tailwind" in response.text
        assert "Crypto Tracker Live" in response.text

    def test_files_endpoint(
        self, client: TestClient, mock_db_session: AsyncMock, tmp_path
    ):
        """GET /api/v1/web-builder/apps/{app_id}/files returns dict of source code files."""
        app_id = "test-files-app"
        test_dir = tmp_path / "web-app" / "1" / app_id
        test_dir.mkdir(parents=True, exist_ok=True)
        app_page = test_dir / "app" / "page.tsx"
        app_page.parent.mkdir(parents=True, exist_ok=True)
        app_page.write_text(
            'export default function Page() { return <div>Files Test</div>; }',
            encoding="utf-8",
        )

        mock_app_entity = WorkspaceApp(
            id=app_id,
            workspace_id=1,
            name="Files Test",
            slug="files-test",
            storage_path=str(test_dir),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_app_entity
        mock_db_session.execute.return_value = mock_result

        response = client.get(f"/api/v1/web-builder/apps/{app_id}/files?workspace_id=1")

        assert response.status_code == 200
        data = response.json()
        assert "app/page.tsx" in data
        assert "Files Test" in data["app/page.tsx"]

