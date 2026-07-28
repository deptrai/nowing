"""AC-5 live freshness harness for Story 3.14.

This module is imported by ``benchmark_memory_story_3_14.py`` and runs only
after the AC-3 latency cells have been seeded, measured, and cleaned.
"""

from __future__ import annotations

import base64
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import config
from app.db import (
    Memory,
    MemorySourceType,
    NewChatMessage,
    NewChatMessageRole,
    NewChatThread,
    ResearchThread,
    User,
    Workspace,
    async_session_maker,
)
from app.routes.workspaces_routes import create_default_roles_and_membership
from app.tasks.celery_tasks.memory_extraction_task import extract_memory_after_chat_turn

_FRESHNESS_USER_TEXT = (
    "Please remember that my favorite programming language is Python "
    "and I work remotely from Da Nang."
)

_FRESHNESS_ASSISTANT_TEXT = (
    "I will remember that your favorite programming language is Python "
    "and you work remotely from Da Nang."
)

_FRESHNESS_TIMEOUT_SECONDS = 120.0
_FRESHNESS_P95_BUDGET_MS = 60_000.0


def has_llm_credentials() -> bool:
    """Best-effort check for at least one LLM API key in the loaded environment."""
    keys = (
        "OPENAI_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "GROQ_API_KEY",
        "GOOGLE_API_KEY",
    )
    if any(bool(os.environ.get(k, "").strip()) for k in keys):
        return True

    b64 = os.environ.get("GLOBAL_LLM_CONFIG_B64", "").strip()
    if not b64:
        return False
    try:
        data = yaml.safe_load(base64.b64decode(b64).decode("utf-8")) or {}
    except Exception:
        return False
    for cfg in data.get("global_llm_configs", []):
        if (cfg.get("api_key") or "").strip():
            return True

    for cfg in config.load_global_llm_configs():
        litellm_params = cfg.get("litellm_params") or {}
        if (litellm_params.get("api_key") or "").strip():
            return True
    return False


