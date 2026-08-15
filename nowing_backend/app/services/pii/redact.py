"""PII redaction for Vietnamese job descriptions and lead enrichment.

Contexts:
- ``job_data`` (E12.5): redact phone, email, person names from scraped job text.
- ``lead_enrichment`` (E21.3): redact phone, email, person names from
  ``Memory.content``, ``Chunk[]``, audit logs, and non-privileged UI surfaces.
  ``VerifiedContact`` stores raw values encrypted at rest and is the
  authoritative source for outreach; it is never passed through this function.
- ``default``: generic redaction.
"""

from __future__ import annotations

import dataclasses
import re


@dataclasses.dataclass(frozen=True)
class RedactedText:
    text: str
    phones_detected: int = 0
    emails_detected: int = 0
    names_detected: int = 0

    @property
    def has_pii(self) -> bool:
        return self.phones_detected > 0 or self.emails_detected > 0 or self.names_detected > 0


_PHONE_PATTERNS = [
    re.compile(r"\+84(?:\s*\d){9,10}"),
    re.compile(r"0\d{9,10}"),
    re.compile(r"0\d{2}[-\s.]\d{3}[-\s.]\d{4}"),
    re.compile(r"0\d{3}[-\s.]\d{3}[-\s.]\d{3,4}"),
    re.compile(r"0\d{1}[-\s.]\d{4}[-\s.]\d{4}"),
]

_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

# Naive person-name heuristic: common Vietnamese surname + 1-2 capitalized words.
_NAME_PATTERN = re.compile(
    r"\b(?:Nguyễn|Trần|Lê|Phạm|Hoàng|Huỳnh|Vũ|Võ|Phan|Trương|Bùi|Đặng|Đỗ|Ngô|Hồ|Dương|Đinh)\s+[A-ZÀÁẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶEÈÉẺẼẸÊỀẾỂỄỆIÌÍỈĨỊOÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢUÙÚỦŨỤƯỪỨỬỮỰYỲÝỶỸỴ][a-zàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ]*(?:\s+[A-ZÀÁẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶEÈÉẺẼẸÊỀẾỂỄỆIÌÍỈĨỊOÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢUÙÚỦŨỤƯỪỨỬỮỰYỲÝỶỸỴ][a-zàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ]*)?")


def _apply_redaction(text: str) -> RedactedText:
    """Apply phone, email, and name redaction; return counts."""
    redacted = text
    phones = 0
    emails = 0
    names = 0

    for pattern in _PHONE_PATTERNS:
        matches = pattern.findall(redacted)
        phones += len(matches)
        redacted = pattern.sub("<PHONE>", redacted)

    emails = len(_EMAIL_PATTERN.findall(redacted))
    redacted = _EMAIL_PATTERN.sub("<EMAIL>", redacted)

    names = len(_NAME_PATTERN.findall(redacted))
    redacted = _NAME_PATTERN.sub("<NAME>", redacted)

    return RedactedText(
        text=redacted,
        phones_detected=phones,
        emails_detected=emails,
        names_detected=names,
    )


def redact_pii(text: str | None, context: str = "default") -> RedactedText:
    """Mask or drop phone numbers, emails, and person names.

    Args:
        text: Input text that may contain PII. ``VerifiedContact`` raw values
            are never passed through this function; they are stored encrypted
            at rest and read directly by authorized send/personalization paths.
        context: Rule set selector. Supported: ``job_data`` (E12.5),
            ``lead_enrichment`` (E21.3), and ``default``. All three currently
            use the same detection patterns; selectors are explicit so future
            per-context rules can diverge without call-site churn.
    """
    if not text:
        return RedactedText(text="")

    if context not in {"job_data", "lead_enrichment", "social_template", "default"}:
        raise ValueError(f"Unknown redaction context: {context}")

    return _apply_redaction(text)


def redact_job_pii(text: str | None) -> RedactedText:
    """Backward-compatible alias for ``redact_pii(..., context='job_data')``."""
    return redact_pii(text, context="job_data")
