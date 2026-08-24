"""Integration tests for Web Builder Build & Preview Routes (Story 27.1b).

Acceptance Criteria:
- AC-2: GET /apps/{app_id}/preview (status transitions: generated -> 202 building, preview_ready -> 200, build_failed -> 422).
- AC-4: Workspace Feature Gating (403 Forbidden when disabled).
- AC-5: GET /apps/{app_id}/build-logs (tail build output).
- Trigger: POST /apps/{app_id}/build.

TDD Phase: RED (Scaffolds for 27.1b endpoints).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.db import WorkspaceApp, get_async_session
from app.routes.web_builder_routes import router as web_builder_router
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
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = MagicMock()
    session.execute.return_value = mock_result
    return session


@pytest.fixture
def client(mock_auth: AuthContext, mock_db_session: AsyncMock) -> TestClient:
    """Fixture creating test FastAPI app with Web Builder routes mounted and auth overridden."""
    import app.routes.web_builder_routes as routes

    app = FastAPI()
    app.include_router(web_builder_router)
    app.dependency_overrides[get_auth_context] = lambda: mock_auth
    app.dependency_overrides[get_async_session] = lambda: mock_db_session
    routes.require_workspace_member = AsyncMock(return_value=None)
    return TestClient(app)


class TestWebBuilderBuildAndPreviewRoutes:
    """Integration route tests for 27.1b build runner & preview lifecycle."""

    def test_preview_endpoint_initiates_build_when_status_is_generated(
        self, client: TestClient, mock_db_session: AsyncMock, tmp_path: Path
    ):
        """AC-2 (Option A): GET /apps/{app_id}/preview when status='generated' returns 202 Accepted and triggers async build."""
        app_id = "test-gen-app"
        app_dir = tmp_path / "web-app" / "1" / app_id
        app_dir.mkdir(parents=True, exist_ok=True)

        mock_app = WorkspaceApp(
            id=app_id,
            workspace_id=1,
            name="Gen App",
            slug="gen-app",
            status="generated",
            storage_path=str(app_dir),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_app
        mock_db_session.execute.return_value = mock_result

        with patch(
            "app.routes.web_builder_routes.BuilderService.trigger_async_build",
            new_callable=AsyncMock,
        ):
            response = client.get(
                f"/api/v1/web-builder/apps/{app_id}/preview?workspace_id=1"
            )

        assert response.status_code == 202
        assert "text/html" in response.headers["content-type"]
        assert "Build initiated" in response.text

    def test_preview_endpoint_serves_built_app_when_preview_ready(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """AC-2: GET /apps/{app_id}/preview when status='preview_ready' serves the built app."""
        from app.config import config

        monkeypatch.setattr(config, "FILE_STORAGE_LOCAL_PATH", str(tmp_path))

        app_id = "test-ready-app"
        app_dir = tmp_path / "web-app" / "1" / app_id
        standalone_dir = app_dir / ".next" / "standalone"
        standalone_dir.mkdir(parents=True, exist_ok=True)
        (standalone_dir / "index.html").write_text(
            "<!DOCTYPE html><html><body>Built App Ready</body></html>", encoding="utf-8"
        )

        mock_app = WorkspaceApp(
            id=app_id,
            workspace_id=1,
            name="Ready App",
            slug="ready-app",
            status="preview_ready",
            storage_path=str(app_dir),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_app
        mock_db_session.execute.return_value = mock_result

        response = client.get(
            f"/api/v1/web-builder/apps/{app_id}/preview?workspace_id=1"
        )

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Built App Ready" in response.text

    def test_preview_endpoint_returns_422_when_build_failed(
        self, client: TestClient, mock_db_session: AsyncMock, tmp_path: Path
    ):
        """AC-2: GET /apps/{app_id}/preview when status='build_failed' returns 422 with error message and build log link."""
        app_id = "test-failed-app"
        app_dir = tmp_path / "web-app" / "1" / app_id
        app_dir.mkdir(parents=True, exist_ok=True)

        mock_app = WorkspaceApp(
            id=app_id,
            workspace_id=1,
            name="Failed App",
            slug="failed-app",
            status="build_failed",
            error_message="Module not found: Can't resolve '@/components/missing'",
            storage_path=str(app_dir),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_app
        mock_db_session.execute.return_value = mock_result

        response = client.get(
            f"/api/v1/web-builder/apps/{app_id}/preview?workspace_id=1"
        )

        assert response.status_code == 422
        assert "text/html" in response.headers["content-type"]
        assert "Module not found" in response.text

    def test_get_build_logs_endpoint(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """AC-5: GET /apps/{app_id}/build-logs returns build stdout/stderr log content."""
        from app.config import config

        monkeypatch.setattr(config, "FILE_STORAGE_LOCAL_PATH", str(tmp_path))

        app_id = "test-log-app"
        app_dir = tmp_path / "web-app" / "1" / app_id
        log_dir = app_dir / ".next"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "build.log").write_text(
            "Line 1: Compiling\nLine 2: Ready on port 3000\n", encoding="utf-8"
        )

        mock_app = WorkspaceApp(
            id=app_id,
            workspace_id=1,
            name="Log App",
            slug="log-app",
            status="preview_ready",
            storage_path=str(app_dir),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_app
        mock_db_session.execute.return_value = mock_result

        response = client.get(
            f"/api/v1/web-builder/apps/{app_id}/build-logs?workspace_id=1"
        )

        assert response.status_code == 200
        data = response.json()
        assert "Compiling" in data["logs"]
        assert data["lines"] >= 2

    def test_trigger_manual_build_endpoint(
        self, client: TestClient, mock_db_session: AsyncMock, tmp_path: Path
    ):
        """Trigger: POST /apps/{app_id}/build triggers asynchronous build execution."""
        app_id = "test-rebuild-app"
        app_dir = tmp_path / "web-app" / "1" / app_id
        app_dir.mkdir(parents=True, exist_ok=True)

        mock_app = WorkspaceApp(
            id=app_id,
            workspace_id=1,
            name="Rebuild App",
            slug="rebuild-app",
            status="generated",
            storage_path=str(app_dir),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_app
        mock_db_session.execute.return_value = mock_result

        with patch(
            "app.routes.web_builder_routes.BuilderService.trigger_async_build",
            new_callable=AsyncMock,
        ):
            response = client.post(
                f"/api/v1/web-builder/apps/{app_id}/build", json={"workspace_id": 1}
            )

        assert response.status_code in [200, 202]
        data = response.json()
        assert data["status"] == "building"

    def test_feature_gate_403_when_web_builder_disabled(self, client: TestClient):
        """AC-4: Endpoints return 403 Forbidden with upgrade message when feature is disabled."""
        with patch("app.config.config.WEB_BUILDER_ENABLED", False):
            response = client.post(
                "/api/v1/web-builder/generate",
                json={"workspace_id": 1, "prompt": "Create test app", "language": "en"},
            )

        assert response.status_code == 403
        assert "not enabled" in response.json().get("detail", "").lower()
