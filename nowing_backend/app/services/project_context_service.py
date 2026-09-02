"""Service for building bounded project context for chat turns."""

from __future__ import annotations

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
    model_name = model_names[0] if model_names else getattr(llm, "model", None)
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
    ) -> str:
        """Build formatted string containing Master Instructions and Pinned Documents.

        Pinned documents are truncated to `max_pinned_tokens` (default 4000 tokens)
        ordered by most recently pinned first.
        """
        sections: list[str] = []

        # 1. Project Master Instructions
        master_instructions = (project.master_instructions or "").strip()
        if master_instructions:
            sections.append(
                f"<project_master_instructions name=\"{project.name}\">\n"
                f"{master_instructions}\n"
                f"</project_master_instructions>"
            )

        # 2. Pinned Documents
        if pinned_pairs:
            doc_blocks: list[str] = []
            accumulated_tokens = 0

            for _pin, doc in pinned_pairs:
                doc_title = doc.title or "Untitled Document"
                # Content prioritization: summary/source_markdown/content
                raw_text = doc.source_markdown or doc.content or ""
                raw_text = raw_text.strip()
                if not raw_text:
                    continue

                # Prepare block header/footer
                block_prefix = f"<pinned_document id=\"{doc.id}\" title=\"{doc_title}\">\n"
                block_suffix = "\n</pinned_document>"

                # Check token consumption
                block_candidate = f"{block_prefix}{raw_text}{block_suffix}"
                block_tokens = _count_tokens(block_candidate, llm=llm)

                if accumulated_tokens + block_tokens <= max_pinned_tokens:
                    doc_blocks.append(block_candidate)
                    accumulated_tokens += block_tokens
                else:
                    # Budget remaining
                    remaining_budget = max_pinned_tokens - accumulated_tokens
                    if remaining_budget <= 50:
                        break  # Not enough space for meaningful content

                    # Estimate chars allowed
                    allowed_chars = remaining_budget * 4
                    truncated_text = raw_text[:allowed_chars].rsplit(" ", 1)[0] + "\n...[truncated]"
                    truncated_candidate = f"{block_prefix}{truncated_text}{block_suffix}"
                    doc_blocks.append(truncated_candidate)
                    break

            if doc_blocks:
                sections.append(
                    "<project_pinned_documents>\n"
                    + "\n\n".join(doc_blocks)
                    + "\n</project_pinned_documents>"
                )

        if not sections:
            return ""

        return (
            f"<project_context id=\"{project.id}\" name=\"{project.name}\">\n"
            + "\n\n".join(sections)
            + "\n</project_context>"
        )
