"""add_memory_encryption_metadata

Revision ID: 8f4c78216b02
Revises: 238_add_admin_health_tables
Create Date: 2026-09-06 05:51:33.117000+00:00

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f4c78216b02"
down_revision: Union[str, None] = "238_add_admin_health_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add row-level encryption metadata columns to Memory, MemoryVersion, and
    # MemoryRelation. All columns are nullable so existing rows stay plaintext
    # and self-host installs that do not enable encryption remain unblocked.
    for table in ("memories", "memory_versions", "memory_relations"):
        op.add_column(table, sa.Column("key_id", sa.String(64), nullable=True))
        op.add_column(table, sa.Column("encryption_iv", sa.Text(), nullable=True))
        op.add_column(table, sa.Column("encryption_algo", sa.String(32), nullable=True))

    # Existing rows are legacy plaintext. We intentionally do NOT force
    # key_id='legacy' here; the decryption code treats NULL and 'legacy' as
    # plaintext equivalently.


def downgrade() -> None:
    # Do not drop columns if encrypted data exists. If we must roll back, keep
    # the columns nullable so encrypted rows remain valid until a future
    # migration decrypts them. Dropping metadata would make ciphertext
    # undecryptable.
    pass
