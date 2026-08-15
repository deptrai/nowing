"""add zalo gateway tables (Story 21.6 / AD-41)

Revision ID: 212
Revises: 211
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "212"
down_revision: str | None = "211"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _exec_statements(*statements: str) -> None:
    for stmt in statements:
        op.execute(text(stmt))


def upgrade() -> None:
    _exec_statements(
        """
        CREATE TABLE IF NOT EXISTS zalo_connections (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            oa_id VARCHAR(100) NOT NULL,
            oa_name VARCHAR(255),
            app_id VARCHAR(100),
            app_secret_encrypted TEXT,
            access_token_encrypted TEXT,
            refresh_token_encrypted TEXT,
            token_expires_at TIMESTAMPTZ,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            webhook_secret VARCHAR(255),
            settings JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_workspace_zalo_oa UNIQUE (workspace_id, oa_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS zalo_message_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            zalo_connection_id UUID REFERENCES zalo_connections(id) ON DELETE SET NULL,
            lead_id UUID REFERENCES leads(id) ON DELETE SET NULL,
            recipient_phone VARCHAR(50),
            recipient_zalo_id VARCHAR(100),
            message_type VARCHAR(50) NOT NULL DEFAULT 'assisted_draft',
            template_id VARCHAR(100),
            template_data JSONB DEFAULT '{}'::jsonb,
            content TEXT NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'generated',
            external_message_id VARCHAR(255),
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_zalo_connections_workspace_id ON zalo_connections(workspace_id);",
        "CREATE INDEX IF NOT EXISTS idx_zalo_connections_oa_id ON zalo_connections(oa_id);",
        "CREATE INDEX IF NOT EXISTS idx_zalo_connections_active ON zalo_connections(is_active);",
        "CREATE INDEX IF NOT EXISTS idx_zalo_message_logs_workspace_id ON zalo_message_logs(workspace_id);",
        "CREATE INDEX IF NOT EXISTS idx_zalo_message_logs_lead_id ON zalo_message_logs(lead_id);",
        "CREATE INDEX IF NOT EXISTS idx_zalo_message_logs_phone ON zalo_message_logs(recipient_phone);",
        "CREATE INDEX IF NOT EXISTS idx_zalo_message_logs_created_at ON zalo_message_logs(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_zalo_message_logs_msg_type ON zalo_message_logs(message_type);",
    )


def downgrade() -> None:
    _exec_statements(
        "DROP TABLE IF EXISTS zalo_message_logs CASCADE;",
        "DROP TABLE IF EXISTS zalo_connections CASCADE;",
    )
