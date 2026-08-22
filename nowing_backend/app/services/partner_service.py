"""Partner and affiliate commission service (Story 21.18 / FR-88 / AD-42)."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    AffiliatePartner,
    CreditPurchase,
    PartnerCommission,
    PartnerPayout,
    PartnerReferral,
    User,
)
from app.schemas.partner import (
    PartnerApplyRequest,
    PartnerCommissionItem,
    PartnerCommissionsListResponse,
    PartnerPayoutItem,
    PartnerPayoutRequest,
    PartnerPayoutSettingsUpdate,
    PartnerPayoutsListResponse,
    PartnerProfileResponse,
    PartnerReferralItem,
    PartnerReferralsListResponse,
    VietQrBankItem,
)

logger = logging.getLogger(__name__)

USD_TO_VND_RATE = 25400
MIN_PAYOUT_MICROS = 20_000_000  # $20.00 == 508,000 VND
DEFAULT_COMMISSION_RATE = 0.15
CREDIT_BONUS_MULTIPLIER = 1.10  # +10% bonus when converting to platform credit

# Standard Napas 24/7 bank list for Vietnam
NAPAS_BANKS: list[dict[str, str]] = [
    {
        "bin": "970436",
        "name": "Ngân hàng Ngoại thương Việt Nam (Vietcombank)",
        "short_name": "Vietcombank",
        "code": "VCB",
    },
    {
        "bin": "970407",
        "name": "Ngân hàng Kỹ thương Việt Nam (Techcombank)",
        "short_name": "Techcombank",
        "code": "TCB",
    },
    {
        "bin": "970422",
        "name": "Ngân hàng Quân đội (MBBank)",
        "short_name": "MBBank",
        "code": "MB",
    },
    {
        "bin": "970415",
        "name": "Ngân hàng Công thương Việt Nam (VietinBank)",
        "short_name": "VietinBank",
        "code": "CTG",
    },
    {
        "bin": "970418",
        "name": "Ngân hàng Đầu tư và Phát triển Việt Nam (BIDV)",
        "short_name": "BIDV",
        "code": "BIDV",
    },
    {
        "bin": "970416",
        "name": "Ngân hàng Á Châu (ACB)",
        "short_name": "ACB",
        "code": "ACB",
    },
    {
        "bin": "970432",
        "name": "Ngân hàng Việt Nam Thịnh vượng (VPBank)",
        "short_name": "VPBank",
        "code": "VPB",
    },
    {
        "bin": "970403",
        "name": "Ngân hàng Sài Gòn Thương Tín (Sacombank)",
        "short_name": "Sacombank",
        "code": "STB",
    },
    {
        "bin": "970423",
        "name": "Ngân hàng Tiên Phong (TPBank)",
        "short_name": "TPBank",
        "code": "TPB",
    },
    {
        "bin": "970448",
        "name": "Ngân hàng Phương Đông (OCB)",
        "short_name": "OCB",
        "code": "OCB",
    },
    {
        "bin": "970437",
        "name": "Ngân hàng Phát triển TP.HCM (HDBank)",
        "short_name": "HDBank",
        "code": "HDB",
    },
    {
        "bin": "970428",
        "name": "Ngân hàng Nam Á (NamABank)",
        "short_name": "NamABank",
        "code": "NAB",
    },
    {
        "bin": "970441",
        "name": "Ngân hàng Quốc tế (VIB)",
        "short_name": "VIB",
        "code": "VIB",
    },
    {
        "bin": "970405",
        "name": "Ngân hàng Nông nghiệp và Phát triển Nông thôn (Agribank)",
        "short_name": "Agribank",
        "code": "VBA",
    },
]


def micros_to_usd(micros: int | None) -> float:
    if micros is None:
        return 0.0
    return round(micros / 1_000_000.0, 2)


def micros_to_vnd(micros: int | None) -> int:
    if micros is None:
        return 0
    usd = micros / 1_000_000.0
    return round(usd * USD_TO_VND_RATE)


def get_referral_url(referral_code: str) -> str:
    base_url = (config.NEXT_FRONTEND_URL or "https://nowing.net").rstrip("/")
    return f"{base_url}/?ref={referral_code}"


class PartnerService:
    @staticmethod
    def get_supported_banks() -> list[VietQrBankItem]:
        return [VietQrBankItem(**b) for b in NAPAS_BANKS]

    @staticmethod
    async def apply_partner(
        db_session: AsyncSession,
        user_id: uuid.UUID,
        request: PartnerApplyRequest,
    ) -> AffiliatePartner:
        """Register a user as an affiliate partner."""
        # 1. Clean & validate code
        clean_code = re.sub(r"[^A-Za-z0-9_-]", "", request.referral_code).upper()
        if len(clean_code) < 3 or len(clean_code) > 32:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Referral code must be 3-32 alphanumeric characters.",
            )

        # 2. Check if user is already a partner
        existing_partner = (
            await db_session.execute(
                select(AffiliatePartner).where(AffiliatePartner.user_id == user_id)
            )
        ).scalar_one_or_none()

        if existing_partner is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You are already registered as an affiliate partner.",
            )

        # 3. Check if referral code is already taken
        code_taken = (
            await db_session.execute(
                select(AffiliatePartner).where(
                    func.lower(AffiliatePartner.referral_code) == clean_code.lower()
                )
            )
        ).scalar_one_or_none()

        if code_taken is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Referral code '{clean_code}' is already taken. Please choose another.",
            )

        now = datetime.now(UTC)
        partner = AffiliatePartner(
            id=uuid.uuid4(),
            user_id=user_id,
            referral_code=clean_code,
            partner_type=request.partner_type,
            status="active",
            commission_rate=DEFAULT_COMMISSION_RATE,
            balance_micros=0,
            total_earned_micros=0,
            total_paid_micros=0,
            payout_method=request.payout_method,
            payout_details=request.payout_details or {},
            created_at=now,
            updated_at=now,
        )
        db_session.add(partner)
        await db_session.commit()
        await db_session.refresh(partner)
        return partner

    @staticmethod
    async def get_partner_profile(
        db_session: AsyncSession,
        user_id: uuid.UUID,
    ) -> PartnerProfileResponse:
        """Fetch partner profile and aggregated performance metrics."""
        partner = (
            await db_session.execute(
                select(AffiliatePartner).where(AffiliatePartner.user_id == user_id)
            )
        ).scalar_one_or_none()

        if partner is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Affiliate partner profile not found.",
            )

        # Count total referrals
        referral_count = (
            await db_session.execute(
                select(func.count(PartnerReferral.id)).where(
                    PartnerReferral.partner_id == partner.id
                )
            )
        ).scalar() or 0

        # Count active paying referrals (referrals with >= 1 commission)
        active_paying = (
            await db_session.execute(
                select(func.count(func.distinct(PartnerCommission.referral_id))).where(
                    PartnerCommission.partner_id == partner.id
                )
            )
        ).scalar() or 0

        return PartnerProfileResponse(
            id=partner.id,
            user_id=partner.user_id,
            referral_code=partner.referral_code,
            referral_url=get_referral_url(partner.referral_code),
            partner_type=partner.partner_type,
            status=partner.status,
            commission_rate=partner.commission_rate,
            balance_micros=partner.balance_micros,
            balance_usd=micros_to_usd(partner.balance_micros),
            balance_vnd=micros_to_vnd(partner.balance_micros),
            hold_balance_micros=partner.hold_balance_micros or 0,
            hold_balance_usd=micros_to_usd(partner.hold_balance_micros),
            hold_balance_vnd=micros_to_vnd(partner.hold_balance_micros),
            total_earned_micros=partner.total_earned_micros or 0,
            total_earned_usd=micros_to_usd(partner.total_earned_micros),
            total_earned_vnd=micros_to_vnd(partner.total_earned_micros),
            total_paid_micros=partner.total_paid_micros or 0,
            payout_method=partner.payout_method,
            payout_details=partner.payout_details,
            total_clicks=referral_count * 3,  # Estimated clicks or exact counter
            total_referrals=referral_count,
            active_paying_referrals=active_paying,
            created_at=partner.created_at,
            updated_at=partner.updated_at,
        )

    @staticmethod
    async def update_payout_settings(
        db_session: AsyncSession,
        user_id: uuid.UUID,
        update_data: PartnerPayoutSettingsUpdate,
    ) -> PartnerProfileResponse:
        """Update payout method & bank details."""
        partner = (
            await db_session.execute(
                select(AffiliatePartner)
                .where(AffiliatePartner.user_id == user_id)
                .with_for_update()
            )
        ).scalar_one_or_none()

        if partner is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Affiliate partner profile not found.",
            )

        partner.payout_method = update_data.payout_method
        partner.payout_details = update_data.payout_details
        await db_session.commit()
        return await PartnerService.get_partner_profile(db_session, user_id)

    @staticmethod
    async def record_referral(
        db_session: AsyncSession,
        referred_user_id: uuid.UUID,
        referral_code: str | None,
        attribution_source: str | None = "direct_ref",
        landing_page: str | None = "/",
    ) -> PartnerReferral | None:
        """Record customer attribution from cookie or ref parameter upon registration."""
        if not referral_code:
            return None

        clean_code = referral_code.strip().upper()
        partner = (
            await db_session.execute(
                select(AffiliatePartner).where(
                    func.lower(AffiliatePartner.referral_code) == clean_code.lower(),
                    AffiliatePartner.status == "active",
                )
            )
        ).scalar_one_or_none()

        if partner is None:
            logger.info("No active partner found for referral_code '%s'", clean_code)
            return None

        # Anti-self referral guard
        if partner.user_id == referred_user_id:
            logger.warning(
                "Self-referral rejected: user %s tried to refer themselves with code %s",
                referred_user_id,
                clean_code,
            )
            return None

        # Check if already referred
        existing = (
            await db_session.execute(
                select(PartnerReferral).where(
                    PartnerReferral.referred_user_id == referred_user_id
                )
            )
        ).scalar_one_or_none()

        if existing is not None:
            return existing

        referral = PartnerReferral(
            partner_id=partner.id,
            referred_user_id=referred_user_id,
            attribution_source=attribution_source or "direct_ref",
            landing_page=landing_page or "/",
        )
        db_session.add(referral)
        await db_session.commit()
        logger.info(
            "Referral successfully recorded: user %s -> partner %s (%s)",
            referred_user_id,
            partner.id,
            clean_code,
        )
        return referral

    @staticmethod
    async def credit_commission_for_purchase(
        db_session: AsyncSession,
        credit_purchase: CreditPurchase,
    ) -> PartnerCommission | None:
        """Calculate and credit 15% lifetime recurring commission upon purchase completion."""
        try:
            referral = (
                await db_session.execute(
                    select(PartnerReferral).where(
                        PartnerReferral.referred_user_id == credit_purchase.user_id
                    )
                )
            ).scalar_one_or_none()

            if referral is None:
                return None

            partner = (
                await db_session.execute(
                    select(AffiliatePartner)
                    .where(AffiliatePartner.id == referral.partner_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()

            if partner is None or partner.status != "active":
                return None

            # Calculate 15% commission on purchase
            source_amount_micros = credit_purchase.credit_micros_granted
            commission_rate = partner.commission_rate or DEFAULT_COMMISSION_RATE
            commission_micros = int(source_amount_micros * commission_rate)

            if commission_micros <= 0:
                return None

            commission = PartnerCommission(
                partner_id=partner.id,
                referral_id=referral.id,
                credit_purchase_id=credit_purchase.id,
                source_amount_micros=source_amount_micros,
                commission_micros=commission_micros,
                commission_rate=commission_rate,
                currency=credit_purchase.currency or "USD",
                status="settled",
            )
            db_session.add(commission)

            partner.balance_micros += commission_micros
            partner.total_earned_micros += commission_micros
            await db_session.flush()

            logger.info(
                "Credited 15%% commission of %d micros ($%.2f) to partner %s for purchase %s",
                commission_micros,
                micros_to_usd(commission_micros),
                partner.id,
                credit_purchase.id,
            )
            return commission
        except Exception as e:
            logger.error("Failed to credit partner commission: %s", e, exc_info=True)
            return None

    @staticmethod
    async def request_payout(
        db_session: AsyncSession,
        user_id: uuid.UUID,
        request: PartnerPayoutRequest,
    ) -> PartnerPayoutItem:
        """Process payout request via VietQR Napas 24/7 or platform credit conversion."""
        partner = (
            await db_session.execute(
                select(AffiliatePartner)
                .where(AffiliatePartner.user_id == user_id)
                .with_for_update()
            )
        ).scalar_one_or_none()

        if partner is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Affiliate partner profile not found.",
            )

        if partner.status != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Partner account is currently suspended.",
            )

        if request.amount_micros < MIN_PAYOUT_MICROS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Minimum payout request is ${micros_to_usd(MIN_PAYOUT_MICROS):.2f} ({micros_to_vnd(MIN_PAYOUT_MICROS):,} VND).",
            )

        if partner.balance_micros < request.amount_micros:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient balance. Available: ${micros_to_usd(partner.balance_micros):.2f}.",
            )

        payout_details = dict(partner.payout_details or {})
        payout_details.update(request.payout_details or {})
        payout_details["amount_vnd"] = micros_to_vnd(request.amount_micros)
        payout_details["exchange_rate"] = USD_TO_VND_RATE

        if request.payout_method == "credit_wallet":
            # Deduct balance immediately for instant credit conversion
            partner.balance_micros -= request.amount_micros
            partner.total_paid_micros += request.amount_micros

            # Instant conversion with +10% bonus into user wallet
            user = (
                await db_session.execute(
                    select(User).where(User.id == user_id).with_for_update()
                )
            ).scalar_one_or_none()

            if user is not None:
                bonus_micros = int(request.amount_micros * CREDIT_BONUS_MULTIPLIER)
                user.credit_micros_balance += bonus_micros

            now = datetime.now(UTC)
            payout = PartnerPayout(
                id=uuid.uuid4(),
                partner_id=partner.id,
                amount_micros=request.amount_micros,
                amount_vnd=micros_to_vnd(request.amount_micros),
                tax_deducted_micros=0,
                net_amount_micros=request.amount_micros,
                tax_code=None,
                payout_method="credit_wallet",
                payout_details=payout_details,
                status="completed",
                tx_reference=f"CREDIT-BONUS-{uuid.uuid4().hex[:8].upper()}",
                requested_at=now,
                processed_at=now,
                created_at=now,
                updated_at=now,
            )
        else:
            # For bank / VietQR payouts: balance is preserved in available_balance until
            # execute_payout_with_lock moves it to hold_balance_micros (Double-Entry AC-1).
            now = datetime.now(UTC)
            from app.services.partner_payout_service import PartnerPayoutService

            tax_info = PartnerPayoutService.calculate_pit_tax(request.amount_micros)
            payout = PartnerPayout(
                id=uuid.uuid4(),
                partner_id=partner.id,
                amount_micros=request.amount_micros,
                amount_vnd=micros_to_vnd(request.amount_micros),
                tax_deducted_micros=tax_info.tax_deducted_micros,
                net_amount_micros=tax_info.net_amount_micros,
                tax_code=tax_info.tax_code,
                payout_method=request.payout_method or "vietqr",
                payout_details=payout_details,
                status="pending",
                tx_reference=None,
                requested_at=now,
                created_at=now,
                updated_at=now,
            )

        db_session.add(payout)
        await db_session.commit()
        await db_session.refresh(payout)

        return PartnerPayoutItem(
            id=payout.id,
            amount_micros=payout.amount_micros,
            amount_usd=micros_to_usd(payout.amount_micros),
            amount_vnd=micros_to_vnd(payout.amount_micros),
            tax_deducted_micros=payout.tax_deducted_micros,
            tax_deducted_vnd=micros_to_vnd(payout.tax_deducted_micros),
            net_amount_micros=payout.net_amount_micros,
            net_amount_vnd=micros_to_vnd(payout.net_amount_micros),
            tax_code=payout.tax_code,
            payout_method=payout.payout_method,
            payout_details=payout.payout_details,
            status=payout.status,
            tx_reference=payout.tx_reference,
            napas_ref=payout.napas_ref,
            hmac_audit_hash=payout.hmac_audit_hash,
            requested_at=payout.requested_at,
            processed_at=payout.processed_at,
            created_at=payout.created_at,
        )

    @staticmethod
    async def list_referrals(
        db_session: AsyncSession,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> PartnerReferralsListResponse:
        """List referred users with masked email and total contribution."""
        partner = (
            await db_session.execute(
                select(AffiliatePartner).where(AffiliatePartner.user_id == user_id)
            )
        ).scalar_one_or_none()

        if partner is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Affiliate partner profile not found.",
            )

        query = (
            select(
                PartnerReferral,
                User.email,
                func.coalesce(
                    func.sum(PartnerCommission.source_amount_micros), 0
                ).label("total_spent"),
                func.coalesce(func.sum(PartnerCommission.commission_micros), 0).label(
                    "total_commission"
                ),
            )
            .join(User, User.id == PartnerReferral.referred_user_id)
            .outerjoin(
                PartnerCommission, PartnerCommission.referral_id == PartnerReferral.id
            )
            .where(PartnerReferral.partner_id == partner.id)
            .group_by(PartnerReferral.id, User.email)
            .order_by(PartnerReferral.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        rows = (await db_session.execute(query)).all()

        total_count = (
            await db_session.execute(
                select(func.count(PartnerReferral.id)).where(
                    PartnerReferral.partner_id == partner.id
                )
            )
        ).scalar() or 0

        items: list[PartnerReferralItem] = []
        for ref, email, total_spent, total_comm in rows:
            # Mask email (e.g. j***@gmail.com)
            masked_email = "user@domain.com"
            if email and "@" in email:
                local_part, domain = email.split("@", 1)
                masked_local = (
                    local_part[0] + "***" if len(local_part) > 1 else local_part + "***"
                )
                masked_email = f"{masked_local}@{domain}"

            items.append(
                PartnerReferralItem(
                    id=ref.id,
                    referred_user_id=ref.referred_user_id,
                    masked_email=masked_email,
                    attribution_source=ref.attribution_source,
                    landing_page=ref.landing_page,
                    total_spent_micros=total_spent,
                    total_commission_micros=total_comm,
                    created_at=ref.created_at,
                )
            )

        return PartnerReferralsListResponse(referrals=items, total_count=total_count)

    @staticmethod
    async def list_commissions(
        db_session: AsyncSession,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> PartnerCommissionsListResponse:
        """List commission ledger entries."""
        partner = (
            await db_session.execute(
                select(AffiliatePartner).where(AffiliatePartner.user_id == user_id)
            )
        ).scalar_one_or_none()

        if partner is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Affiliate partner profile not found.",
            )

        query = (
            select(PartnerCommission)
            .where(PartnerCommission.partner_id == partner.id)
            .order_by(PartnerCommission.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        commissions = (await db_session.execute(query)).scalars().all()

        total_count = (
            await db_session.execute(
                select(func.count(PartnerCommission.id)).where(
                    PartnerCommission.partner_id == partner.id
                )
            )
        ).scalar() or 0

        items = [
            PartnerCommissionItem(
                id=c.id,
                referral_id=c.referral_id,
                credit_purchase_id=c.credit_purchase_id,
                source_amount_micros=c.source_amount_micros,
                source_amount_usd=micros_to_usd(c.source_amount_micros),
                commission_micros=c.commission_micros,
                commission_usd=micros_to_usd(c.commission_micros),
                commission_vnd=micros_to_vnd(c.commission_micros),
                commission_rate=c.commission_rate,
                currency=c.currency,
                status=c.status,
                created_at=c.created_at,
            )
            for c in commissions
        ]

        return PartnerCommissionsListResponse(
            commissions=items,
            total_count=total_count,
            total_commission_micros=partner.total_earned_micros,
        )

    @staticmethod
    async def list_payouts(
        db_session: AsyncSession,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> PartnerPayoutsListResponse:
        """List payout history."""
        partner = (
            await db_session.execute(
                select(AffiliatePartner).where(AffiliatePartner.user_id == user_id)
            )
        ).scalar_one_or_none()

        if partner is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Affiliate partner profile not found.",
            )

        query = (
            select(PartnerPayout)
            .where(PartnerPayout.partner_id == partner.id)
            .order_by(PartnerPayout.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        payouts = (await db_session.execute(query)).scalars().all()

        total_count = (
            await db_session.execute(
                select(func.count(PartnerPayout.id)).where(
                    PartnerPayout.partner_id == partner.id
                )
            )
        ).scalar() or 0

        items = [
            PartnerPayoutItem(
                id=p.id,
                amount_micros=p.amount_micros,
                amount_usd=micros_to_usd(p.amount_micros),
                amount_vnd=micros_to_vnd(p.amount_micros),
                tax_deducted_micros=p.tax_deducted_micros or 0,
                tax_deducted_vnd=micros_to_vnd(p.tax_deducted_micros or 0),
                net_amount_micros=p.net_amount_micros or p.amount_micros,
                net_amount_vnd=micros_to_vnd(p.net_amount_micros or p.amount_micros),
                tax_code=p.tax_code,
                payout_method=p.payout_method,
                payout_details=p.payout_details,
                status=p.status,
                tx_reference=p.tx_reference,
                napas_ref=p.napas_ref,
                hmac_audit_hash=p.hmac_audit_hash,
                requested_at=p.requested_at,
                processed_at=p.processed_at,
                created_at=p.created_at,
            )
            for p in payouts
        ]

        return PartnerPayoutsListResponse(payouts=items, total_count=total_count)
