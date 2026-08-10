"""Platform-superuser routes for managing the AgentConfig registry (AD-30)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import AgentConfig, VerticalClient, get_async_session
from app.schemas.agent_config import (
    AgentConfigCreate,
    AgentConfigRead,
    AgentConfigUpdate,
)
from app.services.agent_registry import list_agents
from app.users import require_superuser

router = APIRouter(prefix="/admin/agent-registry")
logger = logging.getLogger(__name__)


async def _set_admin_tenant_context(
    session: AsyncSession, client_id: str | None = None
) -> None:
    """Set GUCs so the superuser admin routes can read/write RLS-protected rows.

    ``app.internal_service`` is the canonical bypass used by other platform
    tables (runs, memories). ``app.current_client_id`` is also set when the
    caller is targeting a single client so ``WITH CHECK`` stays explicit.
    """
    await session.execute(
        text("SELECT set_config('app.internal_service', 'true', true)")
    )
    if client_id:
        await session.execute(
            text("SELECT set_config('app.current_client_id', :cid, true)"),
            {"cid": client_id},
        )


def _read(config: AgentConfig) -> AgentConfigRead:
    return AgentConfigRead(
        id=config.id,
        client_id=config.client_id,
        name=config.name,
        display_name=config.display_name,
        slug=config.slug,
        system_instructions=config.system_instructions,
        enabled_tools=list(config.enabled_tools or []),
        disabled_tools=list(config.disabled_tools or []),
        model_name=config.model_name,
        citations_enabled=config.citations_enabled,
        is_active=config.is_active,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.get("", response_model=list[AgentConfigRead])
async def list_agent_configs(
    client_id: str | None = None,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
):
    """List all agent configs.  Optional ``client_id`` filter."""
    await _set_admin_tenant_context(session)
    if client_id is not None:
        client_id = client_id.strip() or None
    configs = await list_agents(session, client_id=client_id)
    return [_read(c) for c in configs]


async def _verify_vertical_client(
    session: AsyncSession, client_id: str
) -> VerticalClient:
    """Ensure the target client exists and is active."""
    await _set_admin_tenant_context(session, client_id=client_id)
    result = await session.execute(
        select(VerticalClient).where(
            VerticalClient.client_id == client_id,
            VerticalClient.is_active.is_(True),
        )
    )
    client = result.scalars().first()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="client_id is not a registered active vertical client",
        )
    return client


async def _conflict_check(
    session: AsyncSession,
    client_id: str,
    slug: str,
    name: str,
    exclude_id: UUID | None = None,
) -> None:
    """Fail fast with 409 if ``(client_id, slug)`` or ``(client_id, name)`` exists."""
    stmt = select(AgentConfig).where(
        AgentConfig.client_id == client_id,
        (AgentConfig.slug == slug) | (AgentConfig.name == name),
    )
    if exclude_id is not None:
        stmt = stmt.where(AgentConfig.id != exclude_id)
    result = await session.execute(stmt)
    existing = result.scalars().first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="agent with this client_id and slug/name already exists",
        )


@router.post("", response_model=AgentConfigRead, status_code=status.HTTP_201_CREATED)
async def create_agent_config(
    data: AgentConfigCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
):
    """Create a new agent config."""
    await _verify_vertical_client(session, data.client_id)
    await _conflict_check(session, data.client_id, data.slug, data.name)

    config = AgentConfig(
        client_id=data.client_id,
        name=data.name,
        display_name=data.display_name,
        slug=data.slug,
        system_instructions=data.system_instructions,
        enabled_tools=list(data.enabled_tools),
        disabled_tools=list(data.disabled_tools),
        model_name=data.model_name,
        citations_enabled=data.citations_enabled,
        is_active=data.is_active,
    )
    session.add(config)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="agent with this client_id and slug/name already exists",
        ) from exc
    await session.refresh(config)
    logger.info(
        "[admin-agent-registry] created id=%s client=%s slug=%s",
        config.id,
        config.client_id,
        config.slug,
    )
    return _read(config)


async def _load_config(session: AsyncSession, config_id: UUID) -> AgentConfig:
    await _set_admin_tenant_context(session)
    result = await session.execute(
        select(AgentConfig).where(AgentConfig.id == config_id)
    )
    config = result.scalars().first()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="agent config not found",
        )
    return config


@router.get("/{config_id}", response_model=AgentConfigRead)
async def get_agent_config(
    config_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
):
    """Get a single agent config by id."""
    config = await _load_config(session, config_id)
    return _read(config)


@router.patch("/{config_id}", response_model=AgentConfigRead)
async def update_agent_config(
    config_id: UUID,
    data: AgentConfigUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
):
    """Update an agent config."""
    config = await _load_config(session, config_id)

    new_name = data.name if data.name is not None else config.name
    new_slug = data.slug if data.slug is not None else config.slug
    if new_name != config.name or new_slug != config.slug:
        await _conflict_check(
            session, config.client_id, new_slug, new_name, exclude_id=config.id
        )

    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(config, field, value)

    # Re-coerce JSONB lists if present.
    if data.enabled_tools is not None:
        config.enabled_tools = list(data.enabled_tools)
    if data.disabled_tools is not None:
        config.disabled_tools = list(data.disabled_tools)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="agent with this client_id and slug/name already exists",
        ) from exc
    await session.refresh(config)
    logger.info(
        "[admin-agent-registry] updated id=%s client=%s slug=%s",
        config.id,
        config.client_id,
        config.slug,
    )
    return _read(config)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_config(
    config_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
):
    """Soft-delete by setting ``is_active=False``."""
    config = await _load_config(session, config_id)
    config.is_active = False
    await session.commit()
    logger.info(
        "[admin-agent-registry] deactivated id=%s client=%s slug=%s",
        config.id,
        config.client_id,
        config.slug,
    )
    return None
