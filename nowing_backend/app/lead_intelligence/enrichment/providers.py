"""Waterfall enrichment providers (Cleanlist / BetterContact) for Story 21.3.

AD-36: buy the waterfall via a single provider contract. The primary and
secondary providers are resolved from ``CONTACT_ENRICHMENT_PRIMARY_PROVIDER``;
each provider implements ``WaterfallProvider.find_contacts``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

import httpx

from app.config import config
from app.db import Lead
from app.services.pii.verified_contact_encryption import VerifiedContactDict

logger = logging.getLogger(__name__)


class WaterfallProvider(Protocol):
    """One enrichment provider in the waterfall (AD-36)."""

    name: str

    async def find_contacts(
        self,
        lead: Lead,
        requested_count: int,
    ) -> list[VerifiedContactDict]:
        """Return verified contacts for ``lead``; empty on failure/absence."""
        ...


def _company_key(lead: Lead) -> str:
    """A stable lookup key: company name, else domain, else lead id."""
    if lead.company_name:
        return lead.company_name
    if lead.domain:
        return lead.domain
    return str(lead.id)


class CleanlistClient:
    """Cleanlist.io style company-contact enrichment client."""

    name = "cleanlist"

    def __init__(
        self, api_key: str | None = None, timeout: float | None = None
    ) -> None:
        self._api_key = api_key if api_key is not None else config.CLEANLIST_API_KEY
        self._timeout = (
            timeout
            if timeout is not None
            else config.CONTACT_ENRICHMENT_REQUEST_TIMEOUT_SECONDS
        )

    async def find_contacts(
        self,
        lead: Lead,
        requested_count: int,
    ) -> list[VerifiedContactDict]:
        if not self._api_key:
            logger.info("cleanlist provider not configured; skipping")
            return []
        url = "https://api.cleanlist.io/v1/company/contacts"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        params = {"company": _company_key(lead), "limit": requested_count}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            payload = response.json()
        return _parse_contacts(payload, provider="cleanlist")


class BetterContactClient:
    """BetterContact-style enrichment client."""

    name = "bettercontact"

    def __init__(
        self, api_key: str | None = None, timeout: float | None = None
    ) -> None:
        self._api_key = api_key if api_key is not None else config.BETTERCONTACT_API_KEY
        self._timeout = (
            timeout
            if timeout is not None
            else config.CONTACT_ENRICHMENT_REQUEST_TIMEOUT_SECONDS
        )

    async def find_contacts(
        self,
        lead: Lead,
        requested_count: int,
    ) -> list[VerifiedContactDict]:
        if not self._api_key:
            logger.info("bettercontact provider not configured; skipping")
            return []
        url = "https://api.bettercontact.app/v1/enrich"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        payload = {
            "company": _company_key(lead),
            "domain": lead.domain,
            "limit": requested_count,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
        return _parse_contacts(body, provider="bettercontact")


def _parse_contacts(
    payload: object,
    provider: str,
) -> list[VerifiedContactDict]:
    """Normalize provider JSON (list or ``{"contacts": [...]}``) into dicts."""
    raw = payload if isinstance(payload, list) else []
    if isinstance(payload, dict):
        raw = payload.get("contacts") or payload.get("data") or []
    contacts: list[VerifiedContactDict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        email = item.get("email")
        if not email:
            continue
        contacts.append(
            VerifiedContactDict(
                name=item.get("name") or item.get("full_name"),
                title=item.get("title") or item.get("job_title"),
                email=str(email),
                phone=item.get("phone") or item.get("phone_number"),
                verification_status=(item.get("verification_status") or "verified"),
                confidence=float(item.get("confidence") or 0.0),
                source_provider=provider,
            )
        )
    return contacts[: config.CONTACT_ENRICHMENT_MAX_CONTACTS_PER_LEAD]


def resolve_waterfall(
    primary: str | None = None,
) -> tuple[WaterfallProvider, WaterfallProvider]:
    """Resolve the (primary, secondary) provider pair from config (Task 4.1)."""
    primary_name = (
        (primary or config.CONTACT_ENRICHMENT_PRIMARY_PROVIDER).strip().lower()
    )
    if primary_name not in {"cleanlist", "bettercontact"}:
        logger.warning(
            "unknown CONTACT_ENRICHMENT_PRIMARY_PROVIDER=%r; using cleanlist",
            primary_name,
        )
        primary_name = "cleanlist"

    if primary_name == "bettercontact":
        return BetterContactClient(), CleanlistClient()
    return CleanlistClient(), BetterContactClient()


async def run_waterfall(
    lead: Lead,
    requested_count: int,
    retry_attempts: int | None = None,
) -> tuple[list[VerifiedContactDict], str]:
    """Call primary then secondary provider; return (contacts, provider).

    On both failures (network, 5xx, or no results), returns an empty list and
    the caller falls back to ``FallbackVerifier`` (Task 4.2).
    """
    primary, secondary = resolve_waterfall()
    attempts = (
        retry_attempts
        if retry_attempts is not None
        else config.CONTACT_ENRICHMENT_RETRY_ATTEMPTS
    )
    for provider in (primary, secondary):
        for attempt in range(max(1, attempts)):
            try:
                contacts = await provider.find_contacts(lead, requested_count)
                if contacts:
                    return contacts, provider.name
                logger.info(
                    "provider %s returned no contacts for lead %s",
                    provider.name,
                    lead.id,
                )
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning(
                    "provider %s attempt %d failed for lead %s: %s",
                    provider.name,
                    attempt + 1,
                    lead.id,
                    exc,
                )
            if attempt + 1 < attempts:
                await asyncio.sleep(2**attempt)
        # Move to the secondary provider after exhausting retries.
    return [], "none"
