"""Integration tests for MemoryBrowserService with real Postgres (Story 29.5)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Memory, MemorySourceType, MemoryType
from app.models.memory_review_queue import MemoryReviewQueue
from app.models.users import User, WorkspaceMembership
from app.models.workspaces import ResearchThread, Workspace
from app.schemas.memory_browser import (
    MemoryBrowserDetailResponse,
    MemoryBrowserListResponse,
)
from app.services.memory.memory_browser_service import MemoryBrowserService
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
    membership = WorkspaceMembership(
        user_id=user.id,
        workspace_id=workspace.id,
        is_owner=False,
        role_id=None,
    )
    db_session.add(membership)
    await db_session.commit()
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
        research_thread_id=overrides.get("research_thread_id"),
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


class TestMemoryBrowserServiceIntegrationList:
    """Pattern 6: real SQL execution."""

    async def test_list_returns_workspace_scoped_rows(self, db_session: AsyncSession):
        workspace, user = await _seed_workspace_and_user(db_session)
        other_workspace = Workspace(name="Other", plan_tier="free", user_id=user.id)
        db_session.add(other_workspace)
        await db_session.commit()
        await db_session.refresh(other_workspace)

        await _seed_memory(db_session, workspace, user, content="in workspace")
        await _seed_memory(db_session, other_workspace, user, content="in other workspace")

        service = MemoryBrowserService(db_session)
        result = await service.list_memories(workspace_id=workspace.id, page=1, page_size=50)

        assert isinstance(result, MemoryBrowserListResponse)
        assert result.total == 1
        assert result.items[0].content_snippet == "in workspace"

    async def test_list_source_type_filter(self, db_session: AsyncSession):
        workspace, user = await _seed_workspace_and_user(db_session)
        await _seed_memory(db_session, workspace, user, source_type=MemorySourceType.SCRAPER_RUN, content="scraper")
        await _seed_memory(db_session, workspace, user, source_type=MemorySourceType.DOCUMENT, content="document")

        service = MemoryBrowserService(db_session)
        result = await service.list_memories(
            workspace_id=workspace.id,
            page=1,
            page_size=50,
            source_types=["scraper_run"],
        )

        assert result.total == 1
        assert "scraper" in result.items[0].content_snippet

    async def test_list_confidence_filter(self, db_session: AsyncSession):
        workspace, user = await _seed_workspace_and_user(db_session)
        await _seed_memory(db_session, workspace, user, content="high confidence", confidence=0.9)
        await _seed_memory(db_session, workspace, user, content="low confidence", confidence=0.3)

        service = MemoryBrowserService(db_session)
        result = await service.list_memories(
            workspace_id=workspace.id,
            page=1,
            page_size=50,
            confidence_min=0.5,
            confidence_max=1.0,
        )

        assert result.total == 1
        assert "high confidence" in result.items[0].content_snippet

    async def test_list_keyword_filter_tsvector(self, db_session: AsyncSession):
        workspace, user = await _seed_workspace_and_user(db_session)
        await _seed_memory(db_session, workspace, user, content="neural search engine")
        await _seed_memory(db_session, workspace, user, content="unrelated content")

        service = MemoryBrowserService(db_session)
        result = await service.list_memories(
            workspace_id=workspace.id,
            page=1,
            page_size=50,
            keyword="neural",
        )

        assert result.total == 1
        assert "neural" in result.items[0].content_snippet

    async def test_list_creator_filter(self, db_session: AsyncSession):
        workspace, user = await _seed_workspace_and_user(db_session)
        other_user = User(
            id=uuid.uuid4(),
            email="other@example.com",
            hashed_password="x",
            is_active=True,
        )
        db_session.add(other_user)
        await db_session.commit()

        await _seed_memory(db_session, workspace, user, content="by analyst")
        await _seed_memory(db_session, workspace, other_user, content="by other")

        service = MemoryBrowserService(db_session)
        result = await service.list_memories(
            workspace_id=workspace.id,
            page=1,
            page_size=50,
            created_by=user.id,
        )

        assert result.total == 1
        assert "by analyst" in result.items[0].content_snippet

    async def test_list_pagination_total(self, db_session: AsyncSession):
        workspace, user = await _seed_workspace_and_user(db_session)
        for i in range(5):
            await _seed_memory(db_session, workspace, user, content=f"memory {i}")

        service = MemoryBrowserService(db_session)
        result = await service.list_memories(workspace_id=workspace.id, page=1, page_size=2)

        assert result.total == 5
        assert len(result.items) == 2
        assert result.page == 1
        assert result.page_size == 2


class TestMemoryBrowserServiceIntegrationReviewFlag:
    """Pattern 6: memory_review_queue inserts and notification audit."""

    async def test_flag_creates_review_queue_row(self, db_session: AsyncSession):
        workspace, user = await _seed_workspace_and_user(db_session)
        memory = await _seed_memory(db_session, workspace, user)

        service = MemoryBrowserService(db_session)
        result = await service.flag_for_review(
            workspace_id=workspace.id,
            memory_id=memory.id,
            flag_reason="outdated fact",
            flagged_by=user.id,
        )

        assert result.flag_reason == "outdated fact"
        assert result.status == "open"

        queue = await db_session.scalar(
            select(MemoryReviewQueue).where(MemoryReviewQueue.memory_id == memory.id)
        )
        assert queue is not None
        assert queue.workspace_id == workspace.id

        # AC-5.2: audit event persisted in the same transaction.
        from app.models.billing import AuditEvent
        audit = await db_session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "memory_review_flag",
                AuditEvent.actor_id == user.id,
            )
        )
        assert audit is not None
        assert audit.diff_payload["memory_id"] == memory.id
        assert audit.diff_payload["review_queue_id"] == queue.id

    async def test_flag_notifies_owner(self, db_session: AsyncSession):
        workspace, user = await _seed_workspace_and_user(db_session)
        memory = await _seed_memory(db_session, workspace, user)

        # Make the seeded user an owner so they receive the review notification.
        membership = await db_session.scalar(
            select(WorkspaceMembership).where(
                WorkspaceMembership.user_id == user.id,
                WorkspaceMembership.workspace_id == workspace.id,
            )
        )
        membership.is_owner = True
        await db_session.commit()

        service = MemoryBrowserService(db_session)
        await service.flag_for_review(
            workspace_id=workspace.id,
            memory_id=memory.id,
            flag_reason="outdated",
            flagged_by=user.id,
        )

        from app.notifications.persistence import Notification
        note = await db_session.scalar(
            select(Notification).where(
                Notification.user_id == user.id,
                Notification.workspace_id == workspace.id,
                Notification.type == "memory_review_flag",
            )
        )
        assert note is not None
        assert note.notification_metadata["memory_id"] == memory.id


class TestMemoryBrowserServiceIntegrationDetail:
    """Pattern 6: detail query with research thread and versions."""

    async def test_detail_returns_versions_and_thread(self, db_session: AsyncSession):
        workspace, user = await _seed_workspace_and_user(db_session)

        thread = ResearchThread(
            workspace_id=workspace.id,
            created_by_id=user.id,
            title="Test Thread",
        )
        db_session.add(thread)
        await db_session.commit()
        await db_session.refresh(thread)

        memory = await _seed_memory(db_session, workspace, user, research_thread_id=thread.id)

        from app.db import MemoryVersion
        version = MemoryVersion(
            memory_id=memory.id,
            previous_content="old",
            corrected_content="new",
            corrected_by_id=user.id,
        )
        db_session.add(version)
        await db_session.commit()

        service = MemoryBrowserService(db_session)
        detail = await service.get_memory_detail(workspace_id=workspace.id, memory_id=memory.id)

        assert isinstance(detail, MemoryBrowserDetailResponse)
        assert detail.research_thread is not None
        assert detail.research_thread.title == "Test Thread"
        assert len(detail.versions) == 1
        assert detail.versions[0].previous_content == "old"
        assert detail.versions[0].corrected_content == "new"
