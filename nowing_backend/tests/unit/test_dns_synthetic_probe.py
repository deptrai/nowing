"""Unit tests for synthetic DNS probe script (Story 27.1 / Item 29)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from scripts.dns_synthetic_probe import (
    DnsProbeTarget,
    check_cname_ingress,
    check_txt_ownership,
    probe_single_domain,
)


class MockTxtRecord:
    def __init__(self, val: str):
        self.strings = [val.encode("utf-8")]

    def __str__(self) -> str:
        return self.strings[0].decode("utf-8")


class MockCnameRecord:
    def __init__(self, target: str):
        self.target = target

    def __str__(self) -> str:
        return self.target


class MockIpRecord:
    def __init__(self, ip: str):
        self.ip = ip

    def __str__(self) -> str:
        return self.ip


@pytest.mark.asyncio
async def test_check_txt_ownership_matches_token():
    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = [
        MockTxtRecord("nowing-verify=valid_token_123")
    ]

    with patch(
        "scripts.dns_synthetic_probe.get_dns_resolver", return_value=mock_resolver
    ):
        status, detail, host = await check_txt_ownership(
            domain="app.example.com",
            token="valid_token_123",
        )
        assert status == "ok"
        assert "valid_token_123" in detail
        assert host == "_nowing-verify.app.example.com"


@pytest.mark.asyncio
async def test_check_txt_ownership_token_mismatch():
    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = [MockTxtRecord("nowing-verify=wrong_token")]

    with patch(
        "scripts.dns_synthetic_probe.get_dns_resolver", return_value=mock_resolver
    ):
        status, _detail, host = await check_txt_ownership(
            domain="app.example.com",
            token="expected_token",
        )
        assert status == "mismatch"
        assert host == "_nowing-verify.app.example.com"


@pytest.mark.asyncio
async def test_check_txt_ownership_invalid_length():
    super_long_domain = "a" * 250 + ".com"
    status, detail, _host = await check_txt_ownership(
        domain=super_long_domain,
        token="some_token",
    )
    assert status == "invalid_length"
    assert "exceeds 253 chars" in detail


@pytest.mark.asyncio
async def test_check_cname_ingress_direct_match():
    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = [
        MockCnameRecord("cname-ingress.apps.nowing.net.")
    ]

    with patch(
        "scripts.dns_synthetic_probe.get_dns_resolver", return_value=mock_resolver
    ):
        status, detail = await check_cname_ingress(
            domain="sub.brand.vn",
            target="cname-ingress.apps.nowing.net",
        )
        assert status == "ok"
        assert "hop 1" in detail


@pytest.mark.asyncio
async def test_check_cname_ingress_apex_fallback():
    import dns.resolver

    mock_resolver = MagicMock()

    def mock_resolve(qname, rdtype):
        if rdtype == "CNAME":
            raise dns.resolver.NoAnswer()
        if rdtype == "A":
            return [MockIpRecord("1.2.3.4")]
        if rdtype == "AAAA":
            raise dns.resolver.NoAnswer()
        raise dns.resolver.NXDOMAIN()

    mock_resolver.resolve.side_effect = mock_resolve

    with patch(
        "scripts.dns_synthetic_probe.get_dns_resolver", return_value=mock_resolver
    ):
        status, detail = await check_cname_ingress(
            domain="apexbrand.vn",
            target="cname-ingress.apps.nowing.net",
        )
        assert status == "ok"
        assert "Apex A/AAAA" in detail


@pytest.mark.asyncio
async def test_probe_single_domain_full():
    target = DnsProbeTarget(domain="test.example.com", token="tok999")

    with (
        patch(
            "scripts.dns_synthetic_probe.check_txt_ownership",
            return_value=("ok", "matched", "_nowing-verify.test.example.com"),
        ),
        patch(
            "scripts.dns_synthetic_probe.check_cname_ingress",
            return_value=("ok", "cname matched"),
        ),
    ):
        res = await probe_single_domain(target)
        assert res.passed is True
        assert res.txt_status == "ok"
        assert res.cname_status == "ok"
        assert res.to_dict()["domain"] == "test.example.com"
