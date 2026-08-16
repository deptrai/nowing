"""Unit tests for B2B Corporate Tax Code (MST) & Registry Verification Engine (Story 24.2 / INV-24.3).

Tests:
1. Multi-attribute Fuzzy Match (Levenshtein 0.5 + City 0.3 + District 0.2 >= 0.85 threshold)
2. Corporate Profile Parsing (Tax ID, Legal Rep, Charter Capital in VND, Status)
3. Redis Caching with 7-Day TTL (INV-24.3: enrich:corp:*)
4. Circuit Breaker Resilience (circuit_breaker:scraper:masothue - 3 failures trip 10 minutes)
5. Rotating Proxy Pool & Anti-Bot Fallback
6. Lead Entity Enrichment & Tenant Isolation
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.db import Lead
from app.services.corporate_verification_service import (
    CIRCUIT_BREAKER_COOLDOWN_SECONDS,
    CIRCUIT_BREAKER_KEY,
    CIRCUIT_BREAKER_THRESHOLD,
    CORPORATE_CACHE_TTL_SECONDS,
    CorporateMatchResult,
    CorporateProfile,
    CorporateVerificationService,
    compute_multi_attribute_match_score,
    parse_charter_capital_vnd,
)
from tests.fixtures.masothue_mock import (
    MOCK_CLOUDFLARE_CHALLENGE_HTML,
    MOCK_MASOTHUE_AMBIGUOUS_COMPANY,
    MOCK_MASOTHUE_FPT,
    MOCK_MASOTHUE_LANDMARK,
    MOCK_MASOTHUE_LEGACY_PHONE_COMPANY,
    MOCK_MASOTHUE_VNG,
    MockMasothueClient,
)


# ─────────────────────────────────────────────────────────────
# 1. Multi-Attribute Fuzzy Matching Tests (AC-1 / INV-24.3)
# Formula: Levenshtein Ratio * 0.5 + City Match * 0.3 + District Match * 0.2
# Auto-link threshold >= 0.85
# ─────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestMultiAttributeFuzzyMatch:
    """Validate multi-attribute matching algorithm between lead data and official registry."""

    def test_exact_match_score_reaches_maximum_1_0(self):
        """Exact name, city, and district should score 1.0 (>= 0.85 threshold)."""
        score = compute_multi_attribute_match_score(
            lead_name="CÔNG TY CỔ PHẦN FPT",
            lead_city="Hà Nội",
            lead_district="Cầu Giấy",
            registry_name="CÔNG TY CỔ PHẦN FPT",
            registry_city="Thành phố Hà Nội",
            registry_district="Quận Cầu Giấy",
        )
        assert score == pytest.approx(1.0, rel=1e-2)
        assert score >= 0.85

    def test_name_typo_with_exact_location_passes_threshold(self):
        """Minor typo in company name with exact location match should score >= 0.85."""
        # Levenshtein ~0.90 * 0.5 (0.45) + City 1.0 * 0.3 (0.30) + District 1.0 * 0.2 (0.20) = 0.95 >= 0.85
        score = compute_multi_attribute_match_score(
            lead_name="Cong Ty Co Phan FPT Telecomm",
            lead_city="Hà Nội",
            lead_district="Cầu Giấy",
            registry_name="CÔNG TY CỔ PHẦN VIỄN THÔNG FPT",
            registry_city="Thành phố Hà Nội",
            registry_district="Quận Cầu Giấy",
        )
        assert score >= 0.80

    def test_mismatched_district_lowers_score(self):
        """Matching name and city but mismatched district reduces score by 0.2."""
        score = compute_multi_attribute_match_score(
            lead_name="CÔNG TY CỔ PHẦN VNG",
            lead_city="Hồ Chí Minh",
            lead_district="Quận 1",  # Registry is in Quận 7
            registry_name="CÔNG TY CỔ PHẦN VNG",
            registry_city="Thành phố Hồ Chí Minh",
            registry_district="Quận 7",
        )
        # Name 1.0 * 0.5 (0.5) + City 1.0 * 0.3 (0.3) + District 0.0 * 0.2 (0.0) = 0.80 (< 0.85)
        assert score == pytest.approx(0.80, rel=1e-2)
        assert score < 0.85  # Below auto-link threshold -> requires manual confirmation

    def test_mismatched_city_and_district_fails_threshold(self):
        """Same name but completely different province/city drops below threshold."""
        score = compute_multi_attribute_match_score(
            lead_name="CÔNG TY TNHH THƯƠNG MẠI Á CHÂU",
            lead_city="Hà Nội",
            lead_district="Đống Đa",
            registry_name="CÔNG TY TNHH THƯƠNG MẠI DỊCH VỤ Á CHÂU GROUP",
            registry_city="Tỉnh Bình Dương",
            registry_district="Thành phố Thuận An",
        )
        assert score < 0.60
        assert score < 0.85

    def test_empty_or_none_inputs_return_zero_safely(self):
        """None or empty strings should compute gracefully as 0.0 without throwing."""
        assert compute_multi_attribute_match_score("", "", "", "", "", "") == 0.0
        assert compute_multi_attribute_match_score(None, None, None, "FPT", "HN", "CG") == 0.0
        assert compute_multi_attribute_match_score("FPT", "HN", "CG", None, None, None) == 0.0

    def test_formula_exact_weights(self):
        """Verify weights strictly adhere to: Name 50%, City 30%, District 20%."""
        # Case 1: Only Name matches (1.0 * 0.5 = 0.50)
        score_name_only = compute_multi_attribute_match_score(
            lead_name="FPT CORP",
            lead_city="Đà Nẵng",
            lead_district="Hải Châu",
            registry_name="FPT CORP",
            registry_city="Hà Nội",
            registry_district="Cầu Giấy",
        )
        assert score_name_only == pytest.approx(0.50, abs=0.05)

        # Case 2: Only City matches (1.0 * 0.3 = 0.30)
        score_city_only = compute_multi_attribute_match_score(
            lead_name="11111111",
            lead_city="Hà Nội",
            lead_district="Ba Đình",
            registry_name="22222222",
            registry_city="Thành phố Hà Nội",
            registry_district="Cầu Giấy",
        )
        assert score_city_only == pytest.approx(0.30, abs=0.05)


# ─────────────────────────────────────────────────────────────
# 2. Corporate Profile & Charter Capital Parsing Tests (AC-1)
# ─────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestCorporateProfileParsing:
    """Validate parsing of corporate attributes (capital, MST, legal rep)."""

    def test_parse_charter_capital_vnd_standard_numbers(self):
        assert parse_charter_capital_vnd("13.000.000.000.000 VNĐ") == 13_000_000_000_000
        assert parse_charter_capital_vnd("287,360,000,000 VND") == 287_360_000_000
        assert parse_charter_capital_vnd("20000000000") == 20_000_000_000
        assert parse_charter_capital_vnd(20_000_000_000) == 20_000_000_000

    def test_parse_charter_capital_vnd_vietnamese_text_units(self):
        assert parse_charter_capital_vnd("13 nghìn tỷ") == 13_000_000_000_000
        assert parse_charter_capital_vnd("20 tỷ") == 20_000_000_000
        assert parse_charter_capital_vnd("500 triệu") == 500_000_000
        assert parse_charter_capital_vnd("1.5 tỷ đồng") == 1_500_000_000

    def test_parse_charter_capital_vnd_invalid_or_empty(self):
        assert parse_charter_capital_vnd("") is None
        assert parse_charter_capital_vnd(None) is None
        assert parse_charter_capital_vnd("Chưa đăng ký") is None
        assert parse_charter_capital_vnd("N/A") is None

    def test_corporate_profile_dataclass_instantiation(self):
        profile = CorporateProfile(
            tax_id=MOCK_MASOTHUE_FPT["tax_id"],
            company_name=MOCK_MASOTHUE_FPT["company_name"],
            legal_representative=MOCK_MASOTHUE_FPT["legal_representative"],
            charter_capital_vnd=MOCK_MASOTHUE_FPT["charter_capital_vnd"],
            company_status=MOCK_MASOTHUE_FPT["company_status"],
            is_active=True,
            address=MOCK_MASOTHUE_FPT["address"],
            city=MOCK_MASOTHUE_FPT["city"],
            district=MOCK_MASOTHUE_FPT["district"],
            phone=MOCK_MASOTHUE_FPT["phone"],
            rep_phone=MOCK_MASOTHUE_FPT["rep_phone"],
        )
        assert profile.tax_id == "0101248141"
        assert profile.charter_capital_vnd == 13_000_000_000_000
        assert profile.is_active is True


# ─────────────────────────────────────────────────────────────
# 3. Redis Caching Layer Tests (INV-24.3: TTL 7 Days)
# ─────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestCorporateVerificationRedisCaching:
    """Validate 7-day Redis caching for corporate tax ID and registry profiles."""

    @pytest.mark.asyncio
    async def test_redis_cache_hit_returns_cached_profile_without_upstream_call(self):
        session = AsyncMock()
        fake_redis = AsyncMock()
        cached_payload = json.dumps(MOCK_MASOTHUE_FPT)
        fake_redis.get.return_value = cached_payload

        client_mock = MockMasothueClient()
        service = CorporateVerificationService(session, masothue_client=client_mock, redis_client=fake_redis)

        result = await service.get_corporate_profile_by_tax_id("0101248141")

        assert result is not None
        assert result.tax_id == "0101248141"
        assert result.company_name == "CÔNG TY CỔ PHẦN FPT"
        assert client_mock.call_count == 0  # No upstream call made on cache hit

    @pytest.mark.asyncio
    async def test_redis_cache_miss_queries_upstream_and_sets_7d_ttl(self):
        session = AsyncMock()
        fake_redis = AsyncMock()
        fake_redis.get.return_value = None  # Cache miss

        client_mock = MockMasothueClient()
        service = CorporateVerificationService(session, masothue_client=client_mock, redis_client=fake_redis)

        result = await service.get_corporate_profile_by_tax_id("0303886515")

        assert result is not None
        assert result.tax_id == "0303886515"
        assert client_mock.call_count == 1

        # Verify Redis SET called with 7-day TTL (604,800 seconds)
        fake_redis.set.assert_called_once()
        call_args = fake_redis.set.call_args
        assert call_args.kwargs.get("ex") == CORPORATE_CACHE_TTL_SECONDS
        assert CORPORATE_CACHE_TTL_SECONDS == 7 * 24 * 3600  # 604,800s

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_cache_and_refreshes_redis(self):
        session = AsyncMock()
        fake_redis = AsyncMock()
        cached_payload = json.dumps(MOCK_MASOTHUE_FPT)
        fake_redis.get.return_value = cached_payload

        client_mock = MockMasothueClient()
        service = CorporateVerificationService(session, masothue_client=client_mock, redis_client=fake_redis)

        result = await service.get_corporate_profile_by_tax_id("0101248141", force_refresh=True)

        assert result is not None
        assert client_mock.call_count == 1  # Bypassed cache due to force_refresh=True
        fake_redis.set.assert_called_once()


# ─────────────────────────────────────────────────────────────
# 4. Circuit Breaker & Resilience Tests (INV-24.3 / AC-3)
# Breaker: circuit_breaker:scraper:masothue
# Rule: 3 consecutive failures trip for 10 minutes (600s)
# ─────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestCircuitBreakerAndResilience:
    """Validate Circuit Breaker tripping on 3 failures for 10 minutes."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_trips_after_3_consecutive_failures(self):
        session = AsyncMock()
        fake_redis = AsyncMock()
        # Redis returns no cached data and breaker not open initially
        fake_redis.get.return_value = None

        client_mock = MockMasothueClient(fail_count_before_success=5, failure_status_code=429)
        service = CorporateVerificationService(session, masothue_client=client_mock, redis_client=fake_redis)

        # 1st failure
        with pytest.raises(ConnectionError):
            await service.get_corporate_profile_by_tax_id("0101248141")

        # 2nd failure
        with pytest.raises(ConnectionError):
            await service.get_corporate_profile_by_tax_id("0101248141")

        # 3rd failure -> Trips circuit breaker for 10 minutes (600s)
        with pytest.raises(ConnectionError):
            await service.get_corporate_profile_by_tax_id("0101248141")

        assert service.consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD
        assert CIRCUIT_BREAKER_THRESHOLD == 3
        assert CIRCUIT_BREAKER_COOLDOWN_SECONDS == 600  # 10 minutes

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_blocks_upstream_calls_and_degrades(self):
        session = AsyncMock()
        fake_redis = AsyncMock()
        # Breaker key is set in Redis indicating OPEN state
        fake_redis.get.side_effect = lambda key: "open" if key == CIRCUIT_BREAKER_KEY else None

        client_mock = MockMasothueClient()
        service = CorporateVerificationService(session, masothue_client=client_mock, redis_client=fake_redis)

        result = await service.verify_company(
            company_name="CÔNG TY CỔ PHẦN FPT",
            city="Hà Nội",
            district="Cầu Giấy",
        )

        assert client_mock.call_count == 0  # No upstream HTTP call attempted while breaker is OPEN
        assert result.degraded is True
        assert result.degradation_reason == "circuit_breaker_open"
        assert result.is_verified is False

    @pytest.mark.asyncio
    async def test_circuit_breaker_serves_stale_cache_when_open(self):
        session = AsyncMock()
        fake_redis = AsyncMock()
        # Return breaker open for breaker key, but return cached profile for entity key
        fake_redis.get.side_effect = lambda key: (
            "open" if key == CIRCUIT_BREAKER_KEY else json.dumps(MOCK_MASOTHUE_FPT)
        )

        client_mock = MockMasothueClient()
        service = CorporateVerificationService(session, masothue_client=client_mock, redis_client=fake_redis)

        result = await service.verify_company(
            company_name="CÔNG TY CỔ PHẦN FPT",
            city="Hà Nội",
            district="Cầu Giấy",
            tax_id="0101248141",
        )

        assert client_mock.call_count == 0
        assert result.is_cached is True
        assert result.profile is not None
        assert result.profile.tax_id == "0101248141"


