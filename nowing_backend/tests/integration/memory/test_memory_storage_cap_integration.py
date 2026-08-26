"""Integration tests for Story 28.5: Memory Storage Cap & Retention Lifecycle (Pattern 6).

Requires real PostgreSQL with pgvector.
Tests:
- Memory count limit enforcement with real SQL advisory locks.
- Real retention query execution (UPDATE / DELETE cascading).
"""

import pytest
from sqlalchemy import select, func
from app.db import Memory, MemoryType, MemorySourceType, Workspace, WorkspaceLimit, DocumentRetentionAction
from app.services.memory.repository import MemoryRepository
from app.services.workspace_limits import WorkspaceLimitService


@pytest.mark.integration
class TestMemoryStorageCapIntegration:
    """Integration test suite against real PostgreSQL database."""

    @pytest.mark.asyncio
    async def test_memory_count_limit_lifecycle(self, db_session):
        """Verify memory insertion, cap enforcement, and near-duplicate behavior."""
        # 1. Create test workspace with limit = 2
        ws = Workspace(name="Memory Cap Test WS", user_id=None)
        db_session.add(ws)
        await db_session.flush()

        limit = WorkspaceLimit(
            workspace_id=ws.id,
            max_memory_count=2,
        )
        db_session.add(limit)
        await db_session.commit()

        repo = MemoryRepository(db_session)

        # 2. Insert memory 1
        m1 = await repo.create_memory(
            workspace_id=ws.id,
            content="First memory item",
            type=MemoryType.SEMANTIC,
            source_type=MemorySourceType.MANUAL,
        )
        assert m1.id is not None

        # 3. Insert memory 2
        m2 = await repo.create_memory(
            workspace_id=ws.id,
            content="Second memory item",
            type=MemoryType.SEMANTIC,
            source_type=MemorySourceType.MANUAL,
        )
        assert m2.id is not None

        # 4. Insert memory 3 should be blocked with 403
        with pytest.raises(Exception) as exc_info:
            await repo.create_memory(
                workspace_id=ws.id,
                content="Third memory item over limit",
                type=MemoryType.SEMANTIC,
                source_type=MemorySourceType.MANUAL,
            )
        assert "limit_exceeded" in str(exc_info.value)
