"""LeadExtractionService for hermetic extraction of phones, tax codes, and metadata."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field

from app.proprietary.platforms.xactions.phone_extractor import SocialEntityExtractor
from app.proprietary.platforms.xactions.tax_code import (
    extract_tax_ids,
    is_valid_vietnam_tax_code,
)

_EXTRACTION_TIMEOUT = 60.0

_COMPANY_PATTERNS = [
    re.compile(
        r"(?i:\b(?:CÔNG TY|CTY|TẬP ĐOÀN|TNHH|CỔ PHẦN|DOANH NGHIỆP TƯ NHÂN|DNTN|HỢP TÁC XÃ|HTX|TỔNG CÔNG TY)\b[^\n,\.]+)",
    ),
]


@dataclass
class ExtractedEntities:
    phones: list[str] = field(default_factory=list)
    tax_ids: list[str] = field(default_factory=list)
    tax_ids_valid: list[bool] = field(default_factory=list)
    company_name: str | None = None


class LeadExtractionService:
    """Hermetic entity extraction service for phone numbers, tax codes, and company names."""

    def __init__(self, extractor: SocialEntityExtractor | None = None):
        self.extractor = extractor or SocialEntityExtractor()

    def extract_company_name(self, text: str) -> str | None:
        if not text or not isinstance(text, str):
            return None
        for line in text.splitlines():
            line_str = line.strip()
            if not line_str or line_str.lower().startswith("mã số"):
                continue
            for pattern in _COMPANY_PATTERNS:
                match = pattern.search(line_str)
                if match:
                    candidate = match.group(0).strip()[:255]
                    if len(candidate) > 4:
                        return candidate
        return None

    async def extract_from_text(self, text: str | None) -> ExtractedEntities:
        """Extract phones, tax IDs, and a company name from raw text.

        All CPU-bound extractors are run in worker threads with a 60-second hard
        timeout so the event loop cannot be blocked by a malicious or oversized
        payload.
        """
        if not text or not isinstance(text, str):
            return ExtractedEntities()

        phones = await asyncio.wait_for(
            asyncio.to_thread(self.extractor.extract_phones, text),
            timeout=_EXTRACTION_TIMEOUT,
        )

        tax_ids = await asyncio.wait_for(
            asyncio.to_thread(extract_tax_ids, text),
            timeout=_EXTRACTION_TIMEOUT,
        )

        tax_ids_valid = [is_valid_vietnam_tax_code(t) for t in tax_ids]

        company_name = await asyncio.wait_for(
            asyncio.to_thread(self.extract_company_name, text),
            timeout=_EXTRACTION_TIMEOUT,
        )

        return ExtractedEntities(
            phones=phones,
            tax_ids=tax_ids,
            tax_ids_valid=tax_ids_valid,
            company_name=company_name,
        )
