#!/usr/bin/env python3
"""Seed a workspace + user + vertical client + agent + PAT for agent-chat E2E.

Run from `nowing_backend/`:

    ENVIRONMENT=development uv run --active python scripts/seed_agent_chat_e2e.py

Output includes the plaintext PAT and workspace/client/agent IDs needed for
browser / Playwright tests against the local public agent-chat endpoints.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import UTC, datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import asyncio  # noqa: E402

from fastapi_users.password import PasswordHelper  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.config import config  # noqa: E402
from app.db import (  # noqa: E402
    AgentConfig,
    PersonalAccessToken,
    User,
    VerticalClient,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
    async_session_maker,
    get_default_roles_config,
)
from app.utils.pat import generate_pat, hash_pat, token_prefix  # noqa: E402

DEFAULT_EMAIL = "agent-chat-e2e@nowing.dev"
DEFAULT_PASSWORD = "TestPass123!"
DEFAULT_CLIENT_ID = "bdsai.vn"
DEFAULT_AGENT_SLUG = "bdsai-listing-assistant"
DEFAULT_WORKSPACE_NAME = "Agent Chat E2E"

SCOPES = ["agent_chat:thread:create", "agent_chat:message:create"]


def _require_dev_environment() -> None:
    env = os.getenv("ENVIRONMENT", "development").lower()
    safe = {"development", "dev", "test", "testing", "local"}
    if env not in safe:
        print(
            f"ERROR: refusing to seed agent-chat test data in ENVIRONMENT={env!r}. "
            f"Set ENVIRONMENT to one of {safe} or pass --force."
        )
        sys.exit(1)


async def _get_or_create_user(session: AsyncSession, email: str, password: str) -> User:
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        helper = PasswordHelper()
        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=helper.hash(password),
            is_active=True,
            is_superuser=False,
            is_verified=True,
            display_name=email.split("@")[0],
        )
        session.add(user)
        await session.flush()
    return user


async def _get_or_create_workspace(
    session: AsyncSession, name: str, owner: User
) -> Workspace:
    result = await session.execute(
        select(Workspace).where(Workspace.name == name, Workspace.user_id == owner.id)
    )
    workspace = result.scalar_one_or_none()
    if workspace is None:
        workspace = Workspace(
            name=name,
            description="Seeded workspace for agent-chat browser E2E tests",
            user_id=owner.id,
            citations_enabled=True,
            api_access_enabled=True,
        )
        session.add(workspace)
        await session.flush()
    return workspace


async def _ensure_roles(session: AsyncSession, workspace: Workspace) -> dict[str, int]:
    result = await session.execute(
        select(WorkspaceRole).where(WorkspaceRole.workspace_id == workspace.id)
    )
    existing = {r.name: r for r in result.scalars().all()}
    role_ids: dict[str, int] = {}
    for cfg in get_default_roles_config():
        role = existing.get(cfg["name"])
        if role is None:
            role = WorkspaceRole(
                name=cfg["name"],
                description=cfg["description"],
                permissions=cfg["permissions"],
                is_default=cfg["is_default"],
                is_system_role=cfg["is_system_role"],
                workspace_id=workspace.id,
            )
            session.add(role)
            await session.flush()
        role_ids[role.name] = role.id
    return role_ids


async def _ensure_membership(
    session: AsyncSession,
    user: User,
    workspace: Workspace,
    role_id: int,
    *,
    is_owner: bool = False,
) -> None:
    result = await session.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.user_id == user.id,
            WorkspaceMembership.workspace_id == workspace.id,
        )
    )
    if result.scalar_one_or_none() is None:
        session.add(
            WorkspaceMembership(
                user_id=user.id,
                workspace_id=workspace.id,
                role_id=role_id,
                is_owner=is_owner,
                joined_at=datetime.now(UTC),
            )
        )


async def _get_or_create_vertical_client(
    session: AsyncSession, client_id: str
) -> VerticalClient:
    result = await session.execute(
        select(VerticalClient).where(VerticalClient.client_id == client_id)
    )
    client = result.scalar_one_or_none()
    if client is None:
        client = VerticalClient(
            id=uuid.uuid4(),
            client_id=client_id,
            display_name=f"{client_id} (E2E)",
            is_active=True,
        )
        session.add(client)
        await session.flush()
    return client


async def _get_or_create_agent(
    session: AsyncSession, client_id: str, slug: str
) -> AgentConfig:
    result = await session.execute(
        select(AgentConfig).where(
            AgentConfig.client_id == client_id,
            AgentConfig.slug == slug,
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        agent = AgentConfig(
            id=uuid.uuid4(),
            client_id=client_id,
            name="BDS AI Listing Assistant",
            slug=slug,
            system_instructions="You are a helpful assistant.",
            is_active=True,
        )
        session.add(agent)
        await session.flush()
    return agent


async def _get_or_create_pat(
    session: AsyncSession,
    user: User,
    workspace: Workspace,
    client_id: str,
    agent_id: str | None,
) -> tuple[PersonalAccessToken, str]:
    result = await session.execute(
        select(PersonalAccessToken).where(
            PersonalAccessToken.user_id == user.id,
            PersonalAccessToken.workspace_id == workspace.id,
            PersonalAccessToken.client_id == client_id,
            PersonalAccessToken.token_kind == "agent_chat",
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        # Re-seed with a fresh token so the plaintext is known.
        await session.delete(existing)
        await session.flush()

    plaintext = generate_pat()
    pat = PersonalAccessToken(
        user_id=user.id,
        token_hash=hash_pat(plaintext),
        token_prefix=token_prefix(plaintext),
        label="agent-chat E2E token",
        workspace_id=workspace.id,
        client_id=client_id,
        agent_id=agent_id,
        scopes=SCOPES,
        token_kind="agent_chat",
    )
    session.add(pat)
    await session.flush()
    return pat, plaintext


async def seed(
    email: str = DEFAULT_EMAIL,
    password: str = DEFAULT_PASSWORD,
    workspace_name: str = DEFAULT_WORKSPACE_NAME,
    client_id: str = DEFAULT_CLIENT_ID,
    agent_slug: str = DEFAULT_AGENT_SLUG,
    force: bool = False,
) -> None:
    if not force:
        _require_dev_environment()

    async with async_session_maker() as session:
        user = await _get_or_create_user(session, email, password)
        workspace = await _get_or_create_workspace(session, workspace_name, user)
        role_ids = await _ensure_roles(session, workspace)
        await _ensure_membership(
            session, user, workspace, role_ids["Owner"], is_owner=True
        )

        await _get_or_create_vertical_client(session, client_id)
        await _get_or_create_agent(session, client_id, agent_slug)

        pat, plaintext = await _get_or_create_pat(
            session, user, workspace, client_id, agent_slug
        )

        await session.commit()

        print("Seeded agent-chat E2E data:")
        print(f"  User: {email} / {password}")
        print(f"  Workspace id: {workspace.id}")
        print(f"  Client id: {client_id}")
        print(f"  Agent slug: {agent_slug}")
        print(f"  PAT id: {pat.id}")
        print(f"  PAT plaintext: {plaintext}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed agent-chat E2E data for local browser tests."
    )
    parser.add_argument("--email", default=DEFAULT_EMAIL, help="Owner email.")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Owner password.")
    parser.add_argument(
        "--workspace-name", default=DEFAULT_WORKSPACE_NAME, help="Workspace name."
    )
    parser.add_argument("--client-id", default=DEFAULT_CLIENT_ID, help="Vertical client id.")
    parser.add_argument("--agent-slug", default=DEFAULT_AGENT_SLUG, help="Agent slug.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip the ENVIRONMENT safety check.",
    )
    args = parser.parse_args()
    asyncio.run(
        seed(
            email=args.email,
            password=args.password,
            workspace_name=args.workspace_name,
            client_id=args.client_id,
            agent_slug=args.agent_slug,
            force=args.force,
        )
    )


if __name__ == "__main__":
    main()
