"""add agent_configs client_id fk

Revision ID: 2c422d15105e
Revises: b870a82a7e81
Create Date: 2026-08-10 18:45:06.781883

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by this migration.
revision: str = "2c422d15105e"
down_revision: str | None = "b870a82a7e81"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add FK from agent_configs.client_id to vertical_clients.client_id."""
    # ponytail: drain any orphan rows that were created before this FK existed.
    # Follows the same pattern as 134_relax_revision_fks: NOT NULL + CASCADE
    # can only be added once orphans are removed.
    op.execute(
        """
        DELETE FROM agent_configs
        WHERE client_id NOT IN (SELECT client_id FROM vertical_clients)
        """
    )
    op.create_foreign_key(
        "fk_agent_configs_client_id_vertical_clients",
        "agent_configs",
        "vertical_clients",
        ["client_id"],
        ["client_id"],
        ondelete="CASCADE",
        source_schema=None,
        referent_schema=None,
    )


def downgrade() -> None:
    """Drop the agent_configs.client_id FK."""
    op.drop_constraint(
        "fk_agent_configs_client_id_vertical_clients",
        "agent_configs",
        type_="foreignkey",
    )
