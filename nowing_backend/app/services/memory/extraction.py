"""Extract durable memories from chat turns using the workspace chat model."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.canonical.tenant_context import set_request_tenant_context
from app.config import config
from app.db import (
    Memory,
    MemorySourceType,
    NewChatMessage,
    NewChatMessageRole,
    NewChatThread,
    Workspace,
)
from app.services.llm_service import get_agent_llm
from app.services.memory.extract_budget import (
    REASON_DISABLED,
    check_extract_allowed,
    record_extraction,
)
from app.services.memory.pipeline import (
    CHAT_EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_LLM_TIMEOUT_SECONDS,
    ExtractedFact,
    ExtractionContextWindowError,
    MemoryExtractionResult,
    invoke_extraction_llm,
    parse_llm_output,
    resolve_memory_type,
    select_qualifying_facts,
)
from app.services.memory.repository import MemoryRepository
from app.services.token_tracking_service import record_token_usage, scoped_turn
from app.utils.content_utils import extract_text_content

logger = logging.getLogger(__name__)


# Re-exported for backward compatibility: these names were public-by-use before
# the shared pipeline existed (Story 3.13, D3). The definitions now live in
# ``pipeline.py`` so the chat and run paths cannot drift on policy.
__all__ = [
    "ExtractedFact",
    "MemoryExtractionResult",
    "MemoryExtractionService",
]

_EXTRACTION_LLM_TIMEOUT_SECONDS = EXTRACTION_LLM_TIMEOUT_SECONDS

_EXTRACTION_SYSTEM_PROMPT = CHAT_EXTRACTION_SYSTEM_PROMPT


class MemoryExtractionService:
    """Turn a single assistant turn into durable memory rows."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        workspace_id: int | None = None,
        user_id: Any | None = None,
        client_id: str | None = None,
    ) -> None:
        self.session = session
        self.workspace_id = workspace_id
        self.user_id = user_id
        self.client_id = client_id

    # Kept as a static method on the service: the name was public-by-use before
    # the shared pipeline existed. The body now lives in ``pipeline.py`` so the
    # chat and run paths cannot drift on parsing/validation policy (D3).
    _parse_llm_output = staticmethod(parse_llm_output)

    async def extract_from_turn(
        self,
        thread_id: int,
        turn_id: str | None,
        assistant_message_id: int,
    ) -> list[Memory]:
        """Extract and persist memories for a single assistant turn."""
        # Load the assistant message and its thread.
        assistant_message = await self.session.get(NewChatMessage, assistant_message_id)
        if assistant_message is None:
            logger.warning(
                "Assistant message %s not found; skipping extraction",
                assistant_message_id,
            )
            return []

        thread = await self.session.get(NewChatThread, thread_id)
        if thread is None:
            logger.warning("Chat thread %s not found; skipping extraction", thread_id)
            return []

        # Resolve workspace and global auto-extract gate.
        workspace = await self.session.get(Workspace, thread.workspace_id)
        if workspace is None:
            logger.error(
                "Workspace %s not found for thread %s; skipping extraction",
                thread.workspace_id,
                thread_id,
            )
            return []

        if (
            not config.MEMORY_AUTO_EXTRACT_ENABLED
            or not workspace.memory_auto_extract_enabled
        ):
            # AC-8 enumerates `disabled` alongside the four gate reasons, so it
            # emits the same structured line at the same level — a DEBUG message
            # without a machine-parseable `reason=` is invisible to log
            # consumers in the configurations that matter.
            logger.info(
                "memory_extract_skip reason=%s workspace_id=%s",
                REASON_DISABLED,
                workspace.id,
            )
            return []

        # AC-18.8: set the tenant GUCs for this thread before any Memory query
        # so the FORCE RLS policy does not hide rows from the same workspace.
        effective_client_id = self.client_id or thread.client_id
        await set_request_tenant_context(
            self.session,
            workspace_id=workspace.id,
            client_id=effective_client_id,
            agent_id=thread.agent_id,
        )

        # Idempotency guard: extracted memories carry source_id == the assistant
        # message id, so if any already exist this turn was processed before.
        # Skip to avoid duplicate LLM calls, token rows, and version churn on
        # Celery at-least-once redelivery or a double finalize. (A turn that
        # produced no memories can still be retried; that is a cheap, safe no-op.)
        already_extracted = await self.session.execute(
            select(Memory.id)
            .where(
                Memory.source_type == MemorySourceType.CHAT_MESSAGE,
                Memory.source_id == assistant_message_id,
            )
            .limit(1)
        )
        if already_extracted.first() is not None:
            logger.debug(
                "Memory already extracted for assistant message %s; skipping",
                assistant_message_id,
            )
            return []

        # Find the paired user message for this turn.
        stmt = (
            select(NewChatMessage)
            .where(
                NewChatMessage.thread_id == thread_id,
                NewChatMessage.turn_id == turn_id,
                NewChatMessage.role == NewChatMessageRole.USER,
            )
            .order_by(NewChatMessage.created_at, NewChatMessage.id)
        )
        result = await self.session.execute(stmt)
        user_message = result.scalars().first()
        if user_message is None:
            logger.debug("No user message for turn %s; skipping extraction", turn_id)
            return []

        # Resolve the author to attribute memory and token usage.
        created_by_id = user_message.author_id

        # Cost-control gate (Story 8.7 / AR-6 / RS-1): wallet pre-check, spend
        # budget cap, rate-limit, and anonymous-turn skip. Must run before any
        # LLM call — this is the authoritative gate; assistant_finalize.py
        # also consults it as a cheap best-effort fast-path before enqueueing.
        #
        # Pass created_by_id directly (NOT the workspace-owner fallback used
        # below for usage attribution): AC-4 requires a turn with no author to
        # be skipped as anonymous, not silently billed to the workspace owner.
        # If the gate allows, created_by_id is guaranteed not None (the
        # anonymous check would have blocked otherwise).
        gate_result = await check_extract_allowed(
            self.session, workspace=workspace, attributed_user_id=created_by_id
        )
        if not gate_result.allowed:
            return []

        llm = await get_agent_llm(self.session, workspace.id, disable_streaming=True)
        if llm is None:
            logger.warning(
                "No agent LLM for workspace %s; skipping extraction", workspace.id
            )
            return []

        user_text = extract_text_content(user_message.content)
        assistant_text = extract_text_content(assistant_message.content)

        if not user_text.strip() and not assistant_text.strip():
            logger.debug("User and assistant text are both empty; skipping extraction")
            return []

        prompt = (
            f"{_EXTRACTION_SYSTEM_PROMPT}\n\n"
            f"User message:\n{user_text}\n\n"
            f"Assistant response:\n{assistant_text}"
        )

        repo = MemoryRepository(session=self.session)
        created_memories: list[Memory] = []

        async with scoped_turn() as acc:
            try:
                raw_output = await invoke_extraction_llm(llm, prompt)
            except ExtractionContextWindowError:
                # Chat path treats an oversized prompt as a no-op (the turn is
                # simply not worth memorising); the shared helper already logged
                # it. The run path records a durable terminal state instead, which
                # is exactly why the taxonomy lives in the pipeline (D3).
                return []

            for fact in select_qualifying_facts(self._parse_llm_output(raw_output)):
                memory_type = resolve_memory_type(fact.type)

                try:
                    memory = await repo.create_memory(
                        workspace_id=workspace.id,
                        content=fact.content,
                        type=memory_type,
                        source_type=MemorySourceType.CHAT_MESSAGE,
                        source_id=assistant_message_id,
                        tags=fact.tags,
                        confidence=fact.confidence,
                        research_thread_id=thread.research_thread_id,
                        created_by_id=created_by_id,
                        update_on_duplicate=True,
                        commit=False,
                        client_id=effective_client_id,
                        agent_id=thread.agent_id,
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to persist extracted memory (embedding/service error): %s",
                        exc,
                    )
                    continue
                created_memories.append(memory)

        # Record token usage for the extraction LLM call.
        # ponytail: token_usage has a partial unique index on message_id, so
        # reuse the assistant message_id would collide with the chat turn's
        # own usage row. Track extraction cost against the thread instead.
        # `created_by_id` passed the gate's anonymous check above, so it is
        # guaranteed non-None here. No workspace-owner fallback: re-introducing
        # one would silently attribute an authorless turn to the owner, which is
        # exactly the AC-4 mis-attribution the gate exists to prevent.
        await record_token_usage(
            self.session,
            usage_type="memory_create",
            workspace_id=workspace.id,
            user_id=created_by_id,
            thread_id=thread.id,
            prompt_tokens=acc.total_prompt_tokens,
            completion_tokens=acc.total_completion_tokens,
            total_tokens=acc.grand_total,
            cost_micros=acc.total_cost_micros,
            client_id=thread.client_id,
        )

        # Commit the extracted memories (created with commit=False) and the
        # token-usage row together. Because every fact for this turn is written
        # in a single transaction, a mid-loop crash leaves NOTHING committed and
        # redelivery re-extracts cleanly — the idempotency guard is keyed on
        # committed rows, so a partial write can never make it skip real work.
        await self.session.commit()

        # Count the extraction against the rate-limit window only now that the
        # transaction is durable. Incrementing before commit burned slots when
        # the DB transaction rolled back, because the idempotency guard is keyed
        # on committed rows and Celery retries a failed turn. `record_extraction`
        # is a no-op while the rate limit is disabled.
        await record_extraction(workspace.id)

        # AC-1: extracted facts are written with commit=False, so create_memory
        # deferred their ``memory.changed`` events into the repo buffer. Now that
        # the batch is durable, announce each exactly once (best-effort). The
        # buffer already excluded automation-origin writes (loop guard) — moot
        # here since auto-extraction is not reachable from an automation run, but
        # kept consistent. Redelivery re-hits the idempotency guard above and
        # returns [] before this point, so events are emitted exactly once.
        await repo.flush_pending_memory_changed()

        return created_memories
