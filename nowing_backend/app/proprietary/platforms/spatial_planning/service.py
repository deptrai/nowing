"""Spatial Planning Service for Land Zoning and Road Expansion Verification (Story 10.8 / AD-GIS-2 / AD-GIS-4)."""

from __future__ import annotations

import logging
import math
import time
from typing import TYPE_CHECKING

from geoalchemy2.functions import (
    ST_Intersects,
    ST_MakePoint,
    ST_SetSRID,
)
from sqlalchemy import select

from app.proprietary.platforms.spatial_planning.models import SpatialPlanningZone
from app.proprietary.platforms.spatial_planning.schemas import (
    LandZoningPolarity,
    PlanningZoneItem,
    ZoningCheckResult,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Vietnam Geographical Bounding Box Limits (WGS84 EPSG:4326)
VN_LAT_MIN = 8.5
VN_LAT_MAX = 23.5
VN_LNG_MIN = 102.0
VN_LNG_MAX = 109.5

# Cap the number of intersecting planning zones returned per query to avoid
# memory/DoS issues in dense urban areas with overlapping planning layers.
MAX_INTERSECTING_ZONES = 50


class CoordinateValidationError(ValueError):
    """Raised when latitude/longitude coordinates violate geographical boundary invariants."""
    pass


def validate_vietnam_coordinates(lat: float, lng: float) -> tuple[float, float]:
    """Validates that (lat, lng) falls within Vietnam territory and enforces order invariants (AD-GIS-2).

    Raises:
        CoordinateValidationError: If coordinates are out of bounds or swapped.
        TypeError: If coordinates are non-numeric.
    """
    if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
        raise TypeError(f"Tọa độ phải là kiểu số thực (nhận được lat={type(lat)}, lng={type(lng)})")

    if math.isnan(lat) or math.isnan(lng) or math.isinf(lat) or math.isinf(lng):
        raise CoordinateValidationError("Tọa độ không hợp lệ (NaN hoặc vô cực)")

    lat_f = float(lat)
    lng_f = float(lng)

    # Detect if user swapped latitude and longitude (e.g. passing lat=105.85, lng=21.02)
    if (VN_LNG_MIN <= lat_f <= VN_LNG_MAX) and (VN_LAT_MIN <= lng_f <= VN_LAT_MAX):
        raise CoordinateValidationError(
            f"Tọa độ có vẻ bị đảo thứ tự (latitude={lat_f}, longitude={lng_f}). "
            f"Vui lòng nhập thứ tự (vĩ độ [8.5 - 23.5], kinh độ [102.0 - 109.5])."
        )

    if not (VN_LAT_MIN <= lat_f <= VN_LAT_MAX):
        raise CoordinateValidationError(
            f"Vĩ độ (latitude={lat_f}) nằm ngoài lãnh thổ Việt Nam [{VN_LAT_MIN} - {VN_LAT_MAX}]."
        )

    if not (VN_LNG_MIN <= lng_f <= VN_LNG_MAX):
        raise CoordinateValidationError(
            f"Kinh độ (longitude={lng_f}) nằm ngoài lãnh thổ Việt Nam [{VN_LNG_MIN} - {VN_LNG_MAX}]."
        )

    return lat_f, lng_f


def classify_zone_polarity(zone_code: str, zone_name: str = "") -> tuple[LandZoningPolarity, str]:
    """Determines UI polarity and color for a zoning code (Widget U5).

    Returns:
        (polarity, color_name)
    """
    code = (zone_code or "").strip().upper()
    name_lower = (zone_name or "").lower()

    if code == "DGT" or "mở rộng đường" in name_lower or "giao thông" in name_lower:
        return LandZoningPolarity.DANGER, "red"

    if code in ("ODT", "ONT") or "đất ở" in name_lower:
        return LandZoningPolarity.SAFE, "green"

    if code in ("TMD", "SKC", "SKK", "TMDV") or "thương mại" in name_lower or "sản xuất" in name_lower:
        return LandZoningPolarity.COMMERCIAL, "blue"

    if code in ("CX", "DKV", "CVA") or "cây xanh" in name_lower or "công viên" in name_lower:
        return LandZoningPolarity.WARNING, "orange"

    if code in ("CLN", "HNK", "NTS", "RSX", "RPH", "LUC", "LUK") or "nông nghiệp" in name_lower:
        return LandZoningPolarity.AGRICULTURAL, "yellow"

    return LandZoningPolarity.OTHER, "gray"


class SpatialPlanningService:
    """Fast spatial land zoning query engine using PostGIS ST_Intersects (AD-GIS-4)."""

    def to_wkt_point(self, lat: float, lng: float) -> str:
        """PostGIS WKT representation enforcing (Longitude, Latitude) order."""
        return f"POINT({lng} {lat})"

    def build_point_sql(self, lat: float, lng: float):
        """Constructs PostGIS Point geometry expression: ST_SetSRID(ST_MakePoint(lng, lat), 4326)."""
        return ST_SetSRID(ST_MakePoint(lng, lat), 4326)

    async def check_zoning(
        self,
        session: AsyncSession,
        lat: float,
        lng: float,
        address: str | None = None,
    ) -> ZoningCheckResult:
        """Queries intersecting land zoning master layers for the given coordinates.

        Enforces AD-GIS-2 coordinate validation and AD-GIS-4 sub-10ms spatial query.
        """
        valid_lat, valid_lng = validate_vietnam_coordinates(lat, lng)

        start_time = time.perf_counter()

        # Spatial point in EPSG:4326 (Longitude first)
        point_geom = self.build_point_sql(valid_lat, valid_lng)

        stmt = (
            select(SpatialPlanningZone)
            .where(ST_Intersects(SpatialPlanningZone.polygon_geometry, point_geom))
            .limit(MAX_INTERSECTING_ZONES)
        )

        result = await session.scalars(stmt)
        zones_db = list(result.all())

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        zone_items: list[PlanningZoneItem] = []
        has_road_expansion_risk = False
        risk_notes: list[str] = []

        for z in zones_db:
            polarity, color = classify_zone_polarity(z.zone_code, z.zone_name)
            if polarity == LandZoningPolarity.DANGER or z.zone_code == "DGT":
                has_road_expansion_risk = True
                note = f"Thửa đất nằm trong chỉ giới quy hoạch: {z.zone_name} (Mã: {z.zone_code})."
                if z.legal_document_ref:
                    note += f" Căn cứ: {z.legal_document_ref}."
                risk_notes.append(note)

            zone_items.append(
                PlanningZoneItem(
                    id=z.id,
                    province=z.province,
                    district=z.district,
                    ward=z.ward,
                    zone_code=z.zone_code,
                    zone_name=z.zone_name,
                    planning_period=z.planning_period,
                    effective_year=z.effective_year,
                    expiry_year=z.expiry_year,
                    legal_document_ref=z.legal_document_ref,
                    polarity=polarity,
                    polarity_color=color,
                )
            )

        # Generate summary in Vietnamese (UX Widget U5)
        if not zone_items:
            summary = (
                f"Không tìm thấy dữ liệu quy hoạch chi tiết tại tọa độ ({valid_lat:.5f}, {valid_lng:.5f}). "
                f"Vui lòng kiểm tra bản đồ địa chính quận/huyện trực thuộc."
            )
        else:
            zone_descs = [f"{z.zone_name} ({z.zone_code})" for z in zone_items]
            summary = f"Quy hoạch phát hiện: {', '.join(zone_descs)}."
            if has_road_expansion_risk:
                summary += " CẢNH BÁO: Phát hiện rủi ro mở rộng đường / hành lang giao thông (DGT)!"
            else:
                summary += " Thửa đất an toàn, không phát hiện dính quy hoạch mở đường."

        return ZoningCheckResult(
            latitude=valid_lat,
            longitude=valid_lng,
            has_road_expansion_risk=has_road_expansion_risk,
            zones=zone_items,
            summary=summary,
            risk_notes=risk_notes,
            query_latency_ms=round(elapsed_ms, 2),
        )
