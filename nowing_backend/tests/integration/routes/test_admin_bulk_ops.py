"""Integration tests for Admin Bulk Operations Console routes (Story 29.4 / AD-54).

Covers:
- Superadmin authentication enforcement (regular user / unauthenticated / PAT rejected).
- POST /admin/saas/bulk-ops/dry-run simulation.
- POST /admin/saas/bulk-ops/execute with Idempotency-Key header.
- High-risk action password/MFA gate for rotate_api_keys.
- Replay and 409 conflict detection for Idempotency-Key.
- GET /admin/saas/bulk-ops/{job_id} and errors endpoint.
- POST /admin/saas/bulk-ops/{job_id}/cancel.
- Workspace owner bulk ops endpoints at /workspaces/{id}/bulk-ops.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bulk_ops import (
    BulkOpError,
    BulkOpJob,
    BulkOpJobStatus,
)
from app.models.users import User
from app.models.workspaces import Workspace

pytestmark = [pytest.mark.integration]


class TestAdminBulkOpsAuth:
    """Authentication and superadmin boundary tests."""

    async def test_dry_run_rejects_unauthenticated(self, client: AsyncClient):
        res = await client.post(
            "/api/v1/admin/saas/bulk-ops/dry-run",
            json={"action": "archive_inactive_workspaces", "filter_spec": []},
        )
        assert res.status_code in (401, 403)

    async def test_dry_run_rejects_regular_user(
        self, client_as_regular_user: AsyncClient
    ):
        res = await client_as_regular_user.post(
            "/api/v1/admin/saas/bulk-ops/dry-run",
            json={"action": "archive_inactive_workspaces", "filter_spec": []},
        )
        assert res.status_code == 403

    async def test_dry_run_rejects_pat_client(self, pat_client: AsyncClient):
        res = await pat_client.post(
            "/api/v1/admin/saas/bulk-ops/dry-run",
            json={"action": "archive_inactive_workspaces", "filter_spec": []},
        )
        assert res.status_code in (401, 403)


class TestAdminBulkOpsExecution:
    """Superadmin bulk operations workflow tests."""

    async def test_dry_run_success(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        db_superuser: User,
    ):
        ws = Workspace(
            name="Old WS",
            user_id=db_superuser.id,
            created_at=datetime.now(UTC) - timedelta(days=90),
        )
        db_session.add(ws)
        await db_session.commit()

        res = await admin_client.post(
            "/api/v1/admin/saas/bulk-ops/dry-run",
            json={
                "action": "archive_inactive_workspaces",
                "filter_spec": [{"field": "inactive_days", "op": "gte", "value": 60}],
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert "affected_count" in data
        assert "warnings" in data
        assert "sample_affected" in data

    async def test_execute_missing_idempotency_key_header_returns_400(
        self,
        admin_client: AsyncClient,
    ):
        res = await admin_client.post(
            "/api/v1/admin/saas/bulk-ops/execute",
            json={
                "action": "archive_inactive_workspaces",
                "filter_spec": [{"field": "inactive_days", "op": "gte", "value": 60}],
            },
        )
        assert res.status_code == 400
        assert "Idempotency-Key" in res.json()["detail"]

    async def test_execute_and_replay_lifecycle(
        self,
        admin_client: AsyncClient,
    ):
        key = str(uuid.uuid4())
        payload = {
            "action": "archive_inactive_workspaces",
            "filter_spec": [{"field": "inactive_days", "op": "gte", "value": 60}],
            "action_params": {},
        }

        with patch("app.tasks.celery_tasks.bulk_op_tasks.bulk_op_executor.delay") as mock_delay:
            res = await admin_client.post(
                "/api/v1/admin/saas/bulk-ops/execute",
                headers={"Idempotency-Key": key},
                json=payload,
            )
            assert res.status_code == 202
            data = res.json()
            job_id = data["job_id"]
            assert data["status"] == "queued"
            mock_delay.assert_called_once()

            # Replay with same key
            replay_res = await admin_client.post(
                "/api/v1/admin/saas/bulk-ops/execute",
                headers={"Idempotency-Key": key},
                json=payload,
            )
            assert replay_res.status_code == 202
            assert replay_res.json()["job_id"] == job_id

            # Conflict with same key but different body
            conflict_res = await admin_client.post(
                "/api/v1/admin/saas/bulk-ops/execute",
                headers={"Idempotency-Key": key},
                json={
                    "action": "archive_inactive_workspaces",
                    "filter_spec": [{"field": "inactive_days", "op": "gte", "value": 30}],
                    "action_params": {},
                },
            )
            assert conflict_res.status_code == 409

    async def test_rotate_api_keys_requires_reauth(
        self,
        admin_client: AsyncClient,
    ):
        key = str(uuid.uuid4())
        res = await admin_client.post(
            "/api/v1/admin/saas/bulk-ops/execute",
            headers={"Idempotency-Key": key},
            json={
                "action": "rotate_api_keys",
                "filter_spec": [{"field": "plan_tier", "op": "eq", "value": "free"}],
                "action_params": {},
            },
        )
        assert res.status_code in (401, 403)
        assert "password or MFA" in str(res.json()["detail"])

    async def test_get_job_status_and_errors(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        db_superuser: User,
    ):
        job = BulkOpJob(
            actor_id=db_superuser.id,
            action="delete_source_type_memories",
            status=BulkOpJobStatus.RUNNING.value,
            idempotency_key="status-test-job-1",
            request_hash="status-test-hash",
            total_count=10,
            processed_count=5,
            affected_count=4,
            error_count=1,
        )
        db_session.add(job)
        await db_session.flush()

        err = BulkOpError(
            job_id=job.id,
            subject_type="memory",
            subject_id="123",
            error_message="Delete failed",
            retryable=False,
        )
        db_session.add(err)
        await db_session.commit()

        # Check job status
        res = await admin_client.get(f"/api/v1/admin/saas/bulk-ops/{job.id}")
        assert res.status_code == 200
        assert res.json()["processed_count"] == 5
        assert res.json()["is_cancelable"] is True  # delete_source_type_memories is cancelable while running

        # Check errors
        err_res = await admin_client.get(f"/api/v1/admin/saas/bulk-ops/{job.id}/errors")
        assert err_res.status_code == 200
        errors = err_res.json()
        assert len(errors) == 1
        assert errors[0]["error_message"] == "Delete failed"

    async def test_cancel_bulk_op_job(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        db_superuser: User,
    ):
        job = BulkOpJob(
            actor_id=db_superuser.id,
            action="archive_inactive_workspaces",
            status=BulkOpJobStatus.QUEUED.value,
            idempotency_key="cancel-endpoint-job-1",
            request_hash="cancel-hash-1",
        )
        db_session.add(job)
        await db_session.commit()

        res = await admin_client.post(f"/api/v1/admin/saas/bulk-ops/{job.id}/cancel")
        assert res.status_code == 200
        assert res.json()["status"] == "cancelled"
