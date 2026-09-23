"""presentation.generate capability package."""

from app.capabilities.presentation.generate.definition import (
    presentation_generate_capability,
)
from app.capabilities.presentation.generate.executor import (
    execute_generate_presentation,
)
from app.capabilities.presentation.generate.schemas import (
    PresentationCapabilityInput,
    PresentationCapabilityOutput,
)

__all__ = [
    "PresentationCapabilityInput",
    "PresentationCapabilityOutput",
    "execute_generate_presentation",
    "presentation_generate_capability",
]
