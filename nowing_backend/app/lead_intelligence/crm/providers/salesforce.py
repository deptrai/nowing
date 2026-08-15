"""Salesforce CRM provider (MVP stub)."""

from __future__ import annotations

from typing import Any

from .base import CrmProvider, CrmSearchResult


class SalesforceProvider(CrmProvider):
    """Salesforce provider."""

    async def search_contacts(
        self,
        email: str | None,
        domain: str | None,
        limit: int = 10,
    ) -> CrmSearchResult:
        """ponytail: stub for MVP; real implementation calls /services/data/v58.0/sobjects/Contact."""
        return CrmSearchResult(contacts=[])

    async def create_lead(self, lead_data: dict[str, Any]) -> dict[str, Any]:
        """ponytail: stub for MVP."""
        return {"id": "stub", "success": True}

    async def update_lead(
        self, crm_record_id: str, lead_data: dict[str, Any]
    ) -> dict[str, Any]:
        """ponytail: stub for MVP."""
        return {"id": crm_record_id, "success": True}

    async def handle_webhook(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """ponytail: stub for MVP."""
        return None
