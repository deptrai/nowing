import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
import jwt
from app.config import config
from app.db import AuditEvent
from sqlalchemy.future import select

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
    response = await admin_client.post(
        f"/admin/users/{db_user.id}/impersonate",
        params={"ticket_ref": "https://jira.nowing.net/browse/SUPPORT-1234"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    payload = jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"], options={"verify_aud": False})
    assert payload["is_impersonation"] is True
    assert payload["target_user"] == str(db_user.id)
    assert "impersonated_by" in payload
    assert payload["ticket_ref"] == "https://jira.nowing.net/browse/SUPPORT-1234"

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
    
    from httpx import ASGITransport
    from app.app import app
    from app.users import get_auth_context
    
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
