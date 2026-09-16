"""CRM webhook handler for bi-directional deal stage synchronization (Story 34.1)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime
from typing import Any
import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import CrmSyncLog, Lead, VerifiedContact

logger = logging.getLogger(__name__)

# Standard deal stage mapping to internal lead status
_STAGE_MAPPING: dict[str, str] = {
    # HubSpot standard stages
    "appointmentscheduled": "contacted",
    "qualifiedtobuy": "qualified",
    "presentationscheduled": "qualified",
    "decisionmakerbought-in": "qualified",
    "contractsent": "qualified",
    "closedwon": "converted",
    "closedlost": "lost",
    # Salesforce standard stages
    "prospecting": "contacted",
    "qualification": "qualified",
    "needs analysis": "qualified",
    "value proposition": "qualified",
    "id.decision makers": "qualified",
    "perception analysis": "qualified",
    "proposal/price quote": "qualified",
    "negotiation/review": "qualified",
    "closed won": "converted",
    "closed lost": "lost",
}


def map_stage_to_status(external_stage: str) -> str | None:
    """Map external CRM deal stage to internal Lead.status."""
    if not external_stage:
        return None
    normalized = external_stage.strip().lower()
    return _STAGE_MAPPING.get(normalized)


def verify_hubspot_signature(
    request_body: bytes,
    signature: str | None,
    secret: str | None = None,
) -> bool:
    """Verify HubSpot webhook signature (v1 / v2 HMAC-SHA256)."""
    if not signature:
        return False
    key = secret or getattr(config, "HUBSPOT_WEBHOOK_SECRET", "")
    if not key:
        logger.warning("HUBSPOT_WEBHOOK_SECRET not configured; skipping check in dev")
        return True
    expected = hmac.new(key.encode(), request_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


class CrmWebhookService:
    """Service to process incoming deal stage change webhooks from CRMs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def handle_hubspot_deal_change(
        self,
        events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Process HubSpot deal stage change webhook events."""
        results = []
        for event in events:
            # We look for deal propertyChange events on 'dealstage'
            prop_name = event.get("propertyName")
            sub_type = event.get("subscriptionType")

            if prop_name != "dealstage" and sub_type != "deal.propertyChange":
                continue

            deal_id = str(event.get("objectId"))
            new_stage = event.get("propertyValue")
            new_status = map_stage_to_status(new_stage)

            if not new_status:
                logger.debug("HubSpot stage %s not mapped to lead status", new_stage)
                continue

            # Look up lead via VerifiedContact with matching external deal ID in external_chat_ids
            stmt = select(VerifiedContact).where(
                VerifiedContact.external_chat_ids.contains({"hubspot_deal_id": deal_id})
            )
            res = await self.session.execute(stmt)
            contact = res.scalars().first()
            lead = await self.session.get(Lead, (contact.lead_id, contact.workspace_id)) if contact else None

            if not lead:
                logger.info("No lead found for HubSpot deal %s", deal_id)
                results.append({"deal_id": deal_id, "status": "lead_not_found"})
                continue

            old_status = lead.status
            lead.status = new_status
            lead.updated_at = datetime.now(UTC)

            # Record CRM sync log entry
            log = CrmSyncLog(
                workspace_id=lead.workspace_id,
                connection_id=uuid.uuid4(),  # system inbound connection
                direction="inbound",
                entity_type="lead",
                entity_id=lead.id,
                status="success",
            )
            self.session.add(log)
            results.append({
                "deal_id": deal_id,
                "lead_id": str(lead.id),
                "status": "updated",
                "new_lead_status": new_status,
            })

        await self.session.flush()
        return results

    async def handle_salesforce_deal_change(
        self,
        event: dict[str, Any],
    ) -> dict[str, Any]:
        """Process Salesforce Opportunity stage change event."""
        opp_id = str(event.get("opportunity_id") or event.get("Id") or "")
        stage_name = event.get("stage_name") or event.get("StageName") or ""
        email = event.get("contact_email") or event.get("Email")

        new_status = map_stage_to_status(stage_name)
        if not new_status:
            return {"opportunity_id": opp_id, "status": "stage_not_mapped"}

        lead = None
        # Try finding by external_chat_ids in VerifiedContact
        if opp_id:
            stmt = select(VerifiedContact).where(
                VerifiedContact.external_chat_ids.contains({"salesforce_opp_id": opp_id})
            )
            res = await self.session.execute(stmt)
            contact = res.scalars().first()
            if contact:
                lead = await self.session.get(Lead, (contact.lead_id, contact.workspace_id))

        # Fallback: match by email via VerifiedContact
        if not lead and email:
            c_stmt = select(VerifiedContact).where(VerifiedContact.email == email.lower())
            c_res = await self.session.execute(c_stmt)
            contact = c_res.scalars().first()
            if contact:
                lead = await self.session.get(Lead, (contact.lead_id, contact.workspace_id))

        if not lead:
            return {"opportunity_id": opp_id, "status": "lead_not_found"}

        old_status = lead.status
        lead.status = new_status
        lead.updated_at = datetime.now(UTC)

        log = CrmSyncLog(
            workspace_id=lead.workspace_id,
            connection_id=uuid.uuid4(),
            direction="inbound",
            entity_type="lead",
            entity_id=lead.id,
            status="success",
        )
        self.session.add(log)
        await self.session.flush()

        return {
            "opportunity_id": opp_id,
            "lead_id": str(lead.id),
            "status": "updated",
            "new_lead_status": new_status,
        }
