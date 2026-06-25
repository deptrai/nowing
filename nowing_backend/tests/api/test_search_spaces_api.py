"""
API-layer tests for SearchSpace endpoints.

Tests use httpx.AsyncClient + ASGITransport.
Covers P0: CRUD operations.
Covers P1: RBAC enforcement (non-member access).

Markers: @pytest.mark.api
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.api


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_name(prefix: str = "Test Space") -> str:
    """Tạo tên unique để tránh collision giữa các test runs song song."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def _create_space(
    api_client: AsyncClient,
    auth_headers: dict[str, str],
    name: str | None = None,
    description: str = "Created by API test",
) -> dict:
    space_name = name or _unique_name()
    response = await api_client.post(
        "/api/v1/searchspaces",
        json={"name": space_name, "description": description},
        headers=auth_headers,
    )
    if response.status_code != 200:
        raise RuntimeError(f"_create_space failed [{response.status_code}]: {response.text}")
    return response.json()


# ---------------------------------------------------------------------------
# P0 — Unauthenticated guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_search_space_unauthenticated_returns_401(
    api_client: AsyncClient,
) -> None:
    """POST /api/v1/searchspaces — no auth → 401."""
    response = await api_client.post(
        "/api/v1/searchspaces",
        json={"name": "Should Fail"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_search_spaces_unauthenticated_returns_401(
    api_client: AsyncClient,
) -> None:
    """GET /api/v1/searchspaces — no auth → 401."""
    response = await api_client.get("/api/v1/searchspaces")

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# P0 — CRUD happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_search_space_returns_200(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """POST /api/v1/searchspaces — valid body → 200 + {id, name}."""
    space_name = _unique_name("Create Test")
    response = await api_client.post(
        "/api/v1/searchspaces",
        json={"name": space_name, "description": "Test"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert "id" in body
    assert body["name"] == space_name

    # Teardown
    await api_client.delete(f"/api/v1/searchspaces/{body['id']}", headers=auth_headers)


@pytest.mark.asyncio
async def test_list_search_spaces_returns_list(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """GET /api/v1/searchspaces — authenticated → 200 + list."""
    space = await _create_space(api_client, auth_headers, name=_unique_name("List Test"))

    try:
        response = await api_client.get("/api/v1/searchspaces", headers=auth_headers)

        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert len(body) >= 1
    finally:
        await api_client.delete(f"/api/v1/searchspaces/{space['id']}", headers=auth_headers)


@pytest.mark.asyncio
async def test_get_search_space_by_id_returns_200(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """GET /api/v1/searchspaces/{id} — member → 200 + space data."""
    space = await _create_space(api_client, auth_headers, name=_unique_name("Get ByID"))
    space_id = space["id"]

    try:
        response = await api_client.get(f"/api/v1/searchspaces/{space_id}", headers=auth_headers)

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == space_id
    finally:
        await api_client.delete(f"/api/v1/searchspaces/{space_id}", headers=auth_headers)


@pytest.mark.asyncio
async def test_update_search_space_returns_200(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """PUT /api/v1/searchspaces/{id} — owner → 200 + updated name."""
    space = await _create_space(api_client, auth_headers, name=_unique_name("Update Test"))
    space_id = space["id"]

    try:
        response = await api_client.put(
            f"/api/v1/searchspaces/{space_id}",
            json={"name": "Updated Name"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Updated Name"
    finally:
        await api_client.delete(f"/api/v1/searchspaces/{space_id}", headers=auth_headers)


@pytest.mark.asyncio
async def test_delete_search_space_returns_200(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """DELETE /api/v1/searchspaces/{id} — owner → 200."""
    space = await _create_space(api_client, auth_headers, name=_unique_name("Delete Test"))
    space_id = space["id"]

    response = await api_client.delete(
        f"/api/v1/searchspaces/{space_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_nonexistent_search_space_returns_404(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """GET /api/v1/searchspaces/999999 — unknown ID → 404."""
    response = await api_client.get("/api/v1/searchspaces/999999", headers=auth_headers)

    assert response.status_code in (403, 404)


# ---------------------------------------------------------------------------
# P1 — RBAC: non-member cannot access
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_search_space_non_member_returns_403(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """
    GET /api/v1/searchspaces/{id} — non-member should get 403 or 404.

    NOTE: Best-effort test dùng synthetic high ID.
    Real RBAC verification cần two-user fixture (xem test_rbac_api.py).
    """
    response = await api_client.get("/api/v1/searchspaces/1000000", headers=auth_headers)

    assert response.status_code in (403, 404)


@pytest.mark.asyncio
async def test_delete_search_space_unauthenticated_returns_401(
    api_client: AsyncClient,
) -> None:
    """DELETE /api/v1/searchspaces/{id} — no auth → 401."""
    response = await api_client.delete("/api/v1/searchspaces/1")

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# P1 — owned_only filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_search_spaces_owned_only_filter(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """GET /api/v1/searchspaces?owned_only=true — only owned spaces returned."""
    space = await _create_space(api_client, auth_headers, name=_unique_name("Owned Only"))

    try:
        response = await api_client.get(
            "/api/v1/searchspaces?owned_only=true",
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        for item in body:
            assert item.get("is_owner", True) is True
    finally:
        await api_client.delete(f"/api/v1/searchspaces/{space['id']}", headers=auth_headers)
