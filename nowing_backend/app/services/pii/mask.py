"""Shared PII masking helpers.

Consolidated from `app/services/export_service.py` and
`app/services/phone_waterfall_service.py` to avoid drift between
REST/Zero display and DNC/cache masking (Story 26.5).
"""

from __future__ import annotations

import re


def mask_phone(phone: str | None) -> str:
    """Mask phone number for non-privileged response and zero-cache (e.g. 0908***456).

    ponytail: accepts both 10-digit domestic and E.164 input; E.164 is converted
    to domestic display before masking. Non-phone input returns `***`.
    """
    if not phone:
        return ""
    clean = str(phone).strip()
    if not re.match(r"^[\d\s\+\-\(\)\.]*$", clean):
        return "***"
    digits = re.sub(r"\D", "", clean)
    if digits.startswith("84") and len(digits) == 11:
        digits = "0" + digits[2:]
    if len(digits) == 10 and digits.startswith("0"):
        return f"{digits[:4]}***{digits[7:]}"
    if len(digits) >= 7:
        mid_start = max(2, len(digits) - 5)
        mid_end = len(digits) - 3
        return f"{digits[:mid_start]}***{digits[mid_end:]}"
    return "***"


def mask_email(email: str | None) -> str:
    """Mask email for PII redaction (Story 21.13 / AD-36).

    Returns a redacted placeholder for malformed or non-email input instead of
    leaking the raw value.
    """
    if not email:
        return ""
    clean = str(email).strip()
    if "@" not in clean or "." not in clean.split("@")[-1]:
        return "***"
    parts = clean.split("@", 1)
    username = parts[0]
    domain = parts[1]
    if not username:
        return f"***@{domain}"
    return f"{username[0]}***@{domain}"


def mask_name(name: str | None) -> str:
    """Mask a personal/company name for PII redaction."""
    if not name:
        return ""
    clean = str(name).strip()
    if len(clean) <= 3:
        return "***"
    return f"{clean[0]}***{clean[-1]}"
