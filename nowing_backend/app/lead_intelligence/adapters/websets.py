"""ChainLens Websets universal lead source adapter (Story 41.1)."""

from __future__ import annotations

import logging
import secrets
from typing import Any, ClassVar

from app.config.urls import BACKEND_URL
from app.db import async_session_maker
from app.lead_intelligence.adapters.base import (
    ContactCandidate,
    LeadSourceAdapter,
    LeadSourceCategory,
    NormalizedLead,
    RawLeadRecord,
    normalize_vietnamese_phone,
)
from app.models.webset_campaign import WebsetCampaign
from app.services.chainlens.websets import WebsetsService

logger = logging.getLogger(__name__)

DEFAULT_WEBSET_COLUMNS: list[dict[str, Any]] = [
    {"key": "company_name", "type": "text"},
    {"key": "phone", "type": "phone"},
    {"key": "email", "type": "email"},
    {"key": "title", "type": "text"},
    {"key": "website", "type": "url"},
]


class WebsetsAdapter(LeadSourceAdapter):
    """Adapter triggering asynchronous ChainLens Webset scraping builds."""

    source_name: str = "websets"
    category: LeadSourceCategory = LeadSourceCategory.GENERAL
    last_execution_status: str = "ok"
    priority: int = 1
    lead_quota: int = 50
    supported_provinces: ClassVar[tuple[str, ...]] = ("*",)

    def __init__(self, service: WebsetsService | None = None) -> None:
        self._service = service or WebsetsService()
        self.last_execution_status = "ok"

    async def search_leads(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[RawLeadRecord]:
        """Initiate an asynchronous ChainLens Webset build and record the pending campaign.

        Builds the webhook URL carrying a cryptographically secure token, calls
        ChainLens to start webset extraction, stores the tracking record in
        ``webset_campaigns``, sets ``last_execution_status = "pending"``, and
        returns an empty list (leads are delivered asynchronously).
        """
        filters = filters or {}
        # Singleton adapter: status chỉ phản ánh run gần nhất, reset để không
        # rò rỉ "pending"/"failed" sang campaign/workspace kế tiếp.
        self.last_execution_status = "ok"
        webhook_secret = secrets.token_urlsafe(32)

        base_url = (
            filters.get("base_webhook_url") or BACKEND_URL or "http://localhost:8000"
        )
        webhook_url = f"{base_url.rstrip('/')}/api/v1/webhooks/chainlens/webset-idle?t={webhook_secret}"

        columns = filters.get("columns") or DEFAULT_WEBSET_COLUMNS
        criteria = filters.get("criteria") or {
            "prompt": query or "Find relevant business leads",
            "rules": [],
        }
        source = filters.get("source") or {"type": filters.get("source_type", "web")}

        metadata = dict(filters.get("metadata") or {})
        metadata["webhookUrl"] = webhook_url

        campaign_id = filters.get("campaign_id") or filters.get("client_id")
        if campaign_id:
            metadata["campaign_id"] = str(campaign_id)

        logger.info(
            "Creating ChainLens Webset for workspace_id=%s, campaign_id=%s",
            workspace_id,
            campaign_id,
        )

        try:
            res = await self._service.create_webset(
                source=source,
                columns=columns,
                criteria=criteria,
                metadata=metadata,
                workspace_id=workspace_id,
            )
        except Exception as exc:  # typed degradation, không raise qua orchestrator
            logger.warning(
                "ChainLens create_webset failed for workspace_id=%s: %s",
                workspace_id,
                exc,
            )
            self.last_execution_status = "degraded"
            return []

        webset_id = str(
            res.get("webset_id") or res.get("websetId") or res.get("id") or ""
        )
        if not webset_id:
            logger.error("ChainLens response missing webset_id: %s", res)
            self.last_execution_status = "failed"
            raise ValueError(f"ChainLens response missing webset_id: {res}")

        try:
            async with async_session_maker() as session:
                campaign = WebsetCampaign(
                    webset_id=webset_id,
                    campaign_id=str(campaign_id) if campaign_id else None,
                    workspace_id=workspace_id,
                    webhook_secret=webhook_secret,
                    status="pending",
                    stats={"initial_response": res},
                )
                session.add(campaign)
                await session.commit()
        except Exception as exc:
            # Webset đã tạo trên ChainLens nhưng không lưu được tracking row —
            # webhook sẽ bị 'ignored'; báo failed để nguồn không hiện ready giả
            logger.error(
                "Failed to persist WebsetCampaign for webset_id=%s: %s",
                webset_id,
                exc,
            )
            self.last_execution_status = "failed"
            return []

        self.last_execution_status = "pending"
        return []

    def normalize_lead(self, raw_record: RawLeadRecord) -> NormalizedLead:
        """Transform a raw webset record into NormalizedLead format."""
        data = raw_record.data or {}
        return NormalizedLead(
            source_name=self.source_name,
            source_id=raw_record.source_id,
            title=data.get("title"),
            company_name=data.get("company_name"),
            primary_phone=data.get("phone"),
            primary_email=data.get("email"),
            source_url=data.get("source_url") or raw_record.source_id,
            raw_data=data,
        )

    def extract_contact_candidates(
        self, raw_record: RawLeadRecord
    ) -> list[ContactCandidate]:
        """Extract contact candidates from raw webset record data."""
        candidates: list[ContactCandidate] = []
        data = raw_record.data or {}

        phone = data.get("phone")
        if phone:
            normalized_phone = normalize_vietnamese_phone(str(phone))
            if normalized_phone:
                candidates.append(
                    ContactCandidate(
                        channel="phone",
                        value=normalized_phone,
                    )
                )

        email = data.get("email")
        if email and str(email).strip():
            candidates.append(
                ContactCandidate(
                    channel="email",
                    value=str(email).strip().lower(),
                )
            )

        return candidates
