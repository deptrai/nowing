"""Schemas for test entity extraction endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractEntitiesRequest(BaseModel):
    source_text: str = Field(..., description="Raw unstructured source text")
    source_url: str | None = Field(
        default=None, max_length=2048, description="Optional origin URL"
    )


class ExtractEntitiesResponse(BaseModel):
    phones: list[str] = Field(
        default_factory=list,
        description="Extracted normalized 10-digit Vietnamese phone numbers",
    )
    tax_ids: list[str] = Field(
        default_factory=list,
        description="Extracted 10 or 13 digit tax codes",
    )
    tax_ids_valid: list[bool] = Field(
        default_factory=list,
        description="Modulo-11 validity flags for each extracted tax code",
    )
    company_name: str | None = Field(
        default=None,
        description="Extracted candidate company name",
    )
