"""Integration tests for Spatial Planning & Land Zoning GIS (Story 10.8)."""

from __future__ import annotations

import pytest
from shapely.geometry import MultiPolygon, Polygon
from sqlalchemy import text

from app.proprietary.platforms.spatial_planning.models import SpatialPlanningZone
from app.proprietary.platforms.spatial_planning.schemas import LandZoningPolarity
from app.proprietary.platforms.spatial_planning.service import SpatialPlanningService

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("platform_db_workspace")]


def _wkt(polygon: Polygon) -> str:
    return f"SRID=4326;{MultiPolygon([polygon]).wkt}"


@pytest.mark.asyncio
async def test_check_zoning_finds_intersecting_zone(platform_db_session, platform_db_workspace):
    """A point inside a stored polygon returns the expected zone and polarity."""
    polygon = Polygon([
        (105.8500, 21.0200),
        (105.8600, 21.0200),
        (105.8600, 21.0300),
        (105.8500, 21.0300),
        (105.8500, 21.0200),
    ])
    zone = SpatialPlanningZone(
        province="Hà Nội",
        district="Cầu Giấy",
        ward="Yên Hòa",
        zone_code="ODT",
        zone_name="Đất ở đô thị",
        polygon_geometry=_wkt(polygon),
        polygon_hash="hash_odt_1",
    )
    platform_db_session.add(zone)
    await platform_db_session.commit()

    service = SpatialPlanningService()
    result = await service.check_zoning(
        session=platform_db_session,
        lat=21.0250,
        lng=105.8550,
    )

    assert result.has_road_expansion_risk is False
    assert len(result.zones) == 1
    assert result.zones[0].zone_code == "ODT"
    assert result.zones[0].polarity == LandZoningPolarity.SAFE
    assert result.query_latency_ms is not None
    assert result.query_latency_ms >= 0.0


@pytest.mark.asyncio
async def test_check_zoning_detects_road_expansion_risk(platform_db_session, platform_db_workspace):
    """A DGT zone is flagged as road expansion risk."""
    polygon = Polygon([
        (105.8400, 21.0100),
        (105.8500, 21.0100),
        (105.8500, 21.0200),
        (105.8400, 21.0200),
        (105.8400, 21.0100),
    ])
    zone = SpatialPlanningZone(
        province="Hà Nội",
        district="Cầu Giấy",
        ward="Yên Hòa",
        zone_code="DGT",
        zone_name="Đất giao thông mở rộng đường 20m",
        polygon_geometry=_wkt(polygon),
        polygon_hash="hash_dgt_1",
    )
    platform_db_session.add(zone)
    await platform_db_session.commit()

    service = SpatialPlanningService()
    result = await service.check_zoning(
        session=platform_db_session,
        lat=21.0150,
        lng=105.8450,
    )

    assert result.has_road_expansion_risk is True
    assert result.zones[0].polarity == LandZoningPolarity.DANGER


@pytest.mark.asyncio
async def test_spatial_indexes_exist(platform_db_session, platform_db_workspace):
    """The spatial_planning_zones table and its GIST index were created."""
    result = await platform_db_session.execute(
        text(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename = 'spatial_planning_zones' AND indexname = 'idx_spatial_planning_gist'"
        )
    )
    assert result.scalar() == "idx_spatial_planning_gist"
