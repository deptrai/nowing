"""Unit tests for Vietnamese Administrative Divisions and Location Profile helpers (Story 26.25)."""

from __future__ import annotations

from app.services.location_normalize import (
    format_location_summary,
    get_all_provinces,
    get_districts_by_province,
    remove_diacritics,
    resolve_city_code,
)


def test_get_all_provinces_contains_major_cities() -> None:
    """Provinces list should include Hanoi, HCMC, Da Nang, Hai Phong, Can Tho."""
    provinces = get_all_provinces()
    codes = {p["code"] for p in provinces}

    for major in ["HN", "SG", "DN", "HP", "CT"]:
        assert major in codes


def test_get_districts_by_province() -> None:
    """Districts list for HCMC (SG) should contain District 1 and Thu Duc City."""
    districts = get_districts_by_province("SG")
    names = {d["name"] for d in districts}

    assert "Quận 1" in names
    assert "Thành phố Thủ Đức" in names

    # Case insensitivity
    assert len(get_districts_by_province("sg")) == len(districts)

    # Unknown province returns empty list
    assert get_districts_by_province("UNKNOWN") == []


def test_format_location_summary() -> None:
    """Produces compact string representation for LocationProfile."""
    summary = format_location_summary("SG", ["760", "769"])
    assert "TP. Hồ Chí Minh" in summary
    assert "Quận 1" in summary
    assert "Thành phố Thủ Đức" in summary

    # Single province with no districts
    assert format_location_summary("HN") == "Hà Nội"


def test_diacritic_normalization_and_alias_matching() -> None:
    """Diacritics and common aliases resolve to proper province codes."""
    assert resolve_city_code("Saigon") == "SG"
    assert resolve_city_code("hcm") == "SG"
    assert resolve_city_code("TP. Hồ Chí Minh") == "SG"
    assert resolve_city_code("ha noi") == "HN"
    assert resolve_city_code("Da Nang") == "DN"

    assert remove_diacritics("Đà Nẵng") == "da nang"
    assert remove_diacritics("TP. Hồ Chí Minh") == "tp. ho chi minh"
