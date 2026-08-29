"""Comprehensive Sales Copilot Smoke Tests (Task #17).

Verifies the 3 primary pillars of the Sales Copilot Loop:
1. ChainLens Research Market Analysis (HMAC auth + SSE stream).
2. XActions Social Intent & Vietnamese Phone Extractor (obfuscated regex + intent mapping).
3. MultiSourceLeadGen Orchestrator with Buyer Intent & Smoke Test flag.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
import pytest

from app.lead_intelligence.campaign.schemas import CampaignSpec, ICPCriteria
from app.lead_intelligence.schemas import (
    BuyerIntent,
    EnrichmentDepth,
    MultiSourceLeadGenRequest,
)
from app.lead_intelligence.services.lead_gen_orchestrator import LeadGenOrchestrator
from app.proprietary.platforms.xactions.phone_extractor import (
    SocialEntityExtractor,
    classify_social_intent,
    extract_phone_numbers,
)
from app.services.chainlens.auth import ChainLensServiceAuth

pytestmark = pytest.mark.asyncio


async def test_smoke_1_chainlens_auth_and_outbound_headers():
    """Smoke Test 1: ChainLens HMAC Auth & Token generation."""
    fake_config = SimpleNamespace(
        CHAINLENS_SERVICE_TOKEN="",
        CHAINLENS_API_KEY="",
        CHAINLENS_AUTH_CONTEXT_SECRET="test-secret-key-for-sales-copilot",
        CHAINLENS_HMAC_USER_ID="00000000-0000-0000-0000-000000000001",
    )
    auth = ChainLensServiceAuth(config_obj=fake_config)
    assert auth.configured, "ChainLensServiceAuth should be configured via HMAC secret"

    headers = auth.get_outbound_headers(workspace_id=1)
    assert "X-Workspace-Id" in headers
    assert headers["X-Workspace-Id"] == "1"
    assert "X-Correlation-Id" in headers
    assert "x-user-ctx" in headers, "x-user-ctx header should be present when HMAC secret is set"

    # Verify HMAC format: userId|exp|signature
    parts = headers["x-user-ctx"].split("|")
    assert len(parts) == 3
    assert parts[0] == "00000000-0000-0000-0000-000000000001"
    assert int(parts[1]) > 0


async def test_smoke_2_xactions_social_intent_and_phone_extraction():
    """Smoke Test 2: XActions Social Intent classification & phone extractor."""
    # Test post 1: BĐS bán nhà có số điện thoại viết lách
    post_text_bds = "Chính chủ cần bán gấp căn nhà phố Cầu Giấy giá 6.5 tỷ, liên hệ ngay O912.345.678 (không chín một hai)"
    intent_bds = classify_social_intent(post_text_bds)
    assert intent_bds == "sell", f"Expected 'sell', got {intent_bds}"

    phones_bds = extract_phone_numbers(post_text_bds)
    assert "0912345678" in phones_bds, f"Failed to extract normalized phone from '{post_text_bds}'"

    # Test post 2: Tuyển dụng IT
    post_text_hr = "Công ty mình đang tuyển dụng gấp 2 Senior Python Developer lương 40-50M, gửi CV về hr@techcorp.vn hoặc ib zalo 0988 123 456"
    intent_hr = classify_social_intent(post_text_hr)
    assert intent_hr == "hiring", f"Expected 'hiring', got {intent_hr}"

    phones_hr = extract_phone_numbers(post_text_hr)
    assert "0988123456" in phones_hr, f"Failed to extract phone from '{post_text_hr}'"

    # Test full entity extractor pipeline via extract_all
    extractor = SocialEntityExtractor()
    entities = extractor.extract_all(post_text_hr)
    assert "0988123456" in entities["phones"]
    assert "hr@techcorp.vn" in entities["emails"]
    assert entities["intent"] == "hiring"


async def test_smoke_3_multi_source_lead_gen_schema_and_intent_normalization():
    """Smoke Test 3: MultiSourceLeadGenRequest schema validation & intent parsing."""
    # Normalizing Vietnamese intent synonyms
    req_vi = MultiSourceLeadGenRequest(
        query="Tìm 5 khách mua nhà Hà Nội",
        intent="mua",
        smoke_test=True,
        locations=["Hà Nội"],
        product_type="Nhà phố",
        target_sources=["batdongsan", "chotot"],
    )
    assert req_vi.intent == BuyerIntent.BUY
    assert req_vi.smoke_test is True
    assert req_vi.enrichment_depth == EnrichmentDepth.STANDARD

    req_hire = MultiSourceLeadGenRequest(
        query="Tìm công ty tuyển lập trình viên Python",
        intent="tuyển dụng",
        product_type="Senior Python",
        target_sources=["topcv", "itviec"],
    )
    assert req_hire.intent == BuyerIntent.HIRE


async def test_smoke_4_orchestrator_smoke_test_execution():
    """Smoke Test 4: LeadGenOrchestrator execution with smoke_test=True and 5 lead limit."""
    spec = CampaignSpec(
        name="smoke-test-campaign",
        workspace_id=1,
        client_id="smoke-test",
        query="Tìm 5 căn nhà phố Hà Nội bán",
        icp_criteria=ICPCriteria(
            target_keywords=["nhà phố", "bán"],
            negative_keywords=[],
            target_locations=["Hà Nội"],
            target_industries=["BĐS"],
            min_fit_score=0.0,
        ),
        intent_tags=["sell", "BĐS"],
        target_sources=["batdongsan"],
        max_total_leads=5,
        metadata={"smoke_test": True},
    )

    orchestrator = LeadGenOrchestrator()
    result = await orchestrator.execute_multi_source_lead_gen(
        workspace_id=1,
        campaign_spec=spec,
        limit=5,
    )

    assert result is not None
    assert len(result.leads) > 0, "Smoke test should return at least 1 lead from Batdongsan"
    assert len(result.leads) <= 5, "Smoke test should respect the 5 leads limit"

    first_lead = result.leads[0]
    assert first_lead.source_name == "batdongsan"
    assert first_lead.title is not None
    assert first_lead.icp_fit_score >= 0.0
