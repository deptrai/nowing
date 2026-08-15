"""add spatial_planning_zones table (Story 10.8)

Revision ID: 208
Revises: 207
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP

from alembic import op

revision: str = "208"
down_revision: str | None = "207"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "spatial_planning_zones",
        sa.Column("id", BigInteger, primary_key=True, autoincrement=True),
        sa.Column("province", String(100), nullable=False),
        sa.Column("district", String(100), nullable=False, server_default=""),
        sa.Column("ward", String(100), nullable=True),
        sa.Column("zone_code", String(20), nullable=False, index=True),
        sa.Column("zone_name", Text, nullable=False),
        sa.Column("planning_period", String(50), nullable=True),
        sa.Column("effective_year", Integer, nullable=True),
        sa.Column("expiry_year", Integer, nullable=True),
        sa.Column(
            "polygon_geometry",
            Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True),
            nullable=False,
        ),
        sa.Column("polygon_hash", String(64), nullable=False),
        sa.Column("legal_document_ref", Text, nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "province",
            "district",
            "zone_code",
            "polygon_hash",
            name="uq_spatial_planning_polygon",
        ),
    )

    op.create_index(
        "idx_spatial_planning_gist",
        "spatial_planning_zones",
        ["polygon_geometry"],
        postgresql_using="gist",
    )
    op.create_index(
        "idx_spatial_planning_code",
        "spatial_planning_zones",
        ["zone_code"],
    )
    op.create_index(
        "idx_spatial_planning_loc",
        "spatial_planning_zones",
        ["province", "district"],
    )

    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_spatial_planning_subdivide()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.polygon_geometry IS NOT NULL THEN
                -- Ensure the geometry is valid and contains only polygons
                NEW.polygon_geometry := ST_Multi(
                    ST_CollectionExtract(ST_MakeValid(NEW.polygon_geometry), 3)
                );

                IF NOT ST_IsEmpty(NEW.polygon_geometry) THEN
                    -- Subdivide large polygons for efficient ST_Intersects queries
                    SELECT ST_Multi(ST_Collect(geom)) INTO NEW.polygon_geometry
                    FROM ST_Subdivide(NEW.polygon_geometry, 256) AS d(geom);
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_spatial_planning_subdivide
        BEFORE INSERT OR UPDATE ON spatial_planning_zones
        FOR EACH ROW EXECUTE FUNCTION trg_spatial_planning_subdivide();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_spatial_planning_subdivide ON spatial_planning_zones")
    op.execute("DROP FUNCTION IF EXISTS trg_spatial_planning_subdivide()")
    op.drop_index("idx_spatial_planning_loc", table_name="spatial_planning_zones")
    op.drop_index("idx_spatial_planning_code", table_name="spatial_planning_zones")
    op.drop_index("idx_spatial_planning_gist", table_name="spatial_planning_zones")
    op.drop_table("spatial_planning_zones")
