"""add bulk_op_jobs, bulk_op_errors, idempotency_keys tables and workspaces.archived_at (Story 29.4)

Revision ID: f6a7b8c9d0e1
Revises: e5f8a1b2c3d4
Create Date: 2026-09-07 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f8a1b2c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add archived_at to workspaces
    op.execute(
        sa.text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'workspaces' AND column_name = 'archived_at'
                ) THEN
                    ALTER TABLE workspaces ADD COLUMN archived_at TIMESTAMP WITH TIME ZONE;
                    CREATE INDEX IF NOT EXISTS ix_workspaces_archived_at ON workspaces (archived_at);
                END IF;
            END $$;
        """)
    )

    # 2. Create bulk_op_jobs table
    op.create_table(
        "bulk_op_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("workspace_id", sa.Integer(), nullable=True),
        sa.Column(
            "filter_spec",
            JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "action_params",
            JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "total_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "processed_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "affected_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "error_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_bulk_op_jobs_action", "bulk_op_jobs", ["action"])
    op.create_index("ix_bulk_op_jobs_status", "bulk_op_jobs", ["status"])
    op.create_index("ix_bulk_op_jobs_actor_id", "bulk_op_jobs", ["actor_id"])
    op.create_index("ix_bulk_op_jobs_workspace_id", "bulk_op_jobs", ["workspace_id"])
    op.create_index(
        "ix_bulk_op_jobs_idempotency_key",
        "bulk_op_jobs",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index("ix_bulk_op_jobs_request_hash", "bulk_op_jobs", ["request_hash"])
    op.create_index(
        "ix_bulk_op_jobs_actor_status", "bulk_op_jobs", ["actor_id", "status"]
    )
    op.create_index(
        "ix_bulk_op_jobs_created_status", "bulk_op_jobs", ["created_at", "status"]
    )

    # 3. Create bulk_op_errors table
    op.create_table(
        "bulk_op_errors",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("job_id", UUID(as_uuid=True), nullable=False),
        sa.Column("subject_type", sa.String(length=50), nullable=False),
        sa.Column("subject_id", sa.String(length=100), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column(
            "retryable", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["job_id"], ["bulk_op_jobs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_bulk_op_errors_job_id", "bulk_op_errors", ["job_id"])
    op.create_index("ix_bulk_op_errors_subject_type", "bulk_op_errors", ["subject_type"])
    op.create_index("ix_bulk_op_errors_subject_id", "bulk_op_errors", ["subject_id"])
    op.create_index(
        "ix_bulk_op_errors_job_subject",
        "bulk_op_errors",
        ["job_id", "subject_type", "subject_id"],
    )

    # 4. Create idempotency_keys table
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("job_id", UUID(as_uuid=True), nullable=True),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["job_id"], ["bulk_op_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_idempotency_keys_key", "idempotency_keys", ["key"], unique=True
    )
    op.create_index(
        "ix_idempotency_keys_request_hash", "idempotency_keys", ["request_hash"]
    )
    op.create_index(
        "ix_idempotency_keys_job_id", "idempotency_keys", ["job_id"]
    )
    op.create_index(
        "ix_idempotency_keys_actor_id", "idempotency_keys", ["actor_id"]
    )
    op.create_index(
        "ix_idempotency_keys_expires_at", "idempotency_keys", ["expires_at"]
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.drop_table("bulk_op_errors")
    op.drop_table("bulk_op_jobs")
    op.execute(
        sa.text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'workspaces' AND column_name = 'archived_at'
                ) THEN
                    DROP INDEX IF EXISTS ix_workspaces_archived_at;
                    ALTER TABLE workspaces DROP COLUMN archived_at;
                END IF;
            END $$;
        """)
    )
