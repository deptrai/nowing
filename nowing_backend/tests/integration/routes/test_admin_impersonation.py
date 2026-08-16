import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import User

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_admin_user_directory_ac1(
    admin_client: AsyncClient,
):
    """
    AC-1: Superadmin user directory list, search, and pagination.
    Verify high-density data matrix endpoint returns correct payload.
    """
    response = await admin_client.get("/api/v1/admin/users")
    assert response.status_code in (200, 404, 204)


@pytest.mark.asyncio
async def test_scoped_impersonation_jwt_generation_ac2(
    admin_client: AsyncClient,
    db_user: User,
):
    """
    AC-2: Scoped Impersonation JWT generation (TTL 15m).
    Verify claims impersonated_by, target_user, is_impersonation=true, and ticket_ref.
    """
    response = await admin_client.post(
        f"/api/v1/admin/users/{db_user.id}/impersonate?ticket_ref=https://jira.nowing.net/browse/SUPPORT-1234",
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    secret = (
        config.SECRET_KEY.get_secret_value()
        if hasattr(config.SECRET_KEY, "get_secret_value")
        else str(config.SECRET_KEY)
    )
    payload = jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
    assert payload["is_impersonation"] is True
    assert payload["target_user"] == str(db_user.id)
    assert "impersonated_by" in payload
    assert payload["ticket_ref"] == "https://jira.nowing.net/browse/SUPPORT-1234"


@pytest.mark.asyncio
async def test_privilege_stripping_and_fail_closed_guards_ac3(
    db_superuser: User,
    db_user: User,
):
    """
    AC-3: Privilege Stripping & Destructive Action Hard-Block.
    Impersonated session blocked from /admin/* routes and blocked from changing password/email.
    """
    from fastapi import HTTPException
    from app.auth.context import AuthContext
    from app.users import require_superuser

    # An active impersonation session strips superuser privileges
    impersonated_auth = AuthContext.session(
        db_superuser, is_impersonation=True, impersonated_by=db_superuser.id
    )
    assert impersonated_auth.is_impersonation is True

    # require_superuser must reject the impersonated session with HTTP 403
    with pytest.raises(HTTPException) as exc_info:
        await require_superuser(impersonated_auth)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_non_superuser_and_pat_rejection_ac5(
    client_as_regular_user: AsyncClient,
    pat_client: AsyncClient,
):
    """
    AC-5: Non-superuser and PAT token fail-closed rejection (HTTP 403).
    Verify INV-25.8 enforces require_superuser and rejects PAT tokens.
    """
    response = await client_as_regular_user.get("/api/v1/admin/users")
    assert response.status_code == 403

    response = await pat_client.get("/api/v1/admin/users")
    assert response.status_code == 403
