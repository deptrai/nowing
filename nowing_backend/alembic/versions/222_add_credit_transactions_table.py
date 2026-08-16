"""add credit transactions table

Revision ID: 222
Revises: 221
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "222"
down_revision: str | None = "221"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "credit_transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_admin_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("user.id"),
            nullable=False,
        ),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("amount_micros", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("ticket_ref", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_transactions")),
    )
    op.create_index(
        op.f("ix_credit_transactions_workspace_id"),
        "credit_transactions",
        ["workspace_id"],
    )
    op.create_index(
        op.f("ix_credit_transactions_actor_admin_id"),
        "credit_transactions",
        ["actor_admin_id"],
    )
    op.create_index(
        op.f("ix_credit_transactions_idempotency_key"),
        "credit_transactions",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        op.f("ix_credit_transactions_created_at"),
        "credit_transactions",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_credit_transactions_created_at"), table_name="credit_transactions"
    )
    op.drop_index(
        op.f("ix_credit_transactions_idempotency_key"),
        table_name="credit_transactions",
    )
    op.drop_index(
        op.f("ix_credit_transactions_actor_admin_id"),
        table_name="credit_transactions",
    )
    op.drop_index(
        op.f("ix_credit_transactions_workspace_id"),
        table_name="credit_transactions",
    )
    op.drop_table("credit_transactions")
