"""Hermetic Mock Fixtures for Masothue B2B Corporate Registry & Verification Engine (Story 24.2 / INV-24.3).

Provides deterministic mock payloads, HTML responses, and simulated client behavior for:
- Exact and high-confidence corporate matches (FPT, VNG, Landmark BDS)
- Low-confidence matches requiring manual confirmation (<0.85 threshold)
- 11-digit legacy phone numbers in registry data
- Cloudflare Anti-Bot challenges (HTTP 403)
- Rate-limiting (HTTP 429) and upstream server errors (HTTP 503)
- Circuit Breaker state tracking and Proxy Pool rotation simulation
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


# ─────────────────────────────────────────────────────────────
# 1. Mock Corporate Profile Data Payloads
# ─────────────────────────────────────────────────────────────

MOCK_MASOTHUE_FPT = {
    "tax_id": "0101248141",
    "company_name": "CÔNG TY CỔ PHẦN FPT",
    "international_name": "FPT CORPORATION",
    "short_name": "FPT CORP",
    "legal_representative": "Nguyễn Văn Khoa",
    "charter_capital_vnd": 13_000_000_000_000,  # 13,000 tỷ VND
    "company_status": "Đang hoạt động (đã được cấp GCN ĐKT)",
    "is_active": True,
    "address": "Số 10, phố Phạm Văn Bạch, Phường Dịch Vọng, Quận Cầu Giấy, Thành phố Hà Nội",
    "city": "Thành phố Hà Nội",
    "district": "Quận Cầu Giấy",
    "phone": "02473007300",
    "rep_phone": "0981234567",
    "industry": "Lập trình máy vi tính, dịch vụ tư vấn và các hoạt động khác",
    "date_of_incorporation": "2002-05-13",
}

MOCK_MASOTHUE_VNG = {
    "tax_id": "0303886515",
    "company_name": "CÔNG TY CỔ PHẦN VNG",
    "international_name": "VNG CORPORATION",
    "short_name": "VNG CORP",
    "legal_representative": "Lê Hồng Minh",
    "charter_capital_vnd": 287_360_000_000,  # 287.36 tỷ VND
    "company_status": "Đang hoạt động",
    "is_active": True,
    "address": "Z06, Đường số 13, Phường Tân Thuận Đông, Quận 7, Thành phố Hồ Chí Minh",
    "city": "Thành phố Hồ Chí Minh",
    "district": "Quận 7",
    "phone": "02839623888",
    "rep_phone": "0909123456",
    "industry": "Xuất bản phần mềm, trò chơi điện tử",
    "date_of_incorporation": "2004-09-09",
}

MOCK_MASOTHUE_LANDMARK = {
    "tax_id": "0315891234",
    "company_name": "CÔNG TY TNHH ĐẦU TƯ BẤT ĐỘNG SẢN LANDMARK",
    "international_name": "LANDMARK REAL ESTATE INVESTMENT COMPANY LIMITED",
    "short_name": "LANDMARK INVEST",
    "legal_representative": "Trần Văn B",
    "charter_capital_vnd": 20_000_000_000,  # 20 tỷ VND
    "company_status": "Đang hoạt động",
    "is_active": True,
    "address": "720A Điện Biên Phủ, Phường 22, Quận Bình Thạnh, Thành phố Hồ Chí Minh",
    "city": "Thành phố Hồ Chí Minh",
    "district": "Quận Bình Thạnh",
    "phone": "02838889999",
    "rep_phone": "0912345678",
    "industry": "Kinh doanh bất động sản, quyền sử dụng đất",
    "date_of_incorporation": "2019-06-15",
}

# Legacy 11-digit phone number in corporate registry (to test 2018 conversion in Tier 3)
MOCK_MASOTHUE_LEGACY_PHONE_COMPANY = {
    "tax_id": "0108999888",
    "company_name": "CÔNG TY TNHH CÔNG NGHỆ ALPHA VIỆT NAM",
    "legal_representative": "Hoàng Văn Nam",
    "charter_capital_vnd": 5_000_000_000,
    "company_status": "Đang hoạt động",
    "is_active": True,
    "address": "Số 15 Lê Văn Lương, Phường Nhân Chính, Quận Thanh Xuân, Thành phố Hà Nội",
    "city": "Thành phố Hà Nội",
    "district": "Quận Thanh Xuân",
    "phone": "01689123456",  # 11-digit Viettel legacy -> 0389123456
    "rep_phone": "01234567890",  # 11-digit Vinaphone legacy -> 0834567890
    "industry": "Buôn bán máy vi tính và thiết bị ngoại vi",
    "date_of_incorporation": "2015-03-20",
}

# Low confidence / ambiguous match (different district, different name variant)
MOCK_MASOTHUE_AMBIGUOUS_COMPANY = {
    "tax_id": "0319999999",
    "company_name": "CÔNG TY TNHH THƯƠNG MẠI DỊCH VỤ Á CHÂU GROUP",
    "legal_representative": "Phạm Thị C",
    "charter_capital_vnd": 1_000_000_000,
    "company_status": "Đang hoạt động",
    "is_active": True,
    "address": "Số 99 đường DT743, Phường An Phú, Thành phố Thuận An, Tỉnh Bình Dương",
    "city": "Tỉnh Bình Dương",
    "district": "Thành phố Thuận An",
    "phone": "02743888777",
    "rep_phone": "0977888999",
    "industry": "Bán buôn tổng hợp",
    "date_of_incorporation": "2021-01-10",
}


# ─────────────────────────────────────────────────────────────
# 2. Mock HTML & Raw Responses
# ─────────────────────────────────────────────────────────────

MOCK_MASOTHUE_FPT_HTML = """
<!DOCTYPE html>
<html>
<head><title>CÔNG TY CỔ PHẦN FPT - 0101248141</title></head>
<body>
<table class="table-taxinfo">
  <tbody>
    <tr><td class="cat">Mã số thuế:</td><td><span itemprop="taxId">0101248141</span></td></tr>
    <tr><td class="cat">Tên chính thức:</td><td><span itemprop="name">CÔNG TY CỔ PHẦN FPT</span></td></tr>
    <tr><td class="cat">Tên quốc tế:</td><td><span>FPT CORPORATION</span></td></tr>
    <tr><td class="cat">Người đại diện:</td><td><span itemprop="legalRepresentative">Nguyễn Văn Khoa</span></td></tr>
    <tr><td class="cat">Vốn điều lệ:</td><td><span>13.000.000.000.000 VNĐ</span></td></tr>
    <tr><td class="cat">Địa chỉ:</td><td><address itemprop="address">Số 10, phố Phạm Văn Bạch, Phường Dịch Vọng, Quận Cầu Giấy, Thành phố Hà Nội</address></td></tr>
    <tr><td class="cat">Tỉnh/TP:</td><td><span>Thành phố Hà Nội</span></td></tr>
    <tr><td class="cat">Quận/Huyện:</td><td><span>Quận Cầu Giấy</span></td></tr>
    <tr><td class="cat">Trạng thái:</td><td><span class="badge-success">Đang hoạt động (đã được cấp GCN ĐKT)</span></td></tr>
    <tr><td class="cat">Điện thoại:</td><td><span>02473007300</span></td></tr>
    <tr><td class="cat">Điện thoại ĐDT:</td><td><span>0981234567</span></td></tr>
  </tbody>
