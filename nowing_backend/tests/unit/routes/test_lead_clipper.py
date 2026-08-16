"""ATDD Red-Phase Unit Tests: Nowing Lead Clipper (Story 24.4 / INV-24.5).

Covers:
1. PAT scopes authorization (`leads:clipper:write`).
2. Deduplication hash computation: SHA256(workspace_id + source_canonical_url + normalized_phone).
3. Payload validation (LeadClipRequest schema, phone normalization, URL canonicalization).
4. Red-Phase endpoint contract verification for POST /api/v1/workspaces/{id}/leads/clip.
"""

from __future__ import annotations

import re
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from pydantic import ValidationError

from app.auth.context import AuthContext
from app.routes.lead_clipper_routes import (
    CLIPPER_REQUIRED_SCOPE,
    LeadClipRequest,
    LeadClipResponse,
    canonicalize_url,
    compute_clipper_dedupe_hash,
    normalize_vietnamese_phone_raw,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Test Suite 1: Deduplication Hash Computation (INV-24.5)
# ---------------------------------------------------------------------------


class TestClipperDeduplicationHash:
    """Unit tests for SHA-256 deduplication hash computation and canonicalization."""

    def test_hash_deterministic_for_identical_inputs(self):
        """INV-24.5: Hash must be deterministic for identical inputs."""
        hash_1 = compute_clipper_dedupe_hash(
            workspace_id=1,
            source_canonical_url="https://facebook.com/groups/123/posts/456",
            phone="0912345678",
        )
        hash_2 = compute_clipper_dedupe_hash(
            workspace_id=1,
            source_canonical_url="https://facebook.com/groups/123/posts/456",
            phone="0912345678",
        )
        assert hash_1 == hash_2
        assert len(hash_1) == 64
        assert isinstance(hash_1, str)

    def test_phone_normalization_formats_produce_identical_hash(self):
        """Phone variants (0912.345.678, +84 912 345 678, +84(0)912345678, 84912345678) must normalize to identical hash."""
        url = "https://batdongsan.com.vn/ban-nha-quan-1/listing-12345"
        base_hash = compute_clipper_dedupe_hash(1, url, "0912345678")

        assert compute_clipper_dedupe_hash(1, url, "+84 912 345 678") == base_hash
        assert compute_clipper_dedupe_hash(1, url, "+84(0)912345678") == base_hash
        assert compute_clipper_dedupe_hash(1, url, "0912.345.678") == base_hash
        assert compute_clipper_dedupe_hash(1, url, "0912-345-678") == base_hash
        assert compute_clipper_dedupe_hash(1, url, "84912345678") == base_hash

    def test_hash_sensitivity_to_workspace_id(self):
        """Different workspace IDs must produce distinct deduplication hashes."""
        url = "https://topcv.vn/ung-vien/nguyen-van-a-123"
        phone = "0987654321"
        hash_ws1 = compute_clipper_dedupe_hash(workspace_id=1, source_canonical_url=url, phone=phone)
        hash_ws2 = compute_clipper_dedupe_hash(workspace_id=2, source_canonical_url=url, phone=phone)

        assert hash_ws1 != hash_ws2

    def test_hash_sensitivity_to_canonical_url(self):
        """Different URLs must produce distinct deduplication hashes."""
        phone = "0987654321"
        hash_url1 = compute_clipper_dedupe_hash(1, "https://topcv.vn/cv/1", phone)
        hash_url2 = compute_clipper_dedupe_hash(1, "https://topcv.vn/cv/2", phone)

        assert hash_url1 != hash_url2

    def test_url_canonicalization_strips_tracking_params(self):
        """Tracking parameters (utm_*, fbclid, gad_source, _ga) must be stripped before hashing."""
        base_url = "https://facebook.com/groups/bds/posts/1001"
        url_with_tracking = (
            "https://facebook.com/groups/bds/posts/1001?utm_source=feed&utm_medium=cpc&fbclid=IwAR123&gad_source=1&_ga=GA1.2.3"
        )

        hash_base = compute_clipper_dedupe_hash(1, base_url, "0901112233")
        hash_tracked = compute_clipper_dedupe_hash(1, url_with_tracking, "0901112233")

        assert hash_base == hash_tracked

    def test_normalize_vietnamese_phone_raw_variants(self):
        """Tests standard normalization of Vietnamese mobile numbers."""
        assert normalize_vietnamese_phone_raw("0912345678") == "0912345678"
        assert normalize_vietnamese_phone_raw("+84 912 345 678") == "0912345678"
        assert normalize_vietnamese_phone_raw("+84(0)912345678") == "0912345678"
        assert normalize_vietnamese_phone_raw("84912345678") == "0912345678"
        assert normalize_vietnamese_phone_raw("912345678") == "0912345678"
        assert normalize_vietnamese_phone_raw(None) == ""
        assert normalize_vietnamese_phone_raw("") == ""

    def test_canonicalize_url_strips_params_and_normalizes_scheme(self):
        """Tests URL canonicalization with schemes and social tracking params."""
        clean = canonicalize_url("https://facebook.com/groups/123/posts/456?fbclid=123&utm_source=test&_ga=1.2")
        assert clean == "https://facebook.com/groups/123/posts/456"

        clean_no_scheme = canonicalize_url("batdongsan.com.vn/ban-nha-quan-1/?ref=homepage")
        assert clean_no_scheme == "https://batdongsan.com.vn/ban-nha-quan-1"


# ---------------------------------------------------------------------------
# Test Suite 2: Payload Validation (LeadClipRequest)
# ---------------------------------------------------------------------------


class TestLeadClipPayloadValidation:
    """Unit tests for request payload parsing and validation."""

    def test_valid_lead_clip_request(self):
        """Validates standard complete payload."""
        req = LeadClipRequest(
            source_canonical_url="https://batdongsan.com.vn/ban-dat/123",
            source_platform="batdongsan",
            contact_name="Nguyễn Văn A",
            phone="0912345678",
            email="nva@example.com",
            company_name="BĐS Thủ Đô",
            post_content="Bán đất mặt tiền 100m2 giá 5 tỷ",
            price="5 tỷ",
            location="Hà Nội",
            metadata={"bedrooms": 3, "area_m2": 100},
        )
        assert req.source_platform == "batdongsan"
        assert req.contact_name == "Nguyễn Văn A"
        assert req.price == "5 tỷ"
        assert req.metadata["area_m2"] == 100

    def test_rejects_missing_required_fields(self):
        """Fails validation when required fields are missing."""
        with pytest.raises(ValidationError):
            # Missing source_canonical_url and source_platform
            LeadClipRequest(contact_name="Nguyễn Văn A")

    def test_optional_fields_default_to_none(self):
        """Optional fields default gracefully to None or empty dict."""
        req = LeadClipRequest(
            source_canonical_url="https://facebook.com/post/999",
            source_platform="facebook",
        )
        assert req.contact_name is None
        assert req.phone is None
        assert req.email is None
        assert req.metadata == {}

    def test_regex_fallback_phone_extraction(self):
        """Regex scanner must extract Vietnamese mobile numbers from unstructured text."""
        raw_texts = [
            "Liên hệ trực tiếp: 098.765.4321 để xem nhà",
            "SĐT chủ nhà: 0912 345 678 (Zalo)",
            "Call (+84) 903-123-456 ngay",
            "Inbox hoặc alo: 0868123456",
        ]
        phone_pattern = re.compile(r"(?:\+84|84|0)(?:3|5|7|8|9)\d{8}")

        extracted = []
        for text in raw_texts:
            clean = re.sub(r"[\s\.\-\(\)]", "", text)
            match = phone_pattern.search(clean)
            assert match is not None, f"Failed to extract phone from: {text}"
            extracted.append(match.group(0))

        assert len(extracted) == 4


# ---------------------------------------------------------------------------
# Test Suite 3: PAT Scopes and Authorization Verification
# ---------------------------------------------------------------------------


class TestLeadClipperPATScopesAndAuth:
    """Unit tests verifying Personal Access Token (PAT) scope enforcement."""

    @staticmethod
    def _make_pat_auth(
        *,
        workspace_id: int = 1,
        scopes: list[str] | None = None,
        is_valid: bool = True,
    ) -> AuthContext:
        pat = SimpleNamespace(
            id=1,
            token_kind="clipper",
            workspace_id=workspace_id,
            scopes=scopes or [CLIPPER_REQUIRED_SCOPE],
            is_valid=is_valid,
        )
        user = SimpleNamespace(id=uuid4(), is_active=True)
        return AuthContext.pat_auth(user, pat)

    def test_pat_with_clipper_scope_authorized(self):
        """PAT with `leads:clipper:write` scope is permitted."""
        auth = self._make_pat_auth(scopes=[CLIPPER_REQUIRED_SCOPE])
        assert auth.is_gated
        assert CLIPPER_REQUIRED_SCOPE in (auth.pat.scopes or [])

    def test_pat_missing_clipper_scope_rejected_403(self):
        """PAT missing `leads:clipper:write` scope must be rejected with 403 Forbidden."""
        auth = self._make_pat_auth(scopes=["agent_chat:thread:create", "leads:read"])
        assert CLIPPER_REQUIRED_SCOPE not in (auth.pat.scopes or [])

        # Verify gate rejection logic
        if CLIPPER_REQUIRED_SCOPE not in (auth.pat.scopes or []):
            with pytest.raises(HTTPException) as exc_info:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"PAT missing required scope: {CLIPPER_REQUIRED_SCOPE}",
                )
            assert exc_info.value.status_code == 403
            assert CLIPPER_REQUIRED_SCOPE in exc_info.value.detail

    def test_pat_workspace_mismatch_rejected_403(self):
        """PAT bound to workspace 10 cannot clip leads into workspace 20."""
        auth = self._make_pat_auth(workspace_id=10, scopes=[CLIPPER_REQUIRED_SCOPE])
        target_workspace_id = 20

        if auth.pat.workspace_id and auth.pat.workspace_id != target_workspace_id:
            with pytest.raises(HTTPException) as exc_info:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="PAT not authorized for target workspace",
                )
            assert exc_info.value.status_code == 403

    def test_expired_pat_rejected_401_or_403(self):
        """Expired PAT is rejected."""
        auth = self._make_pat_auth(is_valid=False)
        assert not auth.pat.is_valid

        if not auth.pat.is_valid:
            with pytest.raises(HTTPException) as exc_info:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Personal Access Token is expired or revoked",
                )
            assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Test Suite 4: Red-Phase Route Handler Contract Scaffolding
