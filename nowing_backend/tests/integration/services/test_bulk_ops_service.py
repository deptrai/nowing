"""Unit and integration tests for bulk_ops_service (Story 29.4 / AD-54).

Covers:
- Allow-list filter builder and validation (operator validation, field validation).
- Idempotency hashing and key validation.
- Dry run preview with counts, samples, warnings, and missing dependency detection.
- Execute dispatch with job creation and idempotency caching.
- Replay and conflict detection on Idempotency-Key.
- Cancellation rules (QUEUED vs RUNNING vs TERMINAL).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bulk_ops import (
    BulkAction,
    BulkOpJob,
    BulkOpJobStatus,
)
from app.models.users import User
from app.models.workspaces import Workspace
from app.schemas.bulk_ops import FilterClause
from app.services.bulk_ops_service import (
    bulk_ops_service,
)

pytestmark = [pytest.mark.integration]


class TestBulkOpsServiceFilterValidation:
    """Test filter allow-list and operators validation."""

    def test_unknown_action_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            bulk_ops_service.validate_filters(
                "non_existent_action",  # type: ignore
                [FilterClause(field="created_at", op="gte", value="2026-01-01")],
            )
        assert exc_info.value.status_code == 422
        assert "Unknown bulk action" in exc_info.value.detail

    def test_disallowed_field_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            bulk_ops_service.validate_filters(
                BulkAction.ARCHIVE_INACTIVE_WORKSPACES,
                [FilterClause(field="password_hash", op="eq", value="secret")],
            )
        assert exc_info.value.status_code == 422
        assert "not allowed for action" in exc_info.value.detail

    def test_disallowed_operator_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            bulk_ops_service.validate_filters(
                BulkAction.ROTATE_API_KEYS,
                [FilterClause.model_construct(field="plan_tier", operator="invalid_op", value="free")],
            )
        assert exc_info.value.status_code == 422
        assert "Operator 'invalid_op' not allowed" in exc_info.value.detail

    def test_valid_filters_pass(self):
        clauses = [
            FilterClause(field="inactive_days", op="gte", value=30),
            FilterClause(field="plan_tier", op="eq", value="free"),
        ]
        validated = bulk_ops_service.validate_filters(
            BulkAction.ARCHIVE_INACTIVE_WORKSPACES, clauses
        )
        assert len(validated) == 2


class TestBulkOpsServiceComputeHash:
    """Test deterministic payload hashing for idempotency."""

    def test_hash_consistency_with_unordered_clauses(self):
        c1 = FilterClause(field="plan_tier", op="eq", value="free")
        c2 = FilterClause(field="inactive_days", op="gte", value=30)

        hash1 = bulk_ops_service.compute_request_hash(
            BulkAction.ARCHIVE_INACTIVE_WORKSPACES, [c1, c2], {}
        )
        hash2 = bulk_ops_service.compute_request_hash(
            BulkAction.ARCHIVE_INACTIVE_WORKSPACES, [c2, c1], {}
        )
        assert hash1 == hash2

    def test_hash_differs_on_params(self):
        c1 = FilterClause(field="plan_tier", op="eq", value="free")
        hash1 = bulk_ops_service.compute_request_hash(
            BulkAction.APPLY_TIER, [c1], {"target_tier": "pro"}
        )
        hash2 = bulk_ops_service.compute_request_hash(
            BulkAction.APPLY_TIER, [c1], {"target_tier": "enterprise"}
        )
        assert hash1 != hash2


@pytest.fixture
async def db_superuser(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"superuser-{uuid.uuid4().hex[:8]}@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


class TestBulkOpsServiceDryRun:
    """Test dry-run simulation logic."""

    async def test_dry_run_archive_inactive_workspaces(
        self,
        db_session: AsyncSession,
        db_superuser: User,
    ):
        # Create test workspaces
        ws1 = Workspace(
            name="Inactive WS 1",
            user_id=db_superuser.id,
            created_at=datetime.now(UTC) - timedelta(days=40),
        )
        ws2 = Workspace(
            name="Active WS 2",
            user_id=db_superuser.id,
            created_at=datetime.now(UTC) - timedelta(days=5),
        )
        db_session.add_all([ws1, ws2])
        await db_session.commit()

        res = await bulk_ops_service.dry_run(
            session=db_session,
            action=BulkAction.ARCHIVE_INACTIVE_WORKSPACES,
            filter_spec=[FilterClause(field="inactive_days", op="gte", value=30)],
            action_params={},
        )
        assert res.affected_count >= 1
        assert any(item.get("name") == "Inactive WS 1" for item in res.sample_affected)

    async def test_dry_run_active_workspace_safety_rejected_without_inactive_days(
        self,
        db_session: AsyncSession,
    ):
        # archive_inactive_workspaces without inactive_days should be rejected with 422
        with pytest.raises(HTTPException) as exc_info:
            await bulk_ops_service.dry_run(
                session=db_session,
                action=BulkAction.ARCHIVE_INACTIVE_WORKSPACES,
                filter_spec=[FilterClause(field="plan_tier", op="eq", value="free")],
                action_params={},
            )
        assert exc_info.value.status_code == 422
        assert "requires inactive_days > 0" in exc_info.value.detail

    async def test_dry_run_missing_dependency_assign_role(
        self,
        db_session: AsyncSession,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await bulk_ops_service.dry_run(
                session=db_session,
                action=BulkAction.ASSIGN_ROLE,
                filter_spec=[],
                action_params={"target_role_id": 999999},
                workspace_id=1,
            )
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail.get("error_code") == "missing_dependency"


class TestBulkOpsServiceExecuteAndIdempotency:
    """Test execute, Celery dispatch, and replay/collision handling."""

    async def test_execute_creates_job_and_dispatches_celery(
        self,
        db_session: AsyncSession,
        db_superuser: User,
    ):
        idempotency_key = str(uuid.uuid4())
        with patch("app.tasks.celery_tasks.bulk_op_tasks.bulk_op_executor.delay") as mock_delay:
            resp = await bulk_ops_service.execute(
                session=db_session,
                action=BulkAction.ARCHIVE_INACTIVE_WORKSPACES,
                filter_spec=[FilterClause(field="inactive_days", op="gte", value=30)],
                action_params={},
                actor=db_superuser,
                idempotency_key=idempotency_key,
            )
            assert resp.job_id is not None
            assert resp.status == BulkOpJobStatus.QUEUED.value
            mock_delay.assert_called_once_with(str(resp.job_id))

        # Second call with same key and payload should replay existing job
        with patch("app.tasks.celery_tasks.bulk_op_tasks.bulk_op_executor.delay") as mock_delay:
            replay_resp = await bulk_ops_service.execute(
                session=db_session,
                action=BulkAction.ARCHIVE_INACTIVE_WORKSPACES,
                filter_spec=[FilterClause(field="inactive_days", op="gte", value=30)],
                action_params={},
                actor=db_superuser,
                idempotency_key=idempotency_key,
            )
            assert replay_resp.job_id == resp.job_id
            mock_delay.assert_not_called()

    async def test_execute_idempotency_collision_raises_409(
        self,
        db_session: AsyncSession,
        db_superuser: User,
    ):
        idempotency_key = str(uuid.uuid4())
        with patch("app.tasks.celery_tasks.bulk_op_tasks.bulk_op_executor.delay"):
            await bulk_ops_service.execute(
                session=db_session,
                action=BulkAction.ARCHIVE_INACTIVE_WORKSPACES,
                filter_spec=[FilterClause(field="inactive_days", op="gte", value=30)],
                action_params={},
                actor=db_superuser,
                idempotency_key=idempotency_key,
            )

        # Call with same key but DIFFERENT action/params -> 409
        with pytest.raises(HTTPException) as exc_info:
            await bulk_ops_service.execute(
                session=db_session,
                action=BulkAction.ARCHIVE_INACTIVE_WORKSPACES,
                filter_spec=[FilterClause(field="inactive_days", op="gte", value=60)],
                action_params={},
                actor=db_superuser,
                idempotency_key=idempotency_key,
            )
        assert exc_info.value.status_code == 409
        detail = exc_info.value.detail
        if isinstance(detail, dict):
            assert detail.get("error_code") == "idempotency_conflict"
        else:
            assert "Idempotency" in str(detail)


class TestBulkOpsServiceCancellation:
    """Test job cancellation constraints."""

    async def test_cancel_queued_job(
        self,
        db_session: AsyncSession,
        db_superuser: User,
    ):
        job = BulkOpJob(
            actor_id=db_superuser.id,
            action=BulkAction.ARCHIVE_INACTIVE_WORKSPACES.value,
            status=BulkOpJobStatus.QUEUED.value,
            idempotency_key="job-cancel-test-1",
            request_hash="hash-cancel-1",
        )
        db_session.add(job)
        await db_session.commit()

        resp = await bulk_ops_service.cancel_job(
            session=db_session,
            job_id=job.id,
            actor=db_superuser,
        )
        assert resp.status == BulkOpJobStatus.CANCELLED.value

    async def test_cancel_running_non_cancelable_raises_409(
        self,
        db_session: AsyncSession,
        db_superuser: User,
    ):
        job = BulkOpJob(
            actor_id=db_superuser.id,
            action=BulkAction.ROTATE_API_KEYS.value,  # not cancelable while running
            status=BulkOpJobStatus.RUNNING.value,
            idempotency_key="job-cancel-test-2",
            request_hash="hash-cancel-2",
        )
        db_session.add(job)
        await db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            await bulk_ops_service.cancel_job(
                session=db_session,
                job_id=job.id,
                actor=db_superuser,
            )
        assert exc_info.value.status_code == 409
        assert "cannot be cancelled" in exc_info.value.detail
