"""Unit tests for presentation.generate capability."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.capabilities.core.store import CapabilityRegistry
from app.capabilities.core.types import BillingUnit
from app.capabilities.presentation.generate import (
    PresentationCapabilityInput,
    PresentationCapabilityOutput,
    execute_generate_presentation,
    presentation_generate_capability,
)
from app.services.presentation.schemas import GeneratePresentationOutput


@pytest.mark.unit
def test_presentation_generate_registered_in_capability_registry():
    """Verify presentation.generate is properly registered with correct metadata."""
    cap = CapabilityRegistry.get("presentation.generate")
    assert cap is not None
    assert cap.name == "presentation.generate"
    assert cap.billing_unit == BillingUnit.PRESENTATION_GENERATE
    assert cap.input_schema == PresentationCapabilityInput
    assert cap.output_schema == PresentationCapabilityOutput


@pytest.mark.unit
async def test_execute_generate_presentation_delegates_to_service(monkeypatch):
    """Verify executor forwards input to PresentationStudioService and maps output."""
    mock_output = GeneratePresentationOutput(
        status="ready",
        presentation_id="pres-123",
        workspace_id=1,
        title="Q3 Strategy",
        slug="q3-strategy",
        format="pptx",
        slide_count=5,
        file_path="/data/pres-123.pptx",
        download_url="/download/pres-123",
        preview_url=None,
    )

    mock_service_instance = MagicMock()
    mock_service_instance.generate = AsyncMock(return_value=mock_output)
    monkeypatch.setattr(
        "app.capabilities.presentation.generate.executor.PresentationStudioService",
        lambda: mock_service_instance,
    )

    session = AsyncMock()
    user_id = uuid4()
    input_data = PresentationCapabilityInput(
        prompt="Create a Q3 strategy deck",
        workspace_id=1,
        output_format="pptx",
        language="en",
        user_id=user_id,
    )

    result = await execute_generate_presentation(session, input_data)

    assert isinstance(result, PresentationCapabilityOutput)
    assert result.status == "ready"
    assert result.presentation_id == "pres-123"
    assert result.title == "Q3 Strategy"
    assert result.slug == "q3-strategy"
    assert result.format == "pptx"
    assert result.slide_count == 5
    assert result.download_url == "/download/pres-123"
    mock_service_instance.generate.assert_awaited_once()
