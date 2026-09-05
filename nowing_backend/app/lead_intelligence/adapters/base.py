"""Universal LeadSourceAdapter Abstract Base Class and Data Contracts (Story 21.15)."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field


class LeadSourceCategory(StrEnum):
    """Categorization of lead scrapers and data providers."""

    REAL_ESTATE = "REAL_ESTATE"
    JOB_MARKET = "JOB_MARKET"
    ENTERPRISE = "ENTERPRISE"
    SOCIAL = "SOCIAL"
    E_COMMERCE = "E_COMMERCE"
    NEWS = "NEWS"
    FINANCE = "FINANCE"
    GENERAL = "GENERAL"


class ContactCandidate(BaseModel):
    """Potential contact method extracted from raw records or unmasked listings."""

    model_config = ConfigDict(from_attributes=True)

    channel: str = Field(
        ..., description="Contact channel: 'phone', 'email', 'zalo', 'linkedin'"
    )
    value: str = Field(..., description="Normalized contact value")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RawLeadRecord(BaseModel):
    """Unprocessed data record returned by a platform-specific scraper."""

    model_config = ConfigDict(from_attributes=True)

    source_name: str = Field(..., description="Identifier of the scraper adapter")
    source_id: str = Field(
        ..., description="Native ID or URL of the record on the source platform"
    )
    data: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    category: LeadSourceCategory = LeadSourceCategory.GENERAL


class NormalizedLead(BaseModel):
    """Standardized lead entity ready for deduplication, scoring, and DB persistence."""

    model_config = ConfigDict(from_attributes=True)

    source_name: str
    source_id: str
    title: str | None = None
    company_name: str | None = None
    primary_phone: str | None = None
    primary_email: str | None = None
    tax_id: str | None = None
    canonical_domain: str | None = None
    contact_name: str | None = None
    legal_rep: str | None = None
    address: str | None = None
    city: str | None = None
    price: float | None = None
    area: float | None = None
    source_url: str | None = None
    confidence_score: float = 70.0
    schema_completeness_score: float | None = None
    icp_fit_score: float | None = None
    intent_signal_score: float | None = None
    needs_enrichment: bool | None = None
    sources: list[str] = Field(default_factory=list)
    contact_candidates: list[ContactCandidate] = Field(default_factory=list)
    raw_data: dict[str, Any] = Field(default_factory=dict)
    location_match_score: float | None = None

    def model_post_init(self, __context: Any) -> None:
        if not self.sources and self.source_name:
            self.sources = [self.source_name]


# ReDoS-safe linear regex for Vietnamese mobile and landline numbers
_CLEAN_NON_DIGITS = re.compile(r"[^\d+]")
_PHONE_TOKEN_PATTERN = re.compile(
    r"(?:(?<=[^\d])|^)(?:\+84|84|0)[0-9\s\.\-]{8,15}(?:(?=[^\d])|$)"
)
_VALID_VN_PREFIXES = (
    # Viettel / Vinaphone / Mobifone / Vietnamobile / Gmobile / Itelecom / Wintel / FPT
    "032",
    "033",
    "034",
    "035",
    "036",
    "037",
    "038",
    "039",
    "052",
    "055",
    "056",
    "058",
    "059",
    "070",
    "076",
    "077",
    "078",
    "079",
    "081",
    "082",
    "083",
    "084",
    "085",
    "086",
    "087",
    "088",
    "089",
    "090",
    "091",
    "092",
    "093",
    "094",
    "095",
    "096",
    "097",
    "098",
    "099",
    # Fixed landline prefixes across 63 provinces in Vietnam (020x to 029x)
    "020",
    "021",
    "022",
    "023",
    "024",
    "025",
    "026",
    "027",
    "028",
    "029",
)


def normalize_vietnamese_phone(raw_phone: str) -> str:
    """
    Standardize a Vietnamese phone number to a 10-digit (mobile) or 11-digit (fixed) format starting with '0'.
    Handles '+84', '0084', '84', '.', ' ', '-' separators safely.
    """
    if not raw_phone:
        return ""

    cleaned = _CLEAN_NON_DIGITS.sub("", raw_phone.strip())
    if cleaned.startswith("+84"):
        cleaned = "0" + cleaned[3:]
    elif cleaned.startswith("0084"):
        cleaned = "0" + cleaned[4:]
    elif cleaned.startswith("84") and len(cleaned) in (11, 12):
        cleaned = "0" + cleaned[2:]

    # Remove any extra leading zeros or residual '+' characters
    if cleaned.startswith("00"):
        cleaned = "0" + cleaned[2:]
    cleaned = cleaned.replace("+", "")

    return cleaned


def _to_float(value: Any) -> float | None:
    """Safely cast a value to float, returning ``None`` on non-numeric input."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_phones_from_text(text: str) -> list[str]:
    """
    Safely extract unique, normalized Vietnamese phone numbers from arbitrary text.
    Uses linear-time parsing to prevent catastrophic backtracking (ReDoS safe).
    """
    if not text or not isinstance(text, str):
        return []

    # Limit maximum text chunk evaluated at once to avoid CPU spikes
    bounded_text = text[:50000]

    found_phones: set[str] = set()
    for match in _PHONE_TOKEN_PATTERN.finditer(bounded_text):
        candidate = match.group(0)
        norm = normalize_vietnamese_phone(candidate)
        if len(norm) in (10, 11) and any(
            norm.startswith(pfx) for pfx in _VALID_VN_PREFIXES
        ):
            found_phones.add(norm)

    return sorted(found_phones)


class LeadSourceAdapter(ABC):
    """Abstract Base Class for all universal scraper adapters."""

    source_name: str
    category: LeadSourceCategory = LeadSourceCategory.GENERAL
    last_execution_status: str = "ok"
    supported_provinces: ClassVar[list[str]] = ["*"]
    coverage_quality_by_location: ClassVar[dict[str, str | float]] = {}
    priority: int = 1
    lead_quota: int = 50

    @abstractmethod
    async def search_leads(
        self,
        workspace_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[RawLeadRecord]:
        """Search and fetch raw lead records from upstream scraper platform."""
        ...

    @abstractmethod
    def normalize_lead(self, raw_record: RawLeadRecord) -> NormalizedLead:
        """Transform a raw scraper record into standardized NormalizedLead."""
        ...

    @abstractmethod
    def extract_contact_candidates(
        self, raw_record: RawLeadRecord
    ) -> list[ContactCandidate]:
        """Extract phone numbers, emails, and social profiles from raw lead data."""
        ...
