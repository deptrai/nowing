"""Shared Contact Unlock Service (Story 26.6 / Story 26.5).

Used by REST route (POST .../contacts/{contact_id}/unlock) and Telegram interactive checkpoint bot.
Handles DNC gating, wallet debit (1,500 micros), PII decryption, audit logging, and idempotency.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import Lead, VerifiedContact
from app.lead_intelligence.dnc.service import DncComplianceService
from app.services import wallet_credit
from app.services.billing_event_service import (
    BillingEventService,
    _list_billing_events,
)
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption

logger = logging.getLogger(__name__)


class ContactUnlockResult(BaseModel):
    """Result of unlocking a verified contact."""

    contact_id: UUID
    is_unlocked: bool
    cost_micros: int
    name: str | None = None
    title: str | None = None
    email: str | None = None
    phone: str | None = None


class ContactUnlockService:
    """Service encapsulating business rules for verified contact unlock."""

    def __init__(
        self,
        encryption: VerifiedContactEncryption | None = None,
        dnc_service: DncComplianceService | None = None,
        billing_event_service: BillingEventService | None = None,
    ) -> None:
        self.enc = encryption or VerifiedContactEncryption()
        self.dnc = dnc_service or DncComplianceService(secret_key=config.SECRET_KEY)
        self.billing = billing_event_service or BillingEventService()

    def decrypt_field(self, value: str | None) -> str | None:
        if not value:
            return None
        if self.enc.is_encrypted(value):
            try:
                return self.enc.decrypt(value)
            except Exception:
                return None
        try:
            decrypted = self.enc.decrypt(value)
            if decrypted is not None:
                return decrypted
        except Exception:
            pass
        return value

    async def unlock_contact(
        self,
        session: AsyncSession,
        workspace_id: int,
        contact: VerifiedContact,
        user_id: UUID,
        *,
        lead: Lead | None = None,
        ip_address: str | None = None,
        reason: str = "contact_unlock",
    ) -> ContactUnlockResult:
        """Unlock a contact, checking DNC and wallet, decrypting PII, and logging audit."""
        # 1. Reject purged / withdrawn / invalid contacts
        if not contact.is_valid:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Contact is marked invalid and cannot be unlocked.",
            )
        if contact.consent_status == "withdrawn":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Contact consent has been withdrawn and cannot be unlocked.",
            )

        # 2. Idempotency: if already unlocked, return decrypted PII with 0 cost
        if contact.is_unlocked:
            return ContactUnlockResult(
                contact_id=contact.id,
                is_unlocked=True,
                cost_micros=0,
                name=self.decrypt_field(contact.name),
                title=self.decrypt_field(contact.title),
                email=self.decrypt_field(contact.email),
                phone=self.decrypt_field(contact.phone),
            )

        # 3. Fail-closed DNC check
        decrypted_phone = self.decrypt_field(contact.phone)
        decrypted_email = self.decrypt_field(contact.email)
        domain = getattr(lead, "domain", None) if lead else None

        dnc_result = await self.dnc.is_blocked(
            workspace_id=workspace_id,
            phone=decrypted_phone,
            email=decrypted_email,
            domain=domain,
            session=session,
        )
        if dnc_result.is_blocked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Contact is blocked by DNC: {dnc_result.reason}",
            )

        # 4. Attempt billing
        existing_unlocks = await _list_billing_events(
            session,
            event_entity_type="verified_contact",
            event_type="contact_unlock",
            event_id=contact.id,
            workspace_id=workspace_id,
        )
        is_re_unlock = bool(existing_unlocks)

        try:
            billing_event = await self.billing.record_contact_unlock(
                session,
                verified_contact_id=contact.id,
                workspace_id=workspace_id,
                client_id=None,
                user_id=user_id,
                cost_micros=1_500,
            )
        except wallet_credit.InsufficientCreditsError as exc:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Insufficient credits to unlock contact.",
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Billing validation failed.",
            ) from exc
        except Exception as exc:
            logger.exception(
                "Failed to bill unlock for contact %s: %s", contact.id, exc
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to unlock contact.",
            ) from exc

        # 5. Update contact state and audit log
        contact.is_unlocked = True
        existing_logs = list(contact.pii_access_audit_logs or [])
        contact.pii_access_audit_logs = [
            *existing_logs,
            {
                "user_id": str(user_id),
                "workspace_id": workspace_id,
                "lead_id": str(contact.lead_id),
                "contact_id": str(contact.id),
                "access_type": "unlock",
                "timestamp": datetime.now(UTC).isoformat(),
                "ip_address": ip_address,
                "reason": reason,
            },
        ]

        result_cost = 0 if is_re_unlock else (getattr(billing_event, "cost_micros", 1_500) or 1_500)
        return ContactUnlockResult(
            contact_id=contact.id,
            is_unlocked=True,
            cost_micros=result_cost,
            name=self.decrypt_field(contact.name),
            title=self.decrypt_field(contact.title),
            email=decrypted_email,
            phone=decrypted_phone,
        )
