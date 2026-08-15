"""Unit tests for Vietnam coordinate bounds and ordering validation (Story 10.8 / AD-GIS-2)."""

from __future__ import annotations

import pytest

from app.proprietary.platforms.spatial_planning.service import (
    CoordinateValidationError,
    SpatialPlanningService,
    validate_vietnam_coordinates,
)

pytestmark = pytest.mark.unit


class TestCoordinateValidation:
    """AC-2: Coordinate bounds and longitude-latitude order invariant validation."""

    def test_valid_vietnam_coordinates(self):
        """Test valid coordinates in various regions of Vietnam."""
        valid_points = [
            (21.0285, 105.8542, "Hà Nội"),
            (10.8231, 106.6297, "TP. Hồ Chí Minh"),
            (16.0544, 108.2022, "Đà Nẵng"),
            (10.2899, 103.9840, "Phú Quốc"),
            (23.3927, 105.3236, "Hà Giang (Bắc)"),
            (8.6080, 104.7297, "Cà Mau (Nam)"),
            (21.3855, 102.1704, "Điện Biên (Tây)"),
            (12.6517, 109.4630, "Khánh Hòa (Đông)"),
        ]
        for lat, lng, _name in valid_points:
            norm_lat, norm_lng = validate_vietnam_coordinates(lat, lng)
            assert norm_lat == pytest.approx(lat, abs=1e-5)
            assert norm_lng == pytest.approx(lng, abs=1e-5)

    def test_latitude_out_of_bounds(self):
        """Latitude must be within [8.5, 23.5]."""
        # North of VN
        with pytest.raises(CoordinateValidationError) as exc_info:
            validate_vietnam_coordinates(24.0, 105.8)
        assert "Vĩ độ" in str(exc_info.value) or "latitude" in str(exc_info.value).lower()

        # South of VN
        with pytest.raises(CoordinateValidationError) as exc_info:
            validate_vietnam_coordinates(7.5, 105.8)
        assert "Vĩ độ" in str(exc_info.value) or "latitude" in str(exc_info.value).lower()

    def test_longitude_out_of_bounds(self):
        """Longitude must be within [102.0, 109.5]."""
        # West of VN
        with pytest.raises(CoordinateValidationError) as exc_info:
            validate_vietnam_coordinates(21.0, 101.5)
        assert "Kinh độ" in str(exc_info.value) or "longitude" in str(exc_info.value).lower()

        # East of VN
        with pytest.raises(CoordinateValidationError) as exc_info:
            validate_vietnam_coordinates(21.0, 110.5)
        assert "Kinh độ" in str(exc_info.value) or "longitude" in str(exc_info.value).lower()

    def test_swapped_coordinates_detection(self):
        """Detect when latitude and longitude are inadvertently swapped (e.g. lat=105.85, lng=21.02)."""
        with pytest.raises(CoordinateValidationError) as exc_info:
            validate_vietnam_coordinates(105.8542, 21.0285)
        err_msg = str(exc_info.value).lower()
        assert "đảo" in err_msg or "swap" in err_msg or "inverted" in err_msg or "thứ tự" in err_msg

    def test_invalid_types_and_nan(self):
        """Handle NaN, infinite values, and non-numeric inputs gracefully."""
        with pytest.raises((CoordinateValidationError, TypeError, ValueError)):
            validate_vietnam_coordinates(float("nan"), 105.8)

        with pytest.raises((CoordinateValidationError, TypeError, ValueError)):
            validate_vietnam_coordinates(21.0, float("inf"))

        with pytest.raises((CoordinateValidationError, TypeError, ValueError)):
            validate_vietnam_coordinates("21.0", 105.8)  # type: ignore

    def test_postgis_point_construction_order(self):
        """Verify that PostGIS Point construction uses (lng, lat) order: ST_MakePoint(lng, lat, 4326)."""
        service = SpatialPlanningService()
        wkt = service.to_wkt_point(lat=21.0285, lng=105.8542)
        assert wkt == "POINT(105.8542 21.0285)"

        # Check geometry SQL expression generator
        expr = service.build_point_sql(lat=21.0285, lng=105.8542)
        compiled_sql = str(expr.compile(compile_kwargs={"literal_binds": True}))
        assert "105.8542" in compiled_sql
        assert "21.0285" in compiled_sql
        assert compiled_sql.index("105.8542") < compiled_sql.index("21.0285")
