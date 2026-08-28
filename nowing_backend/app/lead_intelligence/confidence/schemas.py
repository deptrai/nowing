"""Confidence-gate data contracts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SchemaField(StrEnum):
    """Required schema fields evaluated by the confidence gate."""

    PHONE = "phone"
    PRICE = "price"
    DISTRICT = "district"
    AREA = "area"
    TITLE = "title"


REQUIRED_FIELDS = frozenset(SchemaField)


class SchemaCompletenessResult(BaseModel):
    """Result of evaluating a ``NormalizedLead`` against the required schema."""

    model_config = ConfigDict(from_attributes=True)

    score: float = Field(
        ..., ge=0.0, le=1.0, description="Ratio of present required fields."
    )
    present_fields: frozenset[SchemaField] = Field(default_factory=frozenset)
    missing_fields: frozenset[SchemaField] = Field(default_factory=frozenset)
    critical_missing: bool = Field(
        default=False,
        description="True if any critical field (phone, price, district) is missing.",
    )
    needs_enrichment: bool = Field(
        default=False,
        description="True if the record should be scheduled for async enrichment.",
    )


class CompositeConfidenceResult(BaseModel):
    """Result of composite confidence evaluation combining schema completeness, ICP fit, and intent signals."""

    model_config = ConfigDict(from_attributes=True)

    confidence_score: float = Field(
        ..., ge=0.0, le=100.0, description="Aggregate composite score (0-100)."
    )
    schema_completeness_score: float = Field(
        ..., ge=0.0, le=1.0, description="Schema completeness score (0-1)."
    )
    icp_fit_score: float = Field(
        ..., ge=0.0, le=100.0, description="ICP fit score (0-100)."
    )
    intent_signal_score: float = Field(
        ..., ge=0.0, le=100.0, description="Intent signal score (0-100)."
    )
    needs_enrichment: bool = Field(
        default=False,
        description="True if the record needs downstream enrichment.",
    )
    critical_missing: bool = Field(
        default=False,
        description="True if any critical schema field is missing.",
    )

