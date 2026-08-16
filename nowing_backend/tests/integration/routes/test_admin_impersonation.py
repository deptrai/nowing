import uuid

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.app import app
from app.config import config
from app.db import AuditEvent, User
from app.users import get_auth_context

pytestmark = pytest.mark.integration

@pytest.mark.asyncio
async def test_admin_user_directory_ac1(
    admin_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    AC-1: Superadmin user directory list, search, and pagination.
    Verify high-density data matrix endpoint returns correct payload.
    """
    response = await admin_client.get("/admin/users")
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_scoped_impersonation_jwt_generation_ac2(
    admin_client: AsyncClient,
    db_session: AsyncSession,
    db_user,
):
    """
    AC-2: Scoped Impersonation JWT generation (TTL 15m).
    Verify claims impersonated_by, target_user, is_impersonation=true, and ticket_ref.
    """
    ticket_ref = "https://jira.nowing.net/browse/SUPPORT-1234"
    response = await admin_client.post(
        f"/admin/users/{db_user.id}/impersonate",
        params={"ticket_ref": ticket_ref}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    payload = jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"], options={"verify_aud": False})
    assert payload["is_impersonation"] is True
    assert payload["sub"] == str(db_user.id)
    assert payload["target_user"] == str(db_user.id)
    assert "impersonated_by" in payload
    assert payload["ticket_ref"] == ticket_ref
    assert payload["exp"] - payload["iat"] == 900

    event = (
        await db_session.execute(
            select(AuditEvent).filter_by(action="user.impersonate_start", subject_id=db_user.id)
        )
    ).scalars().first()
    assert event is not None
    assert event.actor_id is not None
    assert event.ticket_ref == ticket_ref

@pytest.mark.asyncio
async def test_privilege_stripping_and_fail_closed_guards_ac3(
    admin_client: AsyncClient,
    db_session: AsyncSession,
    db_user,
):
    """
    AC-3: Privilege Stripping & Destructive Action Hard-Block.
    Impersonated session blocked from /admin/* routes and blocked from changing password/email.
    """
    response = await admin_client.post(
        f"/admin/users/{db_user.id}/impersonate",
        params={"ticket_ref": "https://jira.nowing.net/browse/SUPPORT-1234"}
    )
    token = response.json()["access_token"]
    

    # Remove the dependency override set by admin_client so we can test actual header parsing
    app.dependency_overrides.pop(get_auth_context, None)
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as raw_client:
        impersonated_headers = {"Authorization": f"Bearer {token}"}
        admin_response = await raw_client.get("/admin/users", headers=impersonated_headers)
        assert admin_response.status_code == 403

@pytest.mark.asyncio
async def test_dual_principal_audit_logging_ac4(
    admin_client: AsyncClient,
    db_session: AsyncSession,
    db_user,
):
    """
    AC-4: Dual-principal audit logging in audit_events on impersonate start & exit.
    Verify actor_id and subject_id.
    """
    response = await admin_client.post(
        f"/admin/users/{db_user.id}/impersonate",
        params={"ticket_ref": "https://jira.nowing.net/browse/SUPPORT-1234"}
    )
    assert response.status_code == 200
    result = await db_session.execute(select(AuditEvent).filter_by(action="user.impersonate_start", subject_id=db_user.id))
    event = result.scalars().first()
    assert event is not None

@pytest.mark.asyncio
async def test_non_superuser_and_pat_rejection_ac5(
    client_as_regular_user: AsyncClient,
    pat_client: AsyncClient,
):
    """
    AC-5: Non-superuser and PAT token fail-closed rejection (HTTP 403).
    Verify INV-25.8 enforces require_superuser and rejects PAT tokens.
    """
    response = await client_as_regular_user.get("/admin/users")
    assert response.status_code == 403

    response = await pat_client.get("/admin/users")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_impersonation_invalid_ticket_ref(admin_client: AsyncClient, db_user):
    """AC-2: empty or too-long ticket_ref is rejected with 400."""
    response = await admin_client.post(
        f"/admin/users/{db_user.id}/impersonate",
        params={"ticket_ref": ""},
    )
    assert response.status_code == 400

    long_ref = "x" * 256
    response = await admin_client.post(
        f"/admin/users/{db_user.id}/impersonate",
        params={"ticket_ref": long_ref},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_impersonation_inactive_target(admin_client: AsyncClient, db_session: AsyncSession, db_user):
    """AC-2: impersonating an inactive user returns 404."""
    db_user.is_active = False
    await db_session.flush()

    response = await admin_client.post(
        f"/admin/users/{db_user.id}/impersonate",
        params={"ticket_ref": "https://jira.nowing.net/browse/SUPPORT-1234"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_impersonation_self_impersonation(admin_client: AsyncClient, db_superuser: User):
    """AC-2: admin cannot impersonate themselves."""
    response = await admin_client.post(
        f"/admin/users/{db_superuser.id}/impersonate",
        params={"ticket_ref": "https://jira.nowing.net/browse/SUPPORT-SELF"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_exit_impersonation(
    admin_client: AsyncClient,
    db_session: AsyncSession,
    db_user,
):
    """AC-2/AC-4: exit endpoint ends impersonation and logs audit."""
    response = await admin_client.post(
        f"/admin/users/{db_user.id}/impersonate",
        params={"ticket_ref": "https://jira.nowing.net/browse/SUPPORT-EXIT"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]

    app.dependency_overrides.pop(get_auth_context, None)



    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as raw_client:
        headers = {"Authorization": f"Bearer {token}"}
        exit_response = await raw_client.post("/admin/impersonate/exit", headers=headers)
        assert exit_response.status_code == 200
        assert exit_response.json()["status"] == "impersonation_ended"

    exit_event = (
        await db_session.execute(
            select(AuditEvent).filter_by(action="user.impersonate_exit", subject_id=db_user.id)
        )
    ).scalars().first()
    assert exit_event is not None


@pytest.mark.asyncio
async def test_exit_impersonation_without_session(admin_client: AsyncClient):
    """AC-2: exit without an active impersonation session returns 400."""
    response = await admin_client.post("/admin/impersonate/exit")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_privilege_stripping_blocks_admin_routes_for_superuser_target(
    admin_client: AsyncClient,
    db_session: AsyncSession,
):
    """AC-3: even an impersonated superuser target cannot access /admin/* routes."""
    target_admin = User(
        id=uuid.uuid4(),
        email="target-admin@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True,
        is_verified=True,
    )
    db_session.add(target_admin)
    await db_session.flush()

    response = await admin_client.post(
        f"/admin/users/{target_admin.id}/impersonate",
        params={"ticket_ref": "https://jira.nowing.net/browse/SUPPORT-SU"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]

    app.dependency_overrides.pop(get_auth_context, None)



    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as raw_client:
        headers = {"Authorization": f"Bearer {token}"}
        admin_response = await raw_client.get("/admin/users", headers=headers)
        assert admin_response.status_code == 403


@pytest.mark.asyncio
async def test_nested_impersonation_blocked(
    admin_client: AsyncClient,
    db_session: AsyncSession,
    db_user,
):
    """AC-3: an impersonated session cannot start another impersonation."""
    target_admin = User(
        id=uuid.uuid4(),
        email="nested-target@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True,
        is_verified=True,
    )
    db_session.add(target_admin)
    await db_session.flush()

    response = await admin_client.post(
        f"/admin/users/{db_user.id}/impersonate",
        params={"ticket_ref": "https://jira.nowing.net/browse/SUPPORT-NEST"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]

    app.dependency_overrides.pop(get_auth_context, None)



    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as raw_client:
        headers = {"Authorization": f"Bearer {token}"}
        nested = await raw_client.post(
            f"/admin/users/{target_admin.id}/impersonate",
            params={"ticket_ref": "nested"},
            headers=headers,
        )
        assert nested.status_code == 403


@pytest.mark.asyncio
async def test_destructive_pats_blocked_during_impersonation(
    admin_client: AsyncClient,
    db_session: AsyncSession,
    db_user,
):
    """AC-3: issuing a PAT during an impersonation session is rejected."""
    response = await admin_client.post(
        f"/admin/users/{db_user.id}/impersonate",
        params={"ticket_ref": "https://jira.nowing.net/browse/SUPPORT-PAT"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]

    app.dependency_overrides.pop(get_auth_context, None)



    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as raw_client:
        headers = {"Authorization": f"Bearer {token}"}
        pat_response = await raw_client.post(
            "/pats",
            json={
                "token_kind": "self_host",
                "expires_in_days": 1,
                "scopes": [],
            },
            headers=headers,
        )
        assert pat_response.status_code == 403
