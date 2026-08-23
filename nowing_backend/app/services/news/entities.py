"""Entity models for news NER extraction (Story 14.2a / AD-27 / AD-34)."""

from __future__ import annotations

import logging
import unicodedata
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

NewsEntityType = Literal["person", "organization", "location"]
VALID_ENTITY_TYPES: set[str] = {"person", "organization", "location"}

logger = logging.getLogger(__name__)


class NewsEntity(BaseModel):
    """Extracted named entity with confidence and surface mentions."""

    model_config = ConfigDict(extra="ignore")

    text: str = Field(..., min_length=1)
    type: str = Field(...)
    confidence: float = Field(..., ge=0.0, le=1.0)
    surface_forms: list[str] = Field(default_factory=list)

    @field_validator("text")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Entity text too short")
        if cleaned.lower() in {
            "ông",
            "bà",
            "anh",
            "chị",
            "cô",
            "chú",
            "bác",
            "em",
            "ngài",
            "cháu",
            "họ",
        }:
            raise ValueError(f"Entity text is a common pronoun: {cleaned}")
        return cleaned

    @field_validator("type")
    @classmethod
    def _validate_type(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("surface_forms", mode="before")
    @classmethod
    def _normalize_surface_forms(cls, value: list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            cleaned = []
            for item in value:
                if isinstance(item, str) and item.strip():
                    cleaned.append(item.strip())
            return cleaned
        return []

    @property
    def normalized_text(self) -> str:
        """NFC normalized and lowercased text for deduplication."""
        return unicodedata.normalize("NFC", self.text).strip().lower()


class NewsEntityList(BaseModel):
    """Container for structured LLM entity extraction output."""

    entities: list[NewsEntity] = Field(default_factory=list)

    @classmethod
    def model_validate(
        cls,
        obj: Any,
        *,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> NewsEntityList:
        """Parse the LLM JSON object, dropping individual invalid entities.

        The default Pydantic ``model_validate`` aborts the whole list when a
        single entity fails validation. Story 14.2a / AC-3 needs robust
        downstream ingestion, so we keep the valid entities and log the drops.
        """
        if isinstance(obj, dict) and "entities" in obj:
            raw_entities = obj["entities"] or []
        elif isinstance(obj, list):
            raw_entities = obj
        else:
            raw_entities = []

        valid: list[NewsEntity] = []
        for idx, item in enumerate(raw_entities):
            try:
                valid.append(NewsEntity.model_validate(item, strict=strict))
            except Exception:
                logger.warning(
                    "news_entity_dropped index=%s item=%s",
                    idx,
                    item,
                    exc_info=True,
                )
        return cls(entities=valid)
