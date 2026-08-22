from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.agent_chat import _validate_slug, validate_scopes
from app.auth.context import AuthContext
from app.config import config
from app.db import (
    AgentConfig,
    PersonalAccessToken,
    VerticalClient,
    get_async_session,
)
from app.schemas.pat import PATCreate, PATCreated, PATRead
from app.tenant_context import set_request_tenant_context
from app.users import require_non_impersonated_session, require_session_context
from app.utils.pat import generate_pat, hash_pat, token_prefix
from app.utils.rbac import is_workspace_owner

router = APIRouter()


def _expires_at(expires_in_days: int | None) -> datetime | None:
    max_expiry_days = config.PAT_MAX_EXPIRY_DAYS

    if max_expiry_days is not None:
        if expires_in_days is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "This deployment requires PATs to have an expiry of "
                    f"{max_expiry_days} days or less"
                ),
            )
        if expires_in_days > max_expiry_days:
            raise HTTPException(
                status_code=400,
                detail=f"PAT expiry cannot exceed {max_expiry_days} days",
            )

    if expires_in_days is None:
        return None

    return datetime.now(UTC) + timedelta(days=expires_in_days)


@router.post("/pats", response_model=PATCreated)
async def create_personal_access_token(
    body: PATCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_non_impersonated_session),
) -> PATCreated:
    token_kind = body.token_kind.strip().lower()

    workspace_id: int | None = body.workspace_id
    client_id: str | None = body.client_id
    agent_id: str | None = body.agent_id
    scopes: list[str] = body.scopes

    if token_kind == "agent_chat":
        if workspace_id is None or client_id is None:
            raise HTTPException(
                status_code=400,
                detail="agent_chat PAT requires workspace_id and client_id",
            )
        client_id = _validate_slug(client_id, "client_id")
        if agent_id:
            agent_id = _validate_slug(agent_id, "agent_id")

        if not await is_workspace_owner(session, auth.user.id, workspace_id):
            raise HTTPException(
                status_code=403, detail="PAT mint requires workspace owner"
            )

        # Set tenant GUCs so RLS policies can see the targeted client/agent rows.
        await set_request_tenant_context(session, workspace_id, client_id, agent_id)

        client_row = await session.execute(
            select(VerticalClient).where(
                VerticalClient.client_id == client_id,
                VerticalClient.is_active.is_(True),
            )
        )
        if client_row.scalars().first() is None:
            raise HTTPException(
                status_code=400,
                detail="client_id not registered for workspace",
            )

        if agent_id:
            agent_row = await session.execute(
                select(AgentConfig).where(
                    AgentConfig.client_id == client_id,
                    AgentConfig.slug == agent_id,
                    AgentConfig.is_active.is_(True),
                )
            )
            if agent_row.scalars().first() is None:
                # Fail closed: do not reveal that the agent belongs to another client.
                raise HTTPException(
                    status_code=404,
                    detail="agent not found or inactive",
                )

        validate_scopes(scopes)
        if not scopes:
            raise HTTPException(
                status_code=400,
                detail="agent_chat PAT requires at least one scope",
            )

    if token_kind == "self_host":
        # Self-host keys optionally bind to a workspace for attribution.
        if workspace_id is not None and not await is_workspace_owner(
            session, auth.user.id, workspace_id
        ):
            raise HTTPException(
                status_code=403, detail="PAT mint requires workspace owner"
            )
        client_id = None
        agent_id = None
        scopes = []

    token = generate_pat()
    pat = PersonalAccessToken(
        user_id=auth.user.id,
        token_hash=hash_pat(token),
        token_prefix=token_prefix(token),
        label=body.label.strip(),
        expires_at=_expires_at(body.expires_in_days),
        token_kind=token_kind,
        workspace_id=workspace_id,
        client_id=client_id,
        agent_id=agent_id,
        scopes=scopes,
    )
    session.add(pat)
    await session.commit()
    await session.refresh(pat)

    return PATCreated(
        id=pat.id,
        label=pat.label,
        token=token,
        prefix=pat.token_prefix,
        expires_at=pat.expires_at,
        token_kind=pat.token_kind,
        workspace_id=pat.workspace_id,
        client_id=pat.client_id,
        agent_id=pat.agent_id,
        scopes=pat.scopes or [],
    )


@router.get("/pats", response_model=list[PATRead])
async def list_personal_access_tokens(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
) -> list[PATRead]:
    result = await session.execute(
        select(PersonalAccessToken)
        .where(PersonalAccessToken.user_id == auth.user.id)
        .order_by(PersonalAccessToken.created_at.desc())
    )
    return [
        PATRead(
            id=pat.id,
            label=pat.label,
            prefix=pat.token_prefix,
            expires_at=pat.expires_at,
            last_used_at=pat.last_used_at,
            created_at=pat.created_at,
            token_kind=pat.token_kind,
            workspace_id=pat.workspace_id,
            client_id=pat.client_id,
            agent_id=pat.agent_id,
            scopes=pat.scopes or [],
        )
        for pat in result.scalars().all()
    ]


@router.delete("/pats/{pat_id}", status_code=204)
async def delete_personal_access_token(
    pat_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_non_impersonated_session),
) -> None:
    await session.execute(
        delete(PersonalAccessToken).where(
            PersonalAccessToken.id == pat_id,
            PersonalAccessToken.user_id == auth.user.id,
        )
    )
    await session.commit()
