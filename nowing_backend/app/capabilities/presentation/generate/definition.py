"""Capability definition for presentation.generate (Story 27.2a)."""

from app.capabilities.core import Capability, register_capability
from app.capabilities.core.types import BillingUnit
from app.capabilities.presentation.generate.executor import (
    execute_generate_presentation,
)
from app.capabilities.presentation.generate.schemas import (
    PresentationCapabilityInput,
    PresentationCapabilityOutput,
)

presentation_generate_capability = Capability(
    name="presentation.generate",
    description="Generate professional slide decks (PPTX or Marp Markdown) from natural language descriptions",
    input_schema=PresentationCapabilityInput,
    output_schema=PresentationCapabilityOutput,
    executor=execute_generate_presentation,
    billing_unit=BillingUnit.PRESENTATION_GENERATE,
)

register_capability(presentation_generate_capability)
