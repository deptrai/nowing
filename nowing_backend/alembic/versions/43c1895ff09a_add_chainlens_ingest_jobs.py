"""add chainlens ingest jobs

Revision ID: 43c1895ff09a
Revises: e5b50d5e687e
Create Date: 2026-08-11 18:52:38.258668

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "43c1895ff09a"
down_revision: str | None = "e5b50d5e687e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "chainlens_ingest_jobs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "workspace_id",
            sa.Integer,
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scraper_id", sa.String(100), nullable=False),
        sa.Column("parent_ingest_job_id", sa.String(255), nullable=True),
        sa.Column(
            "child_ingest_job_ids",
            sa.dialects.postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "noop_source_ids",
            sa.dialects.postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "ingested_source_ids",
            sa.dialects.postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("dead_letter_payload", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("run_id", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_chainlens_ingest_jobs_workspace_created",
        "chainlens_ingest_jobs",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "ix_chainlens_ingest_jobs_scraper_id", "chainlens_ingest_jobs", ["scraper_id"]
    )
    op.create_index(
        "ix_chainlens_ingest_jobs_run_id", "chainlens_ingest_jobs", ["run_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("chainlens_ingest_jobs")
