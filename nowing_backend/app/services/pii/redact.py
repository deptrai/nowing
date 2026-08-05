"""PII redaction for Vietnamese job descriptions."""

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
    re.compile(r"0\d{2}[-\s]\d{3}[-\s]\d{4}"),
    re.compile(r"0\d{3}[-\s]\d{3}[-\s]\d{3}"),
]

_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

# Naive person-name heuristic: common Vietnamese surname + 1-2 capitalized words.
_NAME_PATTERN = re.compile(
    r"\b(?:Nguyễn|Trần|Lê|Phạm|Hoàng|Huỳnh|Vũ|Võ|Phan|Trương|Bùi|Đặng|Đỗ|Ngô|Hồ|Dương|Đinh)\s+[A-ZÀÁẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶEÈÉẺẼẸÊỀẾỂỄỆIÌÍỈĨỊOÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢUÙÚỦŨỤƯỪỨỬỮỰYỲÝỶỸỴ][a-zàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ]*(?:\s+[A-ZÀÁẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶEÈÉẺẼẸÊỀẾỂỄỆIÌÍỈĨỊOÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢUÙÚỦŨỤƯỪỨỬỮỰYỲÝỶỸỴ][a-zàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ]*)?")


def redact_job_pii(text: str | None) -> RedactedText:
    """Mask or drop phone numbers, emails, and person names from job text."""
    if not text:
        return RedactedText(text="")

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
