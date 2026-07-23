"""Add research memory tables.

Revision ID: 177
Revises: 176

Changes:
1. Create enum types memory_type, memory_source_type, memory_relation_type.
2. Create research_threads, memories, memory_versions, memory_relations tables.
3. Add new_chat_threads.research_thread_id.
4. Backfill memory permissions into workspace_roles system roles.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from app.config import config

revision: str = "177"
down_revision: str | None = "176"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = config.embedding_model_instance.dimension


def _execute_statements(*statements: str) -> None:
    for stmt in statements:
        op.execute(stmt)


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'memory_type') THEN
                CREATE TYPE memory_type AS ENUM ('semantic', 'episodic', 'procedural', 'working');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'memory_source_type') THEN
                CREATE TYPE memory_source_type AS ENUM ('document', 'chat_message', 'scraper_run', 'manual', 'unknown');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'memory_relation_type') THEN
                CREATE TYPE memory_relation_type AS ENUM ('related', 'derived_from', 'corrects', 'source_document', 'source_chat', 'source_run');
            END IF;
        END$$;
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS research_threads (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            created_by_id UUID REFERENCES "user"(id) ON DELETE SET NULL,
            title VARCHAR(500),
            current_chat_thread_id INTEGER REFERENCES new_chat_threads(id) ON DELETE SET NULL
        );
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS memories (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            workspace_id INTEGER REFERENCES workspaces(id) ON DELETE CASCADE,
            created_by_id UUID REFERENCES "user"(id) ON DELETE SET NULL,
            research_thread_id INTEGER REFERENCES research_threads(id) ON DELETE SET NULL,
            type memory_type NOT NULL DEFAULT 'semantic',
            content TEXT NOT NULL,
            embedding vector({EMBEDDING_DIM}) NOT NULL,
            source_type memory_source_type NOT NULL DEFAULT 'unknown',
            source_id INTEGER,
            tags VARCHAR(255)[],
            confidence REAL NOT NULL DEFAULT 1.0
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_versions (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            memory_id INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
            previous_content TEXT NOT NULL,
            corrected_content TEXT NOT NULL,
            corrected_by_id UUID REFERENCES "user"(id) ON DELETE SET NULL
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_relations (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            from_memory_id INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
            to_memory_id INTEGER,
            relation_type memory_relation_type NOT NULL,
            weight REAL NOT NULL DEFAULT 1.0
        );
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'new_chat_threads'
                  AND column_name = 'research_thread_id'
            ) THEN
                ALTER TABLE new_chat_threads ADD COLUMN research_thread_id INTEGER
                    REFERENCES research_threads(id) ON DELETE SET NULL;
            END IF;
        END$$;
        """
    )

    _execute_statements(
        "CREATE INDEX IF NOT EXISTS ix_memories_workspace_id ON memories(workspace_id);",
        "CREATE INDEX IF NOT EXISTS ix_memories_created_by_id ON memories(created_by_id);",
        "CREATE INDEX IF NOT EXISTS ix_memories_research_thread_id ON memories(research_thread_id);",
        "CREATE INDEX IF NOT EXISTS ix_memories_type ON memories(type);",
        "CREATE INDEX IF NOT EXISTS ix_memories_source_id ON memories(source_id);",
        "CREATE INDEX IF NOT EXISTS ix_memories_tags ON memories USING gin(tags);",
        "CREATE INDEX IF NOT EXISTS ix_memories_embedding ON memories USING hnsw (embedding public.vector_cosine_ops);",
        "CREATE INDEX IF NOT EXISTS ix_memories_content_search ON memories USING gin (to_tsvector('english', content));",
        "CREATE INDEX IF NOT EXISTS ix_memory_versions_memory_id ON memory_versions(memory_id);",
        "CREATE INDEX IF NOT EXISTS ix_memory_relations_workspace_id ON memory_relations(workspace_id);",
        "CREATE INDEX IF NOT EXISTS ix_memory_relations_from_memory_id ON memory_relations(from_memory_id);",
        "CREATE INDEX IF NOT EXISTS ix_memory_relations_to_memory_id ON memory_relations(to_memory_id);",
        "CREATE INDEX IF NOT EXISTS ix_research_threads_workspace_id ON research_threads(workspace_id);",
        "CREATE INDEX IF NOT EXISTS ix_research_threads_created_by_id ON research_threads(created_by_id);",
        "CREATE INDEX IF NOT EXISTS ix_research_threads_current_chat_thread_id ON research_threads(current_chat_thread_id);",
    )

    # Backfill memory permissions for system roles.
    _execute_statements(
        "UPDATE workspace_roles SET permissions = array_append(permissions, 'memory:read') WHERE is_system_role = true AND name IN ('Owner', 'Editor', 'Viewer') AND NOT ('memory:read' = ANY(permissions));",
        "UPDATE workspace_roles SET permissions = array_append(permissions, 'memory:create') WHERE is_system_role = true AND name IN ('Owner', 'Editor') AND NOT ('memory:create' = ANY(permissions));",
        "UPDATE workspace_roles SET permissions = array_append(permissions, 'memory:update') WHERE is_system_role = true AND name IN ('Owner', 'Editor') AND NOT ('memory:update' = ANY(permissions));",
        "UPDATE workspace_roles SET permissions = array_append(permissions, 'memory:delete') WHERE is_system_role = true AND name = 'Owner' AND NOT ('memory:delete' = ANY(permissions));",
    )


def downgrade() -> None:
    op.execute("ALTER TABLE new_chat_threads DROP COLUMN IF EXISTS research_thread_id;")
    op.execute("DROP INDEX IF EXISTS ix_research_threads_current_chat_thread_id;")
    op.execute("DROP INDEX IF EXISTS ix_research_threads_created_by_id;")
    op.execute("DROP INDEX IF EXISTS ix_research_threads_workspace_id;")
    op.execute("DROP INDEX IF EXISTS ix_memory_relations_to_memory_id;")
    op.execute("DROP INDEX IF EXISTS ix_memory_relations_from_memory_id;")
    op.execute("DROP INDEX IF EXISTS ix_memory_relations_workspace_id;")
    op.execute("DROP INDEX IF EXISTS ix_memory_versions_memory_id;")
    op.execute("DROP INDEX IF EXISTS ix_memories_content_search;")
    op.execute("DROP INDEX IF EXISTS ix_memories_embedding;")
    op.execute("DROP INDEX IF EXISTS ix_memories_tags;")
    op.execute("DROP INDEX IF EXISTS ix_memories_source_id;")
    op.execute("DROP INDEX IF EXISTS ix_memories_type;")
    op.execute("DROP INDEX IF EXISTS ix_memories_research_thread_id;")
    op.execute("DROP INDEX IF EXISTS ix_memories_created_by_id;")
    op.execute("DROP INDEX IF EXISTS ix_memories_workspace_id;")
    op.execute("DROP TABLE IF EXISTS memory_relations CASCADE;")
    op.execute("DROP TABLE IF EXISTS memory_versions CASCADE;")
    op.execute("DROP TABLE IF EXISTS memories CASCADE;")
    op.execute("DROP TABLE IF EXISTS research_threads CASCADE;")
