"""add token usage and run attribution columns

Revision ID: 50461b6ab1cd
Revises: 10127c164b44
Create Date: 2026-08-10 04:38:09.219040

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import postgresql
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '50461b6ab1cd'
down_revision: Union[str, None] = '10127c164b44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add attribution columns to token_usage and runs."""
    op.add_column(
        "token_usage",
        sa.Column("client_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "token_usage",
        sa.Column("external_metadata", postgresql.JSONB, nullable=True),
    )
    op.add_column(
        "token_usage",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.create_index(
        op.f("ix_token_usage_client_id"),
        "token_usage",
        ["client_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_token_usage_run_id"),
        "token_usage",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_token_usage_workspace_client_created_at"),
        "token_usage",
        ["workspace_id", "client_id", "created_at"],
        unique=False,
    )

    op.add_column("runs", sa.Column("client_id", sa.Text(), nullable=True))
    op.add_column(
        "runs",
        sa.Column("external_metadata", postgresql.JSONB, nullable=True),
    )
    op.create_index(
        op.f("ix_runs_client_id"), "runs", ["client_id"], unique=False
    )
    op.create_index(
        op.f("ix_runs_workspace_client_created"),
        "runs",
        ["workspace_id", "client_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop attribution columns and indexes."""
    op.drop_index(
        op.f("ix_runs_workspace_client_created"), table_name="runs"
    )
    op.drop_index(op.f("ix_runs_client_id"), table_name="runs")
    op.drop_column("runs", "external_metadata")
    op.drop_column("runs", "client_id")

    op.drop_index(
        op.f("ix_token_usage_workspace_client_created_at"),
        table_name="token_usage",
    )
    op.drop_index(op.f("ix_token_usage_run_id"), table_name="token_usage")
    op.drop_index(
        op.f("ix_token_usage_client_id"), table_name="token_usage"
    )

    op.drop_column("token_usage", "run_id")
    op.drop_column("token_usage", "external_metadata")
    op.drop_column("token_usage", "client_id")
