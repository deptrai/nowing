import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


class TestAdminAgentRegistry:
    async def test_superuser_can_create_and_list_agent_config(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        payload = {
            "client_id": "bdsai.vn",
            "name": "BDS AI Listing Assistant",
            "slug": "bdsai-listing-assistant",
            "system_instructions": "You are helpful.",
            "enabled_tools": ["web_search"],
            "disabled_tools": [],
            "citations_enabled": True,
            "is_active": True,
        }
        resp = await admin_client.post("/api/v1/admin/agent-registry", json=payload)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["client_id"] == "bdsai.vn"
        assert data["slug"] == "bdsai-listing-assistant"

        resp = await admin_client.get("/api/v1/admin/agent-registry")
        assert resp.status_code == 200, resp.text
        assert any(a["slug"] == "bdsai-listing-assistant" for a in resp.json())

    async def test_regular_user_cannot_create_agent_config(
        self,
        client_as_regular_user: AsyncClient,
    ):
        payload = {
            "client_id": "bdsai.vn",
            "name": "BDS AI Listing Assistant",
            "slug": "bdsai-listing-assistant",
        }
        resp = await client_as_regular_user.post(
            "/api/v1/admin/agent-registry", json=payload
        )
        assert resp.status_code in (401, 403), resp.text

    async def test_fail_closed_for_invalid_agent_id(
        self,
        admin_client: AsyncClient,
    ):
        resp = await admin_client.get(
            "/api/v1/admin/agent-registry/550e8400-e29b-41d4-a716-446655440000"
        )
        assert resp.status_code == 404, resp.text
