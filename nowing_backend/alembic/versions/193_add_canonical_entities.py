"""add canonical entity storage with tenancy and provenance

Revision ID: 193
Revises: 192
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from app.config import config
from app.zero_publication import apply_publication

revision: str = "193"
down_revision: str | None = "192"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = config.embedding_model_instance.dimension


def _exec_statements(*statements: str) -> None:
    for stmt in statements:
        op.execute(stmt)


def upgrade() -> None:
    # ponytail: raw SQL for vector/GIN/HNSW/RLS so the migration is explicit and
    # mirrors the existing memory-table pattern (migration 177).  Functional
    # indexes are easier to review as plain DDL.
    _exec_statements(
        f"""
        CREATE TABLE canonical_entities (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            entity_type VARCHAR(64) NOT NULL,
            canonical_title VARCHAR(500),
            canonical_data JSONB NOT NULL DEFAULT '{{}}',
            fingerprint VARCHAR(255) NOT NULL,
            search_text TEXT,
            source_count INTEGER NOT NULL DEFAULT 0,
            confidence_score REAL NOT NULL DEFAULT 0.0,
            conflict_flags JSONB NOT NULL DEFAULT '[]',
            version INTEGER NOT NULL DEFAULT 1,
            first_seen_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            embedding vector({EMBEDDING_DIM}),
            embedding_model_name VARCHAR(255),
            embedding_content_hash VARCHAR(64),
            embedding_status VARCHAR(16) NOT NULL DEFAULT 'pending'
                CHECK (embedding_status IN ('pending', 'ready', 'failed')),
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE canonical_entity_sources (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            canonical_entity_id UUID NOT NULL REFERENCES canonical_entities(id) ON DELETE CASCADE,
            entity_type VARCHAR(64) NOT NULL,
            source_name VARCHAR(64) NOT NULL,
            source_record_id VARCHAR(255) NOT NULL,
            source_snapshot JSONB NOT NULL DEFAULT '{}',
            source_url TEXT,
            source_fingerprint VARCHAR(255),
            first_seen_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE canonical_merge_history (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            canonical_entity_id UUID NOT NULL REFERENCES canonical_entities(id) ON DELETE CASCADE,
            workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            entity_type VARCHAR(64) NOT NULL,
            previous_version INTEGER NOT NULL,
            new_version INTEGER NOT NULL,
            previous_data JSONB NOT NULL DEFAULT '{}',
            new_data JSONB NOT NULL DEFAULT '{}',
            previous_source_ids JSONB NOT NULL DEFAULT '[]',
            new_source_ids JSONB NOT NULL DEFAULT '[]',
            operation VARCHAR(64) NOT NULL,
            actor VARCHAR(255),
            conflicts JSONB NOT NULL DEFAULT '[]',
            method VARCHAR(64),
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE canonical_persist_outbox (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            entity_type VARCHAR(64) NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}',
            status VARCHAR(16) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'processing', 'failed', 'done')),
            retry_count INTEGER NOT NULL DEFAULT 0,
            next_attempt_at TIMESTAMP WITH TIME ZONE,
            error TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
        """,
    )

    _exec_statements(
        "CREATE UNIQUE INDEX uq_canonical_entities_workspace_type_fingerprint ON canonical_entities (workspace_id, entity_type, fingerprint);",
        "CREATE INDEX ix_canonical_entities_workspace_type_last_seen ON canonical_entities (workspace_id, entity_type, last_seen_at DESC);",
        "CREATE INDEX ix_canonical_entities_search_text ON canonical_entities USING gin (to_tsvector('english', search_text));",
        "CREATE INDEX ix_canonical_entities_embedding ON canonical_entities USING hnsw (embedding public.vector_cosine_ops) WHERE embedding IS NOT NULL;",
        "CREATE INDEX ix_canonical_entity_sources_canonical_entity_id ON canonical_entity_sources (canonical_entity_id);",
        "CREATE UNIQUE INDEX uq_canonical_entity_sources_workspace_type_source_record ON canonical_entity_sources (workspace_id, entity_type, source_name, source_record_id);",
        "CREATE INDEX ix_canonical_merge_history_entity_created ON canonical_merge_history (canonical_entity_id, created_at);",
        "CREATE INDEX ix_canonical_persist_outbox_status_next_attempt ON canonical_persist_outbox (status, next_attempt_at);",
    )

    # RLS: every canonical table is tenant-scoped to app.workspace_id.
    for table in (
        "canonical_entities",
        "canonical_entity_sources",
        "canonical_merge_history",
        "canonical_persist_outbox",
    ):
        _exec_statements(
            f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;",
            f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;",
            f"""
            CREATE POLICY {table}_tenant_isolation_policy ON {table}
            FOR ALL
            USING (
                workspace_id = (NULLIF(current_setting('app.workspace_id', true), '')::integer)
            )
            WITH CHECK (
                workspace_id = (NULLIF(current_setting('app.workspace_id', true), '')::integer)
            );
            """,
        )

    # Reconcile zero_publication with the new canonical tables.
    apply_publication(op.get_bind())


def downgrade() -> None:
    # Downgrade is safe for a database that has not accepted production writes:
    # drop the tables (and their policies/indexes/constraints) in dependency order.
    _exec_statements(
        "DROP TABLE IF EXISTS canonical_persist_outbox CASCADE;",
        "DROP TABLE IF EXISTS canonical_merge_history CASCADE;",
        "DROP TABLE IF EXISTS canonical_entity_sources CASCADE;",
        "DROP TABLE IF EXISTS canonical_entities CASCADE;",
    )
    apply_publication(op.get_bind())
