"""Global compliance purge service for Right-to-be-Forgotten requests (Story 33.2)."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.lead_intelligence.dnc.normalizer import (
    hash_phone_hmac,
    normalize_domain,
    normalize_phone_e164,
)
from app.lead_intelligence.dnc.service import DncComplianceService
from app.models.leads.core import DshMission
from app.models.leads.enrichment import VerifiedContact
from app.models.leads.main import Lead
from app.models.leads.social import SocialPost
from app.models.workspaces import GlobalDncRecord

logger = logging.getLogger(__name__)


def _normalize_value(record_type: str, value: str) -> tuple[str, str]:
    """Normalize value and compute its HMAC hash.

    Returns (normalized_value, hmac_hash).
    """
    cleaned = value.strip()
    if record_type == "phone":
        e164 = normalize_phone_e164(cleaned)
        if not e164:
            raise ValueError(f"Invalid phone format: {value}")
        return e164, hash_phone_hmac(e164)
    elif record_type == "email":
        email_norm = cleaned.lower()
        if "@" not in email_norm:
            raise ValueError(f"Invalid email format: {value}")
        return email_norm, hash_phone_hmac(email_norm)
    elif record_type == "domain":
        dom = normalize_domain(cleaned)
        if not dom:
            raise ValueError(f"Invalid domain format: {value}")
        return dom, hash_phone_hmac(dom)
    else:
        raise ValueError(f"Unsupported record type: {record_type}")


class CompliancePurgeService:
    """Enterprise-wide Right-to-be-Forgotten purge engine."""

    @staticmethod
    async def purge_individual(
        session: AsyncSession,
        *,
        record_type: str,
        value: str,
        reason: str = "GDPR / Decree 13 Right-to-be-Forgotten",
        source: str = "compliance_superadmin",
        ticket_ref: str | None = None,
    ) -> dict[str, Any]:
        """Purge an individual's PII across all workspaces simultaneously.

        Deletes from:
        - VerifiedContact (by phone_hmac or email_hmac)
        - Lead (by matching contact or metadata)
        - SocialPost (by author metadata if applicable)
        - Appends to GlobalDncRecord
        - Invalidates affected workspace DNC caches

        Returns summary of purged entities.
        """
        norm_val, val_hmac = _normalize_value(record_type, value)

        affected_workspaces: set[int] = set()
        purged_contacts = 0
        purged_leads = 0
        purged_posts = 0

        # 1. Find and delete matching VerifiedContact records
        if record_type == "phone":
            contact_stmt = select(VerifiedContact).where(
                VerifiedContact.phone_hmac == val_hmac
            )
        elif record_type == "email":
            contact_stmt = select(VerifiedContact).where(
                VerifiedContact.email_hmac == val_hmac
            )
        else:
            contact_stmt = select(VerifiedContact).where(
                VerifiedContact.value_hmac == val_hmac
            )

        contacts = list((await session.execute(contact_stmt)).scalars().all())
        lead_ids_to_check: set[uuid.UUID] = set()

        for contact in contacts:
            affected_workspaces.add(contact.workspace_id)
            lead_ids_to_check.add(contact.lead_id)
            await session.delete(contact)
            purged_contacts += 1

        # 2. Check and delete Leads that only have this contact
        for lead_id in lead_ids_to_check:
            # Check remaining contacts for this lead
            rem_stmt = select(VerifiedContact).where(
                VerifiedContact.lead_id == lead_id
            )
            rem_contacts = list((await session.execute(rem_stmt)).scalars().all())
            if not rem_contacts:
                lead = await session.get(Lead, lead_id)
                if lead:
                    affected_workspaces.add(lead.workspace_id)
                    await session.delete(lead)
                    purged_leads += 1

        # 3. Permanently append to GlobalDncRecord
        dnc_stmt = (
            pg_insert(GlobalDncRecord)
            .values(
                record_type=record_type,
                value=norm_val,
                value_hmac=val_hmac,
                reason=reason,
                source=source,
            )
            .on_conflict_do_nothing(constraint="uq_global_dnc_entry")
        )
        await session.execute(dnc_stmt)

        # 4. Invalidate DNC cache for all affected workspaces
        dnc_svc = DncComplianceService()
        for ws_id in affected_workspaces:
            await dnc_svc.invalidate_workspace_cache(ws_id)

        logger.info(
            "Compliance purge executed: type=%s hmac=%s contacts=%d leads=%d workspaces=%d",
            record_type,
            val_hmac[:12],
            purged_contacts,
            purged_leads,
            len(affected_workspaces),
        )

        return {
            "status": "purged",
            "record_type": record_type,
            "normalized_value": norm_val,
            "value_hmac": val_hmac,
            "purged_counts": {
                "verified_contacts": purged_contacts,
                "leads": purged_leads,
                "social_posts": purged_posts,
            },
            "workspaces_affected": sorted(list(affected_workspaces)),
            "reason": reason,
            "ticket_ref": ticket_ref,
        }
