"""add lead indexing: full-text search, trigram, composite and hnsw vector

Revision ID: 235_lead_indexing_fts_and_vector
Revises: 234_add_memory_retention
Create Date: 2026-08-29 02:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "235_lead_indexing_fts_and_vector"
down_revision: str | None = "234_add_memory_retention"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Required extensions; safe to run multiple times.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 1. Generated tsvector column for multi-field Vietnamese-aware full-text search.
    op.execute(
        """
        ALTER TABLE leads
        ADD COLUMN IF NOT EXISTS search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('simple', COALESCE(company_name, '')), 'A') ||
            setweight(to_tsvector('simple', COALESCE(domain, '')), 'A') ||
            setweight(to_tsvector('simple', COALESCE(tax_id, '')), 'A') ||
            setweight(to_tsvector('simple', COALESCE(legal_representative, '')), 'B') ||
            setweight(to_tsvector('simple', COALESCE(industry, '')), 'B') ||
            setweight(to_tsvector('simple', COALESCE(location, '')), 'C') ||
            setweight(to_tsvector('simple', COALESCE(company_status, '')), 'D')
        ) STORED
        """
    )

    # 2. GIN full-text index.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_leads_search_vector_gin ON leads USING gin (search_vector)"
    )

    # 3. Trigram GIN indexes for fuzzy/partial matching.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_leads_company_name_trgm ON leads USING gin (company_name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_leads_domain_trgm ON leads USING gin (domain gin_trgm_ops) WHERE domain IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_leads_tax_id_trgm ON leads USING gin (tax_id gin_trgm_ops) WHERE tax_id IS NOT NULL"
    )

    # 4. Composite covering B-tree indexes for workspace-scoped filter+sort.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_leads_ws_table_fit_score
        ON leads (workspace_id, table_id, fit_score DESC NULLS LAST, id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_leads_ws_status_fit_score
        ON leads (workspace_id, status, fit_score DESC NULLS LAST, id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_leads_ws_stage_created
        ON leads (workspace_id, stage_id, created_at DESC, id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_leads_ws_client_fit_score
        ON leads (workspace_id, client_id, fit_score DESC NULLS LAST, id)
        WHERE client_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_leads_ws_assigned_created
        ON leads (workspace_id, assigned_to_user_id, created_at DESC, id)
        WHERE assigned_to_user_id IS NOT NULL
        """
    )

    # 5. Optional semantic vector column and HNSW index for ICP/semantic search.
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS embedding vector(1536)")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_leads_embedding_hnsw
        ON leads USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_leads_embedding_hnsw", table_name="leads", if_exists=True)
    op.drop_column("leads", "embedding", if_exists=True)

    op.drop_index("ix_leads_ws_assigned_created", table_name="leads", if_exists=True)
    op.drop_index("ix_leads_ws_client_fit_score", table_name="leads", if_exists=True)
    op.drop_index("ix_leads_ws_stage_created", table_name="leads", if_exists=True)
    op.drop_index("ix_leads_ws_status_fit_score", table_name="leads", if_exists=True)
    op.drop_index("ix_leads_ws_table_fit_score", table_name="leads", if_exists=True)

    op.drop_index("ix_leads_tax_id_trgm", table_name="leads", if_exists=True)
    op.drop_index("ix_leads_domain_trgm", table_name="leads", if_exists=True)
    op.drop_index("ix_leads_company_name_trgm", table_name="leads", if_exists=True)
    op.drop_index("ix_leads_search_vector_gin", table_name="leads", if_exists=True)

    op.drop_column("leads", "search_vector", if_exists=True)
