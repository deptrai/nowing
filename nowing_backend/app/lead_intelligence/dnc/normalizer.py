"""DNC Normalizers & Cryptographic Hasher (Story 21.14 / Decree 91 / Decree 13 PDPD)."""

from __future__ import annotations

import fnmatch
import hmac
import re
from hashlib import sha256
from urllib.parse import urlparse

from app.config import config


def normalize_phone_e164(phone: str | None) -> str | None:
    """Normalize local or international phone strings to canonical E.164 (+84...).

    Returns None if input is empty, malformed, or doesn't contain a valid phone pattern.
    """
    if not phone or not isinstance(phone, str):
        return None

    cleaned = phone.strip()
    if not cleaned:
        return None

    # Keep leading + if present, then extract digits
    has_plus = cleaned.startswith("+")
    digits = re.sub(r"\D", "", cleaned)

    if not digits:
        return None

    # Convert legacy 11-digit mobile numbers (2018 telecom reform) before E.164
    if len(digits) == 11 and digits.startswith("0"):
        from app.proprietary.platforms.xactions.phone_extractor import (
            convert_legacy_11_digit,
        )

        digits = convert_legacy_11_digit(digits)

    # Vietnamese standard 10-digit mobile conversion (09x, 08x, 07x, 05x, 03x, 02x)
    if digits.startswith("0") and len(digits) == 10:
        e164 = f"+84{digits[1:]}"
    elif (digits.startswith("84") and len(digits) in (11, 12)) or has_plus:
        e164 = f"+{digits}"
    elif len(digits) >= 8 and len(digits) <= 15:
        # Fallback international assume +
        e164 = f"+{digits}"
    else:
        return None

    # Validate E.164 length constraints: '+' followed by 7 to 15 digits
    if not re.match(r"^\+[1-9]\d{6,14}$", e164):
        return None

    return e164


def hash_phone_hmac(phone_e164: str, secret_key: str | None = None) -> str:
    """Compute Keyed HMAC-SHA256 hex digest for an E.164 phone number."""
    key = secret_key or getattr(config, "SECRET_KEY", "")
    if not key:
        raise ValueError("DNC SECRET_KEY is not configured")
    msg = phone_e164.strip().encode("utf-8")
    return hmac.new(key.encode("utf-8"), msg, sha256).hexdigest()


def normalize_domain(domain_or_url: str | None) -> str | None:
    """Strip protocol, port, path, query and convert domain to lowercase."""
    if not domain_or_url or not isinstance(domain_or_url, str):
        return None

    cleaned = domain_or_url.strip().lower()
    if not cleaned:
        return None

    if "://" in cleaned:
        try:
            parsed = urlparse(cleaned)
            netloc = parsed.netloc
        except Exception:
            netloc = cleaned
    else:
        netloc = cleaned.split("/")[0]

    # Strip port if present
    if ":" in netloc:
        netloc = netloc.split(":")[0]

    netloc = netloc.strip(".")
    return netloc if netloc else None


def is_domain_matching(target_domain: str, rule_domain: str) -> bool:
    """Check if target domain matches exact rule or wildcard subdomain rule (*.domain.com)."""
    norm_target = normalize_domain(target_domain)
    if not norm_target:
        return False

    rule_clean = rule_domain.strip().lower()
    if not rule_clean:
        return False

    # Exact match
    if norm_target == rule_clean:
        return True

    # Wildcard matching (e.g. *.vinhomes.vn)
    if rule_clean.startswith("*."):
        root_domain = rule_clean[2:]
        # Safety invariant: Reject broad TLD wildcards (*.com, *.vn, *) to prevent DoS
        if not root_domain or "." not in root_domain:
            return False
        if norm_target == root_domain:
            return True
        return fnmatch.fnmatch(norm_target, rule_clean)

    return False


def normalize_email(email: str | None) -> str | None:
    """Normalize and validate email address."""
    if not email or not isinstance(email, str):
        return None

    cleaned = email.strip().lower()
    if "@" not in cleaned or "." not in cleaned.split("@")[-1]:
        return None

    return cleaned


def normalize_tax_id(tax_id: str | None) -> str | None:
    """Normalize corporate tax ID (Mã số thuế)."""
    if not tax_id or not isinstance(tax_id, str):
        return None

    cleaned = re.sub(r"[^\w-]", "", tax_id.strip()).lower()
    return cleaned if cleaned else None
