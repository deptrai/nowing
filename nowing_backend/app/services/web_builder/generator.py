"""Web Builder Project Generation Engine (Story 27.1, AC-1)."""

import contextlib
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import FILE_STORAGE_LOCAL_PATH, config as app_config
from app.services.token_tracking_service import record_token_usage
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
    ) -> dict[str, Any] | None:
        """Call workspace LLM with structured system instructions to produce Next.js project files."""
        try:
            from app.services.llm_service import get_agent_llm

            llm = await get_agent_llm(session, workspace_id) if session else None
            if not llm:
                from app.services.llm_service import get_planner_llm

                llm = get_planner_llm()

            system_instruction = (
                "You are an expert Next.js 16 + React 19 + Tailwind CSS developer. "
                "The user will describe a full-stack web application. "
                "Generate a production-ready, beautiful, and fully-functional web application.\n\n"
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
                "DO NOT wrap with markdown fences or extra explanations outside the JSON."
            )

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

            return json.loads(cleaned_text, strict=False)
        except Exception as e:
            logger.warning(
                f"[WebBuilderService] LLM generation failed or returned invalid JSON: {e}"
            )
            return None

    async def _call_llm_for_refinement(
        self,
        existing_files: dict[str, str],
        prompt: str,
        language: str,
        workspace_id: int,
        session: AsyncSession | None = None,
    ) -> dict[str, Any] | None:
        """Call LLM to refine an existing Next.js web application based on user request."""
        try:
            from app.services.llm_service import get_agent_llm

            llm = await get_agent_llm(session, workspace_id) if session else None
            if not llm:
                from app.services.llm_service import get_planner_llm

                llm = get_planner_llm()

            existing_code_snippets = "\n\n".join(
                f"--- {path} ---\n{content}"
                for path, content in existing_files.items()
                if path.endswith((".tsx", ".ts", ".css", ".json"))
            )

            # Cap the refinement context to avoid exceeding LLM context windows.
            if len(existing_code_snippets) > 12_000:
                existing_code_snippets = existing_code_snippets[:12_000]
                # Try to end on a complete file boundary.
                last_file = existing_code_snippets.rfind("\n\n--- ")
                if last_file > 1000:
                    existing_code_snippets = existing_code_snippets[:last_file]

            system_instruction = (
                "You are an expert Next.js 16 + React 19 + Tailwind CSS developer modifying an existing web app. "
                "Preserve existing working components, styling, and sections unless explicitly asked to change them. "
                "Apply the user's modifications cleanly.\n\n"
                "Return ONLY a valid JSON object matching this schema:\n"
                "{\n"
                '  "name": "App Name",\n'
                '  "slug": "app-slug",\n'
                '  "description": "Short description",\n'
                '  "files": [\n'
                '    {"path": "app/page.tsx", "content": "..."}\n'
                "  ]\n"
                "}\n"
                f"Target UI Language: {language}.\n"
                "DO NOT wrap with markdown fences or extra explanations outside the JSON."
            )

            user_message = (
                f"Existing Project Files:\n\n{existing_code_snippets}\n\n"
                f"Requested Changes: {prompt}"
            )

            response = await llm.ainvoke(
                [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_message},
                ]
            )

            raw_text = (
                response.content if hasattr(response, "content") else str(response)
            )
            if isinstance(raw_text, list):
                raw_text = "".join(str(part) for part in raw_text)

            cleaned_text = raw_text.strip()
            if cleaned_text.startswith("```"):
                cleaned_text = re.sub(r"^```(?:json)?\n", "", cleaned_text)
                cleaned_text = re.sub(r"\n```$", "", cleaned_text)

            json_match = re.search(r"(\{.*\})", cleaned_text, re.DOTALL)
            if json_match:
                cleaned_text = json_match.group(1)

            return json.loads(cleaned_text, strict=False)
        except Exception as e:
            logger.warning(
                f"[WebBuilderService] LLM refinement failed or returned invalid JSON: {e}"
            )
            return None

    async def generate_project(
        self,
        build_input: WebAppBuildInput,
        session: AsyncSession | None = None,
    ) -> WebAppBuildOutput:
        """Generate or refine a Next.js project, write files to disk, and persist WorkspaceApp."""
        from sqlalchemy import select

        from app.db import WorkspaceApp
        from app.services.web_builder.deploy_service import disambiguate_slug

        existing_app: WorkspaceApp | None = None
        if build_input.app_id and session:
            stmt = select(WorkspaceApp).where(
                WorkspaceApp.id == build_input.app_id,
                WorkspaceApp.workspace_id == build_input.workspace_id,
            )
            existing_app = (await session.execute(stmt)).scalars().first()

        if existing_app and existing_app.storage_path:
            app_id = existing_app.id
            workspace_dir = Path(existing_app.storage_path).resolve()
            existing_files: dict[str, str] = {}
            for file_path in workspace_dir.rglob("*"):
                if (
                    file_path.is_file()
                    and "node_modules" not in file_path.parts
                    and ".next" not in file_path.parts
                ):
                    rel_path = str(file_path.relative_to(workspace_dir))
                    with contextlib.suppress(Exception):
                        existing_files[rel_path] = file_path.read_text(encoding="utf-8")

            spec_dict = await self._call_llm_for_refinement(
                existing_files=existing_files,
                prompt=build_input.prompt,
                language=build_input.language,
                workspace_id=build_input.workspace_id,
                session=session,
            )
        else:
            app_id = str(uuid.uuid4())
            workspace_dir = (
                self.storage_base_path
                / "web-app"
                / str(build_input.workspace_id)
                / app_id
            )
            spec_dict = await self._call_llm_for_spec(
                prompt=build_input.prompt,
                language=build_input.language,
                workspace_id=build_input.workspace_id,
                session=session,
            )

        if not spec_dict or not isinstance(spec_dict, dict) or "files" not in spec_dict:
            return WebAppBuildOutput(
                app_id=app_id,
                workspace_id=build_input.workspace_id,
                name=build_input.app_name
                or (existing_app.name if existing_app else "Generated Web App"),
                slug=slugify(
                    build_input.app_name
                    or (existing_app.slug if existing_app else "web-app")
                ),
                status="validation_failed",
                message="LLM output validation failed: malformed JSON or missing files specification",
                files=[],
            )

        try:
            spec = GeneratedProjectSpec(**spec_dict)
        except Exception as e:
            return WebAppBuildOutput(
                app_id=app_id,
                workspace_id=build_input.workspace_id,
                name=spec_dict.get(
                    "name", existing_app.name if existing_app else "Generated Web App"
                ),
                slug=slugify(
                    spec_dict.get(
                        "slug", existing_app.slug if existing_app else "web-app"
                    )
                ),
                status="validation_failed",
                message=f"Pydantic schema validation error: {e}",
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
        app_name = spec.name or (
            existing_app.name if existing_app else "Generated Web App"
        )
        app_slug = spec.slug or (existing_app.slug if existing_app else "web-app")
        app_desc = spec.description or (
            existing_app.description if existing_app else None
        )

        # 4. Validate project structure
        is_valid, validation_issues = validate_project_structure(workspace_dir)
        status = "generated" if is_valid else "validation_failed"
        message = (
            None
            if is_valid
            else f"Project validation warnings: {', '.join(validation_issues)}"
        )

        preview_url = f"{app_config.BACKEND_URL.rstrip('/')}/api/v1/web-builder/apps/{app_id}/preview"

        # 5. Persist to DB if session available
        if session:
            try:
                if existing_app:
                    # Cap prompt history at the last 10 turns to avoid unbounded growth
                    history = existing_app.prompt or ""
                    parts = [p for p in history.split("\n---\n") if p.strip()]
                    parts.append(build_input.prompt)
                    if len(parts) > 10:
                        parts = parts[-10:]
                    existing_app.prompt = "\n---\n".join(parts)

                    # Allow LLM/user-provided metadata to update the existing app.
                    # If the slug changes, clear the published URL so the old public
                    # route does not silently serve stale content.
                    existing_app.name = app_name
                    existing_app.description = app_desc
                    existing_app.language = build_input.language

                    existing_slugs_res = await session.scalars(
                        select(WorkspaceApp.slug).where(
                            WorkspaceApp.workspace_id == build_input.workspace_id,
                            WorkspaceApp.id != existing_app.id,
                        )
                    )
                    existing_slugs = set(existing_slugs_res.all())
                    new_slug = disambiguate_slug(app_slug, existing_slugs)
                    if new_slug != existing_app.slug:
                        existing_app.slug = new_slug
                        existing_app.public_url = None
                        existing_app.status = "generated"
                    else:
                        existing_app.status = status
                    existing_app.error_message = message
                    existing_app.preview_url = preview_url
                    app_entity = existing_app
                else:
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
                await session.commit()

                # Record TokenUsage & cost attribution
                await record_token_usage(
                    session=session,
                    workspace_id=build_input.workspace_id,
                    user_id=build_input.user_id,
                    usage_type="web_builder_generate",
                    prompt_tokens=500,
                    completion_tokens=2000,
                    cost_micros=15000,  # $0.015 standard cost estimate
                )
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
            "You are an expert Next.js 16 + React 19 + Tailwind CSS developer. "
            "The user will describe a full-stack web application. "
            "Generate a production-ready, beautiful, and fully-functional web application.\n\n"
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
            "DO NOT wrap with markdown fences or extra explanations outside the JSON."
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

        preview_url = f"{app_config.BACKEND_URL.rstrip('/')}/api/v1/web-builder/apps/{app_id}/preview"

        if session:
            try:
                from app.db import WorkspaceApp

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
                await session.commit()

                await record_token_usage(
                    session=session,
                    workspace_id=build_input.workspace_id,
                    user_id=build_input.user_id,
                    usage_type="web_builder_generate",
                    prompt_tokens=500,
                    completion_tokens=2000,
                    cost_micros=15000,
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
