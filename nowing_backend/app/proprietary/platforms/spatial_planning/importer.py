"""Spatial planning dataset importer supporting GeoJSON/Shapefile and VN-2000 to WGS84 reprojection (AD-GIS-3 / AD-GIS-5)."""

from __future__ import annotations

import hashlib
import json
import logging
from functools import lru_cache
from typing import Any

from pyproj import CRS, Transformer
from pyproj.exceptions import CRSError
from shapely.errors import ShapelyError
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.validation import make_valid

from app.proprietary.platforms.spatial_planning.models import SpatialPlanningZone

logger = logging.getLogger(__name__)

# Maximum number of vertices per geometry. Features larger than this are
# rejected rather than risking OOM or DB DoS during ST_Subdivide.
MAX_GEOMETRY_VERTICES = 500_000


def _vertex_count(geom: Any) -> int:
    """Return an approximate vertex count for the geometry."""
    try:
        # shapely 2.0+
        return int(geom.get_num_coordinates())
    except Exception:
        return 0


def compute_geometry_hash(geom: MultiPolygon | Polygon) -> str:
    """Computes deterministic SHA-256 hash of geometry WKB for idempotent storage (AD-GIS-5)."""
    return hashlib.sha256(geom.wkb).hexdigest()


def normalize_to_multipolygon(geom: Any) -> MultiPolygon:
    """Ensures geometry is valid and cast to MultiPolygon.

    Client-side normalization is a first-pass safety net. The database trigger
    `trg_spatial_planning_subdivide` re-runs `ST_MakeValid` + `ST_Subdivide`
    server-side before storage (AD-GIS-3).
    """
    try:
        if not geom.is_valid:
            geom = make_valid(geom)
    except Exception as exc:
        raise ValueError(f"Could not make geometry valid: {exc}") from exc

    if isinstance(geom, MultiPolygon):
        result = geom
    elif isinstance(geom, Polygon):
        result = MultiPolygon([geom])
    elif hasattr(geom, "geoms"):  # GeometryCollection
        polygons = [g for g in geom.geoms if isinstance(g, Polygon)]
        if not polygons:
            raise ValueError(f"GeometryCollection does not contain valid Polygons: {geom.geom_type}")
        result = MultiPolygon(polygons)
    else:
        raise ValueError(f"Unsupported geometry type: {geom.geom_type}")

    if result.is_empty:
        raise ValueError("Normalized geometry is empty after repair")

    return result


class PlanningDataImporter:
    """Ingests spatial planning layers, reprojects from VN-2000 to WGS84, and repairs geometries."""

    def __init__(self):
        self._transformers: dict[int, Transformer] = {}

    @staticmethod
    @lru_cache(maxsize=8)
    def _build_transformer(source_srid: int) -> Transformer:
        """Build and cache a pyproj Transformer for the given source SRID."""
        try:
            CRS.from_epsg(source_srid)
        except CRSError as exc:
            raise ValueError(f"Invalid source SRID {source_srid}: {exc}") from exc

        return Transformer.from_crs(f"EPSG:{source_srid}", "EPSG:4326", always_xy=True)

    def get_transformer(self, source_srid: int) -> Transformer | None:
        if source_srid == 4326:
            return None
        if source_srid not in self._transformers:
            self._transformers[source_srid] = self._build_transformer(source_srid)
        return self._transformers[source_srid]

    def transform_geometry(self, geom: Any, source_srid: int = 4326) -> MultiPolygon:
        """Reprojects shapely geometry from source SRID to WGS84 (EPSG:4326) and validates."""
        transformer = self.get_transformer(source_srid)

        if transformer is not None:
            from shapely.ops import transform
            geom = transform(transformer.transform, geom)

        return normalize_to_multipolygon(geom)

    @staticmethod
    def _parse_year(value: Any, field: str) -> int | None:
        """Coerce an optional year property to an integer or return None."""
        if value is None or value == "":
            return None
        try:
            year = int(value)
        except (TypeError, ValueError) as exc:
            logger.warning("[%s] Invalid year value %r: %s", field, value, exc)
            return None
        if year < 1900 or year > 2100:
            logger.warning("[%s] Year %d out of realistic range", field, year)
            return None
        return year

    @staticmethod
    def _parse_zone_code(props: dict[str, Any]) -> str:
        """Return a normalized zone code, raising on missing/invalid data."""
        zone_code = (
            props.get("zone_code")
            or props.get("ma_dat")
            or props.get("MA_DAT")
        )
        if not zone_code:
            raise ValueError("Missing required property: zone_code / ma_dat")
        return str(zone_code).strip().upper()

    def parse_features(
        self,
        geojson_data: dict[str, Any] | str,
        source_srid: int = 4326,
    ) -> list[SpatialPlanningZone]:
        """Parses GeoJSON features into a list of SpatialPlanningZone ORM models."""
        if isinstance(geojson_data, str):
            try:
                data = json.loads(geojson_data)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid GeoJSON JSON: {exc}") from exc
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
                logger.warning("Skipping feature with no geometry: %s", feat.get("id", "<unknown>"))
                continue

            try:
                shply_geom = shape(geom_raw)
            except (ShapelyError, TypeError, ValueError) as exc:
                logger.warning("Skipping feature with invalid geometry: %s", exc)
                continue

            if _vertex_count(shply_geom) > MAX_GEOMETRY_VERTICES:
                logger.warning(
                    "Skipping feature with too many vertices (%d > %d)",
                    _vertex_count(shply_geom),
                    MAX_GEOMETRY_VERTICES,
                )
                continue

            try:
                clean_multipoly = self.transform_geometry(shply_geom, source_srid=source_srid)
            except ValueError as exc:
                logger.warning("Skipping feature after geometry repair: %s", exc)
                continue

            poly_hash = compute_geometry_hash(clean_multipoly)

            try:
                zone_code = self._parse_zone_code(props)
            except ValueError as exc:
                logger.warning("Skipping feature: %s", exc)
                continue

            # Convert to WKT for GeoAlchemy2 insertion
            zone = SpatialPlanningZone(
                province=props.get("province") or props.get("tinh", "Việt Nam"),
                district=props.get("district") or props.get("huyen"),
                ward=props.get("ward") or props.get("xa"),
                zone_code=zone_code,
                zone_name=props.get("zone_name") or props.get("ten_quy_hoach", "Đất quy hoạch"),
                planning_period=props.get("planning_period") or props.get("ky_quy_hoach"),
                effective_year=self._parse_year(props.get("effective_year"), "effective_year"),
                expiry_year=self._parse_year(props.get("expiry_year"), "expiry_year"),
                polygon_geometry=f"SRID=4326;{clean_multipoly.wkt}",
                polygon_hash=poly_hash,
                legal_document_ref=props.get("legal_document_ref") or props.get("van_ban_phap_ly"),
            )
            parsed_zones.append(zone)

        return parsed_zones
