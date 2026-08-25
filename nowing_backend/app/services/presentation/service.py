"""Presentation Studio service (Story 27.2a)."""

from __future__ import annotations

import contextlib
import json
import logging
import re
import shutil
import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import FILE_STORAGE_LOCAL_PATH, config as app_config
from app.db import SlidePresentation
from app.services.llm_service import get_planner_llm
from app.services.presentation.marp_driver import build_marp_markdown, render_marp_html
from app.services.presentation.pptx_driver import write_pptx
from app.services.presentation.schemas import (
    DeckSpec,
    GeneratePresentationInput,
    GeneratePresentationOutput,
)
from app.services.token_tracking_service import UsageType, record_token_usage
from app.services.web_builder.deploy_service import disambiguate_slug

logger = logging.getLogger(__name__)


def _llm_content_to_text(raw: Any) -> str:
    """Normalize LangChain content (str | list of parts) to plain text."""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        parts: list[str] = []
        for part in raw:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                text = part.get("text")
                if text is not None:
                    parts.append(str(text))
            else:
                text = getattr(part, "text", None)
                if text is not None:
                    parts.append(str(text))
        return "".join(parts)
    return str(raw)


def _extract_token_usage(response: Any, llm: Any) -> dict[str, Any]:
    """Best-effort token/cost extraction across LiteLLM / OpenAI metadata shapes."""
    rm = getattr(response, "response_metadata", None) or {}
    usage = getattr(response, "usage_metadata", None) or rm.get("token_usage") or {}
    if not isinstance(usage, dict):
        usage = {}

    prompt_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion_tokens = int(
        usage.get("completion_tokens") or usage.get("output_tokens") or 0
    )
    total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
    token_usage: dict[str, Any] = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }

    cost = getattr(response, "cost", None) or rm.get("cost") or usage.get("cost")
    if cost is not None:
        with contextlib.suppress(TypeError, ValueError):
            token_usage["cost_micros"] = int(float(cost) * 1_000_000)

    model_name = (
        getattr(llm, "model", None)
        or getattr(llm, "model_name", None)
        or usage.get("model")
        or rm.get("model")
        or "unknown"
    )
    token_usage["model_name"] = str(model_name)
    return token_usage


