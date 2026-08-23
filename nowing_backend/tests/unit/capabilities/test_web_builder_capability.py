"""Unit tests for web_builder.build_app capability (Story 27.1, AC-5).

Acceptance Criteria:
- AC-5: Capability registration, schema verification, and billing unit tracking.
"""

import pytest

pytestmark = [pytest.mark.unit]


class TestWebBuilderCapability:
    """Capability registration and invocation tests for web_builder."""

    @pytest.mark.skip(reason="RED-PHASE: Capability web_builder.build_app not yet registered")
    def test_capability_is_registered_in_registry(self):
        """AC-5: Capability web_builder.build_app is registered with correct metadata."""
        from app.capabilities.core.registry import capability_registry
        from app.capabilities.core.types import BillingUnit

        cap = capability_registry.get("web_builder.build_app")
        assert cap is not None
        assert cap.name == "web_builder.build_app"
        assert cap.billing_unit in [BillingUnit.WEB_BUILDER_GENERATE, "web_builder_generate"]

    @pytest.mark.skip(reason="RED-PHASE: Capability schemas not yet implemented")
    def test_capability_input_schema_validation(self):
        """AC-5: WebBuilderInput schema validates required prompt and workspace_id."""
        from app.capabilities.web_builder.build_app.schemas import WebBuilderCapabilityInput

        valid_input = WebBuilderCapabilityInput(
            prompt="Build a SaaS dashboard",
            language="en",
            workspace_id=1,
        )
        assert valid_input.prompt == "Build a SaaS dashboard"
        assert valid_input.workspace_id == 1
