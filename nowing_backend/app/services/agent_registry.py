"""Agent Registry service (AD-30).

The registry is the authoritative lookup for per-vertical-client agent
configurations.  It is intentionally platform-scoped, not workspace-scoped.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AgentConfig


class AgentConfigNotFoundError(Exception):
    """Raised when the requested agent is missing or inactive."""

    def __init__(self, message: str = "agent not found or inactive") -> None:
        self.message = message
        super().__init__(message)


async def get_agent_config(
    session: AsyncSession,
    client_id: str,
    agent_id: str,
) -> AgentConfig:
    """Fail-closed lookup of an active agent by client and slug.

    Returns the active ``AgentConfig`` or raises ``AgentConfigNotFoundError``.
    The client_id check is duplicated in the query and as an explicit guard
    so cross-client slugs are not leaked.
    """
    result = await session.execute(
        select(AgentConfig).where(
            AgentConfig.client_id == client_id,
            AgentConfig.slug == agent_id,
            AgentConfig.is_active.is_(True),
        )
    )
    config = result.scalars().first()
    if (
        config is None
        or not config.is_active
        or (config.client_id or "").lower() != client_id.lower()
    ):
        raise AgentConfigNotFoundError()
    return config


async def list_agents(
    session: AsyncSession,
    client_id: str | None = None,
) -> list[AgentConfig]:
    """List agent configs, optionally filtered to a single client."""
    if client_id is not None:
        client_id = client_id.strip() or None
    stmt = select(AgentConfig)
    if client_id is not None:
        stmt = stmt.where(AgentConfig.client_id == client_id)
    stmt = stmt.order_by(AgentConfig.client_id, AgentConfig.name)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def upsert_agent_config(
    session: AsyncSession,
    client_id: str,
    slug: str,
    **fields,
) -> AgentConfig:
    """Idempotent upsert used by seed scripts and admin tooling.

    ``fields`` may include any AgentConfig column.  If the row does not exist,
    it is created; otherwise it is updated in place.
    """
    result = await session.execute(
        select(AgentConfig).where(
            AgentConfig.client_id == client_id,
            AgentConfig.slug == slug,
        )
    )
    config = result.scalars().first()
    if config is None:
        fields.setdefault("display_name", fields.get("name") or slug)
        config = AgentConfig(client_id=client_id, slug=slug, **fields)
        session.add(config)
    else:
        for key, value in fields.items():
            if value is not None or key in ("system_instructions", "model_name"):
                setattr(config, key, value)
    await session.flush()
    return config