class PresentationStudioService:
    """Generate PPTX or Marp Markdown slide decks from natural language."""

    def __init__(self, storage_base_path: str | None = None):
        self.storage_base_path = Path(
            storage_base_path or FILE_STORAGE_LOCAL_PATH
        ).resolve()

    def _resolve_storage_path(
        self,
        workspace_id: int,
        presentation_id: str,
        subdir: str | None = None,
    ) -> Path:
        """Return the workspace-scoped storage directory for a presentation."""
        subdir = subdir or app_config.PRESENTATION_FILE_STORAGE_SUBDIR
        subdir_path = Path(subdir)
        if subdir_path.is_absolute() or ".." in subdir_path.parts:
            raise ValueError("Presentation storage path escapes storage root")
        scoped = (
            self.storage_base_path / subdir / str(workspace_id) / presentation_id
        ).resolve()
        if not scoped.is_relative_to(self.storage_base_path):
            raise ValueError("Presentation storage path escapes storage root")
        return scoped

    def _download_url(self, presentation_id: str, workspace_id: int) -> str:
        return (
            f"{app_config.BACKEND_URL.rstrip('/')}/api/v1/presentations/{presentation_id}"
            f"/download?workspace_id={workspace_id}"
        )

    def _preview_url(self, presentation_id: str, workspace_id: int) -> str:
        return (
            f"{app_config.BACKEND_URL.rstrip('/')}/api/v1/presentations/{presentation_id}"
            f"/preview?workspace_id={workspace_id}"
        )

    async def _record_usage(
        self,
        *,
        session: AsyncSession,
        workspace_id: int,
        user_id: UUID | None,
        token_usage: dict[str, Any],
        presentation_id: str | None,
        status: str,
    ) -> None:
        """Record TokenUsage when we have a real user_id; never raise."""
        if user_id is None:
            return
        try:
            await record_token_usage(
                session=session,
                workspace_id=workspace_id,
                user_id=user_id,
                usage_type=UsageType.PRESENTATION_GENERATE,
                prompt_tokens=int(token_usage.get("prompt_tokens", 0) or 0),
                completion_tokens=int(token_usage.get("completion_tokens", 0) or 0),
                total_tokens=int(token_usage.get("total_tokens", 0) or 0),
                cost_micros=int(token_usage.get("cost_micros", 0) or 0),
                model_breakdown={"model": token_usage.get("model_name", "unknown")},
                call_details={
                    "presentation_id": presentation_id,
                    "status": status,
                },
            )
        except Exception:
            logger.exception(
                "[PresentationStudio] Failed to record presentation_generate usage"
            )

    async def _call_llm_for_deck(
        self,
        prompt: str,
        language: str,
        workspace_id: int,
        session: AsyncSession | None = None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        """Call workspace LLM with structured slide-deck instructions."""
        from app.services.llm_service import get_agent_llm

        llm = await get_agent_llm(session, workspace_id) if session else None
        if not llm:
            llm = get_planner_llm()

        system_instruction = (
            "You are an expert presentation designer. "
            "Generate a slide deck from the user's description. "
            "Return ONLY a valid JSON object matching this schema:\n"
            "{\n"
            '  "title": "Deck Title",\n'
            '  "slug": "deck-slug-optional",\n'
            '  "description": "Short description",\n'
            '  "slides": [\n'
            "    {\n"
            '      "title": "Slide Title",\n'
            '      "bullets": ["point 1", "point 2"],\n'
            '      "notes": "Speaker notes",\n'
            '      "chart": { "categories": ["Q1", "Q2"], "series": [100, 200] }\n'
            "    }\n"
            "  ]\n"
            "}\n"
            f"Target language: {language}.\n"
            "Require at least one content slide in slides[].\n"
            "If the prompt is empty or cannot be turned into a slide deck, return:\n"
            '{"status": "validation_failed", "error": "Could not generate a valid deck from that description. Try a more specific outline."}\n'
            "DO NOT wrap with markdown fences or add explanations outside the JSON."
        )

        try:
            response = await llm.ainvoke(
                [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt},
                ]
            )
            raw_text = _llm_content_to_text(
                response.content if hasattr(response, "content") else response
            )

            cleaned_text = raw_text.strip()
            if cleaned_text.startswith("```"):
                cleaned_text = re.sub(r"^```(?:json)?\n", "", cleaned_text)
                cleaned_text = re.sub(r"\n```$", "", cleaned_text)

            brace_idx = cleaned_text.find("{")
            if brace_idx == -1:
                return None, _extract_token_usage(response, llm)
            try:
                spec, _ = json.JSONDecoder().raw_decode(cleaned_text, brace_idx)
            except json.JSONDecodeError:
                return None, _extract_token_usage(response, llm)

            return spec, _extract_token_usage(response, llm)
        except Exception as e:
            logger.warning("[PresentationStudio] LLM call failed: %s", e)
            return None, {}

    async def generate(
        self,
        build_input: GeneratePresentationInput,
        session: AsyncSession,
    ) -> GeneratePresentationOutput:
        """Generate a slide deck, write files, and persist SlidePresentation."""
        presentation_id = str(uuid.uuid4())
        storage_dir: Path | None = None

        output_format = build_input.output_format.lower().strip()
        if output_format not in ("pptx", "marp"):
            logger.warning(
                "[PresentationStudio] Invalid output_format %r; coercing to pptx",
                output_format,
            )
            output_format = "pptx"

        prompt = build_input.prompt.strip()
        if not prompt:
            return GeneratePresentationOutput(
                status="validation_failed",
                error="Prompt must not be empty.",
                workspace_id=build_input.workspace_id,
            )

        if len(prompt) > app_config.PRESENTATION_MAX_PROMPT_CHARS:
            prompt = prompt[: app_config.PRESENTATION_MAX_PROMPT_CHARS]

        spec_dict, token_usage = await self._call_llm_for_deck(
            prompt=prompt,
            language=build_input.language,
            workspace_id=build_input.workspace_id,
            session=session,
        )

        async def _fail_validation(error: str) -> GeneratePresentationOutput:
            await self._record_usage(
                session=session,
                workspace_id=build_input.workspace_id,
                user_id=build_input.user_id,
                token_usage=token_usage,
                presentation_id=None,
                status="validation_failed",
            )
            try:
                await session.commit()
            except Exception:
                logger.exception(
                    "[PresentationStudio] Failed to commit usage for validation_failed"
                )
            return GeneratePresentationOutput(
                status="validation_failed",
                error=error,
                workspace_id=build_input.workspace_id,
            )

        if spec_dict and spec_dict.get("status") == "validation_failed":
            return await _fail_validation(
                str(
                    spec_dict.get(
                        "error",
                        "Could not generate a valid deck from that description. Try a more specific outline.",
                    )
                )
            )

        if not spec_dict or not isinstance(spec_dict, dict):
            return await _fail_validation(
                "LLM output validation failed: malformed JSON."
            )

        try:
            spec = DeckSpec(**spec_dict)
        except Exception as e:
            logger.warning("[PresentationStudio] DeckSpec validation failed: %s", e)
            return await _fail_validation("Deck spec validation failed.")

        status: str = "ready"
        degradation_reason: str | None = None
        file_path: str | None = None
        preview_url: str | None = None

        try:
            storage_dir = self._resolve_storage_path(
                build_input.workspace_id, presentation_id
            )
            storage_dir.mkdir(parents=True, exist_ok=True)

            if output_format == "marp":
                md_text = build_marp_markdown(spec.model_dump(mode="json"))
                md_file = storage_dir / "output.md"
                md_file.write_text(md_text, encoding="utf-8")
                file_path = str(md_file)

                html_file = storage_dir / "output.html"
                ok, error = await render_marp_html(md_file, html_file)
                if ok:
                    preview_url = self._preview_url(
                        presentation_id, build_input.workspace_id
                    )
                else:
                    status = "degraded"
                    degradation_reason = error
            else:
                pptx_bytes = write_pptx(spec.model_dump(mode="json"))
                pptx_file = storage_dir / "output.pptx"
                pptx_file.write_bytes(pptx_bytes)
                file_path = str(pptx_file)
        except Exception:
            logger.exception("[PresentationStudio] File write failed")
            if storage_dir is not None and storage_dir.exists():
                shutil.rmtree(storage_dir, ignore_errors=True)
            return GeneratePresentationOutput(
                status="failed",
                error="File generation failed.",
                workspace_id=build_input.workspace_id,
            )

        base_slug = (
            spec.slug
            or re.sub(r"[^a-z0-9-]", "-", spec.title.lower()).strip("-")
            or "presentation"
        )
        preview = preview_url if output_format == "marp" else None
        download = self._download_url(presentation_id, build_input.workspace_id)

        slug = base_slug
        last_error: Exception | None = None
        for _attempt in range(3):
            existing_slugs_result = await session.scalars(
                select(SlidePresentation.slug).where(
                    SlidePresentation.workspace_id == build_input.workspace_id
                )
            )
            existing_slugs = set(existing_slugs_result.all())
            slug = disambiguate_slug(base_slug, existing_slugs)

            entity = SlidePresentation(
                id=presentation_id,
                workspace_id=build_input.workspace_id,
                user_id=build_input.user_id,
                title=spec.title,
                slug=slug,
                format=output_format,
                status=status,
                file_path=file_path,
                preview_url=preview,
                slide_count=len(spec.slides),
                degradation_reason=degradation_reason,
                prompt=prompt,
            )
            session.add(entity)
            await self._record_usage(
                session=session,
                workspace_id=build_input.workspace_id,
                user_id=build_input.user_id,
                token_usage=token_usage,
                presentation_id=presentation_id,
                status=status,
            )
            try:
                await session.commit()
                last_error = None
                break
            except IntegrityError as exc:
                last_error = exc
                await session.rollback()
                logger.warning(
                    "[PresentationStudio] Slug collision for %r; retrying", slug
                )
                continue
            except Exception as exc:
                last_error = exc
                await session.rollback()
                break

        if last_error is not None:
            logger.exception("[PresentationStudio] Persist failed: %s", last_error)
            if storage_dir is not None and storage_dir.exists():
                shutil.rmtree(storage_dir, ignore_errors=True)
            return GeneratePresentationOutput(
                status="failed",
                error="Failed to persist presentation.",
                workspace_id=build_input.workspace_id,
            )

        return GeneratePresentationOutput(
            status=status,
            presentation_id=presentation_id,
            workspace_id=build_input.workspace_id,
            title=spec.title,
            slug=slug,
            format=output_format,
            slide_count=len(spec.slides),
            file_path=None,
            download_url=download,
            preview_url=preview,
            degradation_reason=degradation_reason,
        )
