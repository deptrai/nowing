"""Story 26.1: chainlens chunks, verified contact PII vault, batch lead ingestion

Revision ID: ac475d54f6a2
Revises: f7471a265bc5
Create Date: 2026-08-17 17:35:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ac475d54f6a2"
down_revision: str | None = "f7471a265bc5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. chainlens_chunks table (UUID pk, workspace_id, source_url, content, embedding Vector(1536))
    op.create_table(
        "chainlens_chunks",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "workspace_id",
            sa.Integer,
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("source_url", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "embedding",
            Vector(1536),
            nullable=False,
        ),
        sa.Column(
            "chunk_index",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_chainlens_chunks_workspace_source",
        "chainlens_chunks",
        ["workspace_id", "source_url"],
    )

    # 2. VerifiedContact PII vault columns
    op.add_column(
        "verified_contacts",
        sa.Column(
            "is_unlocked",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "verified_contacts",
        sa.Column(
            "pii_access_audit_logs",
            sa.dialects.postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "verified_contacts",
        sa.Column(
            "value_hmac",
            sa.String(64),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_verified_contacts_value_hmac",
        "verified_contacts",
        ["workspace_id", "value_hmac"],
        unique=True,
        postgresql_where=sa.text("value_hmac IS NOT NULL"),
    )

    # 3. ChainLensIngestJob counts
    op.add_column(
        "chainlens_ingest_jobs",
        sa.Column(
            "chunks_received_count",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "chainlens_ingest_jobs",
        sa.Column(
            "chunks_ingested_count",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_table("chainlens_chunks")

    op.drop_column("verified_contacts", "is_unlocked")
    op.drop_column("verified_contacts", "pii_access_audit_logs")
    op.drop_index("ix_verified_contacts_value_hmac", table_name="verified_contacts")
    op.drop_column("verified_contacts", "value_hmac")

    op.drop_column("chainlens_ingest_jobs", "chunks_received_count")
    op.drop_column("chainlens_ingest_jobs", "chunks_ingested_count")
