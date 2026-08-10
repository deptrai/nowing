import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import VerticalClient

pytestmark = pytest.mark.integration


def _payload(**overrides):
    defaults = {
        "client_id": "bdsai.vn",
        "name": "bdsai-listing-assistant",
        "display_name": "BDS AI Listing Assistant",
        "slug": "bdsai-listing-assistant",
        "system_instructions": "You are helpful.",
        "enabled_tools": ["update_memory", "create_automation"],
        "disabled_tools": [],
        "citations_enabled": True,
        "is_active": True,
    }
    defaults.update(overrides)
    return defaults


async def _ensure_vertical_client(db_session: AsyncSession) -> None:
    db_session.add(
        VerticalClient(
            client_id="bdsai.vn",
            display_name="BDS AI",
            is_active=True,
        )
    )
    await db_session.flush()


class TestAdminAgentRegistry:
    async def test_superuser_can_create_and_list_agent_config(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        await _ensure_vertical_client(db_session)

        resp = await admin_client.post("/api/v1/admin/agent-registry", json=_payload())
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["client_id"] == "bdsai.vn"
        assert data["slug"] == "bdsai-listing-assistant"
        assert data["display_name"] == "BDS AI Listing Assistant"
        assert data["citations_enabled"] is True

        resp = await admin_client.get("/api/v1/admin/agent-registry")
        assert resp.status_code == 200, resp.text
        assert any(a["slug"] == "bdsai-listing-assistant" for a in resp.json())

    async def test_regular_user_cannot_create_agent_config(
        self,
        client_as_regular_user: AsyncClient,
    ):
        resp = await client_as_regular_user.post(
            "/api/v1/admin/agent-registry", json=_payload()
        )
        assert resp.status_code in (401, 403), resp.text

    async def test_create_rejects_unregistered_client_id(
        self,
        admin_client: AsyncClient,
    ):
        resp = await admin_client.post(
            "/api/v1/admin/agent-registry",
            json=_payload(client_id="doesnotexist.vn"),
        )
        assert resp.status_code == 400, resp.text

    async def test_create_rejects_duplicate_slug_or_name(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        await _ensure_vertical_client(db_session)
        first = await admin_client.post("/api/v1/admin/agent-registry", json=_payload())
        assert first.status_code == 201, first.text

        # Same slug → 409
        duplicate_slug = _payload(
            name="other-name",
            display_name="Other",
        )
        resp = await admin_client.post(
            "/api/v1/admin/agent-registry", json=duplicate_slug
        )
        assert resp.status_code == 409, resp.text

        # Same name → 409
        duplicate_name = _payload(
            slug="other-slug",
        )
        resp = await admin_client.post(
            "/api/v1/admin/agent-registry", json=duplicate_name
        )
        assert resp.status_code == 409, resp.text

    async def test_create_rejects_unknown_tool_name(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        await _ensure_vertical_client(db_session)
        resp = await admin_client.post(
            "/api/v1/admin/agent-registry",
            json=_payload(enabled_tools=["not_a_real_tool"]),
        )
        assert resp.status_code in (400, 422), resp.text

    async def test_patch_agent_config(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        await _ensure_vertical_client(db_session)
        created = await admin_client.post(
            "/api/v1/admin/agent-registry", json=_payload()
        )
        assert created.status_code == 201, created.text
        config_id = created.json()["id"]

        patch = {
            "display_name": "Updated Display Name",
            "model_name": "gpt-4o-mini",
            "citations_enabled": False,
        }
        resp = await admin_client.patch(
            f"/api/v1/admin/agent-registry/{config_id}", json=patch
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["display_name"] == "Updated Display Name"
        assert data["model_name"] == "gpt-4o-mini"
        assert data["citations_enabled"] is False

    async def test_patch_rejects_duplicate_name(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        await _ensure_vertical_client(db_session)
        first = await admin_client.post(
            "/api/v1/admin/agent-registry",
            json=_payload(),
        )
        assert first.status_code == 201, first.text

        second = await admin_client.post(
            "/api/v1/admin/agent-registry",
            json=_payload(
                name="second-agent",
                display_name="Second",
                slug="second-agent",
            ),
        )
        assert second.status_code == 201, second.text
        second_id = second.json()["id"]

        resp = await admin_client.patch(
            f"/api/v1/admin/agent-registry/{second_id}",
            json={"name": "bdsai-listing-assistant"},
        )
        assert resp.status_code == 409, resp.text

    async def test_delete_soft_deactivates(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        await _ensure_vertical_client(db_session)
        created = await admin_client.post(
            "/api/v1/admin/agent-registry", json=_payload()
        )
        assert created.status_code == 201, created.text
        config_id = created.json()["id"]

        resp = await admin_client.delete(f"/api/v1/admin/agent-registry/{config_id}")
        assert resp.status_code == 204, resp.text

        # Soft-deleted rows remain visible to platform admins but not usable by chat.
        resp = await admin_client.get(f"/api/v1/admin/agent-registry/{config_id}")
        assert resp.status_code == 200, resp.text
        assert resp.json()["is_active"] is False

    async def test_list_filters_by_client_id(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        await _ensure_vertical_client(db_session)
        other = VerticalClient(
            client_id="other.vn",
            display_name="Other",
            is_active=True,
        )
        db_session.add(other)
        await db_session.flush()

        assert (
            await admin_client.post("/api/v1/admin/agent-registry", json=_payload())
        ).status_code == 201
        assert (
            await admin_client.post(
                "/api/v1/admin/agent-registry",
                json=_payload(
                    client_id="other.vn",
                    name="other-agent",
                    display_name="Other Agent",
                    slug="other-agent",
                ),
            )
        ).status_code == 201

        resp = await admin_client.get("/api/v1/admin/agent-registry?client_id=bdsai.vn")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) == 1
        assert data[0]["client_id"] == "bdsai.vn"

    async def test_fail_closed_for_invalid_agent_id(
        self,
        admin_client: AsyncClient,
    ):
        resp = await admin_client.get(
            "/api/v1/admin/agent-registry/550e8400-e29b-41d4-a716-446655440000"
        )
        assert resp.status_code == 404, resp.text
