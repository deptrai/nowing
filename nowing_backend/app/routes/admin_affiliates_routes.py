"""Admin routes for Affiliate Partner Payout Desk & Anti-Fraud Engine (Story 25.3)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import AffiliatePartner, AuditEvent, PartnerPayout, User, get_async_session
from app.redis_client import get_redis_client
from app.schemas.admin_affiliate_payouts import (
    AdminPayoutItem,
    AdminPayoutListResponse,
    PayoutApproveResponse,
    PayoutRejectRequest,
    PayoutRejectResponse,
    PayoutRiskResponse,
)
from app.services.affiliate_anti_fraud_service import (
    AffiliateAntiFraudService,
    verify_bank_name_match,
)
from app.services.partner_payout_service import PartnerPayoutService
from app.services.partner_service import micros_to_vnd
from app.services.vietqr_payout_client import VietQRPayoutClient
from app.users import AuthContext, require_superuser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/affiliates", tags=["admin_affiliates"])

_VALID_PAYOUT_STATUSES = {"pending", "processing", "completed", "rejected"}


def _get_vnd_amounts(payout: PartnerPayout) -> tuple[int, int, int]:
    """Return (gross_vnd, tax_vnd, net_vnd) derived from stored micro amounts."""
    tax_info = PartnerPayoutService.calculate_pit_tax(payout.amount_micros)
    gross_vnd = micros_to_vnd(payout.amount_micros)
    tax_vnd = micros_to_vnd(tax_info.tax_deducted_micros)
    net_vnd = micros_to_vnd(tax_info.net_amount_micros)
    return gross_vnd, tax_vnd, net_vnd


def _name_match_status(details: dict) -> str:
    """Compute name match status from cached payout_details."""
    if details.get("name_match_verified") is True:
        return "100% Match" if details.get("name_match_status") == "100% Match" else "Name Mismatch"
    return "Unverified"


@router.get("/payouts", response_model=AdminPayoutListResponse)
async def list_admin_affiliate_payouts(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
) -> AdminPayoutListResponse:
    """AC-1: List all affiliate payout requests with tax deductions, name match badges, and fraud risk."""
    if status and status not in _VALID_PAYOUT_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status '{status}'. Allowed: {sorted(_VALID_PAYOUT_STATUSES)}",
        )

    base_query = (
        select(PartnerPayout, AffiliatePartner, User)
        .join(AffiliatePartner, PartnerPayout.partner_id == AffiliatePartner.id)
        .join(User, AffiliatePartner.user_id == User.id)
    )

    if status:
        base_query = base_query.where(PartnerPayout.status == status)

    count_query = select(func.count()).select_from(base_query.subquery())
    total_res = await session.execute(count_query)
    total = total_res.scalar_one() or 0

    payout_stmt = (
        base_query.order_by(PartnerPayout.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    res = await session.execute(payout_stmt)
    rows = res.all()

    items: list[AdminPayoutItem] = []
    for row in rows:
        payout: PartnerPayout = row[0]
        partner: AffiliatePartner = row[1]
        user: User = row[2]

        details = payout.payout_details or {}
        gross_vnd, pit_tax_vnd, net_vnd = _get_vnd_amounts(payout)

        account_holder = details.get("account_holder") or ""
        name_match_status = _name_match_status(details)

        risk_score = details.get("risk_score", 10)
        risk_level = details.get("risk_level", "low")
        risk_reasons = details.get("risk_reasons", [])

        items.append(
            AdminPayoutItem(
                id=str(payout.id),
                partner_id=str(partner.id),
                partner_name=getattr(user, "email", partner.referral_code),
                partner_email=getattr(user, "email", None),
                partner_code=partner.referral_code,
                partner_tier=partner.partner_type,
                gross_amount_vnd=gross_vnd,
                pit_tax_deduction_vnd=pit_tax_vnd,
                net_payout_amount_vnd=net_vnd,
                bank_bin=details.get("bank_bin"),
                bank_short_name=details.get("bank_short_name") or details.get("bank_name"),
                account_number=details.get("account_number"),
                account_holder=account_holder,
                name_match_status=name_match_status,
                risk_score=risk_score,
                risk_level=risk_level,
                risk_reasons=risk_reasons,
                status=payout.status,
                tx_reference=payout.tx_reference,
                created_at=payout.created_at,
                processed_at=payout.processed_at,
            )
        )

    return AdminPayoutListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/payouts/{payout_id}/evaluate", response_model=PayoutRiskResponse)
async def evaluate_affiliate_payout_risk(
    payout_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
) -> PayoutRiskResponse:
    """AC-2: Evaluate fraud risk and self-referral rings for an affiliate payout."""
    anti_fraud_service = AffiliateAntiFraudService(session=session)
    result = await anti_fraud_service.evaluate_payout_risk(payout_id)

    payout = await session.get(PartnerPayout, payout_id)
    if payout:
        partner = await session.get(AffiliatePartner, payout.partner_id)
        audit_event = AuditEvent(
            action="affiliate_payout_evaluate",
            actor_id=auth.user.id,
            subject_id=partner.user_id if partner else None,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            diff_payload={
                "payout_id": str(payout_id),
                "risk_score": result["risk_score"],
                "risk_level": result["risk_level"],
                "reasons": result["reasons"],
            },
        )
        session.add(audit_event)
        await session.commit()

    return PayoutRiskResponse(
        payout_id=result["payout_id"],
        risk_score=result["risk_score"],
        risk_level=result["risk_level"],
        reasons=result["reasons"],
        evaluated_at=result["evaluated_at"],
    )


async def _release_payout_lock(redis_client, lock_key: str) -> None:
    try:
        await redis_client.delete(lock_key)
    except Exception:
        logger.exception("Failed to release Redis lock %s", lock_key)


@router.post("/payouts/{payout_id}/approve", response_model=PayoutApproveResponse)
async def approve_affiliate_payout(
    payout_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
) -> PayoutApproveResponse:
    """AC-3 / INV-25.2: 1-Click Napas 24/7 VietQR payout dispatch with distributed lock and audit event."""
    # Pre-checks: payout must exist and risk/name-match must not block one-click approval.
    payout = await session.get(PartnerPayout, payout_id)
    if not payout:
        raise HTTPException(status_code=404, detail="Partner payout request not found")

    details = payout.payout_details or {}
    risk_score = details.get("risk_score")
    risk_level = details.get("risk_level", "low")
    if risk_score is None:
        # Require an explicit risk evaluation before approval.
        anti_fraud_service = AffiliateAntiFraudService(session=session)
        await anti_fraud_service.evaluate_payout_risk(payout_id)
        # evaluate_payout_risk commits, so reload the payout to get cached risk.
        payout = await session.get(PartnerPayout, payout_id)
        details = payout.payout_details or {}
        risk_score = details.get("risk_score", 10)
        risk_level = details.get("risk_level", "low")

    if risk_score >= 70:
        raise HTTPException(
            status_code=409,
            detail=f"Payout is high risk ({risk_score}/100, {risk_level}). Supervisor review required.",
        )

    if _name_match_status(details) == "Name Mismatch":
        raise HTTPException(
            status_code=409,
            detail="Payout bank account name mismatch. Reject or verify before approval.",
        )

    if payout.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Payout {payout_id} is already in '{payout.status}' status",
        )

    # 2-tier lock: Redis first, then SELECT ... FOR UPDATE in execute_payout_with_lock.
    redis_client = await get_redis_client()
    lock_key = f"lock:payout:{payout_id}"
    lock_acquired = await redis_client.set(lock_key, "1", nx=True, ex=10)
    if not lock_acquired:
        raise HTTPException(
            status_code=409,
            detail="Payout is already being processed by another request",
        )

    gateway_response: dict | None = None
    try:
        # Use a deterministic tx_reference based on the payout creation time for idempotency.
        created_at_ts = int(payout.created_at.timestamp()) if payout.created_at else int(datetime.now(UTC).timestamp())
        deterministic_tx_ref = f"payout_{payout_id}_{created_at_ts}"

        # Row-level locked payout execution (INV-23.10 / AC-3)
        payout = await PartnerPayoutService.execute_payout_with_lock(
            session=session,
            payout_id=payout_id,
            tx_reference=deterministic_tx_ref,
        )

        partner = await session.get(AffiliatePartner, payout.partner_id)
        if not partner:
            raise HTTPException(status_code=404, detail="Affiliate partner record not found")

        payout_details = dict(payout.payout_details or {})
        bank_bin = payout_details.get("bank_bin")
        account_number = payout_details.get("account_number")
        account_holder = payout_details.get("account_holder", "")

        if not bank_bin or not account_number or not account_holder:
            raise HTTPException(
                status_code=422,
                detail="Missing bank_bin, account_number, or account_holder in payout details",
            )

        net_amount_vnd = micros_to_vnd(payout.net_amount_micros or payout.amount_micros)

        # Dispatch to VietQR / Napas 24/7 gateway.
        client = VietQRPayoutClient(
            client_id=getattr(config, "VIETQR_CLIENT_ID", "") or "",
            api_key=getattr(config, "VIETQR_API_KEY", "") or "",
            webhook_secret=getattr(config, "VIETQR_WEBHOOK_SECRET", "") or "",
        )
        try:
            gateway_response = await client.initiate_payout(
                tx_reference=payout.tx_reference,
                amount_vnd=net_amount_vnd,
                bank_bin=bank_bin,
                account_number=account_number,
                account_name=account_holder,
                memo="NUTX PAYOUT",
            )
        except Exception as exc:
            logger.exception("VietQR initiate_payout failed for %s: %s", payout_id, exc)
            # Gateway could not be reached. Leave in 'processing' so Celery reconciliation
            # can recover or mark as failed after checking gateway status.
            raise HTTPException(
                status_code=502,
                detail="VietQR gateway unavailable; payout will be reconciled automatically",
            ) from exc

        beneficiary_name = gateway_response.get("beneficiary_name")
        if beneficiary_name:
            is_match, _ = verify_bank_name_match(account_holder, beneficiary_name)
            payout_details["beneficiary_name"] = beneficiary_name
            payout_details["name_match_verified"] = True
            payout_details["name_match_status"] = "100% Match" if is_match else "Name Mismatch"
            if not is_match:
                # Name mismatch: reject and refund the held balance immediately.
                if partner.hold_balance_micros >= payout.amount_micros:
                    partner.hold_balance_micros -= payout.amount_micros
                    partner.balance_micros += payout.amount_micros
                payout.status = "rejected"
                payout_details["rejection_reason"] = "name_mismatch"
                payout.payout_details = payout_details
                await session.flush()

                audit_event = AuditEvent(
                    action="affiliate_payout_reject",
                    actor_id=auth.user.id,
                    subject_id=partner.user_id,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    diff_payload={
                        "payout_id": str(payout.id),
                        "status": "rejected",
                        "rejection_reason": "name_mismatch",
                        "beneficiary_name": beneficiary_name,
                        "account_holder": account_holder,
                        "rolled_back_amount_micros": payout.amount_micros,
                    },
                )
                session.add(audit_event)
                await session.commit()
                raise HTTPException(
                    status_code=409,
                    detail="Bank account name mismatch. Payout rejected and balance refunded.",
                )
        else:
            payout_details["name_match_verified"] = False
            payout_details["name_match_status"] = "Unverified"

        if gateway_response.get("napas_ref"):
            payout.napas_ref = gateway_response["napas_ref"]

        payout.payout_details = payout_details
        await session.flush()

        # Log immutable audit event (INV-25.2)
        audit_event = AuditEvent(
            action="affiliate_payout_approve",
            actor_id=auth.user.id,
            subject_id=partner.user_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            diff_payload={
                "payout_id": str(payout.id),
                "status": payout.status,
                "amount_micros": payout.amount_micros,
                "net_amount_micros": payout.net_amount_micros,
                "tax_deducted_micros": payout.tax_deducted_micros,
                "tx_reference": payout.tx_reference,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "name_match_status": payout_details.get("name_match_status"),
                "beneficiary_name": beneficiary_name,
            },
        )
        session.add(audit_event)
        await session.commit()

        return PayoutApproveResponse(
            status=payout.status,
            payout_id=str(payout.id),
            tx_reference=payout.tx_reference or deterministic_tx_ref,
            amount_micros=payout.amount_micros,
            net_amount_micros=payout.net_amount_micros or payout.amount_micros,
        )
    finally:
        await _release_payout_lock(redis_client, lock_key)


@router.post("/payouts/{payout_id}/reject", response_model=PayoutRejectResponse)
async def reject_affiliate_payout(
    payout_id: uuid.UUID,
    payload: PayoutRejectRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
) -> PayoutRejectResponse:
    """AC-4: Reject payout request, rollback held commission balance to available, and log reason."""
    payout_stmt = (
        select(PartnerPayout).where(PartnerPayout.id == payout_id).with_for_update()
    )
    payout_res = await session.execute(payout_stmt)
    payout = payout_res.scalar_one_or_none()

    if not payout:
        raise HTTPException(status_code=404, detail="Partner payout request not found")

    if payout.status not in ("pending", "processing"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot reject payout in '{payout.status}' status",
        )

    partner_stmt = (
        select(AffiliatePartner)
        .where(AffiliatePartner.id == payout.partner_id)
        .with_for_update()
    )
    partner_res = await session.execute(partner_stmt)
    partner = partner_res.scalar_one_or_none()

    if not partner:
        raise HTTPException(status_code=404, detail="Affiliate partner record not found")

    # Roll back the actual amount that is currently on hold (never more than amount_micros).
    rollback_amount = min(partner.hold_balance_micros, payout.amount_micros)
    if rollback_amount > 0:
        partner.hold_balance_micros -= rollback_amount
        partner.balance_micros += rollback_amount

    payout.status = "rejected"
    payout_details = dict(payout.payout_details or {})
    payout_details["rejection_reason"] = payload.rejection_reason.value
    if payload.notes:
        payout_details["rejection_notes"] = payload.notes
    payout_details["rejected_at"] = datetime.now(UTC).isoformat()
    payout.payout_details = payout_details

    # Log immutable audit event (INV-25.2)
    audit_event = AuditEvent(
        action="affiliate_payout_reject",
        actor_id=auth.user.id,
        subject_id=partner.user_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        diff_payload={
            "payout_id": str(payout.id),
            "status": "rejected",
            "rejection_reason": payload.rejection_reason.value,
            "rejection_notes": payload.notes,
            "rolled_back_amount_micros": rollback_amount,
        },
    )
    session.add(audit_event)
    await session.commit()

    return PayoutRejectResponse(
        status="rejected",
        payout_id=str(payout.id),
        rejection_reason=payload.rejection_reason.value,
        rolled_back_balance_micros=rollback_amount,
    )
