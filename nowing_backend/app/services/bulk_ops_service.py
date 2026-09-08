"""Core bulk operations service (Story 29.4 / AD-54).

Provides:
- Allow-list structured filter validation per BulkAction
- Parameterized SQLAlchemy query building (no raw SQL injection)
- Dry-run simulation with counts, sample subjects, warnings, and conflicts
- Client-provided Idempotency-Key guard with SHA-256 hash matching and 24h TTL
- Asynchronous Celery dispatch and job status retrieval
- Job cancellation with action-specific cancelable rule
- Granular per-subject and summary AuditEvents
- High-risk re-authentication checks (password/MFA)
- Dependency validation for Story 29.1 and Story 29.3
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import MemorySourceType
from app.models.bulk_ops import (
    BulkAction,
    BulkOpError,
    BulkOpJob,
    BulkOpJobStatus,
    IdempotencyKey,
)
from app.models.memory import Memory
from app.models.users import User, WorkspaceMembership, WorkspaceRole
from app.models.workspaces import Workspace
from app.schemas.bulk_ops import (
    BulkOpErrorRead,
    CancelJobResponse,
    DryRunResponse,
    ExecuteResponse,
    FilterClause,
    JobStatusResponse,
)

logger = logging.getLogger(__name__)

# Allowed filter fields per BulkAction
ALLOWED_FILTERS: dict[BulkAction, set[str]] = {
    BulkAction.ARCHIVE_INACTIVE_WORKSPACES: {
        "inactive_days",
        "is_active",
        "plan_tier",
        "workspace_id",
        "id",
    },
    BulkAction.ROTATE_API_KEYS: {
        "workspace_id",
        "id",
        "plan_tier",
        "api_access_enabled",
    },
    BulkAction.ASSIGN_ROLE: {
        "workspace_id",
        "role_id",
        "user_id",
        "is_owner",
    },
    BulkAction.DELETE_SOURCE_TYPE_MEMORIES: {
        "workspace_id",
        "source_type",
        "source_id",
        "source_entity_type",
        "created_before",
        "created_after",
        "memory_type",
    },
    BulkAction.APPLY_TIER: {
        "workspace_id",
        "id",
        "plan_tier",
        "is_active",
    },
    BulkAction.REVOKE_MEMBERSHIP: {
        "workspace_id",
        "role_id",
        "user_id",
        "is_owner",
    },
}

ALLOWED_OPERATORS = {"eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in"}

CANCELABLE_WHILE_RUNNING = {
    BulkAction.ARCHIVE_INACTIVE_WORKSPACES.value,
    BulkAction.DELETE_SOURCE_TYPE_MEMORIES.value,
    BulkAction.REVOKE_MEMBERSHIP.value,
}

OWNER_ALLOWED_ACTIONS = {
    BulkAction.DELETE_SOURCE_TYPE_MEMORIES,
    BulkAction.ASSIGN_ROLE,
    BulkAction.REVOKE_MEMBERSHIP,
}


class BulkOpsService:
    """Service handling bulk administrative and tenant operations."""

    @staticmethod
    def compute_request_hash(
        action: BulkAction,
        filter_spec: list[FilterClause] | list[dict[str, Any]],
        action_params: dict[str, Any],
        workspace_id: int | None = None,
    ) -> str:
        """Deterministically computes SHA-256 hash of the request payload."""
        normalized_filters: list[dict[str, Any]] = []
        for clause in filter_spec:
            if isinstance(clause, FilterClause):
                normalized_filters.append(clause.model_dump())
            else:
                normalized_filters.append(dict(clause))

        payload = {
            "action": action.value if isinstance(action, BulkAction) else str(action),
            "filter_spec": sorted(normalized_filters, key=lambda x: (x.get("field", ""), str(x.get("value")))),
            "action_params": action_params,
            "workspace_id": workspace_id,
        }
        encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def validate_filter(
        self,
        action: BulkAction | str,
        filter_spec: list[FilterClause],
        workspace_id: int | None = None,
    ) -> list[FilterClause]:
        """Validate filter clauses against allow-list and rules."""
        if not isinstance(action, BulkAction):
            try:
                action = BulkAction(action)
            except (ValueError, KeyError):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Unknown bulk action: {action}",
                ) from None

        if action not in ALLOWED_FILTERS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unsupported bulk action: {action}",
            )

        allowed_fields = ALLOWED_FILTERS[action]
        validated_clauses: list[FilterClause] = []

        inactive_days_val: int | None = None
        is_active_val: bool | None = None

        has_workspace_id_filter = False

        for clause in filter_spec:
            if clause.field not in allowed_fields:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Field '{clause.field}' is not allowed for action '{action.value}'",
                )
            if clause.operator not in ALLOWED_OPERATORS:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Operator '{clause.operator}' not allowed for field '{clause.field}'",
                )

            if clause.field == "inactive_days":
                try:
                    val = int(clause.value)
                    if val < 0:
                        raise ValueError
                    inactive_days_val = val
                except (ValueError, TypeError):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Filter 'inactive_days' must be a non-negative integer",
                    ) from None

            elif clause.field in ("created_before", "created_after"):
                if clause.field == "created_before" and clause.operator not in ("lt", "lte"):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Filter 'created_before' requires operator 'lt' or 'lte'",
                    )
                if clause.field == "created_after" and clause.operator not in ("gt", "gte"):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Filter 'created_after' requires operator 'gt' or 'gte'",
                    )

            elif clause.field == "is_active":
                if not isinstance(clause.value, bool):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Filter 'is_active' must be a boolean",
                    )
                is_active_val = clause.value

            elif clause.field == "source_type":
                valid_sources = {st.value for st in MemorySourceType}
                if clause.operator in ("in", "not_in"):
                    if not isinstance(clause.value, list) or not all(v in valid_sources for v in clause.value):
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Invalid source_type value: must be in {valid_sources}",
                        )
                else:
                    if clause.value not in valid_sources:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Invalid source_type '{clause.value}'. Allowed: {valid_sources}",
                        )

            elif clause.field == "workspace_id":
                has_workspace_id_filter = True
                if workspace_id is not None and clause.value != workspace_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Cannot operate outside own workspace",
                    )

            validated_clauses.append(clause)

        # Invariant check for archive_inactive_workspaces:
        # Cannot archive active workspaces unless inactive_days > 0
        if action == BulkAction.ARCHIVE_INACTIVE_WORKSPACES:
            # If is_active is explicitly True, or not specified (which would include active workspaces)
            targeting_active = is_active_val is not False
            if targeting_active and (inactive_days_val is None or inactive_days_val <= 0):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="archive_inactive_workspaces requires inactive_days > 0 when targeting active workspaces",
                )

        # Force workspace_id injection for owner scope
        if workspace_id is not None and not has_workspace_id_filter:
            validated_clauses.append(
                FilterClause(field="workspace_id", operator="eq", value=workspace_id)
            )

        return validated_clauses

    def _build_filter_conditions(
        self,
        model: Any,
        filter_spec: list[FilterClause],
    ) -> list[Any]:
        """Builds parameterized SQLAlchemy binary expressions for model from filter_spec."""
        conditions: list[Any] = []

        for clause in filter_spec:
            field_name = clause.field
            op = clause.operator
            val = clause.value

            # Special field translation
            if field_name == "inactive_days":
                cutoff = datetime.now(UTC) - timedelta(days=int(val))
                if op in ("gt", "gte", "eq"):
                    conditions.append(model.created_at <= cutoff)
                elif op in ("lt", "lte"):
                    conditions.append(model.created_at >= cutoff)
                continue

            if field_name == "is_active" and model is Workspace:
                if op == "eq":
                    if val is True:
                        conditions.append(model.archived_at.is_(None))
                    else:
                        conditions.append(model.archived_at.is_not(None))
                elif op == "neq":
                    if val is True:
                        conditions.append(model.archived_at.is_not(None))
                    else:
                        conditions.append(model.archived_at.is_(None))
                continue

            if field_name == "id" and model is Workspace:
                col = model.id
            elif (field_name == "created_before" and model is Memory) or (field_name == "created_after" and model is Memory):
                col = model.created_at
                val = datetime.fromisoformat(val) if isinstance(val, str) else val
            elif hasattr(model, field_name):
                col = getattr(model, field_name)
            else:
                continue

            if op == "eq":
                conditions.append(col == val)
            elif op == "neq":
                conditions.append(col != val)
            elif op == "gt":
                conditions.append(col > val)
            elif op == "gte":
                conditions.append(col >= val)
            elif op == "lt":
                conditions.append(col < val)
            elif op == "lte":
                conditions.append(col <= val)
            elif op == "in":
                conditions.append(col.in_(val if isinstance(val, list) else [val]))
            elif op == "not_in":
                conditions.append(col.not_in(val if isinstance(val, list) else [val]))

        return conditions

    def build_query(
        self,
        action: BulkAction,
        filter_spec: list[FilterClause],
    ) -> tuple[Any, Any, Any]:
        """Constructs (select_query, count_query, target_model)."""
        if action in (
            BulkAction.ARCHIVE_INACTIVE_WORKSPACES,
            BulkAction.ROTATE_API_KEYS,
            BulkAction.APPLY_TIER,
        ):
            target_model = Workspace
        elif action in (BulkAction.ASSIGN_ROLE, BulkAction.REVOKE_MEMBERSHIP):
            target_model = WorkspaceMembership
        elif action == BulkAction.DELETE_SOURCE_TYPE_MEMORIES:
            target_model = Memory
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unsupported action: {action}",
            )

        conditions = self._build_filter_conditions(target_model, filter_spec)

        # Baseline safeguards per action
        if action == BulkAction.ASSIGN_ROLE or action == BulkAction.REVOKE_MEMBERSHIP:
            # Cannot mutate or revoke workspace owner memberships
            conditions.append(WorkspaceMembership.is_owner.is_(False))

        if action == BulkAction.ARCHIVE_INACTIVE_WORKSPACES:
            # Don't archive workspaces that are already archived
            conditions.append(Workspace.archived_at.is_(None))

        select_stmt = select(target_model).where(*conditions)
        count_stmt = select(func.count()).select_from(target_model).where(*conditions)

        return select_stmt, count_stmt, target_model

    async def dry_run(
        self,
        session: AsyncSession,
        action: BulkAction,
        filter_spec: list[FilterClause],
        action_params: dict[str, Any],
        workspace_id: int | None = None,
    ) -> DryRunResponse:
        """Simulate bulk operation and return previews, warnings, and conflicts."""
        validated_filter = self.validate_filter(action, filter_spec, workspace_id)

        # Dependency validation
        if action == BulkAction.ASSIGN_ROLE:
            target_role_id = action_params.get("target_role_id")
            if not target_role_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="action_params must specify 'target_role_id' for assign_role",
                )
            role = await session.get(WorkspaceRole, target_role_id)
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error_code": "missing_dependency",
                        "message": f"Target role with ID {target_role_id} not found in role catalog",
                    },
                )
            # Prevent cross-tenant role assignment: the target role must belong
            # to the same workspace or be a system role.
            if workspace_id is not None and role.workspace_id is not None and role.workspace_id != workspace_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error_code": "cross_tenant_role",
                        "message": "Cannot assign a role that belongs to a different workspace",
                    },
                )

        if action == BulkAction.APPLY_TIER:
            target_tier = action_params.get("target_tier")
            if not target_tier:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="action_params must specify 'target_tier' for apply_tier",
                )
            from app.services.workspace_limits import workspace_limit_service
            if not workspace_limit_service:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error_code": "missing_dependency",
                        "message": "Subscription management service (Story 29.3) is not available",
                    },
                )

        select_stmt, count_stmt, _target_model = self.build_query(action, validated_filter)

        # Count total
        count_res = await session.execute(count_stmt)
        total_count = count_res.scalar_one()

        # Sample up to 10 subjects
        sample_stmt = select_stmt.limit(10)
        sample_res = await session.execute(sample_stmt)
        rows = sample_res.scalars().all()

        sample_subjects: list[dict[str, Any]] = []
        warnings: list[str] = []
        conflicts: list[dict[str, Any]] = []

        if action in (
            BulkAction.ARCHIVE_INACTIVE_WORKSPACES,
            BulkAction.ROTATE_API_KEYS,
            BulkAction.APPLY_TIER,
        ):
            for ws in rows:
                sample_subjects.append({
                    "id": ws.id,
                    "name": ws.name,
                    "plan_tier": ws.plan_tier,
                    "api_access_enabled": ws.api_access_enabled,
                    "created_at": ws.created_at.isoformat() if ws.created_at else None,
                    "archived_at": ws.archived_at.isoformat() if ws.archived_at else None,
                })
        elif action in (BulkAction.ASSIGN_ROLE, BulkAction.REVOKE_MEMBERSHIP):
            for m in rows:
                sample_subjects.append({
                    "id": m.id,
                    "user_id": str(m.user_id),
                    "workspace_id": m.workspace_id,
                    "role_id": m.role_id,
                    "is_owner": m.is_owner,
                })
        elif action == BulkAction.DELETE_SOURCE_TYPE_MEMORIES:
            for mem in rows:
                sample_subjects.append({
                    "id": mem.id,
                    "workspace_id": mem.workspace_id,
                    "source_type": mem.source_type.value if hasattr(mem.source_type, "value") else str(mem.source_type),
                    "memory_type": mem.type.value if hasattr(mem.type, "value") else str(mem.type),
                    "created_at": mem.created_at.isoformat() if mem.created_at else None,
                })

        # Warnings and conflict analysis
        if action == BulkAction.ROTATE_API_KEYS:
            warnings.append("High-risk operation: Requires password/MFA confirmation before execution.")

        if action == BulkAction.DELETE_SOURCE_TYPE_MEMORIES:
            warnings.append(
                f"Permanent deletion: {total_count} research memories matching the filter will be purged."
            )

        if action == BulkAction.ARCHIVE_INACTIVE_WORKSPACES:
            warnings.append(f"{total_count} workspaces will be marked archived and deactivated.")

        if action == BulkAction.APPLY_TIER:
            from app.services.workspace_limits import workspace_limit_service

            target_tier = action_params.get("target_tier", "")
            for ws in rows:
                quota_conflicts = await workspace_limit_service.check_plan_change_conflicts(
                    session, ws.id, target_tier
                )
                if quota_conflicts:
                    conflicts.append({
                        "workspace_id": ws.id,
                        "workspace_name": ws.name,
                        "conflicts": quota_conflicts,
                    })

        return DryRunResponse(
            action=action,
            total_count=total_count,
            sample_subjects=sample_subjects,
            warnings=warnings,
            conflicts=conflicts,
            can_execute=len(conflicts) == 0,
        )

    async def execute(
        self,
        session: AsyncSession,
        action: BulkAction,
        filter_spec: list[FilterClause],
        action_params: dict[str, Any],
        actor: User,
        workspace_id: int | None = None,
        idempotency_key: str | None = None,
        password: str | None = None,
        mfa_token: str | None = None,
        user_manager: Any = None,
    ) -> ExecuteResponse:
        """Queue a bulk operation job with idempotency and safety guards."""
        if not idempotency_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Header 'Idempotency-Key' is required for bulk operation execution",
            )

        if len(idempotency_key) > 64:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Idempotency-Key must not exceed 64 characters",
            )

        validated_filter = self.validate_filter(action, filter_spec, workspace_id)
        request_hash = self.compute_request_hash(
            action, validated_filter, action_params, workspace_id
        )

        # High-risk re-auth check for rotate_api_keys
        if action == BulkAction.ROTATE_API_KEYS:
            if not password and not mfa_token:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error_code": "reauth_required",
                        "message": "Action rotate_api_keys is high-risk and requires password or MFA confirmation",
                    },
                )
            if password:
                # Verify password
                verified = False
                if user_manager and hasattr(user_manager, "password_helper"):
                    verified, _ = user_manager.password_helper.verify_and_update(
                        password, actor.hashed_password
                    )
                else:
                    from fastapi_users.password import PasswordHelper
                    verified, _ = PasswordHelper().verify_and_update(
                        password, actor.hashed_password
                    )
                if not verified:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={
                            "error_code": "invalid_credentials",
                            "message": "Password confirmation failed",
                        },
                    )
            elif mfa_token:
                # v1: MFA is not yet implemented. Require password confirmation instead.
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error_code": "reauth_required",
                        "message": "Password confirmation is required for high-risk actions. MFA is not enabled in this release.",
                    },
                )

        # Dependency check for 29.1 and 29.3
        if action == BulkAction.ASSIGN_ROLE:
            target_role_id = action_params.get("target_role_id")
            if not target_role_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="action_params must specify 'target_role_id' for assign_role",
                )
            role = await session.get(WorkspaceRole, target_role_id)
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error_code": "missing_dependency",
                        "message": f"Target role with ID {target_role_id} not found in role catalog",
                    },
                )
            # Prevent cross-tenant role assignment: the target role must belong
            # to the same workspace or be a system role.
            if workspace_id is not None and role.workspace_id is not None and role.workspace_id != workspace_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error_code": "cross_tenant_role",
                        "message": "Cannot assign a role that belongs to a different workspace",
                    },
                )

        if action == BulkAction.APPLY_TIER:
            target_tier = action_params.get("target_tier")
            if not target_tier:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="action_params must specify 'target_tier' for apply_tier",
                )
            from app.services.workspace_limits import workspace_limit_service
            if not workspace_limit_service:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error_code": "missing_dependency",
                        "message": "Subscription management service (Story 29.3) is not available",
                    },
                )

        # Idempotency key lookup
        now = datetime.now(UTC)
        idemp_stmt = select(IdempotencyKey).where(IdempotencyKey.key == idempotency_key)
        idemp_res = await session.execute(idemp_stmt)
        existing_key = idemp_res.scalars().first()

        if existing_key:
            if existing_key.expires_at > now:
                if existing_key.request_hash == request_hash:
                    # Return existing job
                    job = await session.get(BulkOpJob, existing_key.job_id)
                    if job:
                        return ExecuteResponse(
                            job_id=job.id,
                            status=job.status,
                            action=BulkAction(job.action),
                            message="Idempotent request returning existing job",
                        )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={
                            "error_code": "idempotency_conflict",
                            "message": "Idempotency-Key reuse with different request body",
                        },
                    )
            else:
                # Key expired, delete old key record
                await session.delete(existing_key)
                await session.flush()

        # Count total subjects
        _, count_stmt, _ = self.build_query(action, validated_filter)
        count_res = await session.execute(count_stmt)
        total_count = count_res.scalar_one()

        # Create new job
        job = BulkOpJob(
            id=uuid.uuid4(),
            action=action.value,
            status=BulkOpJobStatus.QUEUED.value,
            actor_id=actor.id,
            workspace_id=workspace_id,
            filter_spec=[c.model_dump() for c in validated_filter],
            action_params=action_params,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            total_count=total_count,
            processed_count=0,
            affected_count=0,
            error_count=0,
        )
        session.add(job)
        await session.flush()

        # Record idempotency key with 24-hour TTL.
        # If a concurrent request with the same key wins the race, the DB
        # unique constraint will surface IntegrityError; we translate it to
        # 409 so the caller knows the key was already claimed.
        idemp_record = IdempotencyKey(
            key=idempotency_key,
            request_hash=request_hash,
            job_id=job.id,
            actor_id=actor.id,
            expires_at=now + timedelta(hours=24),
        )
        session.add(idemp_record)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error_code": "idempotency_conflict",
                    "message": "Idempotency-Key was already used by a concurrent request",
                },
            ) from None
        await session.refresh(job)

        # Dispatch Celery background task
        try:
            from app.tasks.celery_tasks.bulk_op_tasks import bulk_op_executor

            task = bulk_op_executor.delay(str(job.id))
            job.celery_task_id = str(task.id) if task and hasattr(task, "id") else None
            await session.commit()
        except Exception as e:
            logger.warning(
                "Celery dispatch failed or skipped (e.g. broker offline): %s", e
            )

        return ExecuteResponse(
            job_id=job.id,
            status=job.status,
            action=action,
            message="Job queued successfully",
        )

    async def get_job(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
        actor: User,
        workspace_id: int | None = None,
    ) -> JobStatusResponse:
        """Fetch job progress and state with scope authorization."""
        job = await session.get(BulkOpJob, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bulk operation job not found",
            )

        # Scope authorization: Superadmin or matching workspace/actor
        if not actor.is_superuser:
            if workspace_id is not None:
                if job.workspace_id != workspace_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Not authorized to access bulk job for this workspace",
                    )
            elif job.actor_id != actor.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to access this bulk job",
                )

        # Cancelable calculation:
        # Queued: always cancelable
        # Running: only cancelable for ARCHIVE_INACTIVE_WORKSPACES, DELETE_SOURCE_TYPE_MEMORIES, REVOKE_MEMBERSHIP
        is_cancelable = False
        if job.status == BulkOpJobStatus.QUEUED.value or (
            job.status == BulkOpJobStatus.RUNNING.value
            and job.action in CANCELABLE_WHILE_RUNNING
        ):
            is_cancelable = True

        resp = JobStatusResponse.model_validate(job)
        resp.cancelable = is_cancelable
        return resp

    async def cancel_job(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
        actor: User,
        workspace_id: int | None = None,
    ) -> CancelJobResponse:
        """Cancel a queued or running bulk operation job."""
        job = await session.get(BulkOpJob, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bulk operation job not found",
            )

        # Authorization check
        if not actor.is_superuser:
            if workspace_id is not None and job.workspace_id != workspace_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to cancel this job",
                )
            if job.actor_id != actor.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to cancel this job",
                )

        if job.status in (
            BulkOpJobStatus.COMPLETED.value,
            BulkOpJobStatus.FAILED.value,
            BulkOpJobStatus.CANCELLED.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot cancel job with status '{job.status}'",
            )

        if (
            job.status == BulkOpJobStatus.RUNNING.value
            and job.action not in CANCELABLE_WHILE_RUNNING
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Action '{job.action}' cannot be cancelled once running",
            )

        job.status = BulkOpJobStatus.CANCELLED.value
        job.completed_at = datetime.now(UTC)

        # Revoke Celery task if possible
        # Note: we intentionally do NOT send terminate=True to the worker.
        # The Celery task loop polls job.status and exits cooperatively.

        await session.commit()
        return CancelJobResponse(
            job_id=job.id,
            status=job.status,
            message="Job cancelled successfully",
        )

    async def get_job_errors(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
        actor: User,
        workspace_id: int | None = None,
    ) -> list[BulkOpErrorRead]:
        """Fetch subject-level execution errors for a bulk job."""
        job = await session.get(BulkOpJob, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bulk operation job not found",
            )

        if not actor.is_superuser:
            if workspace_id is not None and job.workspace_id != workspace_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view errors for this job",
                )
            if job.actor_id != actor.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view errors for this job",
                )

        stmt = (
            select(BulkOpError)
            .where(BulkOpError.job_id == job_id)
            .order_by(BulkOpError.id.asc())
        )
        res = await session.execute(stmt)
        errors = res.scalars().all()
        return [BulkOpErrorRead.model_validate(err) for err in errors]

    validate_filters = validate_filter


bulk_ops_service = BulkOpsService()
