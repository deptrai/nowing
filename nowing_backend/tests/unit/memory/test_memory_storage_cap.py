"""Unit tests for Story 28.5: Workspace Memory Storage Cap (AC-1, AC-2, AC-3).

Tests:
- AC-1: Memory creation is blocked with HTTP 403 when memory count >= max_memory_count.
- AC-1: Error response matches {"error_code": "limit_exceeded", "limit_type": "memory"}.
- AC-2: Near-duplicate updates in create_memory do not increment count and bypass limit check.
- AC-3: Unlimited workspace (max_memory_count=None) allows memory creation without limit.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.db import Memory, MemorySourceType, MemoryType
from app.services.memory.repository import MemoryRepository
from app.services.workspace_limits import ResolvedWorkspaceLimits, WorkspaceLimitService


@pytest.mark.unit
class TestWorkspaceMemoryStorageCap:
    """AC-1, AC-2, AC-3: Unit tests for memory limit enforcement."""

    @pytest.mark.asyncio
    async def test_ac1_memory_creation_rejected_when_limit_exceeded(self):
        """AC-1: Given workspace is at max_memory_count, create_memory raises 403 limit_exceeded."""
        session = AsyncMock()
        repo = MemoryRepository(session)

        # Mock embedding
        repo._embed = AsyncMock(return_value=[0.1] * 384)
        repo._find_near_duplicate = AsyncMock(return_value=None)

        # Mock WorkspaceLimitService.assert_can_create_memory to raise limit exceeded
        with patch.object(
            WorkspaceLimitService,
            "assert_can_create_memory",
            side_effect=HTTPException(
                status_code=403,
                detail={"error_code": "limit_exceeded", "limit_type": "memory"},
            ),
        ) as mock_assert:
            with pytest.raises(HTTPException) as exc_info:
                await repo.create_memory(
                    workspace_id=1,
                    content="Important fact about customer preference",
                    type=MemoryType.SEMANTIC,
                    source_type=MemorySourceType.MANUAL,
                )

            assert exc_info.value.status_code == 403
            assert exc_info.value.detail == {
                "error_code": "limit_exceeded",
                "limit_type": "memory",
            }
            mock_assert.assert_awaited_once_with(session, 1, additional=1)

    @pytest.mark.asyncio
    async def test_ac2_near_duplicate_update_bypasses_limit_check(self):
        """AC-2: Updating an existing near-duplicate memory does not increment count and succeeds."""
        session = AsyncMock()
        repo = MemoryRepository(session)

        existing_memory = MagicMock(spec=Memory)
        existing_memory.id = 100
        existing_memory.workspace_id = 1
        existing_memory.content = "Initial memory content"

        repo._embed = AsyncMock(return_value=[0.1] * 384)
        repo._find_near_duplicate = AsyncMock(return_value=existing_memory)
        repo.update_memory = AsyncMock(return_value=existing_memory)

        with patch.object(
            WorkspaceLimitService, "assert_can_create_memory"
        ) as mock_assert:
            result = await repo.create_memory(
                workspace_id=1,
                content="Updated memory content",
                type=MemoryType.SEMANTIC,
                source_type=MemorySourceType.MANUAL,
                update_on_duplicate=True,
            )

            assert result == existing_memory
            # When duplicate is found and updated, assert_can_create_memory should NOT be called
            mock_assert.assert_not_called()

    @pytest.mark.asyncio
    async def test_ac3_unlimited_memory_count_allows_creation(self):
        """AC-3: When max_memory_count is None, memory creation succeeds without limit."""
        session = AsyncMock()
        repo = MemoryRepository(session)

        repo._embed = AsyncMock(return_value=[0.1] * 384)
        repo._find_near_duplicate = AsyncMock(return_value=None)
        repo._load_with_versions = AsyncMock(side_effect=lambda m: m)
        repo._persist = AsyncMock()
        repo._emit_memory_changed = AsyncMock()

        # Workspace limit service allows creation when max_memory_count is None
        limits = ResolvedWorkspaceLimits(
            plan_tier="self_host",
            max_documents=None,
            max_members=None,
            max_runs=None,
            max_storage_bytes=None,
            max_memory_count=None,
            max_memory_bytes=None,
        )

        with (
            patch.object(
                WorkspaceLimitService, "get_effective_limits", return_value=limits
            ),
            patch.object(
                WorkspaceLimitService, "assert_can_create_memory", return_value=None
            ),
        ):
            memory = await repo.create_memory(
                workspace_id=1,
                content="Self-hosted unlimited memory",
                type=MemoryType.SEMANTIC,
                source_type=MemorySourceType.MANUAL,
            )

            assert memory is not None
            assert memory.content == "Self-hosted unlimited memory"
            session.add.assert_called_once()
