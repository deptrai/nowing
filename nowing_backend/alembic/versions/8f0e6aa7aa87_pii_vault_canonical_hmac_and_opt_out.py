"""pii vault canonical hmac and opt out

Revision ID: 8f0e6aa7aa87
Revises: 49988ab02307
Create Date: 2026-08-18 13:21:45.286588

"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

logger = logging.getLogger("alembic.runtime.migration")

# revision identifiers, used by Alembic.
revision: str = "8f0e6aa7aa87"
down_revision: str | None = "49988ab02307"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _backfill_verified_contacts(conn) -> None:
    """Backfill canonical HMAC and blind indexes for existing verified contacts."""
    try:
        from app.config import config
        from app.lead_intelligence.dnc.normalizer import (
            compute_email_hmac,
            compute_phone_hmac,
            compute_verified_contact_hmac,
            normalize_email,
            normalize_phone_e164,
        )
        from app.services.pii.verified_contact_encryption import (
            VerifiedContactEncryption,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Cannot import backfill helpers; skipping: %s", exc)
        return

    if not config.SECRET_KEY:
        logger.warning("SECRET_KEY not set; skipping PII backfill.")
        return

    enc = VerifiedContactEncryption()

    def _plain(value: str | None) -> str | None:
        if not value:
            return None
        if enc.is_encrypted(value):
            try:
                return enc.decrypt(value)
            except Exception:
                return None
        return value

    batch_size = 500
    last_id: UUID | None = None
    total = 0

    while True:
        where_clause = "id > :last_id" if last_id is not None else "1=1"
        rows = conn.execute(
            text(
                f"""
                SELECT id, workspace_id, phone, email, value_hmac,
                       phone_hmac, email_hmac, lead_id
                FROM verified_contacts
                WHERE {where_clause}
                ORDER BY id
                LIMIT :batch_size
                """
            ),
            {"last_id": last_id, "batch_size": batch_size},
        ).fetchall()

        if not rows:
            break

        updates = []
        for row in rows:
            (
                contact_id,
                _workspace_id,
                phone,
                email,
                value_hmac,
                phone_hmac,
                email_hmac,
                lead_id,
            ) = row

            plain_phone = _plain(phone)
            plain_email = _plain(email)

            # Resolve lead domain for canonical HMAC.
            domain = None
            if lead_id is not None:
                domain_row = conn.execute(
                    text("SELECT domain FROM leads WHERE id = :lead_id"),
                    {"lead_id": lead_id},
                ).fetchone()
                if domain_row:
                    domain = domain_row[0]

            new_value_hmac = value_hmac or compute_verified_contact_hmac(
                plain_phone, plain_email, domain
            )
            new_phone_hmac = phone_hmac or compute_phone_hmac(
                normalize_phone_e164(plain_phone)
            )
            new_email_hmac = email_hmac or compute_email_hmac(
                normalize_email(plain_email)
            )

            if (
                new_value_hmac != value_hmac
                or new_phone_hmac != phone_hmac
                or new_email_hmac != email_hmac
            ):
                updates.append(
                    {
                        "id": contact_id,
                        "value_hmac": new_value_hmac,
                        "phone_hmac": new_phone_hmac,
                        "email_hmac": new_email_hmac,
                    }
                )

            last_id = contact_id

        if updates:
            conn.execute(
                text(
                    """
                    UPDATE verified_contacts
                    SET value_hmac = :value_hmac,
                        phone_hmac = :phone_hmac,
                        email_hmac = :email_hmac
                    WHERE id = :id
                    """
                ),
                updates,
            )
            total += len(updates)

    logger.info("Backfilled %d verified_contacts HMAC rows.", total)


def _backfill_leads(conn) -> None:
    """Backfill lead value_hmac for rows missing the canonical hash."""
    try:
        from app.lead_intelligence.services.lead_stream_service import (
            generate_lead_hmac,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Cannot import lead HMAC helper; skipping: %s", exc)
        return

    batch_size = 500
    last_id: UUID | None = None
    total = 0

    while True:
        where_clause = "id > :last_id" if last_id is not None else "1=1"
        rows = conn.execute(
            text(
                f"""
                SELECT id, workspace_id, company_name, domain
                FROM leads
                WHERE value_hmac IS NULL AND {where_clause}
                ORDER BY id
                LIMIT :batch_size
                """
            ),
            {"last_id": last_id, "batch_size": batch_size},
        ).fetchall()

        if not rows:
            break

        updates = []
        for row in rows:
            lead_id, workspace_id, company_name, domain = row
            company = company_name or "Doanh nghiệp"
            hmac = generate_lead_hmac(workspace_id, company, domain)
            updates.append({"id": lead_id, "value_hmac": hmac})
            last_id = lead_id

        if updates:
            conn.execute(
                text("UPDATE leads SET value_hmac = :value_hmac WHERE id = :id"),
                updates,
            )
            total += len(updates)

    logger.info("Backfilled %d leads value_hmac rows.", total)


def _column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = :table AND column_name = :column
            """
        ),
        {"table": table, "column": column},
    ).fetchone()
    return result is not None


def _index_exists(conn, table: str, index: str) -> bool:
    result = conn.execute(
        text(
            """
            SELECT 1
            FROM pg_indexes
            WHERE tablename = :table AND indexname = :index
            """
        ),
        {"table": table, "index": index},
    ).fetchone()
    return result is not None


