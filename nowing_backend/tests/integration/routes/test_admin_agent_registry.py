"""Integration tests for the admin agent registry (Story 18.3).

These tests exercise ``/api/v1/admin/agent-registry`` CRUD, authz, and
validation against a real Postgres database.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import VerticalClient

pytestmark = pytest.mark.integration

_TEST_CLIENT_ID = "bdsai.vn"
_TEST_AGENT_NAME = "bdsai-listing-assistant"
_TEST_DISPLAY_NAME = "BDS AI Listing Assistant"
_TEST_SLUG = "bdsai-listing-assistant"
_TEST_INVALID_AGENT_UUID = "550e8400-e29b-41d4-a716-446655440000"


def _payload(**overrides: Any) -> dict[str, Any]:
    """Return a default AgentConfig payload with optional overrides."""
    defaults = {
        "client_id": _TEST_CLIENT_ID,
        "name": _TEST_AGENT_NAME,
        "display_name": _TEST_DISPLAY_NAME,
        "slug": _TEST_SLUG,
        "system_instructions": "You are helpful.",
        "enabled_tools": ["update_memory", "create_automation"],
        "disabled_tools": [],
        "citations_enabled": True,
        "is_active": True,
    }
    defaults.update(overrides)
    return defaults


async def _ensure_vertical_client(db_session: AsyncSession) -> None:
    """Ensure the test vertical client exists; idempotent across tests."""
    result = await db_session.execute(
        select(VerticalClient).where(VerticalClient.client_id == _TEST_CLIENT_ID)
    )
    if result.scalar_one_or_none() is None:
        db_session.add(
            VerticalClient(
                client_id=_TEST_CLIENT_ID,
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
    ) -> None:
        """AC-1/AC-2: superuser can create and list agent configs."""
        await _ensure_vertical_client(db_session)

        resp = await admin_client.post("/api/v1/admin/agent-registry", json=_payload())
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["client_id"] == _TEST_CLIENT_ID
        assert data["slug"] == _TEST_SLUG
        assert data["display_name"] == _TEST_DISPLAY_NAME
        assert data["citations_enabled"] is True

        resp = await admin_client.get("/api/v1/admin/agent-registry")
        assert resp.status_code == 200, resp.text
        assert any(a["slug"] == _TEST_SLUG for a in resp.json())

    async def test_regular_user_cannot_create_agent_config(
        self,
        client_as_regular_user: AsyncClient,
    ) -> None:
        """AC-3: regular workspace users are forbidden from the admin registry."""
        resp = await client_as_regular_user.post(
            "/api/v1/admin/agent-registry", json=_payload()
        )
        assert resp.status_code == 403, resp.text

    async def test_create_rejects_unregistered_client_id(
        self,
        admin_client: AsyncClient,
    ) -> None:
        """AC-1: creating an agent for an unknown client fails 400."""
        resp = await admin_client.post(
            "/api/v1/admin/agent-registry",
            json=_payload(client_id="doesnotexist.vn"),
        )
        assert resp.status_code == 400, resp.text

    async def test_create_rejects_duplicate_slug_or_name(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """AC-1: duplicate slug or name within a client returns 409."""
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
    ) -> None:
        """AC-2: unknown tool names in enabled_tools fail schema validation (422)."""
        await _ensure_vertical_client(db_session)
        resp = await admin_client.post(
            "/api/v1/admin/agent-registry",
            json=_payload(enabled_tools=["not_a_real_tool"]),
        )
        assert resp.status_code == 422, resp.text

    async def test_patch_agent_config(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """AC-2: superuser can patch an existing agent config."""
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
    ) -> None:
        """AC-2: patching to a duplicate name returns 409."""
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
            json={"name": _TEST_AGENT_NAME},
        )
        assert resp.status_code == 409, resp.text

    async def test_delete_soft_deactivates(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """AC-2: deleting an agent config soft-deactivates it."""
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
    ) -> None:
        """AC-2: listing can filter by client_id."""
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

        resp = await admin_client.get(
            f"/api/v1/admin/agent-registry?client_id={_TEST_CLIENT_ID}"
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) == 1
        assert data[0]["client_id"] == _TEST_CLIENT_ID

    async def test_fail_closed_for_invalid_agent_id(
        self,
        admin_client: AsyncClient,
    ) -> None:
        """AC-2: GET for a non-existent agent UUID returns 404."""
        resp = await admin_client.get(
            f"/api/v1/admin/agent-registry/{_TEST_INVALID_AGENT_UUID}"
        )
        assert resp.status_code == 404, resp.text
