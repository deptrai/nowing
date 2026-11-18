"""252 campaign updated_at + skipped_concurrent + token_usage run-cost index

Retro bundle sau Epic 45 (accepted-with-open-items):
- AI-45.1: ``lead_campaigns.updated_at`` — TimestampMixin chỉ có created_at;
  response trước đây trả created_at làm updated_at (misleading). Column dùng
  ``server_default=now()`` cho existing rows + ``server_onupdate`` ở model
  (ORM UPDATE emit now() — Postgres không có ON UPDATE trigger native).
- AI-44.4: ``lead_campaigns.skipped_concurrent`` — tách concurrent-run skip
  khỏi ``skipped_by_quota`` (trước đây cả hai cộng chung một counter).
- AI-44.3: partial index ``token_usage`` trên
  ``call_details->>'campaign_run_id'`` — per-run cost rollup của 44.4
  (``_sum_run_cost_micros``) trước đây seq-scan toàn bảng.

Revision ID: 252
Revises: 251
Create Date: 2026-11-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "252"
down_revision = "251"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lead_campaigns",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        "lead_campaigns",
        sa.Column(
            "skipped_concurrent",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_index(
        "ix_token_usage_campaign_run_id",
        "token_usage",
        [sa.text("(call_details->>'campaign_run_id')")],
        postgresql_where=sa.text(
            "call_details->>'campaign_run_id' IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_token_usage_campaign_run_id", table_name="token_usage"
    )
    op.drop_column("lead_campaigns", "skipped_concurrent")
    op.drop_column("lead_campaigns", "updated_at")
