"""Unit tests for Spatial Planning Service and Data Importer (Story 10.8 / AD-GIS-1 to AD-GIS-5)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from shapely.geometry import Polygon, mapping

from app.proprietary.platforms.spatial_planning.importer import PlanningDataImporter
from app.proprietary.platforms.spatial_planning.models import SpatialPlanningZone
from app.proprietary.platforms.spatial_planning.schemas import (
    LandZoningPolarity,
    ZoningCheckResult,
)
from app.proprietary.platforms.spatial_planning.service import (
    MAX_RISK_NOTES,
    MAX_SUMMARY_LENGTH,
    SpatialPlanningService,
)

pytestmark = pytest.mark.unit


class TestSpatialPlanningService:
    """AC-2 & AC-3: Spatial intersection queries and zoning risk evaluation."""

    @pytest.mark.asyncio
    async def test_check_zoning_residential_odt(self):
        """Test coordinate query returning residential ODT zone (safe, green polarity)."""
        service = SpatialPlanningService()
        mock_session = AsyncMock()

        # Mock query return
        mock_zone = SpatialPlanningZone(
            id=1,
            province="Hà Nội",
            district="Cầu Giấy",
            ward="Yên Hòa",
            zone_code="ODT",
            zone_name="Đất ở đô thị",
            planning_period="2021-2030",
            effective_year=2021,
            expiry_year=2030,
            polygon_hash="hash_odt_123",
            legal_document_ref="Quyết định 1234/QĐ-UBND",
        )

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_zone]
        mock_session.scalars.return_value = mock_scalars

        result: ZoningCheckResult = await service.check_zoning(
            session=mock_session,
            lat=21.0285,
            lng=105.8542,
        )

        assert result.has_road_expansion_risk is False
        assert len(result.zones) == 1
        assert result.zones[0].zone_code == "ODT"
        assert result.zones[0].polarity == LandZoningPolarity.SAFE
        assert "Đất ở đô thị" in result.summary

    @pytest.mark.asyncio
    async def test_check_zoning_road_expansion_dgt_risk(self):
        """Test coordinate query intersecting DGT zone (road expansion clearance risk)."""
        service = SpatialPlanningService()
        mock_session = AsyncMock()

        mock_zone_odt = SpatialPlanningZone(
            id=1,
            province="Hà Nội",
            district="Cầu Giấy",
            ward="Yên Hòa",
            zone_code="ODT",
            zone_name="Đất ở đô thị",
            planning_period="2021-2030",
            polygon_hash="hash_odt_1",
        )
        mock_zone_dgt = SpatialPlanningZone(
            id=2,
            province="Hà Nội",
            district="Cầu Giấy",
            ward="Yên Hòa",
            zone_code="DGT",
            zone_name="Đất giao thông (Mở rộng đường 20m)",
            planning_period="2021-2030",
            polygon_hash="hash_dgt_2",
            legal_document_ref="Quy hoạch phân khu H2-2",
        )

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_zone_odt, mock_zone_dgt]
        mock_session.scalars.return_value = mock_scalars

        result: ZoningCheckResult = await service.check_zoning(
            session=mock_session,
            lat=21.0285,
            lng=105.8542,
        )

        assert result.has_road_expansion_risk is True
        assert len(result.zones) == 2
        dgt_zone = next(z for z in result.zones if z.zone_code == "DGT")
        assert dgt_zone.polarity == LandZoningPolarity.DANGER
        assert len(result.risk_notes) > 0
        assert any("mở rộng đường" in note.lower() or "dgt" in note.lower() for note in result.risk_notes)

    @pytest.mark.asyncio
    async def test_check_zoning_commercial_and_greenery(self):
        """Test classification of commercial (TMD/SKC) and greenery (CX) zones."""
        service = SpatialPlanningService()
        mock_session = AsyncMock()

        mock_tmd = SpatialPlanningZone(
            id=3,
            province="TP. Hồ Chí Minh",
            district="Quận 1",
            ward="Bến Nghé",
            zone_code="TMD",
            zone_name="Đất thương mại dịch vụ",
            planning_period="2021-2030",
            polygon_hash="hash_tmd",
        )
        mock_cx = SpatialPlanningZone(
            id=4,
            province="TP. Hồ Chí Minh",
            district="Quận 1",
            ward="Bến Nghé",
            zone_code="CX",
            zone_name="Đất cây xanh công cộng",
            planning_period="2021-2030",
            polygon_hash="hash_cx",
        )

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_tmd, mock_cx]
        mock_session.scalars.return_value = mock_scalars

        result: ZoningCheckResult = await service.check_zoning(
            session=mock_session,
            lat=10.7769,
            lng=106.7009,
        )

        tmd_zone = next(z for z in result.zones if z.zone_code == "TMD")
        cx_zone = next(z for z in result.zones if z.zone_code == "CX")

        assert tmd_zone.polarity == LandZoningPolarity.COMMERCIAL
        assert cx_zone.polarity == LandZoningPolarity.WARNING

    @pytest.mark.asyncio
    async def test_check_zoning_caps_summary_and_risk_notes(self):
        """Large result sets are capped to avoid oversized response strings."""
        service = SpatialPlanningService()
        mock_session = AsyncMock()

        mock_zones = [
            SpatialPlanningZone(
                id=i,
                province="Hà Nội",
                district="Cầu Giấy",
                ward="Yên Hòa",
                zone_code="DGT",
                zone_name=f"Đất giao thông phần {i}",
                planning_period="2021-2030",
                polygon_hash=f"hash_{i}",
            )
            for i in range(100)
        ]

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_zones
        mock_session.scalars.return_value = mock_scalars

        result = await service.check_zoning(
            session=mock_session,
            lat=21.0285,
            lng=105.8542,
        )

        assert result.has_road_expansion_risk is True
        assert len(result.zones) == 100
        assert len(result.risk_notes) == MAX_RISK_NOTES
        assert len(result.summary) <= MAX_SUMMARY_LENGTH

    @pytest.mark.asyncio
    async def test_check_zoning_empty_results(self):
        """Test behavior when no spatial zones intersect the given coordinates."""
        service = SpatialPlanningService()
        mock_session = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_session.scalars.return_value = mock_scalars

        result: ZoningCheckResult = await service.check_zoning(
            session=mock_session,
            lat=21.0285,
            lng=105.8542,
        )

        assert result.has_road_expansion_risk is False
        assert len(result.zones) == 0
        assert "không tìm thấy" in result.summary.lower()


class TestPlanningDataImporter:
    """AC-1 & AD-GIS-3: GeoJSON ingestion, VN-2000 to WGS-84 reprojection, and geometry repair."""

    def test_import_wgs84_geojson_features(self):
        """Test importing valid WGS84 GeoJSON features."""
        importer = PlanningDataImporter()

        poly = Polygon([
            (105.8500, 21.0200),
            (105.8600, 21.0200),
            (105.8600, 21.0300),
            (105.8500, 21.0300),
            (105.8500, 21.0200),
        ])
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": mapping(poly),
                    "properties": {
                        "province": "Hà Nội",
                        "district": "Hoàn Kiếm",
                        "ward": "Hàng Trống",
                        "zone_code": "ODT",
                        "zone_name": "Đất ở đô thị",
                        "planning_period": "2021-2030",
                        "legal_document_ref": "QĐ 100/2021/QĐ-UBND",
                    },
                }
            ],
        }

        zones = importer.parse_features(geojson_data, source_srid=4326)
        assert len(zones) == 1
        zone = zones[0]
        assert zone.zone_code == "ODT"
        assert zone.province == "Hà Nội"
        assert zone.polygon_hash is not None
        assert len(zone.polygon_hash) == 64  # SHA-256

    def test_import_vn2000_reprojection(self):
        """Test reprojecting VN-2000 coordinates to WGS84 (EPSG:4326)."""
        importer = PlanningDataImporter()

        # Approximate VN-2000 UTM Zone 48N coordinates for Hanoi
        vn2000_poly = Polygon([
            (588500.0, 2325000.0),
            (589500.0, 2325000.0),
            (589500.0, 2326000.0),
            (588500.0, 2326000.0),
            (588500.0, 2325000.0),
        ])
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": mapping(vn2000_poly),
                    "properties": {
                        "province": "Hà Nội",
                        "district": "Nam Từ Liêm",
                        "ward": "Mỹ Đình 1",
                        "zone_code": "DGT",
                        "zone_name": "Đất giao thông",
                    },
                }
            ],
        }

        # Source SRID 3405 = VN-2000 / UTM zone 48N
        zones = importer.parse_features(geojson_data, source_srid=3405)
        assert len(zones) == 1
        zone = zones[0]
        assert zone.zone_code == "DGT"

    def test_geometry_self_intersection_repair(self):
        """Test self-intersecting polygon (bowtie) repair via shapely.make_valid."""
        importer = PlanningDataImporter()

        # Bowtie polygon (self-intersecting)
        invalid_poly = Polygon([
            (105.85, 21.02),
            (105.87, 21.04),
            (105.87, 21.02),
            (105.85, 21.04),
            (105.85, 21.02),
        ])
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": mapping(invalid_poly),
                    "properties": {
                        "province": "Hà Nội",
                        "district": "Cầu Giấy",
                        "zone_code": "ONT",
                        "zone_name": "Đất ở nông thôn",
                    },
                }
            ],
        }

        zones = importer.parse_features(geojson_data, source_srid=4326)
        assert len(zones) == 1
        assert zones[0].zone_code == "ONT"

    def test_parse_features_invalid_json(self):
        """Invalid JSON string is rejected gracefully."""
        importer = PlanningDataImporter()
        with pytest.raises(ValueError):
            importer.parse_features("not json", source_srid=4326)

    def test_parse_features_missing_zone_code(self):
        """Features without a zone code are skipped and not silently defaulted."""
        importer = PlanningDataImporter()
        poly = Polygon([
            (105.8500, 21.0200),
            (105.8600, 21.0200),
            (105.8600, 21.0300),
            (105.8500, 21.0300),
            (105.8500, 21.0200),
        ])
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": mapping(poly),
                    "properties": {"province": "Hà Nội", "zone_name": "Đất quy hoạch"},
                }
            ],
        }
        zones = importer.parse_features(geojson_data, source_srid=4326)
        assert zones == []

    def test_parse_features_invalid_year(self):
        """Invalid effective_year/expiry_year values are coerced to None."""
        importer = PlanningDataImporter()
        poly = Polygon([
            (105.8500, 21.0200),
            (105.8600, 21.0200),
            (105.8600, 21.0300),
            (105.8500, 21.0300),
            (105.8500, 21.0200),
        ])
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": mapping(poly),
                    "properties": {
                        "province": "Hà Nội",
                        "district": "Cầu Giấy",
                        "zone_code": "ODT",
                        "zone_name": "Đất ở đô thị",
                        "effective_year": "n/a",
                        "expiry_year": 9999,
                    },
                }
            ],
        }
        zones = importer.parse_features(geojson_data, source_srid=4326)
        assert zones[0].effective_year is None
        assert zones[0].expiry_year is None
