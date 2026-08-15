"""Database models for Spatial Planning & Land Zoning GIS (Story 10.8 / AD-GIS-1 / AD-GIS-5)."""

from __future__ import annotations

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Column,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.db import BaseModel, TimestampMixin


class SpatialPlanningZone(BaseModel, TimestampMixin):
    """Stores cadastral land zoning boundaries and planning master layers in PostGIS (AD-GIS-1)."""

    __tablename__ = "spatial_planning_zones"

    # BigInteger primary key matching ARCHITECTURE-SPINE DDL
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    province = Column(String(100), nullable=False)
    district = Column(String(100), nullable=True)
    ward = Column(String(100), nullable=True)

    # Zoning classification code (e.g. 'ODT', 'ONT', 'CLN', 'DGT', 'CX', 'TMD')
    zone_code = Column(String(20), nullable=False, index=True)
    zone_name = Column(Text, nullable=False)
    planning_period = Column(String(50), nullable=True)  # e.g. '2021-2030'
    effective_year = Column(Integer, nullable=True)
    expiry_year = Column(Integer, nullable=True)

    # PostGIS MultiPolygon in WGS84 (SRID 4326) with GIST spatial index
    polygon_geometry = Column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True),
        nullable=False,
    )

    # Hash SHA-256 for idempotent deduplication (AD-GIS-5)
    polygon_hash = Column(String(64), nullable=False)
    legal_document_ref = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "province",
            "district",
            "zone_code",
            "polygon_hash",
            name="uq_spatial_planning_polygon",
        ),
        Index("idx_spatial_planning_gist", "polygon_geometry", postgresql_using="gist"),
        Index("idx_spatial_planning_code", "zone_code"),
        Index("idx_spatial_planning_loc", "province", "district"),
    )

    @property
    def geometry(self):
        return self.polygon_geometry

    @geometry.setter
    def geometry(self, value):
        self.polygon_geometry = value