async def _make_freshness_identity(session: AsyncSession, run_tag: str) -> dict[str, Any]:
    """Create a dedicated workspace, user, research thread, and chat thread."""
    owner = User(
        id=uuid.uuid4(),
        email=f"{run_tag}@s314-fresh.local",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    workspace = Workspace(name=f"s314-fresh-{run_tag}", user_id=owner.id)
    session.add(owner)
    session.add(workspace)
    await session.flush()
    await create_default_roles_and_membership(session, workspace.id, owner.id)

    research_thread = ResearchThread(
        workspace_id=workspace.id,
        created_by_id=owner.id,
        title=f"s314-fresh-rt-{run_tag}",
    )
    session.add(research_thread)
    await session.flush()

    chat_thread = NewChatThread(
        workspace_id=workspace.id,
        created_by_id=owner.id,
        research_thread_id=research_thread.id,
        title=f"s314-fresh-chat-{run_tag}",
    )
    session.add(chat_thread)
    await session.flush()
    await session.commit()

    return {
        "owner": owner,
        "workspace": workspace,
        "research_thread": research_thread,
        "chat_thread": chat_thread,
    }


async def _make_chat_message(
    session: AsyncSession,
    *,
    thread_id: int,
    author_id: uuid.UUID | None,
    role: NewChatMessageRole,
    text: str,
    turn_id: str,
) -> NewChatMessage:
    message = NewChatMessage(
        thread_id=thread_id,
        author_id=author_id,
        role=role,
        content=[{"type": "text", "text": text}],
        turn_id=turn_id,
    )
    session.add(message)
    await session.flush()
    return message


async def _cleanup_freshness_identity(
    identity: dict[str, Any], assistant_ids: list[int]
) -> dict[str, Any]:
    """Remove all freshness harness rows without affecting the latency cells."""
    audit: dict[str, Any] = {"success": True, "errors": []}
    workspace = identity["workspace"]
    chat_thread = identity["chat_thread"]
    research_thread = identity["research_thread"]
    owner = identity["owner"]

    async with async_session_maker() as session:
        try:
            if assistant_ids:
                await session.execute(
                    delete(Memory).where(
                        Memory.source_type == MemorySourceType.CHAT_MESSAGE,
                        Memory.source_id.in_(assistant_ids),
                    )
                )
            await session.execute(
                delete(Memory).where(Memory.workspace_id == workspace.id)
            )
            await session.execute(
                delete(NewChatMessage).where(NewChatMessage.thread_id == chat_thread.id)
            )
            await session.execute(
                delete(NewChatThread).where(NewChatThread.id == chat_thread.id)
            )
            await session.execute(
                delete(ResearchThread).where(ResearchThread.id == research_thread.id)
            )
            await session.execute(delete(Workspace).where(Workspace.id == workspace.id))
            await session.execute(delete(User).where(User.id == owner.id))
            await session.commit()
        except Exception as exc:
            await session.rollback()
            audit["success"] = False
            audit["errors"].append(str(exc))
            raise
    return audit


async def run_freshness_harness(n: int, run_tag: str) -> tuple[dict[str, Any], bool]:
    """AC-5: measure end-to-end memory extraction freshness via the real Celery task.

    Each sample:
      1. Creates a user + assistant message pair sharing one ``turn_id``.
      2. Records ``t0`` immediately before calling
         ``extract_memory_after_chat_turn.delay``.
      3. Captures the returned ``AsyncResult.id`` (the production seam is unchanged).
      4. Waits for the task to return, recording the latency from ``t0`` to completion.
    """
    import asyncio

    if not has_llm_credentials():
        return (
            {
                "status": "partial",
                "pass": False,
                "reason": "missing_llm_credentials",
                "detail": (
                    "No LLM API keys found in the environment; AC-5's live freshness "
                    "harness requires a real Celery worker performing real LLM-based "
                    "memory extraction."
                ),
                "requested_freshness_samples": n,
            },
            True,
        )

    identity: dict[str, Any] | None = None
    assistant_ids: list[int] = []
    samples: list[dict[str, Any]] = []

    async with async_session_maker() as session:
        identity = await _make_freshness_identity(session, run_tag)
    if identity is None:
        raise RuntimeError("Failed to create freshness identity")

    try:
        for i in range(n):
            turn_id = f"fresh:{run_tag}:{i}"
            async with async_session_maker() as session:
                await _make_chat_message(
                    session,
                    thread_id=identity["chat_thread"].id,
                    author_id=identity["owner"].id,
                    role=NewChatMessageRole.USER,
                    text=_FRESHNESS_USER_TEXT,
                    turn_id=turn_id,
                )
                assistant_msg = await _make_chat_message(
                    session,
                    thread_id=identity["chat_thread"].id,
                    author_id=None,
                    role=NewChatMessageRole.ASSISTANT,
                    text=_FRESHNESS_ASSISTANT_TEXT,
                    turn_id=turn_id,
                )
                assistant_ids.append(assistant_msg.id)
                await session.commit()

            # Production seam: invoke the real Celery task, proxy records t0 and task id.
            t0 = time.perf_counter()
            task = extract_memory_after_chat_turn.delay(assistant_msg.id)
            task_id = task.id
            try:
                # Wait for the Celery worker to finish the extraction attempt.
                await asyncio.to_thread(task.get, timeout=_FRESHNESS_TIMEOUT_SECONDS)

                # AC-5 measures freshness as "memory visible" time, not the task result.
                # The task returns None by design; the durable signal is a Memory row
                # with source_type == CHAT_MESSAGE and source_id == assistant_msg.id.
                memory_ids: list[int] = []
                visible_deadline = time.perf_counter() + 10.0
                while time.perf_counter() < visible_deadline and not memory_ids:
                    async with async_session_maker() as session:
                        result = await session.execute(
                            select(Memory.id).where(
                                Memory.source_type == MemorySourceType.CHAT_MESSAGE,
                                Memory.source_id == assistant_msg.id,
                            )
                        )
                        memory_ids = result.scalars().all()
                    if not memory_ids:
                        await asyncio.sleep(0.05)

                t1 = time.perf_counter()
                latency_ms = (t1 - t0) * 1000.0
                memory_count = len(memory_ids)
                samples.append(
                    {
                        "turn": i,
                        "task_id": task_id,
                        "message_id": assistant_msg.id,
                        "latency_ms": round(latency_ms, 3),
                        "memory_count": memory_count,
                        "success": memory_count > 0,
                    }
                )
            except Exception as exc:
                t1 = time.perf_counter()
                latency_ms = (t1 - t0) * 1000.0
                samples.append(
                    {
                        "turn": i,
                        "task_id": task_id,
                        "message_id": assistant_msg.id,
                        "latency_ms": round(latency_ms, 3),
                        "memory_count": 0,
                        "success": False,
                        "error": str(exc),
                    }
                )

        successful_latencies = [s["latency_ms"] for s in samples if s["success"]]
        all_succeeded = len(successful_latencies) == n

        if successful_latencies:
            p95 = float(np.percentile(successful_latencies, 95))
            p50 = float(np.percentile(successful_latencies, 50))
            max_ms = max(successful_latencies)
        else:
            p95 = p50 = max_ms = None

        pass_gate = (
            all_succeeded
            and p95 is not None
            and p95 <= _FRESHNESS_P95_BUDGET_MS
        )

        if pass_gate:
            status = "complete"
            reason = None
            detail = f"AC-5 passed: {n}/{n} turns succeeded, p95={p95:.1f}ms <= 60s."
        elif not all_succeeded:
            status = "partial"
            reason = "task_failures"
            detail = (
                f"AC-5 partial: {len(successful_latencies)}/{n} turns succeeded. "
                "At least one Celery/LLM task failed or timed out."
            )
        else:
            status = "partial"
            reason = "p95_exceeded"
            detail = (
                f"AC-5 partial: all {n} turns succeeded but p95={p95:.1f}ms "
                f"exceeds the 60s budget."
            )

        freshness = {
            "status": status,
            "pass": pass_gate,
            "reason": reason,
            "detail": detail,
            "requested_freshness_samples": n,
            "successful_samples": len(successful_latencies),
            "p95_ms": p95,
            "p50_ms": p50,
            "max_ms": max_ms,
            "per_sample": samples,
        }
        return freshness, not pass_gate

    finally:
        if identity is not None:
            await _cleanup_freshness_identity(identity, assistant_ids)
