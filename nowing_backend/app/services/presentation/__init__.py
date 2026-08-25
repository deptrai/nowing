"""Presentation Studio service (Story 27.2a)."""

from app.services.presentation.schemas import (
    GeneratePresentationInput,
    GeneratePresentationOutput,
)
from app.services.presentation.service import PresentationStudioService

__all__ = [
    "GeneratePresentationInput",
    "GeneratePresentationOutput",
    "PresentationStudioService",
]
