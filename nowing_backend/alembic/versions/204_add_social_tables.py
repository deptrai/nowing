"""add social tables (Story 21.8 / AD-SOC-1 to AD-SOC-7)

Revision ID: 204
Revises: 203
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op
from app.config import config

revision: str = "204"
down_revision: str | None = "203"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = config.embedding_model_instance.dimension


def _exec_statements(*statements: str) -> None:
    for stmt in statements:
        op.execute(text(stmt))


def upgrade() -> None:
    _exec_statements(
        """
        CREATE TABLE IF NOT EXISTS social_monitored_targets (
            id BIGSERIAL PRIMARY KEY,
            workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            platform VARCHAR(50) NOT NULL,
            target_id VARCHAR(255) NOT NULL,
            target_name TEXT NOT NULL,
            target_url TEXT,
            category VARCHAR(50) NOT NULL DEFAULT 'general',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            realtime_stream BOOLEAN NOT NULL DEFAULT FALSE,
            scrape_interval_minutes INTEGER NOT NULL DEFAULT 15,
            status VARCHAR(50) NOT NULL DEFAULT 'active',
            last_polled_at TIMESTAMPTZ,
            last_scraped_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_social_target UNIQUE (platform, target_id)
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS social_posts (
            id BIGSERIAL PRIMARY KEY,
            workspace_id INTEGER REFERENCES workspaces(id) ON DELETE CASCADE,
            target_id BIGINT REFERENCES social_monitored_targets(id) ON DELETE CASCADE,
            platform VARCHAR(50) NOT NULL,
            external_post_id VARCHAR(255) NOT NULL,
            author_name TEXT,
            author_id VARCHAR(255),
            author_url TEXT,
            post_url TEXT,
            content TEXT,
            intent_tag VARCHAR(50),
            fit_score REAL NOT NULL DEFAULT 0.0,
            reactions_count INTEGER NOT NULL DEFAULT 0,
            comments_count INTEGER NOT NULL DEFAULT 0,
            shares_count INTEGER NOT NULL DEFAULT 0,
            raw_entities JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            media_urls TEXT[],
            embedding vector({EMBEDDING_DIM}),
            published_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_social_post UNIQUE (platform, external_post_id)
        );
        """,
    )

    _exec_statements(
        "CREATE INDEX IF NOT EXISTS idx_social_targets_platform ON social_monitored_targets (platform);",
        "CREATE INDEX IF NOT EXISTS idx_social_targets_active ON social_monitored_targets (is_active);",
        "CREATE INDEX IF NOT EXISTS idx_social_targets_workspace_id ON social_monitored_targets (workspace_id);",
        "CREATE INDEX IF NOT EXISTS idx_social_posts_platform_ext ON social_posts (platform, external_post_id);",
        "CREATE INDEX IF NOT EXISTS idx_social_posts_published ON social_posts (published_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_social_posts_intent ON social_posts (intent_tag);",
        "CREATE INDEX IF NOT EXISTS idx_social_posts_gin_entities ON social_posts USING gin (raw_entities);",
        "CREATE INDEX IF NOT EXISTS idx_social_posts_embedding_hnsw ON social_posts USING hnsw (embedding public.vector_cosine_ops) WHERE embedding IS NOT NULL;",
        "CREATE INDEX IF NOT EXISTS idx_social_posts_workspace_id ON social_posts (workspace_id);",
        "CREATE INDEX IF NOT EXISTS idx_social_posts_target_id ON social_posts (target_id);",
    )


def downgrade() -> None:
    _exec_statements(
        "DROP INDEX IF EXISTS idx_social_posts_target_id;",
        "DROP INDEX IF EXISTS idx_social_posts_workspace_id;",
        "DROP INDEX IF EXISTS idx_social_posts_embedding_hnsw;",
        "DROP INDEX IF EXISTS idx_social_posts_gin_entities;",
        "DROP INDEX IF EXISTS idx_social_posts_intent;",
        "DROP INDEX IF EXISTS idx_social_posts_published;",
        "DROP INDEX IF EXISTS idx_social_posts_platform_ext;",
        "DROP INDEX IF EXISTS idx_social_targets_workspace_id;",
        "DROP INDEX IF EXISTS idx_social_targets_active;",
        "DROP INDEX IF EXISTS idx_social_targets_platform;",
        "DROP TABLE IF EXISTS social_posts CASCADE;",
        "DROP TABLE IF EXISTS social_monitored_targets CASCADE;",
    )
