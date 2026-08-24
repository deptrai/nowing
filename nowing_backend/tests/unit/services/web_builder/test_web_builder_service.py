"""Unit tests for WebBuilderService (Story 27.1: Full-Stack Web App Builder).

Acceptance Criteria:
- AC-1: LLM Web App Generation (structured Next.js + Tailwind project, disk writer, validation).
- AC-2: 1-Click Publish & Slug Disambiguation.
- AC-5: Cost tracking & TokenUsage recording.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

# Mark entire module as red-phase scaffold
pytestmark = [pytest.mark.unit]


class TestWebBuilderServiceGeneration:
    """AC-1: LLM Web App Generation tests."""

    @pytest.mark.asyncio
    async def test_generate_web_app_writes_valid_nextjs_project(self, tmp_path):
        """AC-1: Given a valid prompt, WebBuilderService writes runnable Next.js project to disk."""
        from app.services.web_builder.generator import WebBuilderService
        from app.services.web_builder.schemas import WebAppBuildInput

        service = WebBuilderService(storage_base_path=str(tmp_path))
        build_input = WebAppBuildInput(
            prompt="Build a SaaS landing page for an AI accounting tool with hero, pricing table, and contact form.",
            language="en",
            workspace_id=1,
            user_id=uuid4(),
        )

        mock_llm_response = {
            "name": "Accounting AI",
            "slug": "accounting-ai",
            "files": [
                {
                    "path": "package.json",
                    "content": '{"name": "accounting-ai", "dependencies": {"next": "16.0.0", "react": "^19.0.0", "react-dom": "^19.0.0", "tailwindcss": "^4.0.0"}}',
                },
                {
                    "path": "app/layout.tsx",
                    "content": "export default function Layout({children}) { return <html><body>{children}</body></html>; }",
                },
                {
                    "path": "app/page.tsx",
                    "content": "export default function Page() { return <main><h1>Accounting AI</h1></main>; }",
                },
                {"path": "tailwind.config.ts", "content": "export default {};"},
                {
                    "path": "next.config.js",
                    "content": "module.exports = { output: 'standalone' };",
                },
                {
                    "path": "Dockerfile",
                    "content": 'FROM node:20-alpine AS runner\\nCMD ["node", "server.js"]',
                },
            ],
        }

        with patch.object(
            service, "_call_llm_for_spec", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = (mock_llm_response, {})
            output = await service.generate_project(build_input)

        assert output.status == "generated"
        assert output.app_id is not None
        assert (
            output.preview_url.startswith("http://localhost:")
            or "/preview/" in output.preview_url
        )
        assert len(output.files) >= 5

        # Verify disk files
        project_dir = tmp_path / "web-app" / "1" / output.app_id
        assert (project_dir / "package.json").exists()
        assert (project_dir / "app" / "page.tsx").exists()
        assert (project_dir / "next.config.js").exists()

    @pytest.mark.asyncio
    async def test_generate_web_app_handles_malformed_llm_output_gracefully(
        self, tmp_path
    ):
        """AC-1: Given non-JSON or invalid LLM response, service returns validation_failed status without writing files."""
        from app.services.web_builder.generator import WebBuilderService
        from app.services.web_builder.schemas import WebAppBuildInput

        service = WebBuilderService(storage_base_path=str(tmp_path))
        build_input = WebAppBuildInput(
            prompt="Build a blog",
            language="vi",
            workspace_id=1,
            user_id=uuid4(),
        )

        with patch.object(
            service, "_call_llm_for_spec", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = (None, {})  # Or invalid schema / exception

            output = await service.generate_project(build_input)

        assert output.status == "validation_failed"
        assert (
            "validation" in output.message.lower() or "failed" in output.message.lower()
        )
        assert not (tmp_path / "web-app" / "1").exists()

    def test_path_traversal_prevention(self, tmp_path):
        """Security: File writer must reject attempts to write outside the scoped project directory."""
        from app.services.web_builder.project_writer import ProjectWriter

        writer = ProjectWriter(base_path=str(tmp_path / "web-app" / "1" / "app-123"))
        with pytest.raises(ValueError, match="Path traversal detected"):
            writer.write_file("../../../etc/passwd", "malicious content")


class TestSlugDisambiguation:
    """AC-2: Slug collision disambiguation tests."""

    def test_slug_disambiguation_when_collision_exists(self):
        """AC-2: Two apps with same name generate distinct slugs."""
        from app.services.web_builder.deploy_service import disambiguate_slug

        existing_slugs = {"landing-page", "landing-page-1"}
        new_slug = disambiguate_slug("landing-page", existing_slugs)

        assert new_slug not in existing_slugs
        assert new_slug.startswith("landing-page-")
