"""
API-layer tests for RBAC endpoints.

Tổ chức thành 2 lớp:
  Layer 1 — Auth-gate tests: Chạy với 1 user, verify unauthenticated/non-member guards.
  Layer 2 — Two-user isolation: Cần TEST_USER2_EMAIL + TEST_USER2_PASSWORD env vars.
            Tự động skip nếu không có (CI chưa config second user).

Markers: @pytest.mark.api, @pytest.mark.rbac (cho Layer 2)
"""

from __future__ import annotations

import os
import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.api

# Second user available nếu CI có secrets tương ứng
_HAS_SECOND_USER = bool(
    os.environ.get("TEST_USER2_EMAIL") and os.environ.get("TEST_USER2_PASSWORD")
)

requires_second_user = pytest.mark.skipif(
    not _HAS_SECOND_USER,
    reason="TEST_USER2_EMAIL / TEST_USER2_PASSWORD not set — skipping two-user RBAC tests",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def unique_name() -> str:
    return f"RBAC-Test-{uuid.uuid4().hex[:8]}"


async def _create_space(
    client: AsyncClient,
    headers: dict[str, str],
    name: str,
) -> dict:
    response = await client.post(
        "/api/v1/searchspaces",
        json={"name": name, "description": "RBAC test space"},
        headers=headers,
    )
    if response.status_code != 200:
        raise RuntimeError(f"_create_space failed [{response.status_code}]: {response.text}")
    return response.json()


async def _get_second_user_headers(client: AsyncClient) -> dict[str, str]:
    """Login với second test user."""
    email = os.environ["TEST_USER2_EMAIL"]
    password = os.environ["TEST_USER2_PASSWORD"]
    response = await client.post(
        "/auth/jwt/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200, f"Second user login failed: {response.text}"
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}


# ---------------------------------------------------------------------------
# Layer 1 — Auth-gate (no second user needed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_members_unauthenticated_returns_401(api_client: AsyncClient) -> None:
    """GET /searchspaces/{id}/members — no auth → 401."""
    response = await api_client.get("/api/v1/searchspaces/1/members")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_roles_unauthenticated_returns_401(api_client: AsyncClient) -> None:
    """GET /searchspaces/{id}/roles — no auth → 401."""
    response = await api_client.get("/api/v1/searchspaces/1/roles")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_invite_unauthenticated_returns_401(api_client: AsyncClient) -> None:
    """POST /searchspaces/{id}/invites — no auth → 401."""
    response = await api_client.post(
        "/api/v1/searchspaces/1/invites",
        json={"max_uses": 1},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_my_access_unauthenticated_returns_401(api_client: AsyncClient) -> None:
    """GET /searchspaces/{id}/my-access — no auth → 401."""
    response = await api_client.get("/api/v1/searchspaces/1/my-access")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_permissions_requires_auth(api_client: AsyncClient) -> None:
    """GET /permissions — no auth → 401."""
    response = await api_client.get("/api/v1/permissions")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_permissions_authenticated_returns_list(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """GET /permissions — authenticated → 200 + non-empty list."""
    response = await api_client.get("/api/v1/permissions", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert "permissions" in body
    assert isinstance(body["permissions"], list)
    assert len(body["permissions"]) > 0


@pytest.mark.asyncio
async def test_list_members_non_member_returns_403(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """GET /searchspaces/{id}/members — non-member → 403 hoặc 404."""
    response = await api_client.get(
        "/api/v1/searchspaces/1000000/members",
        headers=auth_headers,
    )

    assert response.status_code in (403, 404)


@pytest.mark.asyncio
async def test_list_roles_non_member_returns_403(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """GET /searchspaces/{id}/roles — non-member → 403 hoặc 404."""
    response = await api_client.get(
        "/api/v1/searchspaces/1000000/roles",
        headers=auth_headers,
    )

    assert response.status_code in (403, 404)


@pytest.mark.asyncio
async def test_create_role_non_member_returns_403(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """POST /searchspaces/{id}/roles — non-member → 403."""
    response = await api_client.post(
        "/api/v1/searchspaces/1000000/roles",
        json={"name": "Hacker Role", "permissions": []},
        headers=auth_headers,
    )

    assert response.status_code in (403, 404)


@pytest.mark.asyncio
async def test_get_my_access_for_owned_space_returns_200(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """GET /searchspaces/{id}/my-access — owner của space → 200 + is_owner=True."""
    space = await _create_space(api_client, auth_headers, f"MyAccess-{uuid.uuid4().hex[:8]}")
    space_id = space["id"]

    try:
        response = await api_client.get(
            f"/api/v1/searchspaces/{space_id}/my-access",
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        assert body.get("is_owner") is True
    finally:
        await api_client.delete(f"/api/v1/searchspaces/{space_id}", headers=auth_headers)


@pytest.mark.asyncio
async def test_list_members_for_owned_space_returns_list(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """GET /searchspaces/{id}/members — owner → 200 + list chứa owner."""
    space = await _create_space(api_client, auth_headers, f"Members-{uuid.uuid4().hex[:8]}")
    space_id = space["id"]

    try:
        response = await api_client.get(
            f"/api/v1/searchspaces/{space_id}/members",
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert len(body) >= 1
        # Owner phải có is_owner=True
        assert any(m.get("is_owner") is True for m in body)
    finally:
        await api_client.delete(f"/api/v1/searchspaces/{space_id}", headers=auth_headers)


@pytest.mark.asyncio
async def test_create_invite_for_owned_space_returns_invite(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """POST /searchspaces/{id}/invites — owner → 200 + {invite_code}."""
    space = await _create_space(api_client, auth_headers, f"Invite-{uuid.uuid4().hex[:8]}")
    space_id = space["id"]

    try:
        response = await api_client.post(
            f"/api/v1/searchspaces/{space_id}/invites",
            json={"max_uses": 5},
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        assert "invite_code" in body
        assert body["invite_code"]
    finally:
        await api_client.delete(f"/api/v1/searchspaces/{space_id}", headers=auth_headers)


@pytest.mark.asyncio
async def test_accept_invalid_invite_returns_404(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """POST /invites/accept — mã không tồn tại → 404."""
    response = await api_client.post(
        "/api/v1/invites/accept",
        json={"invite_code": "INVALID-CODE-00000000"},
        headers=auth_headers,
    )

    assert response.status_code in (404, 400)


# ---------------------------------------------------------------------------
# Layer 2 — Two-user isolation (requires TEST_USER2_EMAIL + TEST_USER2_PASSWORD)
# ---------------------------------------------------------------------------


@requires_second_user
@pytest.mark.asyncio
@pytest.mark.rbac
async def test_non_member_cannot_list_members(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """
    User A tạo space → User B (non-member) GET /members → 403.
    Đây là real RBAC test: không thể fake bằng synthetic ID.
    """
    # User A tạo space
    space = await _create_space(api_client, auth_headers, f"RBACreal-{uuid.uuid4().hex[:8]}")
    space_id = space["id"]

    # User B login
    user_b_headers = await _get_second_user_headers(api_client)

    try:
        response = await api_client.get(
            f"/api/v1/searchspaces/{space_id}/members",
            headers=user_b_headers,
        )

        assert response.status_code in (403, 404), (
            f"Expected 403/404 for non-member, got {response.status_code}: {response.text}"
        )
    finally:
        await api_client.delete(f"/api/v1/searchspaces/{space_id}", headers=auth_headers)


@requires_second_user
@pytest.mark.asyncio
@pytest.mark.rbac
async def test_non_member_cannot_get_search_space(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """User A tạo space → User B (non-member) GET space → 403."""
    space = await _create_space(api_client, auth_headers, f"RBACss-{uuid.uuid4().hex[:8]}")
    space_id = space["id"]

    user_b_headers = await _get_second_user_headers(api_client)

    try:
        response = await api_client.get(
            f"/api/v1/searchspaces/{space_id}",
            headers=user_b_headers,
        )

        assert response.status_code in (403, 404)
    finally:
        await api_client.delete(f"/api/v1/searchspaces/{space_id}", headers=auth_headers)


@requires_second_user
@pytest.mark.asyncio
@pytest.mark.rbac
async def test_non_member_cannot_delete_search_space(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """User A tạo space → User B (non-member) DELETE → 403."""
    space = await _create_space(api_client, auth_headers, f"RBACdel-{uuid.uuid4().hex[:8]}")
    space_id = space["id"]

    user_b_headers = await _get_second_user_headers(api_client)

    try:
        response = await api_client.delete(
            f"/api/v1/searchspaces/{space_id}",
            headers=user_b_headers,
        )

        assert response.status_code in (403, 404)
    finally:
        await api_client.delete(f"/api/v1/searchspaces/{space_id}", headers=auth_headers)


@requires_second_user
@pytest.mark.asyncio
@pytest.mark.rbac
async def test_member_can_access_after_invite_accepted(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """
    User A tạo space → tạo invite → User B accept → User B GET space → 200.
    Verify membership grant flow end-to-end.
    """
    space = await _create_space(api_client, auth_headers, f"RBACinvite-{uuid.uuid4().hex[:8]}")
    space_id = space["id"]

    try:
        # Tạo invite link
        invite_resp = await api_client.post(
            f"/api/v1/searchspaces/{space_id}/invites",
            json={"max_uses": 1},
            headers=auth_headers,
        )
        assert invite_resp.status_code == 200
        invite_code = invite_resp.json()["invite_code"]

        # User B accept invite
        user_b_headers = await _get_second_user_headers(api_client)
        accept_resp = await api_client.post(
            "/api/v1/invites/accept",
            json={"invite_code": invite_code},
            headers=user_b_headers,
        )
        assert accept_resp.status_code == 200, (
            f"Accept invite failed: {accept_resp.text}"
        )

        # User B bây giờ là member → có thể GET space
        access_resp = await api_client.get(
            f"/api/v1/searchspaces/{space_id}",
            headers=user_b_headers,
        )
        assert access_resp.status_code == 200
    finally:
        await api_client.delete(f"/api/v1/searchspaces/{space_id}", headers=auth_headers)


@requires_second_user
@pytest.mark.asyncio
@pytest.mark.rbac
async def test_member_cannot_create_roles_without_permission(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """
    User A tạo space → invite User B (default role) → User B POST /roles → 403.
    Default member role không có ROLES_CREATE permission.
    """
    space = await _create_space(api_client, auth_headers, f"RBACrole-{uuid.uuid4().hex[:8]}")
    space_id = space["id"]

    try:
        # Tạo invite và cho User B join
        invite_resp = await api_client.post(
            f"/api/v1/searchspaces/{space_id}/invites",
            json={"max_uses": 1},
            headers=auth_headers,
        )
        assert invite_resp.status_code == 200
        invite_code = invite_resp.json()["invite_code"]

        user_b_headers = await _get_second_user_headers(api_client)
        accept_resp = await api_client.post(
            "/api/v1/invites/accept",
            json={"invite_code": invite_code},
            headers=user_b_headers,
        )
        assert accept_resp.status_code == 200

        # User B cố tạo role (không có permission)
        role_resp = await api_client.post(
            f"/api/v1/searchspaces/{space_id}/roles",
            json={"name": "Unauthorized Role", "permissions": []},
            headers=user_b_headers,
        )

        assert role_resp.status_code in (403, 422)
    finally:
        await api_client.delete(f"/api/v1/searchspaces/{space_id}", headers=auth_headers)
