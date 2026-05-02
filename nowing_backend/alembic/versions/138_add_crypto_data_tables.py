"""138_add_crypto_data_tables — Persistent shared crypto data layer

Revision ID: 138
Revises: 137

Creates 3 tables for Epic 10 (crypto data caching layer):
- crypto_projects: entity registry (token/protocol identity)
- crypto_data_snapshots: append-only cached API results with TTL
- search_space_crypto_watchlist: workspace → crypto project association
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "138"
down_revision: str | None = "137"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(conn, name: str) -> bool:
    return (
        conn.execute(
            sa.text("SELECT 1 FROM information_schema.tables WHERE table_name = :n"),
            {"n": name},
        ).fetchone()
        is not None
    )


def _index_exists(conn, name: str) -> bool:
    return (
        conn.execute(
            sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :n"),
            {"n": name},
        ).fetchone()
        is not None
    )


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "crypto_projects"):
        op.create_table(
            "crypto_projects",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.String(length=128), nullable=False),
            sa.Column("symbol", sa.String(length=32), nullable=True),
            sa.Column("name", sa.String(length=256), nullable=True),
            sa.Column("chain", sa.String(length=64), nullable=True),
            sa.Column("contract_address", sa.String(length=128), nullable=True),
            sa.Column("coingecko_id", sa.String(length=128), nullable=True),
            sa.Column("defillama_slug", sa.String(length=128), nullable=True),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("project_id"),
        )

    if not _index_exists(conn, "ix_crypto_projects_symbol"):
        op.create_index("ix_crypto_projects_symbol", "crypto_projects", ["symbol"])

    if not _index_exists(conn, "ix_crypto_projects_contract_address"):
        op.create_index(
            "ix_crypto_projects_contract_address", "crypto_projects", ["contract_address"]
        )

    if not _table_exists(conn, "crypto_data_snapshots"):
        op.create_table(
            "crypto_data_snapshots",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("data_category", sa.String(length=64), nullable=False),
            sa.Column("tool_name", sa.String(length=128), nullable=False),
            sa.Column("tool_args", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("data_hash", sa.String(length=64), nullable=False),
            sa.Column("args_hash", sa.String(length=64), nullable=True),
            sa.Column(
                "fetched_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("ttl_seconds", sa.Integer(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("is_error", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("api_source", sa.String(length=64), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["project_id"],
                ["crypto_projects.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _index_exists(conn, "ix_crypto_snapshots_project_category_fetched"):
        op.create_index(
            "ix_crypto_snapshots_project_category_fetched",
            "crypto_data_snapshots",
            ["project_id", "data_category", "fetched_at"],
        )

    if not _index_exists(conn, "ix_crypto_snapshots_expires_at"):
        op.create_index(
            "ix_crypto_snapshots_expires_at",
            "crypto_data_snapshots",
            ["expires_at"],
        )

    if not _index_exists(conn, "ix_crypto_snapshots_cache_lookup"):
        op.create_index(
            "ix_crypto_snapshots_cache_lookup",
            "crypto_data_snapshots",
            ["project_id", "data_category", "tool_name", "args_hash"],
        )

    if not _table_exists(conn, "search_space_crypto_watchlist"):
        op.create_table(
            "search_space_crypto_watchlist",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("search_space_id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column(
                "added_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("added_by_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("pin_order", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(
                ["search_space_id"],
                ["searchspaces.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["project_id"],
                ["crypto_projects.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["added_by_id"],
                ["user.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("search_space_id", "project_id"),
        )


def downgrade() -> None:
    op.drop_table("search_space_crypto_watchlist")
    op.drop_index("ix_crypto_snapshots_expires_at", table_name="crypto_data_snapshots")
    op.drop_index(
        "ix_crypto_snapshots_project_category_fetched", table_name="crypto_data_snapshots"
    )
    op.drop_table("crypto_data_snapshots")
    op.drop_index("ix_crypto_projects_contract_address", table_name="crypto_projects")
    op.drop_index("ix_crypto_projects_symbol", table_name="crypto_projects")
    op.drop_table("crypto_projects")
