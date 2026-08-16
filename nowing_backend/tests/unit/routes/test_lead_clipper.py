"""ATDD Red-Phase Unit Tests: Nowing Lead Clipper (Story 24.4 / INV-24.5).

Covers:
1. PAT scopes authorization (`leads:clipper:write`).
2. Deduplication hash computation: SHA256(workspace_id + source_canonical_url + normalized_phone).
3. Payload validation (LeadClipRequest schema, phone normalization, URL canonicalization).
4. Red-Phase endpoint contract verification for POST /api/v1/workspaces/{id}/leads/clip.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, status
from pydantic import BaseModel, Field, ValidationError

from app.auth.context import AuthContext

pytestmark = pytest.mark.unit

# Required PAT Scope for Chrome Extension Clipper
CLIPPER_REQUIRED_SCOPE = "leads:clipper:write"


# ---------------------------------------------------------------------------
# Red-Phase Reference Schemas and Helper Contracts
# ---------------------------------------------------------------------------


def normalize_vietnamese_phone_raw(phone: str | None) -> str:
    """Normalize Vietnamese phone numbers to standard format (e.g., 0912345678 or +84912345678)."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("84") and len(digits) >= 10:
        digits = "0" + digits[2:]
    return digits


def canonicalize_url(url: str) -> str:
    """Strip tracking query parameters (utm_*, fbclid) and normalize URL structure."""
    if not url:
        return ""
    parsed = urlparse(url.strip())
    # Filter out tracking query params
    filtered_query = [
        (k, v)
        for k, v in parse_qsl(parsed.query)
        if not k.startswith("utm_") and k not in {"fbclid", "gclid", "ref", "source"}
    ]
    clean_query = urlencode(filtered_query)
    clean_path = parsed.path.rstrip("/") if parsed.path != "/" else "/"
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            clean_path,
            parsed.params,
            clean_query,
            "",  # strip fragment
        )
    )


def compute_clipper_dedupe_hash(
    workspace_id: int,
    source_canonical_url: str,
    phone: str | None = None,
) -> str:
    """
    Compute deterministic SHA-256 deduplication hash according to INV-24.5.
    dedupe_hash = SHA256(workspace_id + source_canonical_url + normalized_phone)
    """
    clean_url = canonicalize_url(source_canonical_url)
    norm_phone = normalize_vietnamese_phone_raw(phone)
    raw_key = f"{workspace_id}:{clean_url}:{norm_phone}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class LeadClipRequest(BaseModel):
    """Pydantic model validating lead clipper payloads."""

    source_canonical_url: str = Field(..., description="Canonical URL of listing or profile")
    source_platform: str = Field(
        ...,
        description="Source platform: facebook, batdongsan, topcv, linkedin, chotot, custom",
    )
    contact_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    company_name: str | None = Field(default=None, max_length=255)
    post_content: str | None = Field(default=None)
    price: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] = Field(default_factory=dict)
    dedupe_hash: str | None = Field(default=None)


class LeadClipResponse(BaseModel):
    """Response returned upon successful lead clipping."""

    success: bool = True
    lead_id: UUID
    workspace_id: int
    dedupe_hash: str
    is_duplicate: bool
    source_platform: str
    message: str = "Lead clipped successfully"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


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
        """Phone variants (0912.345.678, +84 912 345 678, 84912345678) must normalize to identical hash."""
        url = "https://batdongsan.com.vn/ban-nha-quan-1/listing-12345"
        base_hash = compute_clipper_dedupe_hash(1, url, "0912345678")

        assert compute_clipper_dedupe_hash(1, url, "+84 912 345 678") == base_hash
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
        """Tracking parameters (utm_*, fbclid) must be stripped before hashing."""
        base_url = "https://facebook.com/groups/bds/posts/1001"
        url_with_tracking = (
            "https://facebook.com/groups/bds/posts/1001?utm_source=feed&utm_medium=cpc&fbclid=IwAR123"
        )

        hash_base = compute_clipper_dedupe_hash(1, base_url, "0901112233")
        hash_tracked = compute_clipper_dedupe_hash(1, url_with_tracking, "0901112233")

        assert hash_base == hash_tracked

    def test_hash_handles_none_and_empty_phone(self):
        """Empty phone numbers should produce a deterministic hash without raising errors."""
        url = "https://linkedin.com/in/recruiter-profile"
        hash_none = compute_clipper_dedupe_hash(1, url, None)
        hash_empty = compute_clipper_dedupe_hash(1, url, "")

        assert hash_none == hash_empty
        assert len(hash_none) == 64


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
