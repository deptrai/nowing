"""Affiliate Anti-Fraud Service & Payout Risk Evaluation Engine (Story 25.3)."""

from __future__ import annotations

import logging
import re
import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    AffiliatePartner,
    PartnerCommission,
    PartnerPayout,
    PartnerReferral,
)
from app.services.partner_service import micros_to_vnd

logger = logging.getLogger(__name__)

# ponytail: Phase 2 (device fingerprint / IP / card BIN clustering) is intentionally
# deferred. The underlying tables (User, PartnerReferral, CreditPurchase) do not yet
# expose browser_fingerprint, ip_address, or card_bin columns. Add those columns and
# a migration before enabling the next detection layer.

# Vietnamese PIT Tax withholding threshold per TT 111/2013/TT-BTC
PIT_THRESHOLD_VND = 2_000_000
PIT_TAX_RATE = 0.10


def calculate_payout_net_amount(gross_amount_vnd: int) -> tuple[int, int]:
    """Calculate Net Payout and 10% PIT Tax Deduction.

    Returns: (net_amount_vnd, pit_tax_deduction_vnd)
    """
    if gross_amount_vnd >= PIT_THRESHOLD_VND:
        tax = int(gross_amount_vnd * PIT_TAX_RATE)
        net = gross_amount_vnd - tax
        return net, tax
    return gross_amount_vnd, 0


def normalize_account_holder_name(name: str) -> str:
    """Normalize Vietnamese account holder name for resilient matching.

    Strips accents, converts to uppercase, replaces Đ/đ with D, and collapses spaces.
    """
    if not name:
        return ""
    # Handle Vietnamese Đ/đ explicitly
    cleaned = name.replace("Đ", "D").replace("đ", "d")
    # Decompose unicode and strip combining diacritical marks
    nfkd_form = unicodedata.normalize("NFKD", cleaned)
    no_accents = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    # Convert to upper and collapse whitespace
    collapsed = re.sub(r"\s+", " ", no_accents).strip().upper()
    return collapsed


def verify_bank_name_match(
    account_holder: str, beneficiary_name: str | None
) -> tuple[bool, bool]:
    """Verify account holder against beneficiary name.

    Returns: (is_match: bool, is_verified: bool)
    """
    if not beneficiary_name:
        return False, False
    norm_holder = normalize_account_holder_name(account_holder)
    norm_beneficiary = normalize_account_holder_name(beneficiary_name)
    if not norm_holder or not norm_beneficiary:
        return False, False
    is_match = norm_holder == norm_beneficiary
    return is_match, True


