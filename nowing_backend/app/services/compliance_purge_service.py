"""Global compliance purge service for Right-to-be-Forgotten requests (Story 33.2)."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import Text, cast, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.lead_intelligence.dnc.normalizer import (
    hash_phone_hmac,
    normalize_domain,
    normalize_phone_e164,
)
from app.lead_intelligence.dnc.service import DncComplianceService
from app.models.leads.enrichment import VerifiedContact
from app.models.leads.main import Lead
from app.models.leads.social import SocialPost
from app.models.workspaces import GlobalDncRecord
from app.notifications import NotificationService
from app.services.billing_event_service import (
    BillingEventService,
    NoOriginalUnlockEventError,
    RefundAlreadyProcessedError,
    RefundBudgetExhaustedError,
    RefundWindowExpiredError,
    _list_billing_events,
)

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
        lead_keys_to_check: set[tuple[uuid.UUID, int]] = set()
        refund_candidates: list[dict[str, Any]] = []

        for contact in contacts:
            if contact.workspace_id is not None:
                affected_workspaces.add(contact.workspace_id)
                if contact.lead_id is not None:
                    lead_keys_to_check.add((contact.lead_id, contact.workspace_id))
                refund_candidates.append(
                    {
                        "verified_contact_id": contact.id,
                        "workspace_id": contact.workspace_id,
                        "was_unlocked": bool(contact.is_unlocked),
                    }
                )
            await session.delete(contact)
            purged_contacts += 1

        # 2. Check and delete Leads that only have this contact
        if lead_keys_to_check:
            await session.flush()
        for lead_id, ws_id in lead_keys_to_check:
            # Check remaining contacts for this lead
            rem_stmt = select(VerifiedContact).where(
                VerifiedContact.lead_id == lead_id,
                VerifiedContact.workspace_id == ws_id,
            )
            rem_contacts = list((await session.execute(rem_stmt)).scalars().all())
            if not rem_contacts:
                lead = await session.get(Lead, (lead_id, ws_id))
                if lead:
                    affected_workspaces.add(lead.workspace_id)
                    await session.delete(lead)
                    purged_leads += 1

        # 3. Find and delete matching SocialPost records containing this PII
        post_filters = []
        candidate_values = {
            v for v in [norm_val, value.strip(), value.strip().lstrip("+")] if v
        }
        for v in candidate_values:
            v_esc = v.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            post_filters.append(
                cast(SocialPost.raw_entities, Text).like(f'%"{v_esc}"%')
            )
            post_filters.append(SocialPost.content.like(f"%{v_esc}%"))
            post_filters.append(SocialPost.author_id == v)
            post_filters.append(SocialPost.author_name == v)

        if post_filters:
            post_stmt = select(SocialPost).where(or_(*post_filters))
            posts = list((await session.execute(post_stmt)).scalars().all())
            for post in posts:
                if post.workspace_id:
                    affected_workspaces.add(post.workspace_id)
                await session.delete(post)
                purged_posts += 1

        # 4. Permanently append to GlobalDncRecord
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

        # 5. Invalidate DNC cache for all affected workspaces
        dnc_svc = DncComplianceService()
        for ws_id in affected_workspaces:
            await dnc_svc.invalidate_workspace_cache(ws_id)

        logger.info(
            "Compliance purge executed: type=%s hmac=%s contacts=%d leads=%d posts=%d workspaces=%d",
            record_type,
            val_hmac[:12],
            purged_contacts,
            purged_leads,
            purged_posts,
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
            "workspaces_affected": sorted(affected_workspaces),
            "refund_candidates": refund_candidates,
            "reason": reason,
            "ticket_ref": ticket_ref,
        }

    @classmethod
    async def process_post_purge_refunds(
        cls,
        session: AsyncSession,
        *,
        refund_candidates: list[dict[str, Any]],
        actor_user_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Phase 2: Post-commit credit refund loop and notifications (Story 33.4).

        Iterates over deleted contact candidates, refunds credits for contacts
        unlocked within the 30-day (720h) window, records skips, and sends
        in-app notifications to workspace owners without PII.
        """
        from app.config.dsh import COMPLIANCE_PURGE_REFUND_WINDOW_HOURS
        from app.models.workspaces import Workspace

        refund_window_hours = COMPLIANCE_PURGE_REFUND_WINDOW_HOURS

        refunded_contacts = 0
        refunded_micros = 0
        skipped: list[dict[str, Any]] = []
        details: list[dict[str, Any]] = []

        workspace_purged_count: dict[int, int] = {}
        workspace_refunds: dict[int, int] = {}
        workspace_refunded_count: dict[int, int] = {}
        workspace_expired: dict[int, int] = {}
        workspace_owners: dict[int, uuid.UUID | None] = {}

        async def _workspace_owner_id(ws_id: int) -> uuid.UUID | None:
            if ws_id not in workspace_owners:
                ws = await session.get(Workspace, ws_id)
                workspace_owners[ws_id] = getattr(ws, "user_id", None)
            return workspace_owners[ws_id]

        billing_svc = BillingEventService()
        for candidate in refund_candidates:
            c_id = candidate.get("verified_contact_id")
            ws_id = candidate.get("workspace_id")
            if not c_id or ws_id is None:
                continue

            contact_id = (
                uuid.UUID(str(c_id)) if not isinstance(c_id, uuid.UUID) else c_id
            )
            ws_id = int(ws_id)
            workspace_purged_count[ws_id] = workspace_purged_count.get(ws_id, 0) + 1

            # Contacts that were never unlocked cannot have billing events
            if not candidate.get("was_unlocked", True):
                continue

            try:
                # 1. Idempotency: check if already refunded
                existing_refunds = await _list_billing_events(
                    session,
                    event_entity_type="verified_contact",
                    event_type="contact_unlock_refund",
                    event_id=contact_id,
                    workspace_id=ws_id,
                )
                if existing_refunds:
                    logger.info(
                        "Contact %s in workspace %d already refunded; skipping",
                        contact_id,
                        ws_id,
                    )
                    skipped.append(
                        {
                            "verified_contact_id": str(contact_id),
                            "workspace_id": ws_id,
                            "reason": "already_refunded",
                        }
                    )
                    continue

                # 2. Check for original unlock event and determine cost
                original_unlocks = await _list_billing_events(
                    session,
                    event_entity_type="verified_contact",
                    event_type="contact_unlock",
                    event_id=contact_id,
                    workspace_id=ws_id,
                )
                if not original_unlocks:
                    logger.info(
                        "No original unlock billing event for contact %s in workspace %d; skipping",
                        contact_id,
                        ws_id,
                    )
                    skipped.append(
                        {
                            "verified_contact_id": str(contact_id),
                            "workspace_id": ws_id,
                            "reason": "no_unlock_charge",
                        }
                    )
                    continue

                original_unlock = original_unlocks[0]
                orig_cost = getattr(original_unlock, "cost_micros", None)
                cost_micros = orig_cost if orig_cost is not None else 1500
                target_user_id = getattr(original_unlock, "user_id", None)
                if target_user_id is None:
                    target_user_id = await _workspace_owner_id(ws_id)
                if target_user_id is None:
                    logger.warning(
                        "Cannot resolve refund recipient for contact %s in workspace %d; skipping",
                        contact_id,
                        ws_id,
                    )
                    skipped.append(
                        {
                            "verified_contact_id": str(contact_id),
                            "workspace_id": ws_id,
                            "reason": "missing_user_id",
                        }
                    )
                    continue

                # 3. Call record_contact_unlock_refund_24h with compliance refund window
                event = await billing_svc.record_contact_unlock_refund_24h(
                    session,
                    verified_contact_id=contact_id,
                    workspace_id=ws_id,
                    user_id=target_user_id,
                    cost_micros=cost_micros,
                    refund_window_hours=refund_window_hours,
                )
                refund_amount = abs(getattr(event, "cost_micros", cost_micros))
                refunded_contacts += 1
                refunded_micros += refund_amount
                workspace_refunds[ws_id] = (
                    workspace_refunds.get(ws_id, 0) + refund_amount
                )
                workspace_refunded_count[ws_id] = (
                    workspace_refunded_count.get(ws_id, 0) + 1
                )
                details.append(
                    {
                        "contact_id": str(contact_id),
                        "workspace_id": ws_id,
                        "status": "refunded",
                        "refunded_micros": refund_amount,
                    }
                )
            except RefundWindowExpiredError:
                await session.rollback()  # release pg_advisory_xact_lock held by the tx
                logger.info(
                    "Refund window (%d hours) expired for contact %s in workspace %d",
                    refund_window_hours,
                    contact_id,
                    ws_id,
                )
                workspace_expired[ws_id] = workspace_expired.get(ws_id, 0) + 1
                skipped.append(
                    {
                        "verified_contact_id": str(contact_id),
                        "workspace_id": ws_id,
                        "reason": "window_expired",
                    }
                )
            except NoOriginalUnlockEventError:
                await session.rollback()
                logger.info(
                    "No unlock event for contact %s in workspace %d",
                    contact_id,
                    ws_id,
                )
                skipped.append(
                    {
                        "verified_contact_id": str(contact_id),
                        "workspace_id": ws_id,
                        "reason": "no_unlock_charge",
                    }
                )
            except RefundAlreadyProcessedError:
                await session.rollback()
                logger.info(
                    "Refund already processed for contact %s in workspace %d",
                    contact_id,
                    ws_id,
                )
                skipped.append(
                    {
                        "verified_contact_id": str(contact_id),
                        "workspace_id": ws_id,
                        "reason": "already_refunded",
                    }
                )
            except RefundBudgetExhaustedError:
                await session.rollback()
                logger.warning(
                    "Refund budget exhausted for workspace %d (contact %s)",
                    ws_id,
                    contact_id,
                )
                skipped.append(
                    {
                        "verified_contact_id": str(contact_id),
                        "workspace_id": ws_id,
                        "reason": "budget_exhausted",
                    }
                )
            except Exception as exc:
                logger.exception(
                    "Unexpected error refunding contact %s for workspace %d: %s",
                    contact_id,
                    ws_id,
                    exc,
                )
                await session.rollback()
                skipped.append(
                    {
                        "verified_contact_id": str(contact_id),
                        "workspace_id": ws_id,
                        "reason": "internal_error",
                    }
                )

        for skip_entry in skipped:
            details.append(
                {
                    "contact_id": skip_entry["verified_contact_id"],
                    "workspace_id": skip_entry["workspace_id"],
                    "status": "skipped",
                    "skip_reason": skip_entry["reason"],
                }
            )

        # 4. Workspace Notifications (without PII)
        for ws_id, purged_count in workspace_purged_count.items():
            refunded_micros_ws = workspace_refunds.get(ws_id, 0)
            refunded_count_ws = workspace_refunded_count.get(ws_id, 0)
            has_expired = workspace_expired.get(ws_id, 0) > 0

            # Send notification only if >= 1 refund OR >= 1 expired refund
            if not (refunded_count_ws > 0 or has_expired):
                continue

            refunded_credits = (
                refunded_micros_ws // 1_000_000
                if refunded_micros_ws % 1_000_000 == 0
                else round(refunded_micros_ws / 1_000_000, 4)
            )

            msg = (
                f"Hệ thống đã gỡ bỏ {purged_count} liên hệ do yêu cầu tuân thủ. "
                + (
                    f"Đã hoàn trả {refunded_credits} credits cho {refunded_count_ws} liên hệ đã mở khóa. "
                    if refunded_count_ws > 0
                    else ""
                )
                + "Lý do: gỡ bỏ theo yêu cầu bảo vệ dữ liệu cá nhân."
            )

            notif_metadata = {
                "purged_contacts": purged_count,
                "refunded_contacts": refunded_count_ws,
                "refunded_credits": refunded_credits,
                "refunded_micros": refunded_micros_ws,
                "reason": "compliance_purge_data_protection",
                "has_expired_refunds": has_expired,
            }

            try:
                target_user = await _workspace_owner_id(ws_id)
                if target_user is None:
                    logger.warning(
                        "Cannot send compliance purge notification: no owner user_id for workspace %d",
                        ws_id,
                    )
                    continue

                await NotificationService.create_notification(
                    session,
                    user_id=target_user,
                    workspace_id=ws_id,
                    notification_type="compliance_purge_refund",
                    title="Thông báo gỡ bỏ liên hệ theo quy định tuân thủ",
                    message=msg,
                    notification_metadata=notif_metadata,
                )
            except Exception as notif_err:
                await (
                    session.rollback()
                )  # reset aborted tx so next workspace can proceed
                logger.exception(
                    "Failed to create compliance purge notification for workspace %d: %s",
                    ws_id,
                    notif_err,
                )

        return {
            "refunded_contacts": refunded_contacts,
            "refunded_micros": refunded_micros,
            "skipped": skipped,
            "details": details,
        }