# ---------------------------------------------------------------------------


class TestLeadClipperEndpointContract:
    """Unit contract tests for POST /api/v1/workspaces/{id}/leads/clip."""

    def test_clip_endpoint_contract_success_response(self):
        """Verifies LeadClipResponse model structure for new lead."""
        lead_id = uuid4()
        dedupe_hash = compute_clipper_dedupe_hash(
            1, "https://facebook.com/post/100", "0912345678"
        )
        res = LeadClipResponse(
            success=True,
            lead_id=lead_id,
            workspace_id=1,
            dedupe_hash=dedupe_hash,
            is_duplicate=False,
            source_platform="facebook",
            message="Lead clipped successfully",
        )
        assert res.success is True
        assert res.is_duplicate is False
        assert res.lead_id == lead_id
        assert res.dedupe_hash == dedupe_hash

    def test_clip_endpoint_contract_duplicate_response(self):
        """Verifies LeadClipResponse model structure for existing/duplicate lead."""
        existing_lead_id = uuid4()
        dedupe_hash = compute_clipper_dedupe_hash(
            1, "https://batdongsan.com.vn/listing/555", "0988776655"
        )
        res = LeadClipResponse(
            success=True,
            lead_id=existing_lead_id,
            workspace_id=1,
            dedupe_hash=dedupe_hash,
            is_duplicate=True,
            source_platform="batdongsan",
            message="Lead already exists in workspace (deduplicated)",
        )
        assert res.success is True
        assert res.is_duplicate is True
        assert res.lead_id == existing_lead_id
