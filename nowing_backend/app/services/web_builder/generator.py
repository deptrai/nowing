"""Web Builder Project Generation Engine (Story 27.1, AC-1)."""

import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import FILE_STORAGE_LOCAL_PATH, config as app_config
from app.services.token_tracking_service import record_token_usage
from app.services.web_builder.builder import BuilderService
from app.services.web_builder.project_writer import ProjectWriter
from app.services.web_builder.schemas import (
    GeneratedProjectSpec,
    WebAppBuildInput,
    WebAppBuildOutput,
)
from app.services.web_builder.validator import validate_project_structure

logger = logging.getLogger(__name__)


def slugify(text: str) -> str:
    """Convert text into a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text or "app"


class WebBuilderService:
    """Orchestrates AI-driven full-stack Next.js project generation."""

    def __init__(self, storage_base_path: str | None = None):
        self.storage_base_path = Path(
            storage_base_path or FILE_STORAGE_LOCAL_PATH
        ).resolve()

    async def _call_llm_for_spec(
        self,
        prompt: str,
        language: str,
        workspace_id: int,
        session: AsyncSession | None = None,
    ) -> tuple[dict[str, Any] | None, dict[str, int]]:
        """Call workspace LLM with structured sales/marketing system instructions.

        Returns the parsed project specification plus usage metadata from the LLM
        response so token/cost tracking is not hard-coded (P24).
        """
        from app.services.llm_service import get_agent_llm, get_planner_llm

        llm = await get_agent_llm(session, workspace_id) if session else None
        if not llm:
            llm = get_planner_llm()

        system_instruction = (
            "You are an expert single-page Next.js 16 + React 19 + Tailwind CSS "
            "developer for sales and marketing sites.\n\n"
            "Generate ONE of these five lightweight, single-page templates:\n"
            "- landing: hero, value props, social proof, CTA\n"
            "- pricing: 2-4 tier pricing table with feature bullets\n"
            "- lead-capture: headline, benefit bullets, lead form\n"
            "- waitlist: coming soon, email signup, launch details\n"
            "- report: featured report/whitepaper with download CTA\n\n"
            "Return ONLY a valid JSON object matching this schema:\n"
            "{\n"
            '  "name": "App Name",\n'
            '  "slug": "app-slug",\n'
            '  "description": "Short description",\n'
            '  "files": [\n'
            '    {"path": "package.json", "content": "..."},\n'
            '    {"path": "app/layout.tsx", "content": "..."},\n'
            '    {"path": "app/page.tsx", "content": "..."},\n'
            '    {"path": "app/globals.css", "content": "..."},\n'
            '    {"path": "tailwind.config.ts", "content": "..."}\n'
            "  ]\n"
            "}\n"
            f"Target UI Language: {language}.\n"
            "The app must be a SINGLE PAGE. No multi-page routing, no API routes, "
            "no database, no backend logic, and no container lifecycle.\n"
            "If the user asks for anything out of scope, return:\n"
            '{"status": "validation_failed", "error": "v1 supports single-page sales/marketing sites only. Choose from: landing, pricing, lead-capture, waitlist, report.", "files": []}\n'
            "DO NOT wrap with markdown fences or add explanations outside the JSON."
        )

        try:
            response = await llm.ainvoke(
                [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt},
                ]
            )

            raw_text = (
                response.content if hasattr(response, "content") else str(response)
            )
            if isinstance(raw_text, list):
                raw_text = "".join(str(part) for part in raw_text)

            # Strip possible markdown code fences
            cleaned_text = raw_text.strip()
            if cleaned_text.startswith("```"):
                cleaned_text = re.sub(r"^```(?:json)?\n", "", cleaned_text)
                cleaned_text = re.sub(r"\n```$", "", cleaned_text)

            # Try extracting json substring if surrounding text exists
            json_match = re.search(r"(\{.*\})", cleaned_text, re.DOTALL)
            if json_match:
                cleaned_text = json_match.group(1)

            spec = json.loads(cleaned_text, strict=False)

            # Extract token usage from the LLM response when available.
            usage = getattr(response, "usage_metadata", None) or {}
            if not usage:
                rm = getattr(response, "response_metadata", None) or {}
                usage = rm.get("token_usage") or {}
            token_usage = {
                "prompt_tokens": int(usage.get("input_tokens", 0)),
                "completion_tokens": int(usage.get("output_tokens", 0)),
                "total_tokens": int(
                    usage.get("total_tokens", 0)
                    or usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                ),
            }
            return spec, token_usage
        except Exception as e:
            logger.warning(
                f"[WebBuilderService] LLM generation failed or returned invalid JSON: {e}"
            )
            return None, {}

    async def generate_project(
        self,
        build_input: WebAppBuildInput,
        session: AsyncSession | None = None,
    ) -> WebAppBuildOutput:
        """Generate a new single-page sales/marketing web app, write files, and persist WorkspaceApp."""
        from sqlalchemy import select

        from app.db import WorkspaceApp
        from app.services.web_builder.deploy_service import disambiguate_slug

        app_id = str(uuid.uuid4())
        workspace_dir = (
            self.storage_base_path / "web-app" / str(build_input.workspace_id) / app_id
        )

        spec_dict, token_usage = await self._call_llm_for_spec(
            prompt=build_input.prompt,
            language=build_input.language,
            workspace_id=build_input.workspace_id,
            session=session,
        )

        # The LLM can return an explicit out-of-scope guardrail (P9).
        if spec_dict and spec_dict.get("status") == "validation_failed":
            error = spec_dict.get(
                "error",
                "v1 supports single-page sales/marketing sites only. "
                "Choose from: landing, pricing, lead-capture, waitlist, report.",
            )
            return WebAppBuildOutput(
                app_id=app_id,
                workspace_id=build_input.workspace_id,
                name=build_input.app_name or "Generated Web App",
                slug="",
                status="validation_failed",
                error=error,
                message=error,
                files=[],
            )

        if not spec_dict or not isinstance(spec_dict, dict) or "files" not in spec_dict:
            return WebAppBuildOutput(
                app_id=app_id,
                workspace_id=build_input.workspace_id,
                name=build_input.app_name or "Generated Web App",
                slug="",
                status="validation_failed",
                error="LLM output validation failed: malformed JSON or missing files specification",
                message="LLM output validation failed: malformed JSON or missing files specification",
                files=[],
            )

        try:
            spec = GeneratedProjectSpec(**spec_dict)
        except Exception as e:
            err = f"Pydantic schema validation error: {e}"
            return WebAppBuildOutput(
                app_id=app_id,
                workspace_id=build_input.workspace_id,
                name=spec_dict.get("name", build_input.app_name or "Generated Web App"),
                slug="",
                status="validation_failed",
                error=err,
                message=err,
                files=[],
            )

        workspace_dir.mkdir(parents=True, exist_ok=True)
        writer = ProjectWriter(base_path=workspace_dir)
        written_files = []

        for file_spec in spec.files:
            writer.write_file(file_spec.path, file_spec.content)
            written_files.append(file_spec.path)

        scaffold_files = writer.ensure_scaffold_defaults(
            app_name=spec.name, slug=spec.slug
        )
        written_files.extend([f for f in scaffold_files if f not in written_files])
        app_name = spec.name or build_input.app_name or "Generated Web App"
        app_slug = spec.slug or "web-app"
        app_desc = spec.description

        # 4. Validate project structure
        is_valid, validation_issues = validate_project_structure(workspace_dir)
        status = "generated" if is_valid else "validation_failed"
        message = (
            None
            if is_valid
            else f"Project validation warnings: {', '.join(validation_issues)}"
        )

        preview_url = (
            f"{app_config.BACKEND_URL.rstrip('/')}/api/v1/web-builder/apps/{app_id}/preview"
            f"?workspace_id={build_input.workspace_id}"
        )

        # 5. Persist to DB if session available
        if session:
            try:
                existing_slugs_res = await session.scalars(
                    select(WorkspaceApp.slug).where(
                        WorkspaceApp.workspace_id == build_input.workspace_id
                    )
                )
                existing_slugs = set(existing_slugs_res.all())
                app_slug = disambiguate_slug(app_slug, existing_slugs)

                app_entity = WorkspaceApp(
                    id=app_id,
                    workspace_id=build_input.workspace_id,
                    user_id=build_input.user_id,
                    name=app_name,
                    slug=app_slug,
                    description=app_desc,
                    prompt=build_input.prompt,
                    language=build_input.language,
                    status=status,
                    preview_url=preview_url,
                    storage_path=str(workspace_dir),
                    error_message=message,
                )
                session.add(app_entity)

                # Record actual TokenUsage before commit so it is persisted (R-01).
                await record_token_usage(
                    session=session,
                    workspace_id=build_input.workspace_id,
                    user_id=build_input.user_id,
                    usage_type="web_builder_generate",
                    prompt_tokens=token_usage.get("prompt_tokens", 0),
                    completion_tokens=token_usage.get("completion_tokens", 0),
                    total_tokens=token_usage.get("total_tokens", 0),
                    cost_micros=0,  # priced by usage tokens, not a fixed estimate
                )
                await session.commit()


            except Exception as db_err:
                logger.error(
                    f"[WebBuilderService] DB persistence failed for app {app_id}: {db_err}"
                )

        return WebAppBuildOutput(
            app_id=app_id,
            workspace_id=build_input.workspace_id,
            name=app_name,
            slug=app_slug,
            status=status,
            preview_url=preview_url,
            error=None,
            message=message,
            files=written_files,
        )

    async def generate_project_stream(
        self,
        build_input: WebAppBuildInput,
        session: AsyncSession | None = None,
    ):
        """Stream SSE generation events in real time as LLM creates the full-stack app."""
        app_id = str(uuid.uuid4())
        workspace_dir = (
            self.storage_base_path / "web-app" / str(build_input.workspace_id) / app_id
        )

        yield f"data: {json.dumps({'type': 'phase', 'phase': 'planning', 'message': 'Analyzing prompt and planning Next.js component hierarchy...'})}\n\n"

        from app.services.llm_service import get_agent_llm, get_planner_llm

        llm = (
            await get_agent_llm(session, build_input.workspace_id) if session else None
        )
        if not llm:
            llm = get_planner_llm()

        system_instruction = (
            "You are an expert single-page Next.js 16 + React 19 + Tailwind CSS "
            "developer for sales and marketing sites.\n\n"
            "Generate ONE of these five lightweight, single-page templates:\n"
            "- landing: hero, value props, social proof, CTA\n"
            "- pricing: 2-4 tier pricing table with feature bullets\n"
            "- lead-capture: headline, benefit bullets, lead form\n"
            "- waitlist: coming soon, email signup, launch details\n"
            "- report: featured report/whitepaper with download CTA\n\n"
            "Return ONLY a valid JSON object matching this schema:\n"
            "{\n"
            '  "name": "App Name",\n'
            '  "slug": "app-slug",\n'
            '  "description": "Short description",\n'
            '  "files": [\n'
            '    {"path": "package.json", "content": "..."},\n'
            '    {"path": "app/layout.tsx", "content": "..."},\n'
            '    {"path": "app/page.tsx", "content": "..."},\n'
            '    {"path": "app/globals.css", "content": "..."},\n'
            '    {"path": "tailwind.config.ts", "content": "..."}\n'
            "  ]\n"
            "}\n"
            f"Target UI Language: {build_input.language}.\n"
            "The app must be a SINGLE PAGE. No multi-page routing, no API routes, "
            "no database, no backend logic, and no container lifecycle.\n"
            "DO NOT wrap with markdown fences or add explanations outside the JSON."
        )

        yield f"data: {json.dumps({'type': 'phase', 'phase': 'coding', 'message': 'Streaming full-stack React 19 & Tailwind components...'})}\n\n"

        raw_parts = []
        try:
            async for chunk in llm.astream(
                [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": build_input.prompt},
                ]
            ):
                content = chunk.content if hasattr(chunk, "content") else str(chunk)
                if isinstance(content, list):
                    content = "".join(str(p) for p in content)
                raw_parts.append(content)
                yield f"data: {json.dumps({'type': 'token', 'token': content})}\n\n"
        except Exception as err:
            logger.warning(f"[WebBuilderService] Streaming LLM failed, fallback: {err}")

        raw_text = "".join(raw_parts)
        cleaned_text = raw_text.strip()
        if cleaned_text.startswith("```"):
            cleaned_text = re.sub(r"^```(?:json)?\n", "", cleaned_text)
            cleaned_text = re.sub(r"\n```$", "", cleaned_text)

        json_match = re.search(r"(\{.*\})", cleaned_text, re.DOTALL)
        if json_match:
            cleaned_text = json_match.group(1)

        spec = None
        try:
            spec_dict = json.loads(cleaned_text, strict=False)
            if spec_dict and isinstance(spec_dict, dict) and "files" in spec_dict:
                spec = GeneratedProjectSpec(**spec_dict)
        except Exception as e:
            logger.warning(f"[WebBuilderService] Parsing streaming spec failed: {e}")

        workspace_dir.mkdir(parents=True, exist_ok=True)
        writer = ProjectWriter(base_path=workspace_dir)
        written_files = []

        yield f"data: {json.dumps({'type': 'phase', 'phase': 'scaffolding', 'message': 'Writing project files and standalone configurations...'})}\n\n"

        if spec and spec.files:
            for file_spec in spec.files:
                writer.write_file(file_spec.path, file_spec.content)
                written_files.append(file_spec.path)
                yield f"data: {json.dumps({'type': 'file_written', 'path': file_spec.path, 'size': len(file_spec.content)})}\n\n"

            scaffold_files = writer.ensure_scaffold_defaults(
                app_name=spec.name, slug=spec.slug
            )
            written_files.extend([f for f in scaffold_files if f not in written_files])
            app_name = spec.name
            app_slug = spec.slug
            app_desc = spec.description
        else:
            app_name = build_input.app_name or "Generated Web App"
            app_slug = slugify(app_name)
            app_desc = build_input.prompt[:200]
            written_files = ProjectWriter.write_minimal_nextjs_scaffold(
                workspace_dir, app_name
            )
            for f in written_files:
                yield f"data: {json.dumps({'type': 'file_written', 'path': f})}\n\n"

        is_valid, validation_issues = validate_project_structure(workspace_dir)
        status = "generated" if is_valid else "validation_failed"
        message = (
            None
            if is_valid
            else f"Project validation warnings: {', '.join(validation_issues)}"
        )

        preview_url = (
            f"{app_config.BACKEND_URL.rstrip('/')}/api/v1/web-builder/apps/{app_id}/preview"
            f"?workspace_id={build_input.workspace_id}"
        )

        # ponytail: streaming providers do not reliably expose usage metadata,
        # so we approximate tokens from character counts (about 4 chars/token).
        prompt_tokens = max(1, len(build_input.prompt) // 4)
        completion_tokens = max(1, len(raw_text) // 4)

        if session:
            try:
                from sqlalchemy import select

                from app.db import WorkspaceApp
                from app.services.web_builder.deploy_service import disambiguate_slug

                existing_slugs_res = await session.scalars(
                    select(WorkspaceApp.slug).where(
                        WorkspaceApp.workspace_id == build_input.workspace_id
                    )
                )
                existing_slugs = set(existing_slugs_res.all())
                app_slug = disambiguate_slug(app_slug, existing_slugs)

                app_entity = WorkspaceApp(
                    id=app_id,
                    workspace_id=build_input.workspace_id,
                    user_id=build_input.user_id,
                    name=app_name,
                    slug=app_slug,
                    description=app_desc,
                    prompt=build_input.prompt,
                    language=build_input.language,
                    status=status,
                    preview_url=preview_url,
                    storage_path=str(workspace_dir),
                    error_message=message,
                )
                session.add(app_entity)

                # Record actual TokenUsage before commit so it is persisted (R-01).
                await record_token_usage(
                    session=session,
                    workspace_id=build_input.workspace_id,
                    user_id=build_input.user_id,
                    usage_type="web_builder_generate",
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    cost_micros=0,
                )
                await session.commit()

                if is_valid and status == "generated":
                    await BuilderService.trigger_async_build(
                        app_id=app_id, workspace_id=build_input.workspace_id
                    )
            except Exception as db_err:
                logger.error(
                    f"[WebBuilderService] DB persistence failed for app {app_id}: {db_err}"
                )

        complete_payload = {
            "type": "complete",
            "app": {
                "id": app_id,
                "workspace_id": build_input.workspace_id,
                "name": app_name,
                "slug": app_slug,
                "status": status,
                "preview_url": preview_url,
                "public_url": f"https://{app_slug}.apps.nowing.net",
                "files": written_files,
                "message": message,
            },
        }
        yield f"data: {json.dumps(complete_payload)}\n\n"
