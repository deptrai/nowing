"""Integration tests for workspace plan/limit resolution and gating."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config, config
from app.db import (
    Document,
    DocumentType,
    Run,
    User,
    Workspace,
    WorkspaceInvite,
    WorkspaceLimit,
    WorkspaceMembership,
)
from app.file_storage.persistence.models import DocumentFile
from app.schemas import PlanDefinitionCreate, PlanDefinitionUpdate
from app.services.workspace_limits import ResolvedWorkspaceLimits, WorkspaceLimitService

pytestmark = pytest.mark.integration


async def _seed_plan_defaults(session: AsyncSession) -> None:
    session.add_all(
        [
            WorkspaceLimit(
                plan_tier="free",
                workspace_id=None,
                max_documents=5,
                max_members=2,
                max_runs=3,
                max_storage_bytes=1_000_000_000,
                run_period_hours=720,
            ),
            WorkspaceLimit(
                plan_tier="team",
                workspace_id=None,
                max_documents=100,
                max_members=10,
                max_runs=50,
                max_storage_bytes=10_000_000_000,
                run_period_hours=720,
            ),
        ]
    )
    await session.flush()


async def test_self_hosted_returns_unlimited_limits(
    db_session: AsyncSession, db_workspace: Workspace, monkeypatch
):
    monkeypatch.setattr(config, "DEPLOYMENT_MODE", "self-hosted")
    service = WorkspaceLimitService()

    limits = await service.get_effective_limits(db_session, db_workspace.id)

    assert limits == ResolvedWorkspaceLimits(
        plan_tier=db_workspace.plan_tier,
        max_documents=None,
        max_members=None,
        max_runs=None,
        max_storage_bytes=None,
        run_period_hours=720,
    )


async def test_cloud_uses_plan_defaults(
    db_session: AsyncSession, db_workspace: Workspace, monkeypatch
):
    monkeypatch.setattr(Config, "DEPLOYMENT_MODE", "cloud")
    await _seed_plan_defaults(db_session)

    service = WorkspaceLimitService()
    limits = await service.get_effective_limits(db_session, db_workspace.id)

    assert limits.max_documents == 5
    assert limits.max_members == 2
    assert limits.max_runs == 3


async def test_cloud_uses_workspace_override(
    db_session: AsyncSession, db_workspace: Workspace, monkeypatch
):
    monkeypatch.setattr(Config, "DEPLOYMENT_MODE", "cloud")
    await _seed_plan_defaults(db_session)

    db_session.add(
        WorkspaceLimit(
            plan_tier=None,
            workspace_id=db_workspace.id,
            max_documents=20,
            max_members=None,
            max_runs=None,
            max_storage_bytes=None,
            run_period_hours=24,
        )
    )
    await db_session.flush()

    service = WorkspaceLimitService()
    limits = await service.get_effective_limits(db_session, db_workspace.id)

    assert limits.max_documents == 20
    assert limits.max_members == 2  # from plan default
    assert limits.run_period_hours == 24


async def test_env_override_applies_to_plan_defaults(
    db_session: AsyncSession, db_workspace: Workspace, monkeypatch
):
    monkeypatch.setattr(Config, "DEPLOYMENT_MODE", "cloud")
    await _seed_plan_defaults(db_session)
    monkeypatch.setattr(
        config,
        "WORKSPACE_PLAN_LIMITS",
        {"free": {"max_documents": 1}},
    )

    service = WorkspaceLimitService()
    limits = await service.get_effective_limits(db_session, db_workspace.id)

    assert limits.max_documents == 1


async def test_document_limit_enforced(
    db_session: AsyncSession, db_workspace: Workspace, db_user, monkeypatch
):
    monkeypatch.setattr(Config, "DEPLOYMENT_MODE", "cloud")
    await _seed_plan_defaults(db_session)

    for i in range(5):
        db_session.add(
            Document(
                workspace_id=db_workspace.id,
                title=f"Doc {i}",
                document_type=DocumentType.FILE,
                content="...",
                content_hash=f"hash-{i}",
                unique_identifier_hash=f"unique-{i}",
            )
        )
    await db_session.flush()

    service = WorkspaceLimitService()
    with pytest.raises(HTTPException) as exc_info:
        await service.check_document_limit(db_session, db_workspace.id, additional=1)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error_code"] == "limit_exceeded"
    assert exc_info.value.detail["limit_type"] == "documents"


async def test_document_limit_allows_within_limit(
    db_session: AsyncSession, db_workspace: Workspace, monkeypatch
):
    monkeypatch.setattr(Config, "DEPLOYMENT_MODE", "cloud")
    await _seed_plan_defaults(db_session)

    service = WorkspaceLimitService()
    # free plan max_documents=5; workspace has 0 documents
    await service.check_document_limit(db_session, db_workspace.id, additional=5)


async def test_member_limit_counts_invites_and_memberships(
    db_session: AsyncSession, db_workspace: Workspace, db_user, monkeypatch
):
    monkeypatch.setattr(Config, "DEPLOYMENT_MODE", "cloud")
    await _seed_plan_defaults(db_session)

    # One existing member
    other_user = User(
        id=uuid.uuid4(),
        email="other@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(other_user)
    await db_session.flush()
    db_session.add(
        WorkspaceMembership(
            user_id=other_user.id,
            workspace_id=db_workspace.id,
            role_id=None,
            is_owner=False,
        )
    )
    # One active unexpired invite
    db_session.add(
        WorkspaceInvite(
            invite_code="invite-1",
            workspace_id=db_workspace.id,
            is_active=True,
            uses_count=0,
            max_uses=None,
        )
    )
    await db_session.flush()

    service = WorkspaceLimitService()
    # max_members=2, used=2, additional=1 should fail
    with pytest.raises(HTTPException) as exc_info:
        await service.check_member_limit(db_session, db_workspace.id, additional=1)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["limit_type"] == "members"


async def test_run_limit_counts_recent_runs(
    db_session: AsyncSession, db_workspace: Workspace, monkeypatch
):
    monkeypatch.setattr(Config, "DEPLOYMENT_MODE", "cloud")
    await _seed_plan_defaults(db_session)

    now = datetime.now(UTC)
    for _ in range(3):
        db_session.add(
            Run(
                workspace_id=db_workspace.id,
                capability="test",
                origin="rest",
                status="success",
                created_at=now,
            )
        )
    await db_session.flush()

    service = WorkspaceLimitService()
    with pytest.raises(HTTPException) as exc_info:
        await service.check_run_limit(db_session, db_workspace.id)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["limit_type"] == "runs"


async def test_storage_sum_uses_document_files(
    db_session: AsyncSession, db_workspace: Workspace, monkeypatch
):
    monkeypatch.setattr(Config, "DEPLOYMENT_MODE", "cloud")
    await _seed_plan_defaults(db_session)

    doc = Document(
        workspace_id=db_workspace.id,
        title="File doc",
        document_type="FILE",
        content="...",
        content_hash="hash",
        unique_identifier_hash="unique",
    )
    db_session.add(doc)
    await db_session.flush()

    db_session.add(
        DocumentFile(
            document_id=doc.id,
            workspace_id=db_workspace.id,
            storage_backend="local",
            storage_key="key",
            original_filename="test.txt",
            size_bytes=1234,
        )
    )
    await db_session.flush()

    service = WorkspaceLimitService()
    usage = await service.get_usage_snapshot(db_session, db_workspace.id)

    assert usage["storage_bytes"] == 1234


async def test_cancelled_runs_not_counted(
    db_session: AsyncSession, db_workspace: Workspace, monkeypatch
):
    monkeypatch.setattr(Config, "DEPLOYMENT_MODE", "cloud")
    await _seed_plan_defaults(db_session)

    now = datetime.now(UTC)
    db_session.add(
        Run(
            workspace_id=db_workspace.id,
            capability="test",
            origin="rest",
            status="cancelled",
            created_at=now,
        )
    )
    await db_session.flush()

    service = WorkspaceLimitService()
    await service.check_run_limit(db_session, db_workspace.id)


async def test_old_runs_outside_period_not_counted(
    db_session: AsyncSession, db_workspace: Workspace, monkeypatch
):
    monkeypatch.setattr(Config, "DEPLOYMENT_MODE", "cloud")
    await _seed_plan_defaults(db_session)

    old = datetime.now(UTC) - timedelta(days=60)
    for _ in range(10):
        db_session.add(
            Run(
                workspace_id=db_workspace.id,
                capability="test",
                origin="rest",
                status="success",
                created_at=old,
            )
        )
    await db_session.flush()

    service = WorkspaceLimitService()
    await service.check_run_limit(db_session, db_workspace.id)


async def test_unknown_plan_tier_falls_back_to_free(
    db_session: AsyncSession, db_workspace: Workspace, monkeypatch
):
    monkeypatch.setattr(Config, "DEPLOYMENT_MODE", "cloud")
    await _seed_plan_defaults(db_session)
    db_workspace.plan_tier = "premium"
    await db_session.flush()

    service = WorkspaceLimitService()
    limits = await service.get_effective_limits(db_session, db_workspace.id)

    # Unknown tier should fall back to free defaults.
    assert limits.plan_tier == "premium"
    assert limits.max_documents == 5
    assert limits.max_members == 2
    assert limits.max_runs == 3


async def test_env_override_misconfiguration_is_ignored(
    db_session: AsyncSession, db_workspace: Workspace, monkeypatch
):
    monkeypatch.setattr(Config, "DEPLOYMENT_MODE", "cloud")
    await _seed_plan_defaults(db_session)
    monkeypatch.setattr(
        config,
        "WORKSPACE_PLAN_LIMITS",
        {"free": "invalid"},
    )

    service = WorkspaceLimitService()
    limits = await service.get_effective_limits(db_session, db_workspace.id)

    # Malformed env override should be ignored and fall back to DB defaults.
    assert limits.max_documents == 5


async def test_negative_limit_value_raises(
    db_session: AsyncSession, db_workspace: Workspace, monkeypatch
):
    monkeypatch.setattr(Config, "DEPLOYMENT_MODE", "cloud")
    await _seed_plan_defaults(db_session)

    db_session.add(
        WorkspaceLimit(
            plan_tier=None,
            workspace_id=db_workspace.id,
            max_documents=-1,
            max_members=None,
            max_runs=None,
            max_storage_bytes=None,
            run_period_hours=720,
        )
    )
    await db_session.flush()

    service = WorkspaceLimitService()
    with pytest.raises(ValueError):
        await service.get_effective_limits(db_session, db_workspace.id)


async def test_member_limit_allows_at_boundary_when_invite_is_consumed(
    db_session: AsyncSession, db_workspace: Workspace, db_user, monkeypatch
):
    monkeypatch.setattr(Config, "DEPLOYMENT_MODE", "cloud")
    # db_workspace fixture creates a default owner membership, so we use
    # max_members=3 to have room for one more after the second member and the
    # consumed invite are no longer counted as an invite.
    db_session.add(
        WorkspaceLimit(
            plan_tier="free",
            workspace_id=None,
            max_documents=5,
            max_members=3,
            max_runs=3,
            max_storage_bytes=1_000_000_000,
            run_period_hours=720,
        )
    )

    other_user = User(
        id=uuid.uuid4(),
        email="other-boundary@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(other_user)
    await db_session.flush()
    db_session.add(
        WorkspaceMembership(
            user_id=other_user.id,
            workspace_id=db_workspace.id,
            role_id=None,
            is_owner=False,
        )
    )
    invite = WorkspaceInvite(
        invite_code="single-use",
        workspace_id=db_workspace.id,
        is_active=True,
        uses_count=1,
        max_uses=1,
    )
    db_session.add(invite)
    await db_session.flush()

    service = WorkspaceLimitService()
    await service.check_member_limit(db_session, db_workspace.id, additional=1)


async def test_concurrent_document_limit_boundary(async_engine, monkeypatch):
    """Only one of two concurrent at-boundary requests may create a document.

    The advisory lock around count + check is supposed to serialize the two
    requests so the second one observes the first committed row and fails.
    """
    monkeypatch.setattr(Config, "DEPLOYMENT_MODE", "cloud")

    async with AsyncSession(async_engine) as session:
        # Seed a tight free plan default.
        session.add(
            WorkspaceLimit(
                plan_tier="free",
                workspace_id=None,
                max_documents=1,
                max_members=1,
                max_runs=1,
                max_storage_bytes=1_000_000_000,
                run_period_hours=720,
            )
        )

        user = User(
            id=uuid.uuid4(),
            email="concurrent-test@nowing.net",
            hashed_password="hashed",
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )
        session.add(user)
        await session.flush()

        workspace = Workspace(
            name="Concurrent Test",
            user_id=user.id,
            plan_tier="free",
        )
        session.add(workspace)
        await session.flush()

        # Capture plain IDs before closing the setup session.
        workspace_id = workspace.id
        user_id = str(user.id)

        await session.commit()

    service = WorkspaceLimitService()

    async def _try_create() -> HTTPException | None:
        async with AsyncSession(async_engine) as session:
            try:
                await service.check_document_limit(session, workspace_id, additional=1)
                session.add(
                    Document(
                        workspace_id=workspace_id,
                        title="Concurrent doc",
                        document_type=DocumentType.FILE,
                        content="...",
                        content_hash=str(uuid.uuid4()),
                        unique_identifier_hash=str(uuid.uuid4()),
                        created_by_id=str(user_id),
                    )
                )
                await session.commit()
                return None
            except HTTPException as exc:
                return exc

    results = await asyncio.gather(_try_create(), _try_create())

    # Exactly one should succeed, the other should be rejected.
    exceptions = [r for r in results if isinstance(r, HTTPException)]
    successes = [r for r in results if r is None]
    assert len(exceptions) == 1
    assert len(successes) == 1
    assert exceptions[0].status_code == 403
    assert exceptions[0].detail["error_code"] == "limit_exceeded"
    assert exceptions[0].detail["limit_type"] == "documents"


async def test_check_plan_change_conflicts_blocks_downgrade(
    db_session: AsyncSession, db_workspace: Workspace, monkeypatch
):
    monkeypatch.setattr(Config, "DEPLOYMENT_MODE", "cloud")
    await _seed_plan_defaults(db_session)
    db_workspace.plan_tier = "team"
    await db_session.flush()

    # Add 6 documents (exceeds free plan limit of 5)
    for i in range(6):
        db_session.add(
            Document(
                workspace_id=db_workspace.id,
                title=f"Doc {i}",
                document_type="FILE",
                content="...",
                content_hash=f"hash_{i}",
                unique_identifier_hash=f"uniq_{i}",
            )
        )
    await db_session.flush()

    service = WorkspaceLimitService()
    free_plan = await service.get_plan_definition(db_session, "free")
    assert free_plan is not None

    conflicts = await service.check_plan_change_conflicts(
        db_session, db_workspace.id, "free"
    )
    assert "documents" in conflicts
    assert conflicts["documents"]["current"] == 6
    assert conflicts["documents"]["limit"] == free_plan.max_documents

    with pytest.raises(HTTPException) as exc_info:
        await service.create_subscription_change(
            db_session, db_workspace.id, "free", immediate=True
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error_code"] == "quota_conflict"


async def test_create_subscription_change_scheduled_and_cancel(
    db_session: AsyncSession, db_workspace: Workspace, monkeypatch
):
    monkeypatch.setattr(Config, "DEPLOYMENT_MODE", "cloud")
    await _seed_plan_defaults(db_session)
    db_workspace.plan_tier = "free"
    await db_session.flush()

    service = WorkspaceLimitService()
    change = await service.create_subscription_change(
        db_session, db_workspace.id, "team", immediate=False
    )
    assert change.status == "pending"
    assert change.from_plan == "free"
    assert change.to_plan == "team"
    assert change.effective_at > datetime.now(UTC) + timedelta(days=6)
    assert db_workspace.plan_tier == "free"

    # Cancel the pending change
    cancelled = await service.cancel_subscription_change(
        db_session, db_workspace.id, change.id
    )
    assert cancelled.status == "cancelled"


async def test_create_subscription_change_immediate_and_revert(
    db_session: AsyncSession, db_workspace: Workspace, monkeypatch
):
    monkeypatch.setattr(Config, "DEPLOYMENT_MODE", "cloud")
    await _seed_plan_defaults(db_session)
    db_workspace.plan_tier = "free"
    await db_session.flush()

    service = WorkspaceLimitService()
    change = await service.create_subscription_change(
        db_session, db_workspace.id, "team", immediate=True
    )
    assert change.status == "active"
    assert change.from_plan == "free"
    assert change.to_plan == "team"
    assert change.reversible_until is not None
    assert change.reversible_until > datetime.now(UTC) + timedelta(days=6)
    assert db_workspace.plan_tier == "team"

    # Revert within the 7-day window
    reverted = await service.revert_subscription_change(
        db_session, db_workspace.id, change.id
    )
    assert reverted.status == "reverted"
    assert db_workspace.plan_tier == "free"


async def test_admin_plan_definition_crud_and_grandfathering(
    db_session: AsyncSession, db_workspace: Workspace, monkeypatch
):
    monkeypatch.setattr(Config, "DEPLOYMENT_MODE", "cloud")
    await _seed_plan_defaults(db_session)

    service = WorkspaceLimitService()

    # 1. Create custom plan
    created = await service.create_plan_definition(
        db_session,
        PlanDefinitionCreate(
            plan_tier="custom_tier",
            max_documents=50,
            max_members=5,
            price_micros=15_000_000,
            support_level="email",
        ),
    )
    assert created.plan_tier == "custom_tier"
    assert created.max_documents == 50
    assert created.is_system_default is False

    # Assign workspace to custom_tier
    db_workspace.plan_tier = "custom_tier"
    await db_session.flush()

    # 2. Update plan definition -> triggers grandfathering
    await service.update_plan_definition(
        db_session,
        "custom_tier",
        PlanDefinitionUpdate(max_documents=30),
    )
    await db_session.flush()

    # Check that workspace got grandfathered override with old limit (50)
    from sqlalchemy import select

    res = await db_session.execute(
        select(WorkspaceLimit).where(
            WorkspaceLimit.workspace_id == db_workspace.id,
            WorkspaceLimit.plan_tier.is_(None),
        )
    )
    override_row = res.scalars().first()
    assert override_row is not None
    assert override_row.max_documents == 50

    # 3. System defaults cannot be deleted
    with pytest.raises(HTTPException) as exc_free:
        await service.delete_plan_definition(db_session, "free")
    assert exc_free.value.status_code == 400

    # 4. Cannot delete custom_tier while assigned to workspace
    with pytest.raises(HTTPException) as exc_custom:
        await service.delete_plan_definition(db_session, "custom_tier")
    assert exc_custom.value.status_code == 409

    # Move workspace off and delete
    db_workspace.plan_tier = "free"
    await db_session.flush()
    await service.delete_plan_definition(db_session, "custom_tier")
    plan = await service.get_plan_definition(db_session, "custom_tier")
    assert plan is None

@pytest.mark.asyncio
async def test_reconcile_workspace_storage_cleans_orphaned_and_computes_total(
    db_session: AsyncSession,
    db_workspace: Workspace,
) -> None:
    from app.db import Document, DocumentType
    from app.file_storage.persistence.enums import DocumentFileKind
    from app.file_storage.persistence.models import DocumentFile

    valid_doc = Document(
        workspace_id=db_workspace.id,
        title="Valid Doc",
        document_type=DocumentType.FILE,
        content_hash="dummy_hash_123",
        content="Some content",
    )
    db_session.add(valid_doc)
    await db_session.flush()

    valid_file = DocumentFile(
        document_id=valid_doc.id,
        workspace_id=db_workspace.id,
        kind=DocumentFileKind.ORIGINAL,
        storage_backend="local",
        storage_key="test/valid.pdf",
        original_filename="valid.pdf",
        size_bytes=5000,
    )
    db_session.add(valid_file)

    corrupt_file = DocumentFile(
        document_id=valid_doc.id,
        workspace_id=db_workspace.id,
        kind=DocumentFileKind.REDACTED,
        storage_backend="local",
        storage_key="test/corrupt.pdf",
        original_filename="corrupt.pdf",
        size_bytes=-100,
    )
    db_session.add(corrupt_file)
    await db_session.flush()

    res = await WorkspaceLimitService.reconcile_workspace_storage(
        db_session, db_workspace.id, purge_orphans=True
    )
    assert res["reconciled_storage_bytes"] == 5000
    assert res["orphaned_files_cleaned"] == 1


@pytest.mark.asyncio
async def test_reconcile_workspace_storage_dry_run_does_not_purge(
    db_session: AsyncSession,
    db_workspace: Workspace,
) -> None:
    from app.db import Document, DocumentType
    from app.file_storage.persistence.enums import DocumentFileKind
    from app.file_storage.persistence.models import DocumentFile

    valid_doc = Document(
        workspace_id=db_workspace.id,
        title="Valid Doc",
        document_type=DocumentType.FILE,
        content_hash="dummy_hash_dry_run",
        content="Some content",
    )
    db_session.add(valid_doc)
    await db_session.flush()

    corrupt_file = DocumentFile(
        document_id=valid_doc.id,
        workspace_id=db_workspace.id,
        kind=DocumentFileKind.REDACTED,
        storage_backend="local",
        storage_key="test/corrupt_dry_run.pdf",
        original_filename="corrupt.pdf",
        size_bytes=-50,
    )
    db_session.add(corrupt_file)
    await db_session.flush()

    res = await WorkspaceLimitService.reconcile_workspace_storage(
        db_session, db_workspace.id, purge_orphans=False
    )
    assert res["orphaned_files_cleaned"] == 0

    check = await db_session.get(DocumentFile, corrupt_file.id)
    assert check is not None
