"""Unit tests for company aggregator deduplication helpers."""

from __future__ import annotations

import hashlib

import pytest

from app.services.company_aggregator import (
    fingerprint,
    merge,
    normalize,
    search_text,
)

pytestmark = pytest.mark.unit


def _company_data(tax_code: str, name: str) -> dict[str, str]:
    data = {
        "tax_code": tax_code,
        "name": name,
        "address": "10 Đường 3/2, P. 12, Q. 10, TP. HCM",
        "legal_representative": "Nguyễn Văn A",
        "status": "Đang hoạt động",
        "company_type": "Công ty TNHH",
        "main_industry": "Sản xuất sữa",
        "managed_by": "Cục Thuế TP. Hồ Chí Minh",
    }
    data["fingerprint"] = hashlib.sha256(tax_code.encode("utf-8")).hexdigest()[:16]
    return data


def test_fingerprint_from_tax_code() -> None:
    data = _company_data("0314539064", "Công ty TNHH Vinamilk Tân Sơn")
    assert fingerprint(data) == data["fingerprint"]


def test_fingerprint_normalizes_tax_code() -> None:
    data = _company_data("031-4539 064", "Công ty TNHH Vinamilk Tân Sơn")
    expected = hashlib.sha256(b"0314539064").hexdigest()[:16]
    assert fingerprint(data) == expected


def test_fingerprint_fallback_to_name_address() -> None:
    data = {
        "name": "Công ty TNHH Vinamilk Tân Sơn",
        "address": "10 Đường 3/2, P. 12, Q. 10, TP. HCM",
    }
    fp = fingerprint(data)
    assert isinstance(fp, str)
    assert len(fp) == 16


def test_search_text_contains_key_fields() -> None:
    data = _company_data("0314539064", "Công ty TNHH Vinamilk Tân Sơn")
    text = search_text(data)
    assert "0314539064" in text
    assert "Công ty TNHH Vinamilk Tân Sơn" in text
    assert "Sản xuất sữa" in text


def test_merge_passes_through() -> None:
    canonical = {"name": "Old", "tax_code": "123"}
    new = _company_data("0314539064", "Công ty TNHH Vinamilk Tân Sơn")
    merged = merge(canonical, new)
    assert merged["tax_code"] == "0314539064"


def test_fingerprint_fallback_variations() -> None:
    # Name only (no address)
    fp1 = fingerprint({"name": "Công ty TNHH Vinamilk Tân Sơn"})
    expected1 = hashlib.sha256(
        f"{normalize('Công ty TNHH Vinamilk Tân Sơn')}|".encode()
    ).hexdigest()[:16]
    assert fp1 == expected1

    # Address only (no name)
    fp2 = fingerprint({"address": "10 Đường 3/2, P. 12, Q. 10, TP. HCM"})
    expected2 = hashlib.sha256(
        f"|{normalize('10 Đường 3/2, P. 12, Q. 10, TP. HCM')}".encode()
    ).hexdigest()[:16]
    assert fp2 == expected2

    # Neither name nor address -> str(raw_data)
    data3 = {"foo": "bar"}
    fp3 = fingerprint(data3)
    expected3 = hashlib.sha256(str(data3).encode("utf-8")).hexdigest()[:16]
    assert fp3 == expected3

    # Empty tax code fallback
    fp4 = fingerprint({"tax_code": "   ", "name": "Vinamilk"})
    assert fp4 == hashlib.sha256(f"{normalize('Vinamilk')}|".encode()).hexdigest()[:16]


def test_merge_edges() -> None:
    assert merge(None, {"name": "Test"}) == {"name": "Test"}
    assert merge("not a dict", {"name": "Test"}) == {"name": "Test"}

    canonical = {"name": "Old", "tax_code": "123", "address": "123 Street"}
    new = {"name": "New", "tax_code": "456"}
    merged = merge(canonical, new)
    assert merged["name"] == "New"
    assert merged["tax_code"] == "456"
    assert merged["address"] == "123 Street"


def test_normalize() -> None:
    assert normalize(None) == ""
    assert normalize("  Vinamilk  ") == "vinamilk"
    assert normalize("Công ty TNHH!") == "công ty tnhh"
