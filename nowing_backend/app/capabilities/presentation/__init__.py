"""Presentation capability package."""

from app.capabilities.presentation.generate import (
    PresentationCapabilityInput,
    PresentationCapabilityOutput,
    execute_generate_presentation,
    presentation_generate_capability,
)

__all__ = [
    "PresentationCapabilityInput",
    "PresentationCapabilityOutput",
    "execute_generate_presentation",
    "presentation_generate_capability",
]
