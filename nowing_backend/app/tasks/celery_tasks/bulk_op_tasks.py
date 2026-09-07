"""Celery tasks for executing bulk operations (Story 29.4 / AD-54).

Provides:
- bulk_op_executor: Batch-processes entities (batch size = 100) with error recording and audit logging.
- cleanup_expired_idempotency_keys: Prunes expired idempotency key records periodically.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select

from app.celery_app import celery_app
from app.models.billing import AuditEvent
from app.models.bulk_ops import (
    BulkAction,
    BulkOpError,
    BulkOpJob,
    BulkOpJobStatus,
    IdempotencyKey,
)
from app.models.users import PersonalAccessToken, WorkspaceMembership
from app.models.workspaces import Workspace
from app.schemas.bulk_ops import FilterClause
from app.services.bulk_ops_service import bulk_ops_service
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task
from app.utils.pat import generate_pat, hash_pat, token_prefix

logger = logging.getLogger(__name__)

BATCH_SIZE = 100


async def _execute_bulk_op(job_id_str: str) -> None:
    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        job_uuid = uuid.UUID(job_id_str)
        job = await session.get(BulkOpJob, job_uuid)
        if not job:
            logger.error("BulkOpJob %s not found", job_id_str)
            return

        if job.status == BulkOpJobStatus.CANCELLED.value:
            logger.info("BulkOpJob %s is already cancelled", job_id_str)
            return

        job.status = BulkOpJobStatus.RUNNING.value
        job.started_at = datetime.now(UTC)
        await session.commit()

        action = BulkAction(job.action)
        filter_spec = [FilterClause(**c) for c in (job.filter_spec or [])]
        action_params = job.action_params or {}

        _, _, target_model = bulk_ops_service.build_query(action, filter_spec)

        processed = 0
        affected = 0
        errors_count = 0
        last_id = 0

        while True:
            # Check for cancellation between batches
            await session.refresh(job)
            if job.status == BulkOpJobStatus.CANCELLED.value:
                logger.info("BulkOpJob %s was cancelled during batch execution", job_id_str)
                break

            # Build fresh conditions with ID cursor
            conditions = bulk_ops_service._build_filter_conditions(target_model, filter_spec)
            if action in (BulkAction.ASSIGN_ROLE, BulkAction.REVOKE_MEMBERSHIP):
                conditions.append(WorkspaceMembership.is_owner.is_(False))
            if action == BulkAction.ARCHIVE_INACTIVE_WORKSPACES:
                conditions.append(Workspace.archived_at.is_(None))

            conditions.append(target_model.id > last_id)

            batch_stmt = (
                select(target_model)
                .where(*conditions)
                .order_by(target_model.id.asc())
                .limit(BATCH_SIZE)
            )
            res = await session.execute(batch_stmt)
            batch = res.scalars().all()

            if not batch:
                break

            for item in batch:
                last_id = max(last_id, item.id)
                processed += 1
                try:
                    if action == BulkAction.ARCHIVE_INACTIVE_WORKSPACES:
                        item.archived_at = datetime.now(UTC)
                        affected += 1
                        session.add(
                            AuditEvent(
                                action="bulk_op.archive_inactive_workspaces.workspace",
                                actor_id=job.actor_id,
                                subject_id=None,
                                ticket_ref=job.idempotency_key,
                                diff_payload={
                                    "workspace_id": item.id,
                                    "name": item.name,
                                    "archived_at": item.archived_at.isoformat(),
                                },
                            )
                        )

                    elif action == BulkAction.ROTATE_API_KEYS:
                        # Rotate PATs belonging to this workspace
                        pats_stmt = select(PersonalAccessToken).where(
                            PersonalAccessToken.workspace_id == item.id
                        )
                        pats_res = await session.execute(pats_stmt)
                        pats = pats_res.scalars().all()
                        rotated_count = 0
                        for pat in pats:
                            new_token = generate_pat()
                            pat.token_hash = hash_pat(new_token)
                            pat.token_prefix = token_prefix(new_token)
                            rotated_count += 1

                        affected += 1
                        session.add(
                            AuditEvent(
                                action="bulk_op.rotate_api_keys.workspace",
                                actor_id=job.actor_id,
                                subject_id=None,
                                ticket_ref=job.idempotency_key,
                                diff_payload={
                                    "workspace_id": item.id,
                                    "rotated_tokens_count": rotated_count,
                                },
                            )
                        )

                    elif action == BulkAction.ASSIGN_ROLE:
                        target_role_id = action_params["target_role_id"]
                        old_role_id = item.role_id
                        item.role_id = target_role_id
                        affected += 1
                        session.add(
                            AuditEvent(
                                action="bulk_op.assign_role.membership",
                                actor_id=job.actor_id,
                                subject_id=item.user_id,
                                ticket_ref=job.idempotency_key,
                                diff_payload={
                                    "workspace_id": item.workspace_id,
                                    "user_id": str(item.user_id),
                                    "old_role_id": old_role_id,
                                    "new_role_id": target_role_id,
                                },
                            )
                        )

                    elif action == BulkAction.REVOKE_MEMBERSHIP:
                        user_id = item.user_id
                        ws_id = item.workspace_id
                        await session.delete(item)
                        affected += 1
                        session.add(
                            AuditEvent(
                                action="bulk_op.revoke_membership.membership",
                                actor_id=job.actor_id,
                                subject_id=user_id,
                                ticket_ref=job.idempotency_key,
                                diff_payload={
                                    "workspace_id": ws_id,
                                    "user_id": str(user_id),
                                },
                            )
                        )

                    elif action == BulkAction.DELETE_SOURCE_TYPE_MEMORIES:
                        mem_id = item.id
                        ws_id = item.workspace_id
                        st = (
                            item.source_type.value
                            if hasattr(item.source_type, "value")
                            else str(item.source_type)
                        )
                        await session.delete(item)
                        affected += 1
                        session.add(
                            AuditEvent(
                                action="bulk_op.delete_source_type_memories.memory",
                                actor_id=job.actor_id,
                                subject_id=None,
                                ticket_ref=job.idempotency_key,
                                diff_payload={
                                    "workspace_id": ws_id,
                                    "memory_id": mem_id,
                                    "source_type": st,
                                },
                            )
                        )

                    elif action == BulkAction.APPLY_TIER:
                        target_tier = action_params["target_tier"]
                        old_tier = item.plan_tier
                        item.plan_tier = target_tier
                        from app.services.workspace_limits import (
                            workspace_limit_service,
                        )
                        if workspace_limit_service:
                            await workspace_limit_service.create_subscription_change(
                                session=session,
                                workspace_id=item.id,
                                new_tier=target_tier,
                                actor_id=job.actor_id,
                            )
                        affected += 1
                        session.add(
                            AuditEvent(
                                action="bulk_op.apply_tier.workspace",
                                actor_id=job.actor_id,
                                subject_id=None,
                                ticket_ref=job.idempotency_key,
                                diff_payload={
                                    "workspace_id": item.id,
                                    "old_tier": old_tier,
                                    "new_tier": target_tier,
                                },
                            )
                        )

                except Exception as ex:
                    errors_count += 1
                    err_record = BulkOpError(
                        job_id=job.id,
                        subject_type=target_model.__name__.lower(),
                        subject_id=str(getattr(item, "id", "unknown")),
                        error_message=str(ex),
                        retryable=False,
                    )
                    session.add(err_record)
                    logger.warning("Error processing item %s in bulk job %s: %s", item, job.id, ex)

            # Update progress per batch
            job.processed_count = processed
            job.affected_count = affected
            job.error_count = errors_count
            await session.commit()

        # Finalize job status if not cancelled
        await session.refresh(job)
        if job.status != BulkOpJobStatus.CANCELLED.value:
            if errors_count == 0:
                job.status = BulkOpJobStatus.COMPLETED.value
            elif affected > 0:
                job.status = BulkOpJobStatus.PARTIAL.value
            else:
                job.status = BulkOpJobStatus.FAILED.value

            job.completed_at = datetime.now(UTC)

            # Summary AuditEvent
            session.add(
                AuditEvent(
                    action=f"bulk_op.{job.action}.summary",
                    actor_id=job.actor_id,
                    subject_id=None,
                    ticket_ref=job.idempotency_key,
                    diff_payload={
                        "job_id": str(job.id),
                        "total_count": job.total_count,
                        "processed_count": job.processed_count,
                        "affected_count": job.affected_count,
                        "error_count": job.error_count,
                        "status": job.status,
                    },
                )
            )
            await session.commit()


async def _cleanup_expired_idempotency_keys() -> int:
    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        now = datetime.now(UTC)
        stmt = delete(IdempotencyKey).where(IdempotencyKey.expires_at < now)
        res = await session.execute(stmt)
        await session.commit()
        deleted_count = res.rowcount
        logger.info("Pruned %d expired bulk_op idempotency keys", deleted_count)
        return deleted_count


@celery_app.task(name="bulk_op_executor", bind=True)
def bulk_op_executor(self, job_id_str: str) -> None:
    """Celery background worker executing bulk operations in batches."""
    return run_async_celery_task(lambda: _execute_bulk_op(job_id_str))


@celery_app.task(name="cleanup_expired_idempotency_keys")
def cleanup_expired_idempotency_keys() -> int:
    """Celery beat periodic cleanup of expired idempotency keys."""
    return run_async_celery_task(_cleanup_expired_idempotency_keys)
