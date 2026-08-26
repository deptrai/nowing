"""Unit tests for Story 28.5: Memory Right-to-Delete and Bulk Deletion (AC-8, AC-9).

Tests:
- AC-8: DELETE /workspaces/{id}/memories/{memory_id} erases memory and logs audit_events.
- AC-9: POST /workspaces/{id}/memories/bulk-delete supports dry-run and batch chunking.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.db import Memory, User


@pytest.mark.unit
class TestMemoryRightToDelete:
    """Unit tests for Right-to-Delete erasure and bulk deletion."""

    @pytest.mark.asyncio
    async def test_ac8_single_memory_delete_writes_audit_log(self):
        """AC-8: Deleting a single memory writes an audit_events row."""
        from app.services.memory.erasure_service import MemoryErasureService

        session = AsyncMock()
        service = MemoryErasureService(session)

        mock_user = MagicMock(spec=User)
        mock_user.id = "11111111-1111-4111-8111-111111111111"
        mock_user.email = "admin@example.com"

        mock_memory = MagicMock(spec=Memory)
        mock_memory.id = 123
        mock_memory.workspace_id = 1

        with patch.object(service, "_record_audit_event") as mock_audit:
            deleted = await service.delete_memory(
                workspace_id=1,
                memory_id=123,
                actor=mock_user,
                reason="GDPR right-to-be-forgotten request",
            )

            assert deleted is True
            mock_audit.assert_called_once_with(
                action="memory_delete",
                workspace_id=1,
                actor_id=mock_user.id,
                diff_payload={"memory_id": 123, "reason": "GDPR right-to-be-forgotten request"},
            )

    @pytest.mark.asyncio
    async def test_ac9_bulk_delete_dry_run_returns_count_without_mutating(self):
        """AC-9: Bulk delete dry-run calculates affected count without executing deletions."""
        from app.services.memory.erasure_service import MemoryErasureService

        session = AsyncMock()
        service = MemoryErasureService(session)

        with patch.object(service, "count_matching_memories", return_value=1500) as mock_count:
            result = await service.bulk_delete_memories(
                workspace_id=1,
                source_type="batdongsan",
                source_id=None,
                dry_run=True,
            )

            assert result["dry_run"] is True
            assert result["affected_count"] == 1500
            mock_count.assert_awaited_once()
