"""Red-phase unit tests for EntityDeduplicationService & DNC Compliance Pipeline (Story 21.15)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

# Target module to be implemented in Story 21.15:
# from app.lead_intelligence.adapters.base import NormalizedLead
# from app.lead_intelligence.services.deduplication_service import (
#     EntityDeduplicationService,
#     compute_phone_hmac,
#     DeduplicationResult,
# )

pytestmark = pytest.mark.unit


class TestEntityDeduplicationService:
    """Test 4-key entity deduplication, confidence boosting, and DNC compliance."""

    def test_compute_phone_hmac_is_deterministic_and_zero_pii(self) -> None:
        """Should produce consistent keyed SHA-256 HMAC for the same phone number and secret."""
        from app.lead_intelligence.services.deduplication_service import (
            compute_phone_hmac,
        )

        secret = "workspace_secret_salt_123"
        hmac1 = compute_phone_hmac("0912345678", secret=secret)
        hmac2 = compute_phone_hmac("0912345678", secret=secret)
        hmac_diff_phone = compute_phone_hmac("0987654321", secret=secret)
        hmac_diff_secret = compute_phone_hmac("0912345678", secret="other_salt")

        assert hmac1 == hmac2
        assert len(hmac1) == 64  # SHA-256 hex digest length
        assert hmac1 != hmac_diff_phone
        assert hmac1 != hmac_diff_secret
        assert "0912345678" not in hmac1  # Zero-PII

    def test_deduplicate_by_phone_hmac(self) -> None:
        """Should unify two lead records with the same primary phone number."""
        from app.lead_intelligence.adapters.base import NormalizedLead
        from app.lead_intelligence.services.deduplication_service import (
            EntityDeduplicationService,
        )

        service = EntityDeduplicationService()
        lead1 = NormalizedLead(
            source_name="batdongsan",
            source_id="bds_1",
            title="Bán nhà mặt phố Cầu Giấy 80m2",
            primary_phone="0912345678",
            contact_name="Nguyễn Văn A",
            price=12000000000,
            confidence_score=75.0,
        )
        lead2 = NormalizedLead(
            source_name="chotot",
            source_id="ct_2",
            title="Chính chủ cần bán nhà Cầu Giấy gấp",
            primary_phone="0912345678",
            contact_name=None,
            price=11800000000,
            confidence_score=70.0,
        )

        result = service.deduplicate_leads([lead1, lead2], secret_key="salt")
        assert len(result.unified_leads) == 1
        unified = result.unified_leads[0]
        assert unified.primary_phone == "0912345678"
        assert unified.contact_name == "Nguyễn Văn A"  # Merged from lead1
        assert "batdongsan" in unified.sources
        assert "chotot" in unified.sources
        # Confidence score boosted due to multi-source presence
        assert unified.confidence_score > 75.0

    def test_deduplicate_by_tax_id(self) -> None:
        """Should unify two lead records sharing the same Tax ID (Mã số thuế)."""
        from app.lead_intelligence.adapters.base import NormalizedLead
        from app.lead_intelligence.services.deduplication_service import (
            EntityDeduplicationService,
        )

        service = EntityDeduplicationService()
        lead_masothue = NormalizedLead(
            source_name="masothue",
            source_id="mst_01",
            tax_id="0109876543",
            company_name="Công Ty Cổ Phần Công Nghệ Sao Mai",
            legal_rep="Trần Văn B",
            confidence_score=85.0,
        )
        lead_job = NormalizedLead(
            source_name="topcv",
            source_id="topcv_99",
            tax_id="0109876543",
            company_name="Sao Mai Tech Corp",
            canonical_domain="saomaitech.vn",
            primary_email="hr@saomaitech.vn",
            confidence_score=80.0,
        )

        result = service.deduplicate_leads([lead_masothue, lead_job], secret_key="salt")
        assert len(result.unified_leads) == 1
        unified = result.unified_leads[0]
        assert unified.tax_id == "0109876543"
        assert unified.legal_rep == "Trần Văn B"
        assert unified.primary_email == "hr@saomaitech.vn"
        assert unified.canonical_domain == "saomaitech.vn"
        assert "masothue" in unified.sources
        assert "topcv" in unified.sources

    def test_deduplicate_by_canonical_domain_and_email(self) -> None:
        """Should unify leads matching on domain or email."""
        from app.lead_intelligence.adapters.base import NormalizedLead
        from app.lead_intelligence.services.deduplication_service import (
            EntityDeduplicationService,
        )

        service = EntityDeduplicationService()
        lead_domain1 = NormalizedLead(
            source_name="google_search",
            source_id="goog_1",
            canonical_domain="vinhomes.vn",
            company_name="Vinhomes",
            confidence_score=70.0,
        )
        lead_domain2 = NormalizedLead(
            source_name="itviec",
            source_id="itv_2",
            canonical_domain="vinhomes.vn",
            company_name="Vinhomes Group",
            primary_email="contact@vinhomes.vn",
            confidence_score=75.0,
        )

        result = service.deduplicate_leads(
            [lead_domain1, lead_domain2], secret_key="salt"
        )
        assert len(result.unified_leads) == 1
        unified = result.unified_leads[0]
        assert unified.canonical_domain == "vinhomes.vn"
        assert unified.primary_email == "contact@vinhomes.vn"

    def test_attribute_merging_does_not_overwrite_valid_values_with_none(self) -> None:
        """Merging sparse lead attributes should keep all non-null values."""
        from app.lead_intelligence.adapters.base import NormalizedLead
        from app.lead_intelligence.services.deduplication_service import (
            EntityDeduplicationService,
        )

        service = EntityDeduplicationService()
        lead_a = NormalizedLead(
            source_name="source_a",
            source_id="a1",
            primary_phone="0901112233",
            contact_name="Lê Hoàng",
            address="123 Kim Mã, Ba Đình, Hà Nội",
            city="Hà Nội",
        )
        lead_b = NormalizedLead(
            source_name="source_b",
            source_id="b1",
            primary_phone="0901112233",
            contact_name=None,
            address=None,
            primary_email="lehoang@gmail.com",
        )

        result = service.deduplicate_leads([lead_a, lead_b], secret_key="salt")
        unified = result.unified_leads[0]
        assert unified.contact_name == "Lê Hoàng"
        assert unified.address == "123 Kim Mã, Ba Đình, Hà Nội"
        assert unified.city == "Hà Nội"
        assert unified.primary_email == "lehoang@gmail.com"

    def test_dnc_compliance_filtering_marks_or_drops_blacklisted_numbers(self) -> None:
        """DNC engine should flag or suppress contacts present in national/workspace DNC registry."""
        from app.lead_intelligence.adapters.base import NormalizedLead
        from app.lead_intelligence.services.deduplication_service import (
            EntityDeduplicationService,
        )

        service = EntityDeduplicationService()
        lead_clean = NormalizedLead(
            source_name="batdongsan",
            source_id="clean_1",
            primary_phone="0911223344",
            title="Bán đất Đông Anh",
        )
        lead_dnc = NormalizedLead(
            source_name="batdongsan",
            source_id="dnc_1",
            primary_phone="0999999999",  # On DNC list
            title="Bán căn hộ Tây Hồ",
        )

        with patch.object(
            service,
            "_check_dnc_batch",
            return_value={"0999999999": True, "0911223344": False},
        ):
            filtered_result = service.apply_dnc_compliance(
                [lead_clean, lead_dnc],
                workspace_id=1,
                suppress_dnc=True,
            )

            # lead_dnc is suppressed from outreach-ready list
            assert len(filtered_result.compliant_leads) == 1
            assert filtered_result.compliant_leads[0].primary_phone == "0911223344"
            assert len(filtered_result.dnc_suppressed_leads) == 1
            assert filtered_result.dnc_suppressed_leads[0].primary_phone == "0999999999"
