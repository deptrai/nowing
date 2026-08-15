"""Base CRM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class CrmContact:
    """Normalized CRM contact/lead record."""

    crm_record_id: str
    email: str | None
    domain: str | None
    company_name: str | None
    first_name: str | None
    last_name: str | None
    title: str | None
    phone: str | None
    owner_id: str | None
    raw: dict[str, Any] | None = None


@dataclass
class CrmSearchResult:
    """Result of a dedup search."""

    contacts: list[CrmContact]
    has_more: bool = False


class CrmProvider(ABC):
    """Abstract CRM provider."""

    def __init__(self, credentials: dict[str, Any]) -> None:
        self.credentials = credentials

    @abstractmethod
    async def search_contacts(
        self,
        email: str | None,
        domain: str | None,
        limit: int = 10,
    ) -> CrmSearchResult:
        """Search existing CRM contacts by email or domain."""

    @abstractmethod
    async def create_lead(self, lead_data: dict[str, Any]) -> dict[str, Any]:
        """Create a lead/contact in the CRM and return raw response."""

    @abstractmethod
    async def update_lead(
        self, crm_record_id: str, lead_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing lead/contact."""

    @abstractmethod
    async def handle_webhook(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Process an inbound webhook payload and return normalized lead update."""