def _constraint_exists(conn, table: str, constraint: str) -> bool:
    result = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.table_constraints
            WHERE table_name = :table AND constraint_name = :constraint
            """
        ),
        {"table": table, "constraint": constraint},
    ).fetchone()
    return result is not None


def upgrade() -> None:
    conn = op.get_bind()

    # 0. Add value_hmac to leads if it does not exist yet (e.g. unpartitioned
    #    table without the canonical hash column).
    if not _column_exists(conn, "leads", "value_hmac"):
        op.add_column(
            "leads",
            sa.Column("value_hmac", sa.String(64), nullable=True),
        )

    # 1. Add blind-index columns to verified_contacts if they do not exist yet.
    if not _column_exists(conn, "verified_contacts", "phone_hmac"):
        op.add_column(
            "verified_contacts",
            sa.Column("phone_hmac", sa.String(64), nullable=True),
        )
    if not _column_exists(conn, "verified_contacts", "email_hmac"):
        op.add_column(
            "verified_contacts",
            sa.Column("email_hmac", sa.String(64), nullable=True),
        )

    # 2. Ensure value_hmac is nullable on verified_contacts (opt-out clears it)
    #    and add refunded_at for opt-out refund tracking.
    op.alter_column(
        "verified_contacts",
        "value_hmac",
        existing_type=sa.String(64),
        nullable=True,
    )
    if not _column_exists(conn, "verified_contacts", "refunded_at"):
        op.add_column(
            "verified_contacts",
            sa.Column("refunded_at", sa.TIMESTAMP(timezone=True), nullable=True),
        )

    # 3. Backfill canonical HMACs for existing rows.
    _backfill_verified_contacts(conn)
    _backfill_leads(conn)

    # 4. Enforce leads.value_hmac NOT NULL after backfill.
    op.alter_column(
        "leads",
        "value_hmac",
        existing_type=sa.String(64),
        nullable=False,
    )

    # 5. Replace the partial unique index on verified_contacts with a full
    #    unique constraint that still permits multiple NULLs in PostgreSQL.
    if _index_exists(conn, "verified_contacts", "ix_verified_contacts_value_hmac"):
        op.drop_index("ix_verified_contacts_value_hmac", table_name="verified_contacts")
    if not _constraint_exists(
        conn, "verified_contacts", "uq_verified_contacts_workspace_hmac"
    ):
        op.create_unique_constraint(
            "uq_verified_contacts_workspace_hmac",
            "verified_contacts",
            ["workspace_id", "value_hmac"],
        )

    # 6. Replace the partial unique index on leads with a full unique constraint.
    if _index_exists(conn, "leads", "uq_leads_workspace_value_hmac"):
        op.drop_index("uq_leads_workspace_value_hmac", table_name="leads")
    if not _constraint_exists(conn, "leads", "uq_leads_workspace_value_hmac"):
        op.create_unique_constraint(
            "uq_leads_workspace_value_hmac",
            "leads",
            ["workspace_id", "value_hmac"],
        )

    # 7. Add workspace-specific blind indexes for verified_contacts.
    if not _index_exists(
        conn, "verified_contacts", "ix_verified_contacts_workspace_phone_hmac"
    ):
        op.create_index(
            "ix_verified_contacts_workspace_phone_hmac",
            "verified_contacts",
            ["workspace_id", "phone_hmac"],
        )
    if not _index_exists(
        conn, "verified_contacts", "ix_verified_contacts_workspace_email_hmac"
    ):
        op.create_index(
            "ix_verified_contacts_workspace_email_hmac",
            "verified_contacts",
            ["workspace_id", "email_hmac"],
        )

    # 8. Add BillingEvent lookup index for refund-cycle counting.
    if not _index_exists(
        conn, "billing_events", "ix_billing_events_workspace_type_created"
    ):
        op.create_index(
            "ix_billing_events_workspace_type_created",
            "billing_events",
            ["workspace_id", "event_type", "created_at"],
        )

    # 9. Add workspace DNC value_hmac index if missing.
    if not _index_exists(
        conn, "workspace_dnc_records", "ix_workspace_dnc_records_value_hmac"
    ):
        op.create_index(
            "ix_workspace_dnc_records_value_hmac",
            "workspace_dnc_records",
            ["value_hmac"],
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Drop new indexes.
    index_table_map = {
        "ix_workspace_dnc_records_value_hmac": "workspace_dnc_records",
        "ix_billing_events_workspace_type_created": "billing_events",
        "ix_verified_contacts_workspace_email_hmac": "verified_contacts",
        "ix_verified_contacts_workspace_phone_hmac": "verified_contacts",
    }
    for index, table in index_table_map.items():
        if _index_exists(conn, table, index):
            op.drop_index(index, table_name=table)

    # Restore partial unique indexes instead of full unique constraints.
    if _constraint_exists(conn, "leads", "uq_leads_workspace_value_hmac"):
        op.drop_constraint("uq_leads_workspace_value_hmac", table_name="leads")
    op.create_index(
        "uq_leads_workspace_value_hmac",
        "leads",
        ["workspace_id", "value_hmac"],
        unique=True,
        postgresql_where=sa.text("value_hmac IS NOT NULL"),
    )

    if _constraint_exists(
        conn, "verified_contacts", "uq_verified_contacts_workspace_hmac"
    ):
        op.drop_constraint(
            "uq_verified_contacts_workspace_hmac", table_name="verified_contacts"
        )
    op.create_index(
        "ix_verified_contacts_value_hmac",
        "verified_contacts",
        ["workspace_id", "value_hmac"],
        unique=True,
        postgresql_where=sa.text("value_hmac IS NOT NULL"),
    )

    # Restore nullability.
    op.alter_column(
        "leads",
        "value_hmac",
        existing_type=sa.String(64),
        nullable=True,
    )

    # Drop new columns.
    for column in ("email_hmac", "phone_hmac", "refunded_at"):
        if _column_exists(conn, "verified_contacts", column):
            op.drop_column("verified_contacts", column)
