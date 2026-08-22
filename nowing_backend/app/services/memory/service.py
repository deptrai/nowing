"""Canonical read/write/reset/extract service for markdown memory.

This module is the backward-compatible bridge. Under the hood it stores
memory in the structured ``Memory`` table and renders to markdown for
legacy clients.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Memory, User
from app.services.memory.document import parse_memory_document, render_memory_document
from app.services.memory.parser import parse_memory_markdown_to_facts
from app.services.memory.renderer import render_memory_markdown
from app.services.memory.repository import MemoryRepository
from app.services.memory.rewrite import forced_rewrite
from app.services.memory.schemas import MemoryLimits
from app.services.memory.validation import (
    MEMORY_HARD_LIMIT,
    MEMORY_SOFT_LIMIT,
    soft_limit_warning,
    strip_preamble_to_first_heading,
    validate_bullet_format,
    validate_diff,
    validate_heading_sanity,
    validate_memory_scope,
    validate_memory_size,
)
from app.tenant_context import set_request_tenant_context

logger = logging.getLogger(__name__)

_NO_UPDATE_SENTINELS = frozenset(
    {
        "NO_UPDATE",
        "NO UPDATE",
        "NO_CHANGE",
        "NO CHANGE",
    }
)


class MemoryScope(StrEnum):
    USER = "user"
    TEAM = "team"


@dataclass(frozen=True)
class SaveResult:
    status: Literal["saved", "error", "no_op"]
    message: str
    memory_md: str = ""
    warnings: list[str] = field(default_factory=list)
    diff_warnings: list[str] = field(default_factory=list)
    format_warnings: list[str] = field(default_factory=list)
    notice: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "status": self.status,
            "message": self.message,
            "memory_md": self.memory_md,
        }
        if self.notice:
            data["notice"] = self.notice
        if self.warnings:
            data["warnings"] = self.warnings
            if len(self.warnings) == 1:
                data["warning"] = self.warnings[0]
        if self.diff_warnings:
            data["diff_warnings"] = self.diff_warnings
        if self.format_warnings:
            data["format_warnings"] = self.format_warnings
        return data


def memory_limits() -> MemoryLimits:
    return MemoryLimits(soft=MEMORY_SOFT_LIMIT, hard=MEMORY_HARD_LIMIT)


def _normalize_scope(scope: MemoryScope | str) -> MemoryScope:
    return scope if isinstance(scope, MemoryScope) else MemoryScope(scope)


def _normalize_user_id(target_id: str | UUID) -> UUID:
    return UUID(target_id) if isinstance(target_id, str) else target_id


async def _load_user_display_name(user_id: UUID, session: AsyncSession) -> str | None:
    result = await session.execute(select(User.display_name).where(User.id == user_id))
    return result.scalar_one_or_none()


async def read_memory(
    *,
    scope: MemoryScope | str,
    target_id: str | int | UUID,
    session: AsyncSession,
) -> str:
    """Read memory markdown for a user or team."""
    normalized = _normalize_scope(scope)
    if normalized is MemoryScope.USER:
        user_id = _normalize_user_id(target_id)
        # User-scoped memories have workspace_id=NULL and client_id=NULL; the
        # helper writes None as an empty string and the RLS NULLIF wrapper
        # treats it as SQL NULL.
        await set_request_tenant_context(session, workspace_id=None, client_id=None)
        result = await session.execute(
            select(Memory).where(
                Memory.workspace_id.is_(None),
                Memory.created_by_id == user_id,
                Memory.client_id.is_(None),
            )
        )
        memories = result.scalars().all()
        return render_memory_markdown(list(memories), scope="user")

    workspace_id = int(target_id)
    await set_request_tenant_context(session, workspace_id=workspace_id, client_id=None)
    result = await session.execute(
        select(Memory).where(
            Memory.workspace_id == workspace_id,
            Memory.client_id.is_(None),
        )
    )
    memories = result.scalars().all()
    return render_memory_markdown(list(memories), scope="team")


async def save_memory(
    *,
    scope: MemoryScope | str,
    target_id: str | int | UUID,
    content: str,
    session: AsyncSession,
    llm: Any | None = None,
    created_by_id: UUID | None = None,
) -> SaveResult:
    """Save markdown memory by parsing it into structured ``Memory`` rows."""
    normalized = _normalize_scope(scope)
    if not isinstance(content, str):
        return SaveResult(
            status="error",
            message="Internal error: memory payload must be a string.",
        )

    next_content = strip_preamble_to_first_heading(content.strip())
    notice: str | None = None
    warnings: list[str] = []

    if next_content.upper() in _NO_UPDATE_SENTINELS:
        old_memory = await read_memory(
            scope=normalized, target_id=target_id, session=session
        )
        return SaveResult(
            status="no_op",
            message="No memory update requested.",
            memory_md=old_memory,
        )

    if len(next_content) > MEMORY_HARD_LIMIT and llm is not None:
        rewritten = await forced_rewrite(next_content, llm)
        if rewritten is not None and len(rewritten) < len(next_content):
            next_content = strip_preamble_to_first_heading(rewritten)
            notice = "Memory was automatically rewritten to fit within limits."

    for validation in (
        validate_memory_size(next_content),
        validate_heading_sanity(next_content),
    ):
        if validation:
            return SaveResult(
                status="error",
                message=validation["message"],
                memory_md=await read_memory(
                    scope=normalized, target_id=target_id, session=session
                ),
            )

    scope_error, scope_warnings = validate_memory_scope(
        next_content,
        normalized.value,
    )
    warnings.extend(scope_warnings)
    if scope_error:
        return SaveResult(
            status="error",
            message=scope_error["message"],
            memory_md=await read_memory(
                scope=normalized, target_id=target_id, session=session
            ),
            warnings=warnings,
        )

    # Parse and store each fact.
    repo = MemoryRepository(session)
    facts = parse_memory_markdown_to_facts(next_content)

    if normalized is MemoryScope.USER:
        user_id = _normalize_user_id(target_id)
        # AC-18.8: set the tenant GUC before the DELETE so FORCE RLS does not
        # hide the rows we are about to remove.  User-scoped memory uses
        # workspace_id=NULL and client_id=NULL.
        await set_request_tenant_context(session, workspace_id=None, client_id=None)
        # Delete existing user-scoped personal memory facts before rewriting.
        await session.execute(
            delete(Memory).where(
                Memory.workspace_id.is_(None),
                Memory.created_by_id == user_id,
                Memory.client_id.is_(None),
            )
        )
        for fact in facts:
            await repo.create_memory(
                workspace_id=None,
                content=fact.content,
                type=fact.type,
                source_type=fact.source_type,
                tags=fact.tags,
                created_by_id=user_id,
            )
    else:
        workspace_id = int(target_id)
        # AC-18.8: set the tenant GUC before the DELETE so FORCE RLS does not
        # hide the rows we are about to remove.  Team memory is client-less.
        await set_request_tenant_context(
            session, workspace_id=workspace_id, client_id=None
        )
        # Delete existing workspace team memory facts before rewriting.
        await session.execute(
            delete(Memory).where(
                Memory.workspace_id == workspace_id,
                Memory.client_id.is_(None),
            )
        )
        for fact in facts:
            await repo.create_memory(
                workspace_id=workspace_id,
                content=fact.content,
                type=fact.type,
                source_type=fact.source_type,
                tags=fact.tags,
                created_by_id=created_by_id,
            )

    rendered = render_memory_document(parse_memory_document(next_content))
    diff_warnings = validate_diff(
        await read_memory(scope=normalized, target_id=target_id, session=session),
        rendered,
    )
    format_warnings = validate_bullet_format(rendered)
    warning = soft_limit_warning(rendered)
    if warning:
        warnings.append(warning)

    return SaveResult(
        status="saved",
        message=(
            "Memory updated."
            if normalized is MemoryScope.USER
            else "Team memory updated."
        ),
        memory_md=rendered,
        warnings=warnings,
        diff_warnings=diff_warnings,
        format_warnings=format_warnings,
        notice=notice,
    )


async def reset_memory(
    *,
    scope: MemoryScope | str,
    target_id: str | int | UUID,
    session: AsyncSession,
) -> SaveResult:
    """Reset memory by deleting all structured rows for the scope."""
    normalized = _normalize_scope(scope)
    if normalized is MemoryScope.USER:
        user_id = _normalize_user_id(target_id)
        await set_request_tenant_context(session, workspace_id=None, client_id=None)
        await session.execute(
            delete(Memory).where(
                Memory.workspace_id.is_(None),
                Memory.created_by_id == user_id,
                Memory.client_id.is_(None),
            )
        )
    else:
        workspace_id = int(target_id)
        await set_request_tenant_context(
            session, workspace_id=workspace_id, client_id=None
        )
        await session.execute(
            delete(Memory).where(
                Memory.workspace_id == workspace_id,
                Memory.client_id.is_(None),
            )
        )
    await session.commit()
    return SaveResult(
        status="saved",
        message="Memory reset."
        if normalized is MemoryScope.USER
        else "Team memory reset.",
        memory_md="",
    )
