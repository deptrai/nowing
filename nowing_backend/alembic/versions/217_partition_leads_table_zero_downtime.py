"""partition leads table zero downtime with 16 hash shards and RLS

Revision ID: 217
Revises: 216
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "217"
down_revision: str | None = "216"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Ensure citext extension exists
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext;"))

    # =========================================================================
    # Phase 1 (Shadow Table Creation): Create leads_partitioned with 16 hash shards
    # =========================================================================
    conn.execute(
        text("""
        CREATE TABLE IF NOT EXISTS leads_partitioned (
            id UUID NOT NULL,
            workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            client_id CITEXT,
            source VARCHAR(100) NOT NULL,
            source_url TEXT,
            source_chunk_id UUID,
            company_name VARCHAR(200) NOT NULL,
            domain VARCHAR(255),
            industry VARCHAR(100),
            company_size VARCHAR(50),
            location VARCHAR(100),
            tech_stack VARCHAR[],
            fit_score FLOAT,
            intent_score FLOAT,
            composite_score FLOAT,
            status VARCHAR(50) NOT NULL DEFAULT 'new',
            enriched BOOLEAN NOT NULL DEFAULT FALSE,
            consent_status VARCHAR(50),
            legal_basis VARCHAR(50),
            table_id UUID REFERENCES workspace_tables(id) ON DELETE SET NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            PRIMARY KEY (id, workspace_id)
        ) PARTITION BY HASH (workspace_id);
        """)
    )

    # In PostgreSQL, HASH partitioning across modulus 16 exhaustively spans remainders 0..15.
    # Note: DEFAULT partition is not supported on HASH partitioned tables in PostgreSQL.
    for i in range(16):
        conn.execute(
            text(f"""
            CREATE TABLE IF NOT EXISTS leads_p{i}
            PARTITION OF leads_partitioned
            FOR VALUES WITH (MODULUS 16, REMAINDER {i});
            """)
        )

    # Shard indexes on partitioned root table
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_leads_part_ws ON leads_partitioned (workspace_id);"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_leads_part_company ON leads_partitioned (company_name);"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_leads_part_domain ON leads_partitioned (domain);"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_leads_part_status ON leads_partitioned (status);"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_leads_part_created ON leads_partitioned (created_at DESC);"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_leads_part_composite_score ON leads_partitioned (composite_score DESC);"))

    # =========================================================================
    # Phase 2 (Dual-Writing Trigger): Attach sync trigger on leads
    # =========================================================================
    conn.execute(
        text("""
        CREATE OR REPLACE FUNCTION trg_sync_leads_dual_write()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO leads_partitioned (
                    id, workspace_id, client_id, source, source_url, source_chunk_id,
                    company_name, domain, industry, company_size, location, tech_stack,
                    fit_score, intent_score, composite_score, status, enriched,
                    consent_status, legal_basis, table_id, created_at, updated_at
                ) VALUES (
                    NEW.id, NEW.workspace_id, NEW.client_id, NEW.source, NEW.source_url, NEW.source_chunk_id,
                    NEW.company_name, NEW.domain, NEW.industry, NEW.company_size, NEW.location, NEW.tech_stack,
                    NEW.fit_score, NEW.intent_score, NEW.composite_score, NEW.status, NEW.enriched,
                    NEW.consent_status, NEW.legal_basis, NEW.table_id, NEW.created_at, NEW.updated_at
                ) ON CONFLICT (id, workspace_id) DO UPDATE SET
                    client_id = EXCLUDED.client_id,
                    source = EXCLUDED.source,
                    source_url = EXCLUDED.source_url,
                    source_chunk_id = EXCLUDED.source_chunk_id,
                    company_name = EXCLUDED.company_name,
                    domain = EXCLUDED.domain,
                    industry = EXCLUDED.industry,
                    company_size = EXCLUDED.company_size,
                    location = EXCLUDED.location,
                    tech_stack = EXCLUDED.tech_stack,
                    fit_score = EXCLUDED.fit_score,
                    intent_score = EXCLUDED.intent_score,
                    composite_score = EXCLUDED.composite_score,
                    status = EXCLUDED.status,
                    enriched = EXCLUDED.enriched,
                    consent_status = EXCLUDED.consent_status,
                    legal_basis = EXCLUDED.legal_basis,
                    table_id = EXCLUDED.table_id,
                    updated_at = EXCLUDED.updated_at;
                RETURN NEW;
            ELSIF TG_OP = 'UPDATE' THEN
                IF OLD.workspace_id IS DISTINCT FROM NEW.workspace_id THEN
                    DELETE FROM leads_partitioned WHERE id = OLD.id AND workspace_id = OLD.workspace_id;
                    INSERT INTO leads_partitioned (
                        id, workspace_id, client_id, source, source_url, source_chunk_id,
                        company_name, domain, industry, company_size, location, tech_stack,
                        fit_score, intent_score, composite_score, status, enriched,
                        consent_status, legal_basis, table_id, created_at, updated_at
                    ) VALUES (
                        NEW.id, NEW.workspace_id, NEW.client_id, NEW.source, NEW.source_url, NEW.source_chunk_id,
                        NEW.company_name, NEW.domain, NEW.industry, NEW.company_size, NEW.location, NEW.tech_stack,
                        NEW.fit_score, NEW.intent_score, NEW.composite_score, NEW.status, NEW.enriched,
                        NEW.consent_status, NEW.legal_basis, NEW.table_id, NEW.created_at, NEW.updated_at
                    );
                ELSE
                    UPDATE leads_partitioned SET
                        client_id = NEW.client_id,
                        source = NEW.source,
                        source_url = NEW.source_url,
                        source_chunk_id = NEW.source_chunk_id,
                        company_name = NEW.company_name,
                        domain = NEW.domain,
                        industry = NEW.industry,
                        company_size = NEW.company_size,
                        location = NEW.location,
                        tech_stack = NEW.tech_stack,
                        fit_score = NEW.fit_score,
                        intent_score = NEW.intent_score,
                        composite_score = NEW.composite_score,
                        status = NEW.status,
                        enriched = NEW.enriched,
                        consent_status = NEW.consent_status,
                        legal_basis = NEW.legal_basis,
                        table_id = NEW.table_id,
                        updated_at = NEW.updated_at
                    WHERE id = NEW.id AND workspace_id = NEW.workspace_id;
                END IF;
                RETURN NEW;
            ELSIF TG_OP = 'DELETE' THEN
                DELETE FROM leads_partitioned WHERE id = OLD.id AND workspace_id = OLD.workspace_id;
                RETURN OLD;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """)
    )

    conn.execute(
        text("""
        DROP TRIGGER IF EXISTS sync_leads_to_partitioned_trg ON leads;
        CREATE TRIGGER sync_leads_to_partitioned_trg
        AFTER INSERT OR UPDATE OR DELETE ON leads
        FOR EACH ROW EXECUTE FUNCTION trg_sync_leads_dual_write();
        """)
    )

    # =========================================================================
    # Phase 3 (Online Batched Backfill): Backfill existing leads in batches of 5000
    # =========================================================================
    conn.execute(
        text("""
        DO $$
        DECLARE
            v_batch_size INT := 5000;
            v_last_id UUID := '00000000-0000-0000-0000-000000000000'::uuid;
            v_next_last_id UUID;
        BEGIN
            LOOP
                INSERT INTO leads_partitioned (
                    id, workspace_id, client_id, source, source_url, source_chunk_id,
                    company_name, domain, industry, company_size, location, tech_stack,
                    fit_score, intent_score, composite_score, status, enriched,
                    consent_status, legal_basis, table_id, created_at, updated_at
                )
                SELECT
                    id, workspace_id, client_id, source, source_url, source_chunk_id,
                    company_name, domain, industry, company_size, location, tech_stack,
                    fit_score, intent_score, composite_score, status, enriched,
                    consent_status, legal_basis, table_id, created_at, updated_at
                FROM leads
                WHERE id > v_last_id
                ORDER BY id ASC
                LIMIT v_batch_size
                ON CONFLICT (id, workspace_id) DO NOTHING;

                SELECT max(id) INTO v_next_last_id
                FROM (
                    SELECT id FROM leads WHERE id > v_last_id ORDER BY id ASC LIMIT v_batch_size
                ) sub;

                EXIT WHEN v_next_last_id IS NULL;
                v_last_id := v_next_last_id;
            END LOOP;
        END $$;
        """)
    )

    # =========================================================================
    # Phase 4 (Atomic Swap & FK Rewiring): Swap tables and rewire foreign keys
    # =========================================================================
    # Drop trigger
    conn.execute(text("DROP TRIGGER IF EXISTS sync_leads_to_partitioned_trg ON leads;"))
    conn.execute(text("DROP FUNCTION IF EXISTS trg_sync_leads_dual_write();"))

    # Drop old single-column foreign keys from dependent tables
    child_fks = [
        ("lead_scores", "lead_scores_lead_id_fkey"),
        ("enrichment_requests", "enrichment_requests_lead_id_fkey"),
        ("verified_contacts", "verified_contacts_lead_id_fkey"),
        ("phone_waterfall_logs", "phone_waterfall_logs_lead_id_fkey"),
        ("zalo_message_logs", "zalo_message_logs_lead_id_fkey"),
        ("outcome_events", "outcome_events_lead_id_fkey"),
    ]
    for table_name, fk_name in child_fks:
        conn.execute(text(f"ALTER TABLE IF EXISTS {table_name} DROP CONSTRAINT IF EXISTS {fk_name};"))

    # Swap tables
    conn.execute(text("ALTER TABLE leads RENAME TO leads_legacy_backup;"))
    conn.execute(text("ALTER TABLE leads_partitioned RENAME TO leads;"))

    # Add composite foreign keys to child tables
    conn.execute(
        text("""
        ALTER TABLE IF EXISTS lead_scores
            ADD CONSTRAINT fk_lead_scores_lead_id_workspace_id
            FOREIGN KEY (lead_id, workspace_id) REFERENCES leads (id, workspace_id) ON DELETE CASCADE;
        """)
    )
    conn.execute(
        text("""
        ALTER TABLE IF EXISTS enrichment_requests
            ADD CONSTRAINT fk_enrichment_requests_lead_id_workspace_id
            FOREIGN KEY (lead_id, workspace_id) REFERENCES leads (id, workspace_id) ON DELETE CASCADE;
        """)
    )
    conn.execute(
        text("""
        ALTER TABLE IF EXISTS verified_contacts
            ADD CONSTRAINT fk_verified_contacts_lead_id_workspace_id
            FOREIGN KEY (lead_id, workspace_id) REFERENCES leads (id, workspace_id) ON DELETE CASCADE;
        """)
    )
    conn.execute(
        text("""
        ALTER TABLE IF EXISTS phone_waterfall_logs
            ADD CONSTRAINT fk_phone_waterfall_logs_lead_id_workspace_id
            FOREIGN KEY (lead_id, workspace_id) REFERENCES leads (id, workspace_id) ON DELETE CASCADE;
        """)
    )
    conn.execute(
        text("""
        ALTER TABLE IF EXISTS zalo_message_logs
            ADD CONSTRAINT fk_zalo_message_logs_lead_id_workspace_id
            FOREIGN KEY (lead_id, workspace_id) REFERENCES leads (id, workspace_id) ON DELETE CASCADE;
        """)
    )
    conn.execute(
        text("""
        ALTER TABLE IF EXISTS outcome_events
            ADD CONSTRAINT fk_outcome_events_lead_id_workspace_id
            FOREIGN KEY (lead_id, workspace_id) REFERENCES leads (id, workspace_id) ON DELETE CASCADE;
        """)
    )

    # =========================================================================
    # Phase 5 (RLS & Zero-Cache Reconnect): Fail-closed policies & pubviaroot
    # =========================================================================
    conn.execute(text("ALTER TABLE leads ENABLE ROW LEVEL SECURITY;"))
    conn.execute(text("ALTER TABLE leads FORCE ROW LEVEL SECURITY;"))

    conn.execute(text("DROP POLICY IF EXISTS leads_tenant_read_policy ON leads;"))
    conn.execute(
        text("""
        CREATE POLICY leads_tenant_read_policy ON leads
            FOR SELECT
            USING (workspace_id IS NOT DISTINCT FROM NULLIF(current_setting('app.workspace_id', true), '')::int);
        """)
    )

    conn.execute(text("DROP POLICY IF EXISTS leads_tenant_write_policy ON leads;"))
    conn.execute(
        text("""
        CREATE POLICY leads_tenant_write_policy ON leads
            FOR ALL
            USING (workspace_id IS NOT DISTINCT FROM NULLIF(current_setting('app.workspace_id', true), '')::int)
            WITH CHECK (workspace_id IS NOT DISTINCT FROM NULLIF(current_setting('app.workspace_id', true), '')::int);
        """)
    )

    conn.execute(
        text("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'zero_publication') THEN
                ALTER PUBLICATION zero_publication SET (publish_via_partition_root = true);
                BEGIN
                    ALTER PUBLICATION zero_publication ADD TABLE leads;
                EXCEPTION WHEN duplicate_object THEN
                    NULL;
                END;
            END IF;
        END $$;
        """)
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Drop composite foreign keys
    composite_fks = [
        ("lead_scores", "fk_lead_scores_lead_id_workspace_id"),
        ("enrichment_requests", "fk_enrichment_requests_lead_id_workspace_id"),
        ("verified_contacts", "fk_verified_contacts_lead_id_workspace_id"),
        ("phone_waterfall_logs", "fk_phone_waterfall_logs_lead_id_workspace_id"),
        ("zalo_message_logs", "fk_zalo_message_logs_lead_id_workspace_id"),
        ("outcome_events", "fk_outcome_events_lead_id_workspace_id"),
    ]
    for table_name, fk_name in composite_fks:
        conn.execute(text(f"ALTER TABLE IF EXISTS {table_name} DROP CONSTRAINT IF EXISTS {fk_name};"))

    # Drop partitioned table
    conn.execute(text("DROP TABLE IF EXISTS leads CASCADE;"))

    # Restore legacy unpartitioned table
    conn.execute(text("ALTER TABLE IF EXISTS leads_legacy_backup RENAME TO leads;"))

    # Restore old foreign keys
    conn.execute(text("ALTER TABLE IF EXISTS lead_scores ADD CONSTRAINT lead_scores_lead_id_fkey FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE;"))
    conn.execute(text("ALTER TABLE IF EXISTS enrichment_requests ADD CONSTRAINT enrichment_requests_lead_id_fkey FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE;"))
    conn.execute(text("ALTER TABLE IF EXISTS verified_contacts ADD CONSTRAINT verified_contacts_lead_id_fkey FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE;"))
    conn.execute(text("ALTER TABLE IF EXISTS phone_waterfall_logs ADD CONSTRAINT phone_waterfall_logs_lead_id_fkey FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE;"))
    conn.execute(text("ALTER TABLE IF EXISTS zalo_message_logs ADD CONSTRAINT zalo_message_logs_lead_id_fkey FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE SET NULL;"))
    conn.execute(text("ALTER TABLE IF EXISTS outcome_events ADD CONSTRAINT outcome_events_lead_id_fkey FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE;"))
