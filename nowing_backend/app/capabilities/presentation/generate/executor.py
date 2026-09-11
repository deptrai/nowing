"""Executor for presentation.generate capability (Story 27.2a)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.presentation.generate.schemas import (
    PresentationCapabilityInput,
    PresentationCapabilityOutput,
)
from app.services.presentation.schemas import GeneratePresentationInput
from app.services.presentation.service import PresentationStudioService


async def execute_generate_presentation(
    session: AsyncSession,
    input_data: PresentationCapabilityInput,
) -> PresentationCapabilityOutput:
    """Execute presentation generation and return structured status."""
    service = PresentationStudioService()
    build_input = GeneratePresentationInput(
        prompt=input_data.prompt,
        output_format=input_data.output_format,
        workspace_id=input_data.workspace_id,
        user_id=input_data.user_id,
        language=input_data.language,
    )

    result = await service.generate(build_input, session=session)
    return PresentationCapabilityOutput(
        status=result.status,
        presentation_id=result.presentation_id,
        workspace_id=result.workspace_id,
        title=result.title,
        slug=result.slug,
        format=result.format,
        slide_count=result.slide_count,
        file_path=result.file_path,
        download_url=result.download_url,
        preview_url=result.preview_url,
        error=result.error,
        degradation_reason=result.degradation_reason,
    )
