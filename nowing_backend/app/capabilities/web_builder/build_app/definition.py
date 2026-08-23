"""Capability definition for web_builder.build_app (Story 27.1, AC-5)."""

from app.capabilities.core import Capability, register_capability
from app.capabilities.core.types import BillingUnit
from app.capabilities.web_builder.build_app.executor import execute_build_app
from app.capabilities.web_builder.build_app.schemas import (
    WebBuilderCapabilityInput,
    WebBuilderCapabilityOutput,
)

web_builder_build_app_capability = Capability(
    name="web_builder.build_app",
    description="Generate a full-stack Next.js and Tailwind CSS web application from a natural language description",
    input_schema=WebBuilderCapabilityInput,
    output_schema=WebBuilderCapabilityOutput,
    executor=execute_build_app,
    billing_unit=BillingUnit.WEB_BUILDER_GENERATE,
)

register_capability(web_builder_build_app_capability)
