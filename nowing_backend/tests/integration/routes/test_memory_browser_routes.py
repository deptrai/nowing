"""Integration tests for memory-browser routes (Story 29.5 / FR-104)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Memory, MemorySourceType, MemoryType
from app.models.users import User
from app.models.workspaces import Workspace
from tests.integration.conftest import _EMBEDDING_DIM

pytestmark = [pytest.mark.integration]


async def _seed_workspace_and_user(db_session: AsyncSession) -> tuple[Workspace, User]:
    user = User(
        id=uuid.uuid4(),
        email="analyst@example.com",
        hashed_password="x",
        is_active=True,
    )
    db_session.add(user)
    workspace = Workspace(
        name="Test Workspace",
        plan_tier="free",
        user_id=user.id,
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace, user


async def _seed_memory(
    db_session: AsyncSession,
    workspace: Workspace,
    user: User,
    **overrides,
) -> Memory:
    memory = Memory(
        workspace_id=workspace.id,
        created_by_id=user.id,
        content=overrides.get("content", "This is a memory content"),
        type=MemoryType.SEMANTIC,
        source_type=overrides.get("source_type", MemorySourceType.MANUAL),
        source_id=overrides.get("source_id"),
        source_run_id=overrides.get("source_run_id"),
        source_uuid=overrides.get("source_uuid"),
        source_entity_type=overrides.get("source_entity_type"),
        confidence=overrides.get("confidence", 1.0),
        content_search=overrides.get("content"),
        embedding=overrides.get("embedding", [0.1] * _EMBEDDING_DIM),
        created_at=overrides.get("created_at", datetime.now(UTC)),
    )
    db_session.add(memory)
    await db_session.commit()
    await db_session.refresh(memory)
    return memory


class TestMemoryBrowserRoutes:
    async def test_list_returns_403_without_permission(
        self, client_as_other: AsyncClient, db_session: AsyncSession, db_workspace: Workspace
    ):
        """Non-member gets 403."""
        response = await client_as_other.get(f"/api/v1/workspaces/{db_workspace.id}/memory-browser")
        assert response.status_code == 403

    async def test_list_returns_paginated_memories(
        self, client_as_regular_user: AsyncClient, db_session: AsyncSession, db_user: User, db_workspace: Workspace
    ):
        """Member gets paginated list."""
        await _seed_memory(db_session, db_workspace, db_user, content="first")
        await _seed_memory(db_session, db_workspace, db_user, content="second")

        response = await client_as_regular_user.get(
            f"/api/v1/workspaces/{db_workspace.id}/memory-browser",
            params={"page": 1, "page_size": 10},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2
        assert data["page"] == 1
        assert data["page_size"] == 10

    async def test_list_filters_by_source_type(
        self, client_as_regular_user: AsyncClient, db_session: AsyncSession, db_user: User, db_workspace: Workspace
    ):
        await _seed_memory(db_session, db_workspace, db_user, content="scraper", source_type=MemorySourceType.SCRAPER_RUN)
        await _seed_memory(db_session, db_workspace, db_user, content="document", source_type=MemorySourceType.DOCUMENT)

        response = await client_as_regular_user.get(
            f"/api/v1/workspaces/{db_workspace.id}/memory-browser",
            params={"source_types": "scraper_run"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert "scraper" in data["items"][0]["content_snippet"]

    async def test_detail_returns_memory(
        self, client_as_regular_user: AsyncClient, db_session: AsyncSession, db_user: User, db_workspace: Workspace
    ):
        memory = await _seed_memory(db_session, db_workspace, db_user)
        response = await client_as_regular_user.get(
            f"/api/v1/workspaces/{db_workspace.id}/memory-browser/{memory.id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == memory.id
        assert data["content"] == memory.content

    async def test_flag_creates_review_queue(
        self, client_as_regular_user: AsyncClient, db_session: AsyncSession, db_user: User, db_workspace: Workspace
    ):
        memory = await _seed_memory(db_session, db_workspace, db_user)
        response = await client_as_regular_user.post(
            f"/api/v1/workspaces/{db_workspace.id}/memory-browser/{memory.id}/flag",
            json={"flag_reason": "outdated fact"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["flag_reason"] == "outdated fact"
        assert data["status"] == "open"