</table>
</body>
</html>
"""

MOCK_CLOUDFLARE_CHALLENGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <title>Just a moment...</title>
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
</head>
<body>
  <div class="main-content">
    <h2>Checking your browser before accessing masothue.com.</h2>
    <div id="cf-challenge-running">This process is automatic.</div>
  </div>
</body>
</html>
"""


# ─────────────────────────────────────────────────────────────
# 3. Hermetic Mock Masothue Client
# ─────────────────────────────────────────────────────────────

@dataclass
class MockMasothueClient:
    """Configurable mock client to simulate Masothue API and scraper operations."""

    fail_count_before_success: int = 0
    failure_status_code: int = 429
    simulate_cloudflare: bool = False
    simulate_timeout: bool = False
    delay_seconds: float = 0.0
    call_count: int = 0
    proxies_used: list[str] = field(default_factory=list)

    async def search_company(
        self,
        query: str,
        city: str | None = None,
        district: str | None = None,
        proxy: str | None = None,
    ) -> list[dict[str, Any]]:
        """Simulate searching company by name, tax ID, or keywords."""
        self.call_count += 1
        if proxy:
            self.proxies_used.append(proxy)

        if self.simulate_timeout:
            raise TimeoutError("Masothue request timed out (>5.0s)")

        if self.call_count <= self.fail_count_before_success:
            if self.simulate_cloudflare:
                raise ConnectionError(f"Cloudflare 403 Challenge: {MOCK_CLOUDFLARE_CHALLENGE_HTML[:60]}")
            raise ConnectionError(f"HTTP {self.failure_status_code} Upstream Failure")

        q_clean = query.strip().upper()
        if "0101248141" in q_clean or "FPT" in q_clean:
            return [dict(MOCK_MASOTHUE_FPT)]
        if "0303886515" in q_clean or "VNG" in q_clean:
            return [dict(MOCK_MASOTHUE_VNG)]
        if "0315891234" in q_clean or "LANDMARK" in q_clean:
            return [dict(MOCK_MASOTHUE_LANDMARK)]
        if "0108999888" in q_clean or "ALPHA" in q_clean:
            return [dict(MOCK_MASOTHUE_LEGACY_PHONE_COMPANY)]
        if "Á CHÂU" in q_clean or "A CHAU" in q_clean:
            return [dict(MOCK_MASOTHUE_AMBIGUOUS_COMPANY)]

        return []

    async def get_company_by_tax_id(
        self, tax_id: str, proxy: str | None = None
    ) -> dict[str, Any] | None:
        """Simulate direct lookup by exact tax_id (MST)."""
        self.call_count += 1
        if proxy:
            self.proxies_used.append(proxy)

        if self.call_count <= self.fail_count_before_success:
            raise ConnectionError(f"HTTP {self.failure_status_code} Upstream Failure")

        tax_id_clean = tax_id.strip().replace("-", "")
        if tax_id_clean == "0101248141":
            return dict(MOCK_MASOTHUE_FPT)
        if tax_id_clean == "0303886515":
            return dict(MOCK_MASOTHUE_VNG)
        if tax_id_clean == "0315891234":
            return dict(MOCK_MASOTHUE_LANDMARK)
        if tax_id_clean == "0108999888":
            return dict(MOCK_MASOTHUE_LEGACY_PHONE_COMPANY)
        if tax_id_clean == "0319999999":
            return dict(MOCK_MASOTHUE_AMBIGUOUS_COMPANY)

        return None
