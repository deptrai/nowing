"""cast lead client_id from citext to text

Revision ID: 142d54696fd7
Revises: 3e0decbbbfbf
Create Date: 2026-08-27 08:53:14.240985

"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op
from app.zero_publication import apply_publication

# revision identifiers, used by Alembic.
revision: str = "142d54696fd7"
down_revision: str | None = "3e0decbbbfbf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO_TABLES = (
    "leads",
    "lead_pipeline_stages",
    "lead_assignments",
    "lead_activity_logs",
)


def _client_id_is_citext(conn, table: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM pg_catalog.pg_attribute a
            JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_catalog.pg_type t ON t.oid = a.atttypid
            WHERE n.nspname = current_schema()
              AND c.relname = :table
              AND a.attname = 'client_id'
              AND a.attnum > 0
              AND NOT a.attisdropped
              AND t.typname = 'citext'
            """
        ),
        {"table": table},
    ).fetchone()
    return row is not None


def _published_tables(conn) -> list[str]:
    rows = conn.execute(
        text(
            "SELECT tablename FROM pg_publication_tables "
            "WHERE pubname = 'zero_publication' AND schemaname = current_schema()"
        )
    ).fetchall()
    return [r[0] for r in rows]


def _drop_from_publication(conn) -> None:
    published = set(_published_tables(conn))
    to_drop = [t for t in _ZERO_TABLES if t in published]
    if to_drop:
        conn.execute(
            text(
                'ALTER PUBLICATION "zero_publication" DROP TABLE '
                + ", ".join(f'"{t}"' for t in to_drop)
            )
        )


def upgrade() -> None:
    bind = op.get_bind()

    # Postgres forbids ALTER COLUMN ... TYPE on a column that a publication
    # depends on, so drop the lead tables from the publication first and
    # re-apply at the end.
    _drop_from_publication(bind)

    # Zero does not support the citext type. Cast client_id to text for all
    # lead tables that are part of the publication. This is idempotent: it
    # only runs on columns that are still citext.
    for table in _ZERO_TABLES:
        if _client_id_is_citext(bind, table):
            bind.execute(
                text(
                    f'ALTER TABLE "{table}" '
                    f"ALTER COLUMN client_id TYPE text USING client_id::text"
                )
            )

    # Reconcile zero_publication now that client_id is Zero-compatible.
    apply_publication(bind)


def downgrade() -> None:
    bind = op.get_bind()

    _drop_from_publication(bind)

    for table in _ZERO_TABLES:
        # Detect text columns and cast back to citext if necessary.
        row = bind.execute(
            text(
                """
                SELECT 1
                FROM pg_catalog.pg_attribute a
                JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
                JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_catalog.pg_type t ON t.oid = a.atttypid
                WHERE n.nspname = current_schema()
                  AND c.relname = :table
                  AND a.attname = 'client_id'
                  AND a.attnum > 0
                  AND NOT a.attisdropped
                  AND t.typname = 'text'
                """
            ),
            {"table": table},
        ).fetchone()
        if row:
            bind.execute(
                text(
                    f'ALTER TABLE "{table}" '
                    f"ALTER COLUMN client_id TYPE citext USING client_id::citext"
                )
            )

    apply_publication(bind)
