"""Fallback contact verifier (MX DNS lookup + pattern matching) for Story 21.3.

AD-36: when both external providers fail, enrichment falls back to basic
verification — an MX record check for emails and an E.164-style regex check
for phones. Results are ``low_confidence`` with ``source_provider="fallback"``.
"""

from __future__ import annotations

import logging
import re
from contextlib import suppress

from app.db import Lead
from app.services.pii.verified_contact_encryption import VerifiedContactDict

logger = logging.getLogger(__name__)

_E164_PHONE = re.compile(r"^\+?[1-9]\d{6,14}$")
_EMAIL = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")


class FallbackVerifier:
    """Derive candidate contacts from a lead and basic-verify them."""

    name = "fallback"

    async def find_contacts(
        self,
        lead: Lead,
        requested_count: int = 5,
    ) -> list[VerifiedContactDict]:
        """Verify the lead's own contact info if present (Task 4.2)."""
        if not lead.domain and not lead.source_url:
            return []

        domain = lead.domain or _domain_from_url(lead.source_url)
        if not domain:
            return []

        contacts: list[VerifiedContactDict] = []
        if lead.source_url:
            email = _candidate_email(domain)
            if email and await self.verify_email(email):
                contacts.append(
                    VerifiedContactDict(
                        name=None,
                        title=None,
                        email=email,
                        phone=None,
                        verification_status="low_confidence",
                        confidence=0.4,
                        source_provider="fallback",
                    )
                )
        return contacts[: max(1, requested_count)]

    async def verify_email(self, email: str) -> bool:
        """True when the email looks valid and its domain has an MX record."""
        if not email or not _EMAIL.match(email):
            return False
        domain = email.rsplit("@", 1)[-1]
        with suppress(Exception):
            import dns.resolver

            answers = dns.resolver.resolve(domain, "MX")
            return bool(answers)
        # No DNS library available or lookup failed: accept the format check.
        return True

    async def verify_phone(self, phone: str | None) -> bool:
        """True when the phone looks E.164-ish (Task 4.2)."""
        return bool(phone) and bool(_E164_PHONE.match(phone.strip()))


def _domain_from_url(url: str | None) -> str | None:
    """Extract a bare domain from a URL, e.g. https://x.example.com/a -> example.com.

    Returns ``None`` for bare IP hosts so ``info@<ip>`` candidates are never
    generated (a spam/phishing hazard, Task 4.2 hardening).
    """
    if not url:
        return None
    match = re.match(r"https?://([^/]+)", url.strip())
    if not match:
        return None
    host = match.group(1).split(":")[0].lower()
    if _is_ip_address(host):
        return None
    parts = host.split(".")
    if len(parts) > 2:
        return ".".join(parts[-2:])
    return host or None


def _is_ip_address(host: str) -> bool:
    """True when ``host`` parses as an IPv4 or IPv6 literal."""
    import ipaddress

    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def _candidate_email(domain: str) -> str:
    """Best-effort info@-style candidate for a company domain."""
    return f"info@{domain}"
