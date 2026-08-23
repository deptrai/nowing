"""Executor for web_builder.build_app capability (Story 27.1, AC-5)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.web_builder.build_app.schemas import (
    WebBuilderCapabilityInput,
    WebBuilderCapabilityOutput,
)
from app.services.web_builder.generator import WebBuilderService
from app.services.web_builder.schemas import WebAppBuildInput


async def execute_build_app(
    session: AsyncSession,
    input_data: WebBuilderCapabilityInput,
) -> WebBuilderCapabilityOutput:
    """Execute AI project generation and return structured status."""
    service = WebBuilderService()
    build_input = WebAppBuildInput(
        prompt=input_data.prompt,
        language=input_data.language,
        workspace_id=input_data.workspace_id,
        app_name=input_data.app_name,
    )

    result = await service.generate_project(build_input, session=session)
    return WebBuilderCapabilityOutput(
        app_id=result.app_id,
        workspace_id=result.workspace_id,
        name=result.name,
        slug=result.slug,
        status=result.status,
        preview_url=result.preview_url,
        public_url=result.public_url,
        files_count=len(result.files),
        message=result.message,
    )
