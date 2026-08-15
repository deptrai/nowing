"""Spatial planning dataset importer supporting GeoJSON/Shapefile and VN-2000 to WGS84 reprojection (AD-GIS-3 / AD-GIS-5)."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from pyproj import Transformer
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.validation import make_valid

from app.proprietary.platforms.spatial_planning.models import SpatialPlanningZone

logger = logging.getLogger(__name__)


def compute_geometry_hash(geom: MultiPolygon | Polygon) -> str:
    """Computes deterministic SHA-256 hash of geometry WKB for idempotent storage (AD-GIS-5)."""
    return hashlib.sha256(geom.wkb).hexdigest()


def normalize_to_multipolygon(geom: Any) -> MultiPolygon:
    """Ensures geometry is valid and cast to MultiPolygon.

    Client-side normalization is a first-pass safety net. The database trigger
    `trg_spatial_planning_subdivide` re-runs `ST_MakeValid` + `ST_Subdivide`
    server-side before storage (AD-GIS-3).
    """
    if not geom.is_valid:
        geom = make_valid(geom)

    if isinstance(geom, MultiPolygon):
        return geom
    elif isinstance(geom, Polygon):
        return MultiPolygon([geom])
    elif hasattr(geom, "geoms"):  # GeometryCollection
        polygons = [g for g in geom.geoms if isinstance(g, Polygon)]
        if polygons:
            return MultiPolygon(polygons)
        raise ValueError(f"GeometryCollection does not contain valid Polygons: {geom.geom_type}")
    else:
        raise ValueError(f"Unsupported geometry type: {geom.geom_type}")


class PlanningDataImporter:
    """Ingests spatial planning layers, reprojects from VN-2000 to WGS84, and repairs geometries."""

    def __init__(self):
        self._transformers: dict[int, Transformer] = {}

    def get_transformer(self, source_srid: int) -> Transformer | None:
        if source_srid == 4326:
            return None
        if source_srid not in self._transformers:
            # EPSG:3405 = VN-2000 / UTM zone 48N (North/Central VN)
            # EPSG:3406 = VN-2000 / UTM zone 49N (South/East VN)
            self._transformers[source_srid] = Transformer.from_crs(
                f"EPSG:{source_srid}", "EPSG:4326", always_xy=True
            )
        return self._transformers[source_srid]

    def transform_geometry(self, geom: Any, source_srid: int = 4326) -> MultiPolygon:
        """Reprojects shapely geometry from source SRID to WGS84 (EPSG:4326) and validates."""
        transformer = self.get_transformer(source_srid)

        if transformer is not None:
            from shapely.ops import transform
            geom = transform(transformer.transform, geom)

        return normalize_to_multipolygon(geom)

    def parse_features(
        self,
        geojson_data: dict[str, Any] | str,
        source_srid: int = 4326,
    ) -> list[SpatialPlanningZone]:
        """Parses GeoJSON features into a list of SpatialPlanningZone ORM models."""
        if isinstance(geojson_data, str):
            data = json.loads(geojson_data)
        else:
            data = geojson_data

        features = data.get("features", [])
        if not features and data.get("type") == "Feature":
            features = [data]

        parsed_zones: list[SpatialPlanningZone] = []

        for feat in features:
            geom_raw = feat.get("geometry")
            props = feat.get("properties", {})

            if not geom_raw:
                continue

            shply_geom = shape(geom_raw)
            clean_multipoly = self.transform_geometry(shply_geom, source_srid=source_srid)
            poly_hash = compute_geometry_hash(clean_multipoly)

            # Convert to WKT for GeoAlchemy2 insertion
            zone = SpatialPlanningZone(
                province=props.get("province") or props.get("tinh", "Việt Nam"),
                district=props.get("district") or props.get("huyen"),
                ward=props.get("ward") or props.get("xa"),
                zone_code=str(props.get("zone_code") or props.get("ma_dat", "ODT")).upper(),
                zone_name=props.get("zone_name") or props.get("ten_quy_hoach", "Đất quy hoạch"),
                planning_period=props.get("planning_period") or props.get("ky_quy_hoach"),
                effective_year=props.get("effective_year"),
                expiry_year=props.get("expiry_year"),
                polygon_geometry=f"SRID=4326;{clean_multipoly.wkt}",
                polygon_hash=poly_hash,
                legal_document_ref=props.get("legal_document_ref") or props.get("van_ban_phap_ly"),
            )
            parsed_zones.append(zone)

        return parsed_zones
