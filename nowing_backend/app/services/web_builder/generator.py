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
        from app.agents.chat.runtime.llm_config import create_chat_litellm_from_config

        # Build a prioritized list of LLM candidates
        llm_candidates: list[Any] = []

        if session:
            agent_llm = await get_agent_llm(session, workspace_id, disable_streaming=True)
            if agent_llm:
                logger.info("[WebBuilderService] Using workspace chat LLM")
                llm_candidates.append(agent_llm)

        planner_llm = get_planner_llm()
        if planner_llm:
            logger.info("[WebBuilderService] Using planner LLM")
            llm_candidates.append(planner_llm)

        if app_config.GLOBAL_LLM_CONFIGS:
            for cfg in app_config.GLOBAL_LLM_CONFIGS:
                if cfg.get("model_name"):
                    global_llm = create_chat_litellm_from_config(cfg)
                    if global_llm:
                        logger.info("[WebBuilderService] Adding global LLM candidate: %s", cfg.get("name"))
                        llm_candidates.append(global_llm)

        if not llm_candidates:
            logger.error("[WebBuilderService] No LLM available for project generation")
            return None, {}

        system_instruction = (
            "You are an expert single-page Next.js 16 + React 19 + Tailwind CSS "
            "developer for sales and marketing sites.\n\n"
            "CRITICAL: Return ONLY a single, valid JSON object. No prose, no markdown "
            "fences, no explanation before or after the JSON.\n\n"
            "Generate ONE of these five lightweight, single-page templates:\n"
            "- landing: hero, value props, social proof, CTA\n"
            "- pricing: 2-4 tier pricing table with feature bullets\n"
            "- lead-capture: headline, benefit bullets, lead form\n"
            "- waitlist: coming soon, email signup, launch details\n"
            "- report: featured report/whitepaper with download CTA\n\n"
            "Your JSON MUST match this exact schema and be minified/compact when possible:\n"
            '{"name":"App Name","slug":"app-slug","description":"Short description","files":[{"path":"package.json","content":"..."},{"path":"app/layout.tsx","content":"..."},{"path":"app/page.tsx","content":"..."},{"path":"app/globals.css","content":"..."},{"path":"tailwind.config.ts","content":"..."}]}\n'
            f"Target UI Language: {language}.\n"
            "The app must be a SINGLE PAGE. No multi-page routing, no API routes, "
            "no database, no backend logic, and no container lifecycle.\n"
            "If the user asks for anything out of scope, return:\n"
            '{"status":"validation_failed","error":"v1 supports single-page sales/marketing sites only. Choose from: landing, pricing, lead-capture, waitlist, report.","files":[]}\n'
            "DO NOT wrap with markdown fences or add explanations outside the JSON."
        )

        def _extract_json(text: str) -> dict[str, Any] | None:
            """Extract the first valid top-level JSON object from arbitrary LLM text."""
            if not text:
                return None

            cleaned = text.strip()

            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)

            try:
                return json.loads(cleaned, strict=False)
            except json.JSONDecodeError:
                pass

            decoder = json.JSONDecoder()
            for start_idx in (m.start() for m in re.finditer(r"(?<!\\)\{", cleaned)):
                try:
                    obj, end = decoder.raw_decode(cleaned, start_idx)
                    if isinstance(obj, dict):
                        return obj
                except (json.JSONDecodeError, ValueError):
                    continue

            fence_match = re.search(r"```(?:json)?\n(.*?)\n```", text, re.DOTALL)
            if fence_match:
                try:
                    return json.loads(fence_match.group(1), strict=False)
                except json.JSONDecodeError:
                    pass

            return None

        def _classify_error(e: BaseException) -> str:
            error_str = str(e).lower()
            if any(k in error_str for k in ["quota", "rate", "429", "exhausted"]):
                return "AI model service is temporarily unavailable due to rate limit. Please try again in a few minutes."
            if any(k in error_str for k in ["timeout", "timed out"]):
                return "AI model service timed out. Please try a shorter prompt or try again later."
            if any(k in error_str for k in ["no llm", "none", "not configured"]):
                return "No AI model is configured for this workspace."
            if "content" in error_str and "moderation" in error_str:
                return "Content was rejected by the AI safety filter. Please rephrase your request."
            return f"AI generation failed: {e}"

        last_error: BaseException | None = None
        for attempt, current_llm in enumerate(llm_candidates, start=1):
            try:
                model_name = getattr(current_llm, "model", getattr(current_llm, "model_name", "unknown"))
                logger.info("[WebBuilderService] LLM attempt %d with %s", attempt, model_name)

                # Gemini/OpenAI-compatible providers support response_format json_object
                invoke_kwargs: dict[str, Any] = {}
                if isinstance(model_name, str):
                    m = model_name.lower()
                    if any(p in m for p in ["openai", "gemini", "gpt", "claude"]):
                        invoke_kwargs["response_format"] = {"type": "json_object"}

                response = await current_llm.ainvoke(
                    [
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": prompt},
                    ],
                    **invoke_kwargs,
                )

                raw_text = ""
                if hasattr(response, "content"):
                    content = response.content
                    if isinstance(content, str):
                        raw_text = content
                    elif isinstance(content, list):
                        parts = []
                        for block in content:
                            if isinstance(block, str):
                                parts.append(block)
                            elif isinstance(block, dict):
                                if block.get("type") == "text" and isinstance(block.get("text"), str):
                                    parts.append(block["text"])
                                elif isinstance(block.get("text"), str):
                                    # OpenAI / compatible text blocks
                                    parts.append(block["text"])
                                elif isinstance(block.get("content"), str):
                                    parts.append(block["content"])
                            # Skip non-text blocks (e.g. Anthropic thinking) to avoid
                            # injecting the stringified dict into JSON extraction.
                        raw_text = "".join(parts)
                    else:
                        raw_text = str(content)
                else:
                    raw_text = str(response)

                logger.info(
                    "[WebBuilderService] Raw LLM response length: %d chars",
                    len(raw_text),
                )
                if raw_text:
                    logger.info(
                        "[WebBuilderService] Raw LLM response (first 1500 chars): %s",
                        raw_text[:1500],
                    )

                spec = _extract_json(raw_text)

                if spec is None and raw_text:
                    first_brace = raw_text.find("{")
                    last_brace = raw_text.rfind("}")
                    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                        retry_text = raw_text[first_brace : last_brace + 1]
                        logger.warning("[WebBuilderService] Retry JSON extraction with bounded braces")
                        spec = _extract_json(retry_text)

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

                if spec is None:
                    logger.warning(
                        "[WebBuilderService] Could not parse JSON from LLM output on attempt %d",
                        attempt,
                    )
                    last_error = ValueError("LLM returned output that could not be parsed as JSON")
                    continue

                return spec, token_usage

            except Exception as e:
                logger.warning(
                    "[WebBuilderService] LLM attempt %d failed: %s: %s",
                    attempt,
                    type(e).__name__,
                    e,
                )
                last_error = e
                continue

        logger.error(
            "[WebBuilderService] All %d LLM candidates failed. Last error: %s",
            len(llm_candidates),
            last_error,
        )

        error_message = _classify_error(last_error or Exception("Unknown error"))
        return {"__llm_error__": True, "__error_message__": error_message}, {}


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
            # Distinguish between an LLM infrastructure failure and a malformed output
            if spec_dict and spec_dict.get("__llm_error__") is True:
                error = spec_dict.get(
                    "__error_message__",
                    "AI model service unavailable. Please try again later.",
                )
                status = "llm_error"
            else:
                error = "LLM output validation failed: malformed JSON or missing files specification"
                status = "validation_failed"

            return WebAppBuildOutput(
                app_id=app_id,
                workspace_id=build_input.workspace_id,
                name=build_input.app_name or "Generated Web App",
                slug="",
                status=status,
                error=error,
                message=error,
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
