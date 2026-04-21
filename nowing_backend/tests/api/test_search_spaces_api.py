"""
API-layer tests for SearchSpace endpoints.

Tests use httpx.AsyncClient + ASGITransport.
Covers P0: CRUD operations.
Covers P1: RBAC enforcement (non-member access).

Markers: @pytest.mark.api
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.api


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_space(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    name: str = "Test Space API",
    description: str = "Created by API test",
) -> dict:
    response = await api_client.post(
        "/api/searchspaces",
        json={"name": name, "description": description},
        headers=auth_headers,
    )
    assert response.status_code == 200, f"create failed: {response.text}"
    return response.json()


# ---------------------------------------------------------------------------
# P0 — Unauthenticated guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_search_space_unauthenticated_returns_401(
    api_client: AsyncClient,
) -> None:
    """POST /api/searchspaces — no auth → 401."""
    response = await api_client.post(
        "/api/searchspaces",
        json={"name": "Should Fail"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_search_spaces_unauthenticated_returns_401(
    api_client: AsyncClient,
) -> None:
    """GET /api/searchspaces — no auth → 401."""
    response = await api_client.get("/api/searchspaces")

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# P0 — CRUD happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_search_space_returns_200(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """POST /api/searchspaces — valid body → 200 + {id, name}."""
    response = await api_client.post(
        "/api/searchspaces",
        json={"name": "API Test Space", "description": "Test"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert "id" in body
    assert body["name"] == "API Test Space"


@pytest.mark.asyncio
async def test_list_search_spaces_returns_list(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """GET /api/searchspaces — authenticated → 200 + list."""
    # Ensure at least one space exists
    await _create_space(api_client, auth_headers, name="List Test Space")

    response = await api_client.get("/api/searchspaces", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1


@pytest.mark.asyncio
async def test_get_search_space_by_id_returns_200(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """GET /api/searchspaces/{id} — member → 200 + space data."""
    space = await _create_space(api_client, auth_headers, name="Get By ID Space")
    space_id = space["id"]

    response = await api_client.get(f"/api/searchspaces/{space_id}", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == space_id


@pytest.mark.asyncio
async def test_update_search_space_returns_200(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """PUT /api/searchspaces/{id} — owner → 200 + updated name."""
    space = await _create_space(api_client, auth_headers, name="Update Test Space")
    space_id = space["id"]

    response = await api_client.put(
        f"/api/searchspaces/{space_id}",
        json={"name": "Updated Name"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_delete_search_space_returns_200(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """DELETE /api/searchspaces/{id} — owner → 200."""
    space = await _create_space(api_client, auth_headers, name="Delete Test Space")
    space_id = space["id"]

    response = await api_client.delete(
        f"/api/searchspaces/{space_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# P0 — 404 for non-existent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_nonexistent_search_space_returns_404(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """GET /api/searchspaces/999999 — unknown ID → 404."""
    response = await api_client.get("/api/searchspaces/999999", headers=auth_headers)

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# P1 — RBAC: non-member cannot access
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_search_space_non_member_returns_403(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """
    GET /api/searchspaces/{id} — non-member should get 403 or 404.
    We create a space and then try to access a different space_id
    that another user created (simulate by using an ID offset).

    NOTE: This is a best-effort RBAC test using a synthetic ID.
    For a proper RBAC test, two user fixtures are needed.
    """
    # Use a known high ID that the test user is unlikely to be a member of
    # Real RBAC verification requires two-user fixture (marked as integration)
    response = await api_client.get("/api/searchspaces/1000000", headers=auth_headers)

    # Should be 403 (RBAC) or 404 (not found) — never 200
    assert response.status_code in (403, 404)


@pytest.mark.asyncio
async def test_delete_search_space_unauthenticated_returns_401(
    api_client: AsyncClient,
) -> None:
    """DELETE /api/searchspaces/{id} — no auth → 401."""
    response = await api_client.delete("/api/searchspaces/1")

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# P1 — owned_only filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_search_spaces_owned_only_filter(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """GET /api/searchspaces?owned_only=true — only owned spaces returned."""
    await _create_space(api_client, auth_headers, name="Owned Only Test")

    response = await api_client.get(
        "/api/searchspaces?owned_only=true",
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    # All returned spaces should have is_owner=True
    for space in body:
        assert space.get("is_owner", True) is True
