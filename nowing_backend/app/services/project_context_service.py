"""Service for building bounded project context for chat turns."""

from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.documents import Document
from app.models.projects import Project, ProjectPinnedDocument

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

try:
    from litellm import token_counter
except Exception:  # pragma: no cover - optional dep
    token_counter = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

MAX_PINNED_DOCS_TOKENS = 4000

# Leave headroom for base system prompt, mode prompt and tool rules when the
# final combined instructions are clamped to _MAX_INSTRUCTIONS_LEN chars.
MAX_PROJECT_CONTEXT_CHARS = 6000


def _approx_tokens(text: str) -> int:
    """Fallback token counter (1 token ~= 4 characters)."""
    return max(1, (len(text) + 3) // 4)


def _count_tokens(text: str, *, llm: BaseChatModel | None = None) -> int:
    """Calculate token count with litellm if possible or fallback to length estimation."""
    if not text:
        return 0
    if llm is None:
        return _approx_tokens(text)

    count_fn = getattr(llm, "_count_tokens", None)
    if callable(count_fn):
        try:
            return int(count_fn([{"role": "user", "content": text}]))
        except Exception:
            pass

    profile = getattr(llm, "profile", None)
    model_names: list[str] = []
    if isinstance(profile, dict):
        tcms = profile.get("token_count_models")
        if isinstance(tcms, list):
            model_names.extend(name for name in tcms if isinstance(name, str) and name)
        tcm = profile.get("token_count_model")
        if isinstance(tcm, str) and tcm and tcm not in model_names:
            model_names.append(tcm)

    model_name = model_names[0] if model_names else None
    if not model_name:
        # LangChain chat models commonly use ``model_name`` rather than ``model``.
        model_name = getattr(llm, "model_name", None)
    if not model_name:
        model_name = getattr(llm, "model", None)

    if not isinstance(model_name, str) or not model_name or token_counter is None:
        return _approx_tokens(text)

    try:
        return int(
            token_counter(
                messages=[{"role": "user", "content": text}],
                model=model_name,
            )
        )
    except Exception:
        return _approx_tokens(text)


def _truncate_text(text: str, remaining_chars: int) -> str:
    """Trim ``text`` to ``remaining_chars`` while avoiding mid-word breaks.

    Falls back to a hard character cut when no whitespace break is available
    (e.g. URLs, CJK text, minified code).
    """
    if remaining_chars <= 0:
        return ""

    if len(text) <= remaining_chars:
        return text

    # Account for the "...[truncated]" suffix we append later.
    truncated = text[:remaining_chars]
    # ``rfind`` returns -1 on no space, which lets us fall back cleanly.
    last_space = truncated.rfind(" ")
    if last_space > 0:
        return truncated[:last_space]
    # No whitespace in the budget window: hard cut.
    return truncated


class ProjectContextService:
    """Service to load and build bounded project context."""

    @classmethod
    async def load_project_with_pinned_docs(
        cls,
        session: AsyncSession,
        project_id: int,
        workspace_id: int,
    ) -> tuple[Project | None, list[tuple[ProjectPinnedDocument, Document]]]:
        """Load project and active pinned documents belonging to the workspace."""
        stmt = (
            select(Project)
            .where(
                Project.id == project_id,
                Project.workspace_id == workspace_id,
            )
        )
        res = await session.execute(stmt)
        project = res.scalars().first()
        if not project or project.is_archived:
            return None, []

        pins_stmt = (
            select(ProjectPinnedDocument, Document)
            .join(Document, ProjectPinnedDocument.document_id == Document.id)
            .where(
                ProjectPinnedDocument.project_id == project_id,
                Document.workspace_id == workspace_id,
                Document.archived_at.is_(None),
            )
            .order_by(ProjectPinnedDocument.pinned_at.desc())
        )
        pins_res = await session.execute(pins_stmt)
        pinned_pairs = list(pins_res.all())
        return project, pinned_pairs

    @classmethod
    def build_project_context(
        cls,
        project: Project,
        pinned_pairs: list[tuple[ProjectPinnedDocument, Document]],
        *,
        llm: BaseChatModel | None = None,
        max_pinned_tokens: int = MAX_PINNED_DOCS_TOKENS,
        max_total_chars: int = MAX_PROJECT_CONTEXT_CHARS,
    ) -> str:
        """Build formatted string containing Master Instructions and Pinned Documents.

        Pinned documents are truncated to ``max_pinned_tokens`` (default 4000
        tokens) ordered by most recently pinned first. The total returned string
        is also bounded by ``max_total_chars`` to avoid starving the rest of the
        combined system prompt when ``_clamp_agent_instructions`` runs.
        """
        sections: list[str] = []

        # 1. Project Master Instructions
        master_instructions = (project.master_instructions or "").strip()
        if master_instructions:
            safe_master = html.escape(master_instructions)
            safe_name = html.escape(project.name)
            sections.append(
                f"<project_master_instructions name=\"{safe_name}\">\n"
                f"{safe_master}\n"
                f"</project_master_instructions>"
            )

        # Track overall character budget for the whole project context.
        accumulated_chars = sum(len(s) for s in sections)

        # 2. Pinned Documents
        if pinned_pairs:
            doc_blocks: list[str] = []
            accumulated_tokens = 0

            for _pin, doc in pinned_pairs:
                doc_title = (doc.title or "Untitled Document").strip()
                safe_title = html.escape(doc_title)
                # Content prioritization: summary/source_markdown/content
                raw_text = doc.source_markdown or doc.content or ""
                raw_text = raw_text.strip()
                if not raw_text:
                    continue

                safe_raw = html.escape(raw_text)

                # Prepare block header/footer
                block_prefix = f"<pinned_document id=\"{doc.id}\" title=\"{safe_title}\">\n"
                block_suffix = "\n</pinned_document>"

                # Check token consumption
                block_candidate = f"{block_prefix}{safe_raw}{block_suffix}"
                block_tokens = _count_tokens(block_candidate, llm=llm)

                if accumulated_tokens + block_tokens <= max_pinned_tokens:
                    if accumulated_chars + len(block_candidate) > max_total_chars:
                        # Whole block would exceed the char budget: attempt a truncation.
                        suffix = "\n...[truncated]"
                        available_chars = max(
                            0,
                            max_total_chars
                            - accumulated_chars
                            - len(block_prefix)
                            - len(block_suffix)
                            - len(suffix),
                        )
                        truncated = _truncate_text(safe_raw, available_chars)
                        if truncated:
                            block = f"{block_prefix}{truncated}{suffix}{block_suffix}"
                            if accumulated_chars + len(block) <= max_total_chars:
                                doc_blocks.append(block)
                                accumulated_chars += len(block)
                        break

                    doc_blocks.append(block_candidate)
                    accumulated_tokens += block_tokens
                    accumulated_chars += len(block_candidate)
                else:
                    # Budget remaining
                    remaining_budget = max_pinned_tokens - accumulated_tokens
                    if remaining_budget <= 50:
                        break  # Not enough space for meaningful content

                    # Estimate chars allowed, but also respect the total char cap.
                    remaining_chars = min(
                        remaining_budget * 4,
                        max(0, max_total_chars - accumulated_chars - len(block_prefix) - len(block_suffix) - 50),
                    )
                    if remaining_chars <= 0:
                        break

                    truncated_text = _truncate_text(safe_raw, int(remaining_chars))
                    if not truncated_text:
                        break

                    truncated_candidate = (
                        f"{block_prefix}{truncated_text}\n...[truncated]{block_suffix}"
                    )
                    doc_blocks.append(truncated_candidate)
                    accumulated_chars += len(truncated_candidate)
                    break

            if doc_blocks:
                sections.append(
                    "<project_pinned_documents>\n"
                    + "\n\n".join(doc_blocks)
                    + "\n</project_pinned_documents>"
                )

        if not sections:
            return ""

        safe_name = html.escape(project.name)
        return (
            f"<project_context id=\"{project.id}\" name=\"{safe_name}\">\n"
            + "\n\n".join(sections)
            + "\n</project_context>"
        )
