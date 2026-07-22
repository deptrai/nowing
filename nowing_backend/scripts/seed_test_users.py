#!/usr/bin/env python3
"""Seed test users + workspace with Owner/Editor/Viewer roles for local E2E.

Run from `nowing_backend/`:

    ENVIRONMENT=development uv run --active python scripts/seed_test_users.py

This creates three verified users sharing one workspace:

- test-owner@nowing.dev / TestPass123!  (Owner)
- test-editor@nowing.dev / TestPass123! (Editor)
- test-viewer@nowing.dev / TestPass123! (Viewer)

The script is idempotent; re-running it skips already-existing users/roles.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import UTC, datetime

# Allow `python scripts/seed_test_users.py` from the repo root or nowing_backend.
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
    User,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
    async_session_maker,
    get_default_roles_config,
)

DEFAULT_PASSWORD = "TestPass123!"
ROLE_USERS = [
    ("owner", "Owner"),
    ("editor", "Editor"),
    ("viewer", "Viewer"),
]


def _require_dev_environment() -> None:
    env = os.getenv("ENVIRONMENT", "development").lower()
    safe = {"development", "dev", "test", "testing", "local"}
    if env not in safe:
        print(
            f"ERROR: refusing to seed test users in ENVIRONMENT={env!r}. "
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
            description="Seeded workspace for local browser E2E tests",
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


async def seed(password: str = DEFAULT_PASSWORD, force: bool = False) -> None:
    if not force:
        _require_dev_environment()

    async with async_session_maker() as session:
        owner_email = f"test-{ROLE_USERS[0][0]}@nowing.dev"
        owner = await _get_or_create_user(session, owner_email, password)

        workspace = await _get_or_create_workspace(session, "E2E Test Workspace", owner)
        role_ids = await _ensure_roles(session, workspace)
        await _ensure_membership(
            session, owner, workspace, role_ids["Owner"], is_owner=True
        )

        for slug, role_name in ROLE_USERS[1:]:
            email = f"test-{slug}@nowing.dev"
            user = await _get_or_create_user(session, email, password)
            await _ensure_membership(session, user, workspace, role_ids[role_name])

        await session.commit()

        print("Seeded test users and workspace:")
        for slug, role_name in ROLE_USERS:
            print(f"  - test-{slug}@nowing.dev / {password} => {role_name}")
        print(f"  Workspace: {workspace.name} (id={workspace.id})")
        print(f"  ChainLens API URL configured: {config.CHAINLENS_API_URL}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed test users for local E2E browser tests."
    )
    parser.add_argument(
        "--password",
        default=DEFAULT_PASSWORD,
        help="Password for all seeded test accounts.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip the ENVIRONMENT safety check.",
    )
    args = parser.parse_args()
    asyncio.run(seed(password=args.password, force=args.force))


if __name__ == "__main__":
    main()
