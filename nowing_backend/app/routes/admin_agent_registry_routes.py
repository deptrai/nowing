"""Platform-superuser routes for managing the AgentConfig registry (AD-30)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import AgentConfig, get_async_session
from app.schemas.agent_config import (
    AgentConfigCreate,
    AgentConfigRead,
    AgentConfigUpdate,
)
from app.services.agent_registry import list_agents
from app.users import require_superuser

router = APIRouter(prefix="/admin/agent-registry")
logger = logging.getLogger(__name__)


def _read(config: AgentConfig) -> AgentConfigRead:
    return AgentConfigRead(
        id=config.id,
        client_id=config.client_id,
        name=config.name,
        slug=config.slug,
        system_instructions=config.system_instructions,
        enabled_tools=list(config.enabled_tools or []),
        disabled_tools=list(config.disabled_tools or []),
        model_name=config.model_name,
        citations_enabled=config.citations_enabled,
        is_active=config.is_active,
    )


@router.get("", response_model=list[AgentConfigRead])
async def list_agent_configs(
    client_id: str | None = None,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
):
    """List all agent configs.  Optional ``client_id`` filter."""
    configs = await list_agents(session, client_id=client_id)
    return [_read(c) for c in configs]


@router.post("", response_model=AgentConfigRead, status_code=status.HTTP_201_CREATED)
async def create_agent_config(
    data: AgentConfigCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
):
    """Create a new agent config."""
    slug = data.slug or data.name.strip().lower().replace(" ", "-")
    existing = await session.execute(
        select(AgentConfig).where(
            AgentConfig.client_id == data.client_id,
            AgentConfig.slug == slug,
        )
    )
    if existing.scalars().first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="agent with this client_id and slug already exists",
        )

    config = AgentConfig(
        client_id=data.client_id,
        name=data.name,
        slug=slug,
        system_instructions=data.system_instructions,
        enabled_tools=list(data.enabled_tools),
        disabled_tools=list(data.disabled_tools),
        model_name=data.model_name,
        citations_enabled=data.citations_enabled,
        is_active=data.is_active,
    )
    session.add(config)
    await session.commit()
    await session.refresh(config)
    logger.info(
        "[admin-agent-registry] created id=%s client=%s slug=%s",
        config.id,
        config.client_id,
        config.slug,
    )
    return _read(config)


async def _load_config(session: AsyncSession, config_id: UUID) -> AgentConfig:
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

    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "slug" and not value:
            continue
        if value is not None:
            setattr(config, field, value)

    # Re-coerce JSONB lists if present.
    if data.enabled_tools is not None:
        config.enabled_tools = list(data.enabled_tools)
    if data.disabled_tools is not None:
        config.disabled_tools = list(data.disabled_tools)

    await session.commit()
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
