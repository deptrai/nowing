"""workspace_tables.key column + unique (workspace_id, key) + orphan backfill (Story 42.7).

Revision ID: 250
Revises: 249
Create Date: 2026-11-17

- ``key`` (Text, nullable) holds the stable key of auto-created default tables
  (``key = client_id``, fallback ``"default"``). User-created tables keep
  ``key = NULL``; the composite UNIQUE allows any number of NULL keys.
- One-shot backfill: every workspace with leads whose ``table_id IS NULL``
  gets a default table (``key = 'default'``) and its orphan leads are pointed
  at it. Data migration runs as plain ``op.execute`` SQL — no background job.

Race-safe get-or-create on the ingest path relies on
``uq_workspace_tables_workspace_key`` with ``ON CONFLICT DO NOTHING``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "250"
down_revision: str | None = "249"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workspace_tables", sa.Column("key", sa.Text(), nullable=True))
    op.create_unique_constraint(
        "uq_workspace_tables_workspace_key", "workspace_tables", ["workspace_id", "key"]
    )

    # One-shot backfill: create a default table per workspace that has orphan
    # leads (table_id IS NULL), then point those leads at it. ON CONFLICT keeps
    # this idempotent if a workspace already has a key='default' table.
    op.execute(
        """
        INSERT INTO workspace_tables (id, workspace_id, name, icon, key)
        SELECT gen_random_uuid(), w.id, 'Leads', 'table', 'default'
        FROM workspaces w
        WHERE EXISTS (
            SELECT 1 FROM leads l
            WHERE l.workspace_id = w.id AND l.table_id IS NULL
        )
        ON CONFLICT (workspace_id, key) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE leads l
        SET table_id = t.id
        FROM workspace_tables t
        WHERE t.workspace_id = l.workspace_id
          AND t.key = 'default'
          AND l.table_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_workspace_tables_workspace_key", "workspace_tables", type_="unique"
    )
    op.drop_column("workspace_tables", "key")
