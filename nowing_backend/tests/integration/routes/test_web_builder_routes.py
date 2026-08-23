"""Integration tests for Web Builder API Routes (Story 27.1).

Acceptance Criteria:
- AC-1: POST /api/v1/web-builder/generate
- AC-2: POST /api/v1/web-builder/apps/{app_id}/publish
- AC-3: POST /api/v1/web-builder/apps/{app_id}/custom-domain
- AC-4: POST /api/v1/web-builder/apps/{app_id}/mark
- AC-5: GET /api/v1/web-builder/apps
"""

from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration]


class TestWebBuilderRoutes:
    """REST API route integration tests for Web Builder."""

    @pytest.mark.skip(reason="RED-PHASE: web_builder_routes not yet registered")
    @pytest.mark.asyncio
    async def test_generate_web_app_endpoint(self, async_client: AsyncClient, auth_headers: dict):
        """AC-1: POST /api/v1/web-builder/generate returns app_id, preview_url, and generated status."""
        payload = {
            "workspace_id": 1,
            "prompt": "Create a real-time cryptocurrency portfolio tracker with Next.js and Tailwind.",
            "language": "en",
        }

        response = await async_client.post(
            "/api/v1/web-builder/generate",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "app_id" in data
        assert data["status"] == "generated"
        assert "preview_url" in data

    @pytest.mark.skip(reason="RED-PHASE: web_builder_routes not yet registered")
    @pytest.mark.asyncio
    async def test_publish_web_app_endpoint(self, async_client: AsyncClient, auth_headers: dict):
        """AC-2: POST /api/v1/web-builder/apps/{app_id}/publish returns public_url at *.apps.nowing.net."""
        app_id = "test-app-001"
        payload = {
            "workspace_id": 1,
            "slug": "crypto-tracker",
        }

        with patch("app.services.web_builder.deploy_service.WebAppDeployService.deploy_app", new_callable=AsyncMock) as mock_deploy:
            mock_deploy.return_value = {
                "status": "published",
                "public_url": "https://crypto-tracker.apps.nowing.net",
                "slug": "crypto-tracker",
            }

            response = await async_client.post(
                f"/api/v1/web-builder/apps/{app_id}/publish",
                json=payload,
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "published"
        assert data["public_url"] == "https://crypto-tracker.apps.nowing.net"

    @pytest.mark.skip(reason="RED-PHASE: web_builder_routes not yet registered")
    @pytest.mark.asyncio
    async def test_custom_domain_validation_and_assignment(self, async_client: AsyncClient, auth_headers: dict):
        """AC-3: POST /api/v1/web-builder/apps/{app_id}/custom-domain verifies CNAME and registers route."""
        app_id = "test-app-001"
        payload = {
            "workspace_id": 1,
            "custom_domain": "portfolio.mybrand.io",
        }

        with patch("app.services.web_builder.deploy_service.WebAppDeployService.verify_and_bind_custom_domain", new_callable=AsyncMock) as mock_cname:
            mock_cname.return_value = {
                "status": "active",
                "custom_domain": "portfolio.mybrand.io",
            }

            response = await async_client.post(
                f"/api/v1/web-builder/apps/{app_id}/custom-domain",
                json=payload,
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["custom_domain"] == "portfolio.mybrand.io"

    @pytest.mark.skip(reason="RED-PHASE: web_builder_routes not yet registered")
    @pytest.mark.asyncio
    async def test_mark_tool_patch_endpoint(self, async_client: AsyncClient, auth_headers: dict):
        """AC-4: POST /api/v1/web-builder/apps/{app_id}/mark applies visual patch to component AST."""
        app_id = "test-app-001"
        payload = {
            "workspace_id": 1,
            "selector": "#main-header",
            "patch": {"type": "text", "value": "Welcome to CryptoTracker Pro"},
        }

        response = await async_client.post(
            f"/api/v1/web-builder/apps/{app_id}/mark",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["patched", "rebuilding"]