class AffiliateAntiFraudService:
    """Evaluates fraud risks, self-referral rings, and name discrepancies for affiliate payouts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get_payout(self, payout_id: uuid.UUID) -> PartnerPayout:
        stmt = select(PartnerPayout).where(PartnerPayout.id == payout_id)
        res = await self.session.execute(stmt)
        payout = res.scalar_one_or_none()
        if not payout:
            raise HTTPException(status_code=404, detail="Partner payout request not found")
        return payout

    async def _get_partner(self, partner_id: uuid.UUID) -> AffiliatePartner:
        stmt = select(AffiliatePartner).where(AffiliatePartner.id == partner_id)
        res = await self.session.execute(stmt)
        partner = res.scalar_one_or_none()
        if not partner:
            raise HTTPException(status_code=404, detail="Affiliate partner record not found")
        return partner

    async def _detect_rapid_self_referral_ring(
        self, partner: AffiliatePartner
    ) -> list[dict[str, Any]]:
        """Phase 1: Detect referrals registered within 1h of affiliate creation with rapid purchases.

        A self-referral ring requires:
        - the referred user account was created within 1h of the affiliate partner creation; and
        - at least one PartnerCommission for that referral with commission_micros > 0 was created
          within 1h of the referred user's registration (i.e. an immediate qualifying purchase).
        Results are grouped by referral to avoid duplicate rows from multiple commissions.
        """
        if not partner.created_at:
            return []

        stmt = (
            select(
                PartnerReferral.id,
                PartnerReferral.referred_user_id,
                PartnerReferral.created_at,
                func.coalesce(func.sum(PartnerCommission.commission_micros), -1).label(
                    "total_commission_micros"
                ),
                func.min(PartnerCommission.created_at).label("first_commission_at"),
            )
            .outerjoin(
                PartnerCommission, PartnerCommission.referral_id == PartnerReferral.id
            )
            .where(PartnerReferral.partner_id == partner.id)
            .group_by(PartnerReferral.id)
        )
        res = await self.session.execute(stmt)
        rows = res.all()

        suspicious_referrals: list[dict[str, Any]] = []
        partner_created_at = partner.created_at

        for row in rows:
            _, referred_user_id, referral_created_at, total_commission, first_commission_at = row
            if not referral_created_at:
                continue

            # Referral must have been created within 1h of the affiliate partner's own creation
            referral_delta = abs((referral_created_at - partner_created_at).total_seconds())
            if referral_delta > 3600:
                continue

            # Must have a qualifying commission created within 1h of the referral creation
            if not total_commission or total_commission <= 0:
                continue
            if not first_commission_at:
                continue
            commission_delta = abs(
                (first_commission_at - referral_created_at).total_seconds()
            )
            if commission_delta > 3600:
                continue

            suspicious_referrals.append(
                {
                    "referred_user_id": str(referred_user_id),
                    "created_within_minutes": int(referral_delta / 60),
                    "commission_micros": int(total_commission),
                }
            )

        return suspicious_referrals

    async def evaluate_payout_risk(self, payout_id: uuid.UUID) -> dict[str, Any]:
        """Compute comprehensive anti-fraud risk score and reasons for a payout request."""
        payout = await self._get_payout(payout_id)
        partner = await self._get_partner(payout.partner_id)

        risk_score = 5
        reasons: list[str] = []

        # 1. Self-referral ring check (Phase 1)
        rapid_referrals = await self._detect_rapid_self_referral_ring(partner)
        if rapid_referrals:
            risk_score += 70
            reasons.append(
                f"Phát hiện {len(rapid_referrals)} tài khoản được giới thiệu tạo trong vòng 1 giờ từ khi kích hoạt affiliate (Nghi vấn self-referral ring)"
            )

        # 2. Phase 2 (TODO): Device / IP / Card BIN clustering
        # Note: Columns browser_fingerprint, ip_address, card_bin do not exist in Phase 1 schema.

        # 3. High amount threshold check (>= 50,000,000 VND)
        gross_vnd = micros_to_vnd(payout.amount_micros) if payout.amount_micros else 0
        if gross_vnd >= 50_000_000:
            risk_score += 15
            reasons.append("Giá trị yêu cầu chi trả lớn (≥ 50.000.000 VNĐ), cần xác thực mở rộng")

        # 4. Bank account name match check (if cached in payout_details)
        details = payout.payout_details or {}
        beneficiary_name = details.get("beneficiary_name")
        account_holder = details.get("account_holder", "")
        if beneficiary_name and account_holder:
            is_match, _ = verify_bank_name_match(account_holder, beneficiary_name)
            if not is_match:
                risk_score += 25
                reasons.append(
                    f"Tên chủ tài khoản ngân hàng '{account_holder}' không khớp với tên thụ hưởng Napas '{beneficiary_name}'"
                )

        risk_score = min(100, max(0, risk_score))

        if risk_score < 30:
            risk_level = "low"
            if not reasons:
                reasons.append("Hồ sơ giao dịch và lịch sử giới thiệu tự nhiên, rủi ro thấp")
        elif risk_score < 70:
            risk_level = "mid"
        else:
            risk_level = "high"

        result = {
            "payout_id": str(payout.id),
            "risk_score": risk_score,
            "risk_level": risk_level,
            "reasons": reasons,
            "evaluated_at": datetime.now(UTC).isoformat(),
        }

        # Cache merged risk assessment in payout_details
        new_details = dict(payout.payout_details or {})
        new_details["risk_score"] = risk_score
        new_details["risk_level"] = risk_level
        new_details["risk_reasons"] = reasons
        new_details["last_evaluated_at"] = result["evaluated_at"]
        payout.payout_details = new_details
        await self.session.commit()

        return result
