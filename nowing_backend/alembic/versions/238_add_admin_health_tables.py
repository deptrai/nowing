"""add admin third party health tables and seed alert rules

Revision ID: 238_add_admin_health_tables
Revises: 237_add_projects_and_skills
Create Date: 2026-09-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "238_add_admin_health_tables"
down_revision: str | Sequence[str] | None = "237_add_projects_and_skills"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. admin_health_status
    op.create_table(
        "admin_health_status",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("service_id", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("service_name", sa.String(255), nullable=False),
        sa.Column("display_group", sa.String(100), nullable=False, server_default="General"),
        sa.Column("status", sa.String(50), nullable=False, server_default="not_configured"),
        sa.Column("last_probe_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("next_probe_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_rate_15m", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("success_rate_15m", sa.Float(), nullable=False, server_default="100.0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("suggested_action", sa.Text(), nullable=True),
        sa.Column(
            "metadata_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("alert_threshold", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("acknowledged_until", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_admin_health_status_category", "admin_health_status", ["category"])
    op.create_index("ix_admin_health_status_status", "admin_health_status", ["status"])

    # 2. admin_health_history
    op.create_table(
        "admin_health_history",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("service_id", sa.String(255), nullable=False, index=True),
        sa.Column(
            "probe_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            index=True,
        ),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_admin_health_history_service_probe",
        "admin_health_history",
        ["service_id", "probe_at"],
    )

    # 3. admin_health_alert_rules
    alert_rules_table = op.create_table(
        "admin_health_alert_rules",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("service_id_pattern", sa.String(255), nullable=True),
        sa.Column(
            "condition_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("severity", sa.String(50), nullable=False, server_default="high"),
        sa.Column(
            "channels",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='["in_app"]',
        ),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # 4. admin_health_alerts
    op.create_table(
        "admin_health_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "rule_id",
            sa.Integer(),
            sa.ForeignKey("admin_health_alert_rules.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("service_id", sa.String(255), nullable=False, index=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="open"),
        sa.Column("severity", sa.String(50), nullable=False, server_default="high"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "triggered_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("acknowledged_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("acknowledged_until", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_admin_health_alerts_service_status",
        "admin_health_alerts",
        ["service_id", "status"],
    )

    # Seed 5 default alert rules
    op.bulk_insert(
        alert_rules_table,
        [
            {
                "name": "Core infra unavailable",
                "category": "infra",
                "service_id_pattern": None,
                "condition_json": {"status": "unavailable", "consecutive_probes": 1},
                "severity": "critical",
                "channels": ["in_app", "email"],
                "cooldown_minutes": 15,
                "enabled": True,
            },
            {
                "name": "LLM/AI model dead",
                "category": "model",
                "service_id_pattern": None,
                "condition_json": {"status": "unavailable", "consecutive_probes": 2},
                "severity": "high",
                "channels": ["in_app", "email"],
                "cooldown_minutes": 15,
                "enabled": True,
            },
            {
                "name": "Scraper degraded",
                "category": "scraper",
                "service_id_pattern": None,
                "condition_json": {"metric": "success_rate_15m", "op": "<", "threshold": 50.0},
                "severity": "medium",
                "channels": ["in_app"],
                "cooldown_minutes": 15,
                "enabled": True,
            },
            {
                "name": "Proxy dead",
                "category": "proxy",
                "service_id_pattern": None,
                "condition_json": {"status": "unavailable", "consecutive_probes": 1},
                "severity": "high",
                "channels": ["in_app", "email"],
                "cooldown_minutes": 15,
                "enabled": True,
            },
            {
                "name": "ChainLens research degraded",
                "category": "research",
                "service_id_pattern": None,
                "condition_json": {"status_not": "healthy", "consecutive_probes": 2},
                "severity": "medium",
                "channels": ["in_app"],
                "cooldown_minutes": 15,
                "enabled": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("admin_health_alerts")
    op.drop_table("admin_health_alert_rules")
    op.drop_table("admin_health_history")
    op.drop_table("admin_health_status")
