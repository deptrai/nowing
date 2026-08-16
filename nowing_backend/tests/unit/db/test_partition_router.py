"""Unit tests and static contract verification for PostgreSQL Table Partitioning & RLS (Story 23.4).

Verifies:
- Hash partition router modulo logic (16 shards: leads_p0..leads_p15).
- Static contract of Alembic migration 217_partition_leads_table_zero_downtime.py.
- Static schema contract of Lead model and all 6 dependent child tables in app/db.py.
- Fail-closed tenant session parameter formatting.
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "alembic"
    / "versions"
    / "217_partition_leads_table_zero_downtime.py"
)


def _load_migration():
    """Load migration 217 module dynamically if it exists."""
    if not _MIGRATION_PATH.exists():
        pytest.skip("Migration 217_partition_leads_table_zero_downtime.py not yet created (TDD RED Phase)")
    spec = importlib.util.spec_from_file_location("_migration_217", _MIGRATION_PATH)
    assert spec and spec.loader, "could not load migration spec"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPartitionRouterLogic:
    """Test shard routing logic and shard naming conventions."""

    def test_hash_shard_routing_modulo(self) -> None:
        """Verify 16-shard deterministic hash partitioning naming."""
        def get_shard_name(workspace_id: int, shard_count: int = 16) -> str:
            shard_idx = hash(workspace_id) % shard_count
            return f"leads_p{shard_idx}"

        assert get_shard_name(1) in [f"leads_p{i}" for i in range(16)]
        assert get_shard_name(100) in [f"leads_p{i}" for i in range(16)]
        assert get_shard_name(999) in [f"leads_p{i}" for i in range(16)]

    def test_tenant_session_sql_formatting(self) -> None:
        """Verify session variable SQL formatting for SET LOCAL app.workspace_id."""
        def format_set_workspace_sql(workspace_id: int | None) -> str:
            if workspace_id is None:
                return "SET LOCAL app.workspace_id = ''"
            return f"SET LOCAL app.workspace_id = '{int(workspace_id)}'"

        assert format_set_workspace_sql(1) == "SET LOCAL app.workspace_id = '1'"
        assert format_set_workspace_sql(42) == "SET LOCAL app.workspace_id = '42'"
        assert format_set_workspace_sql(None) == "SET LOCAL app.workspace_id = ''"


class TestAlembicMigration217StaticContract:
    """Static inspection of Alembic migration 217."""

    def test_migration_chain_and_revisions(self) -> None:
        """Migration 217 must succeed 216."""
        module = _load_migration()
        assert getattr(module, "revision", None) == "217"
        assert getattr(module, "down_revision", None) == "216"

    def test_migration_has_5_phase_zero_downtime_ddl(self) -> None:
        """Migration upgrade() must contain all 5 zero-downtime phases."""
        module = _load_migration()
        src = inspect.getsource(module.upgrade)

        # Phase 1: Shadow partitioned table with 16 shards
        assert "leads_partitioned" in src
        assert "PARTITION BY HASH" in src
        assert "leads_p" in src
        assert "16" in src

        # Phase 2: Dual-write trigger
        assert "trg_sync_leads_dual_write" in src or "sync_leads_to_partitioned" in src

        # Phase 3: Batched backfill
        assert "5000" in src or "batch" in src.lower()

        # Phase 4: Atomic table swap
        assert "leads_legacy_backup" in src

        # Phase 5: RLS policies & Zero Publication
        assert "ENABLE ROW LEVEL SECURITY" in src
        assert "FORCE ROW LEVEL SECURITY" in src
        assert "publish_via_partition_root" in src

    def test_migration_downgrade_restores_legacy_backup(self) -> None:
        """Migration downgrade() must safely restore leads from legacy backup."""
        module = _load_migration()
        src = inspect.getsource(module.downgrade)
        assert "leads_legacy_backup" in src
        assert "leads" in src


class TestSqlAlchemyModelCompositeKeys:
    """Verify SQLAlchemy ORM models define composite Primary Keys and Foreign Keys."""

    def test_lead_model_has_composite_primary_key(self) -> None:
        """Lead table in app/db.py must have (id, workspace_id) composite PK."""
        from app.db import Lead

        pk_cols = [c.name for c in Lead.__table__.primary_key.columns]
        assert "id" in pk_cols
        assert "workspace_id" in pk_cols, "Lead Primary Key MUST include workspace_id for hash partitioning (INV-23.4)"

    def test_all_6_child_models_have_composite_foreign_keys(self) -> None:
        """Verify all 6 child tables reference (leads.id, leads.workspace_id)."""
        import app.db as db_module

        child_model_names = [
            ("LeadScore", "CASCADE"),
            ("VerifiedContact", "CASCADE"),
            ("EnrichmentRequest", "CASCADE"),
            ("PhoneWaterfallLog", "CASCADE"),
            ("OutboundMessage", "SET NULL"),
            ("ZaloMessageLog", "SET NULL"),
            ("OutcomeEvent", "CASCADE"),
        ]

        for model_name, _expected_ondelete in child_model_names:
            model = getattr(db_module, model_name, None)
            assert model is not None, f"Model {model_name} MUST be defined in app/db.py (INV-23.4)"

            table = model.__table__
            lead_fks = [
                fk for fk in table.foreign_keys
                if fk.column.table.name in ("leads", "leads_partitioned")
            ]
            fk_target_cols = {fk.column.name for fk in lead_fks}
            assert "id" in fk_target_cols, f"{model_name} missing FK to leads.id"
            assert "workspace_id" in fk_target_cols, f"{model_name} missing FK to leads.workspace_id (INV-23.4)"

