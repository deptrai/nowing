"""add verified contact external chat ids and sequence step fallback channels

Revision ID: 227
Revises: 225
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "227"
down_revision: str | None = "225"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    if table_name not in sa.inspect(op.get_bind()).get_table_names():
        return False
    return column_name in {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)
    }


def upgrade() -> None:
    if not _column_exists("verified_contacts", "external_chat_ids"):
        op.add_column(
            "verified_contacts",
            sa.Column(
                "external_chat_ids",
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'{}'::jsonb"),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_verified_contacts_external_chat_ids",
            "verified_contacts",
            ["external_chat_ids"],
            postgresql_using="gin",
        )

    if not _column_exists("sequence_steps", "fallback_channels"):
        op.add_column(
            "sequence_steps",
            sa.Column(
                "fallback_channels",
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'[]'::jsonb"),
                nullable=False,
            ),
        )


def downgrade() -> None:
    op.drop_index("ix_verified_contacts_external_chat_ids", table_name="verified_contacts")
    op.drop_column("verified_contacts", "external_chat_ids")
    op.drop_column("sequence_steps", "fallback_channels")