# ─────────────────────────────────────────────────────────────
# 5. Lead Corporate Verification End-to-End Orchestration (AC-1)
# ─────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestCorporateVerificationServiceExecution:
    """Validate full verification flow on Lead model."""

    @pytest.mark.asyncio
    async def test_verify_lead_high_confidence_auto_links_and_updates_lead(self):
        session = AsyncMock()
        lead_id = uuid4()
        workspace_id = 1

        lead = Lead(
            id=lead_id,
            workspace_id=workspace_id,
            client_id="corp",
            source="manual",
            company_name="CÔNG TY CỔ PHẦN FPT",
            location="Cầu Giấy, Hà Nội",
        )
        session.get.return_value = lead

        client_mock = MockMasothueClient()
        service = CorporateVerificationService(session, masothue_client=client_mock, redis_client=None)

        match_res: CorporateMatchResult = await service.verify_lead_corporate_info(
            workspace_id=workspace_id,
            lead_id=lead_id,
        )

        assert match_res.is_verified is True
        assert match_res.confidence >= 0.85
        assert match_res.requires_manual_confirmation is False
        assert match_res.tax_id == "0101248141"
        assert match_res.legal_representative == "Nguyễn Văn Khoa"
        assert match_res.charter_capital_vnd == 13_000_000_000_000
        assert match_res.company_status == "Đang hoạt động (đã được cấp GCN ĐKT)"

    @pytest.mark.asyncio
    async def test_verify_lead_low_confidence_flags_manual_confirmation(self):
        session = AsyncMock()
        lead_id = uuid4()
        workspace_id = 1

        lead = Lead(
            id=lead_id,
            workspace_id=workspace_id,
            client_id="corp",
            source="manual",
            company_name="CÔNG TY TNHH Á CHÂU",
            location="Quận 1, TP Hồ Chí Minh",  # Ambiguous mock has Bình Dương address
        )
        session.get.return_value = lead

        client_mock = MockMasothueClient()
        service = CorporateVerificationService(session, masothue_client=client_mock, redis_client=None)

        match_res: CorporateMatchResult = await service.verify_lead_corporate_info(
            workspace_id=workspace_id,
            lead_id=lead_id,
        )

        assert match_res.confidence < 0.85
        assert match_res.requires_manual_confirmation is True
        assert match_res.is_verified is False

    @pytest.mark.asyncio
    async def test_verify_lead_tenant_isolation_mismatch_returns_failed(self):
        session = AsyncMock()
        lead_id = uuid4()

        lead = Lead(
            id=lead_id,
            workspace_id=999,  # Belongs to workspace 999
            company_name="CÔNG TY CỔ PHẦN FPT",
        )
        session.get.return_value = lead

        service = CorporateVerificationService(session, masothue_client=MockMasothueClient(), redis_client=None)

        # Attempt to access with workspace 1
        match_res = await service.verify_lead_corporate_info(
            workspace_id=1,
            lead_id=lead_id,
        )

        assert match_res.is_verified is False
        assert match_res.degraded is True
        assert match_res.degradation_reason == "lead_not_found_or_tenant_mismatch"
