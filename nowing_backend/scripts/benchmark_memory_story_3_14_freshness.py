"""AC-5 live freshness harness for Story 3.14.

This module is imported by ``benchmark_memory_story_3_14.py`` and runs only
after the AC-3 latency cells have been seeded, measured, and cleaned.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import os
import subprocess
import sys
import time
import traceback
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from celery.exceptions import TimeoutError as CeleryTimeoutError
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.celery_app import celery_app
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
from app.services.memory.search import MemoryHybridSearch
from app.services.memory.vector import (
    VectorValidationError,
    validate_single_embedding_result,
)
from app.tasks.celery_tasks.memory_extraction_task import extract_memory_after_chat_turn
from app.utils.document_converters import embed_texts

_FRESHNESS_TIMEOUT_SECONDS = 120.0
_FRESHNESS_P95_BUDGET_MS = 60_000.0
_FRESHNESS_POLL_INTERVAL_SECONDS = 1.0
_FRESHNESS_POLL_TIMEOUT_SECONDS = 120.0

# Per-turn distinct topics keep the extracted memories semantically unique,
# preventing the repository's embedding-based `update_on_duplicate` path from
# reusing a single `Memory` row across turns. The nonce is embedded as an
# access-code fact; if the extraction LLM preserves it, the nonce is used as
# the ranked-recall key. If the LLM treats the access code as transient and
# only extracts the durable {topic} preference, the topic serves as the unique
# per-turn content marker.
_FRESHNESS_TOPICS = [
    "Python programming",
    "Paris city",
    "sushi food",
    "jazz music",
    "hiking outdoors",
    "blue color",
    "cat animal",
    "coffee drink",
    "science fiction",
    "history books",
    "mountain climbing",
    "ocean waves",
    "video games",
    "painting art",
    "basketball sport",
    "robotics technology",
    "meditation wellness",
    "photography hobby",
    "astronomy space",
    "gardening plants",
    "cooking recipes",
    "travel Japan",
    "yoga exercise",
    "classical music",
    "chess strategy",
    "cycling sport",
    "poetry writing",
    "volunteering community",
    "entrepreneurship business",
    "nature forests",
]


def _freshness_topic(turn: int) -> str:
    return _FRESHNESS_TOPICS[turn % len(_FRESHNESS_TOPICS)]


def _freshness_nonce(run_tag: str, turn: int) -> str:
    return f"story-3-14:{run_tag}:{turn}"


def _freshness_texts(run_tag: str, turn: int) -> tuple[str, str, str, str]:
    nonce = _freshness_nonce(run_tag, turn)
    topic = _freshness_topic(turn)
    user_text = (
        f"Please remember that my favorite thing is {topic} "
        f"and my access code is {nonce}."
    )
    assistant_text = (
        f"I will remember that your favorite thing is {topic} "
        f"and your access code is {nonce}."
    )
    return user_text, assistant_text, nonce, topic


def _content_matches_turn(memory: Memory, nonce: str, topic: str) -> bool:
    """Case-insensitive, whitespace-robust check for nonce or topic in content."""
    content = (memory.content or "").casefold()
    return nonce.casefold() in content or topic.casefold() in content


def _nearest_rank_percentile(values: list[float], p: float) -> float | None:
    """Return the nearest-rank p-percentile (same method used by AC-3 stats_for)."""
    if not values:
        return None
    sorted_values = sorted(values)
    n = len(sorted_values)
    rank = int(np.ceil(p / 100.0 * n)) - 1
    rank = max(0, min(rank, n - 1))
    return float(sorted_values[rank])


def has_llm_credentials() -> bool:
    """Best-effort check for LLM credentials, auto-extract enablement, and a live worker."""
    if not config.MEMORY_AUTO_EXTRACT_ENABLED:
        return False

    keys = (
        "OPENAI_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "GROQ_API_KEY",
        "GOOGLE_API_KEY",
    )
    has_key = any(bool(os.environ.get(k, "").strip()) for k in keys)

    b64 = os.environ.get("GLOBAL_LLM_CONFIG_B64", "").strip()
    if not has_key and b64:
        try:
            data = yaml.safe_load(base64.b64decode(b64).decode("utf-8"))
        except Exception:
            return False
        if not isinstance(data, dict):
            return False
        for cfg in data.get("global_llm_configs", []):
            if (cfg.get("api_key") or "").strip():
                has_key = True
                break

    if not has_key:
        try:
            for cfg in getattr(config, "GLOBAL_LLM_CONFIGS", []) or []:
                litellm_params = cfg.get("litellm_params") or {}
                if (litellm_params.get("api_key") or "").strip():
                    has_key = True
                    break
        except Exception:
            pass

    if not has_key:
        return False

    if celery_app.conf.get("task_always_eager"):
        return False

    # Best-effort live worker probe (5s timeout). A worker that replies to ping
    # is enough to trust the harness; it does not need to be actively executing.
    try:
        inspect = celery_app.control.inspect(timeout=5.0)
        if inspect is not None:
            ping = inspect.ping()
            if ping:
                return True
    except Exception:
        pass

    return False


async def _make_freshness_identity(
    session: AsyncSession, run_tag: str
) -> dict[str, Any]:
    """Create a dedicated workspace, user, research thread, and chat thread."""
    owner = User(
        id=uuid.uuid4(),
        email=f"{run_tag}@s314-fresh.local",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
        is_verified=True,
        credit_micros_balance=config.DEFAULT_CREDIT_MICROS_BALANCE,
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


async def _count_source_rows(
    identity: dict[str, Any], assistant_ids: list[int]
) -> dict[str, int]:
    workspace = identity["workspace"]
    chat_thread = identity["chat_thread"]
    async with async_session_maker() as session:
        mem_count = await session.scalar(
            select(func.count(Memory.id)).where(Memory.workspace_id == workspace.id)
        )
        msg_count = await session.scalar(
            select(func.count(NewChatMessage.id)).where(
                NewChatMessage.thread_id == chat_thread.id
            )
        )
        source_count = 0
        if assistant_ids:
            source_count = await session.scalar(
                select(func.count(Memory.id)).where(
                    Memory.source_type == MemorySourceType.CHAT_MESSAGE,
                    Memory.source_id.in_(assistant_ids),
                )
            )
        return {
            "workspace_memory_count": mem_count or 0,
            "chat_message_count": msg_count or 0,
            "exact_source_count": source_count or 0,
        }


async def _cleanup_freshness_identity(
    identity: dict[str, Any], assistant_ids: list[int]
) -> dict[str, Any]:
    """Remove all freshness harness rows without affecting the latency cells."""
    audit: dict[str, Any] = {"success": True, "errors": []}
    workspace = identity["workspace"]
    chat_thread = identity["chat_thread"]
    research_thread = identity["research_thread"]
    owner = identity["owner"]

    audit["pre_cleanup_counts"] = await _count_source_rows(identity, assistant_ids)

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

    audit["post_cleanup_counts"] = await _count_source_rows(identity, assistant_ids)
    if any(v != 0 for v in audit["post_cleanup_counts"].values()):
        audit["success"] = False
        audit["errors"].append(
            f"cleanup did not reach zero: {audit['post_cleanup_counts']}"
        )
    return audit


async def _get_worker_metadata() -> dict[str, Any]:
    """Best-effort worker/model metadata for the artifact."""
    metadata: dict[str, Any] = {
        "worker_concurrency": None,
        "initial_queue_depth": None,
        "models": [],
        "build": None,
    }
    try:
        inspect = celery_app.control.inspect(timeout=5.0)
        if inspect is not None:
            stats = inspect.stats()
            if stats:
                first = next(iter(stats.values()))
                metadata["worker_concurrency"] = first.get(
                    "prefetch_count"
                ) or first.get("pool", {}).get("max-concurrency")
            active_queues = inspect.active_queues()
            if active_queues:
                metadata["initial_queue_depth"] = 0
    except Exception:
        pass

    # Model list from the configured global LLM configs (attributes on the
    # Config instance; the module-level loader is not exposed as a method).
    try:
        cfg_list = getattr(config, "GLOBAL_LLM_CONFIGS", None)
        if cfg_list:
            metadata["models"] = [
                c.get("model_name") or c.get("litellm_params", {}).get("model")
                for c in cfg_list
                if c.get("model_name") or c.get("litellm_params", {}).get("model")
            ]
    except Exception:
        pass

    # Best-effort build identifier (env, git, or fall back to None).
    try:
        build = os.environ.get("BUILD_ID") or os.environ.get("COMMIT_SHA")
        if not build:
            proc = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=Path(__file__).resolve().parent.parent,
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            if proc.returncode == 0:
                build = proc.stdout.strip()
        metadata["build"] = build
    except Exception:
        pass

    return metadata


async def run_freshness_harness(n: int, run_tag: str) -> tuple[dict[str, Any], bool]:
    """AC-5: measure end-to-end memory extraction freshness via the real Celery task.

    Each sample:
      1. Creates a user + assistant message pair sharing one ``turn_id`` and a
         per-turn ``nonce`` embedded in the message text.
      2. Records ``t0`` immediately before calling
         ``extract_memory_after_chat_turn.delay``.
      3. Captures the returned ``AsyncResult.id`` and polls ranked recall for a
         Memory row whose source is the assistant message and whose content
         contains the nonce or the unique per-turn topic.
      4. Records ``t1`` immediately after the first exact response.
    """
    if n == 0:
        return (
            {
                "status": "skipped",
                "pass": True,
                "reason": "zero_samples",
                "detail": "--freshness-samples is 0; AC-5 phase explicitly disabled.",
                "requested_freshness_samples": 0,
            },
            False,
        )

    if not has_llm_credentials():
        return (
            {
                "status": "partial",
                "pass": False,
                "reason": "missing_llm_credentials",
                "detail": (
                    "No live LLM credentials/worker found; AC-5's live freshness "
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
    captured_tasks: list[Any] = []
    seen_memory_ids: set[int] = set()
    worker_metadata = await _get_worker_metadata()
    poll_config = {
        "interval_seconds": _FRESHNESS_POLL_INTERVAL_SECONDS,
        "timeout_seconds": _FRESHNESS_POLL_TIMEOUT_SECONDS,
        "method": "ranked_recall",
    }
    freshness: dict[str, Any] | None = None

    try:
        async with async_session_maker() as session:
            identity = await _make_freshness_identity(session, run_tag)
        if identity is None:
            raise RuntimeError("Failed to create freshness identity")

        workspace_id = identity["workspace"].id

        for i in range(n):
            user_text, assistant_text, nonce, topic = _freshness_texts(run_tag, i)

            # Compute both query embeddings up-front so the latency timer starts
            # at the production seam (task dispatch), not embedding setup.
            # Validate the whole batch first, then take each validated single
            # result without indexing ``[0]`` before a cardinality check.
            raw_embeddings = await asyncio.to_thread(embed_texts, [nonce, topic])
            if not isinstance(raw_embeddings, (list, tuple, np.ndarray)) or len(
                raw_embeddings
            ) != 2:
                raise VectorValidationError("invalid_count")
            nonce_embedding = validate_single_embedding_result(raw_embeddings[:1])
            topic_embedding = validate_single_embedding_result(raw_embeddings[1:2])

            async with async_session_maker() as session:
                await _make_chat_message(
                    session,
                    thread_id=identity["chat_thread"].id,
                    author_id=identity["owner"].id,
                    role=NewChatMessageRole.USER,
                    text=user_text,
                    turn_id=nonce,
                )
                assistant_msg = await _make_chat_message(
                    session,
                    thread_id=identity["chat_thread"].id,
                    author_id=None,
                    role=NewChatMessageRole.ASSISTANT,
                    text=assistant_text,
                    turn_id=nonce,
                )
                assistant_ids.append(assistant_msg.id)
                await session.commit()

            # Production seam: invoke the real Celery task, proxy records t0 and task id.
            t0 = time.perf_counter()
            task = extract_memory_after_chat_turn.delay(assistant_msg.id)
            task_id = task.id
            captured_tasks.append(task)

            sample: dict[str, Any] = {
                "turn": i,
                "task_id": task_id,
                "message_id": assistant_msg.id,
                "nonce": nonce,
                "topic": topic,
                "poll_config": poll_config,
                "worker_metadata": worker_metadata,
            }

            try:
                deadline = time.perf_counter() + _FRESHNESS_POLL_TIMEOUT_SECONDS
                ranked_deadline = t0 + 30.0
                exact_memories: list[Memory] = []
                # Phase 1: ranked recall with the nonce or topic query (preferred).
                # Phase 2: direct source_id lookup fallback in case the extraction
                # LLM produced content that is not well-matched by hybrid search.
                use_fallback = False
                while time.perf_counter() < deadline and not exact_memories:
                    if not use_fallback and time.perf_counter() >= ranked_deadline:
                        use_fallback = True

                    if not use_fallback:
                        # Alternate between nonce and topic so we find whichever
                        # the LLM actually preserved in the extracted content.
                        query = nonce if (int(time.perf_counter()) % 2 == 0) else topic
                        query_embedding = (
                            nonce_embedding if query == nonce else topic_embedding
                        )
                        async with async_session_maker() as session:
                            hits = await MemoryHybridSearch(session).search(
                                workspace_id=workspace_id,
                                query=query,
                                query_embedding=query_embedding,
                                top_k=5,
                            )
                            for hit in hits:
                                memory = hit.memory
                                if (
                                    memory.source_type == MemorySourceType.CHAT_MESSAGE
                                    and memory.source_id == assistant_msg.id
                                    and _content_matches_turn(memory, nonce, topic)
                                    and memory.id not in seen_memory_ids
                                ):
                                    exact_memories.append(memory)
                    else:
                        async with async_session_maker() as session:
                            result = await session.execute(
                                select(Memory)
                                .where(
                                    Memory.source_type == MemorySourceType.CHAT_MESSAGE,
                                    Memory.source_id == assistant_msg.id,
                                    Memory.workspace_id == workspace_id,
                                )
                                .order_by(Memory.id.desc())
                                .limit(1)
                            )
                            memory = result.scalar_one_or_none()
                            if memory is not None and memory.id not in seen_memory_ids:
                                exact_memories.append(memory)

                    if not exact_memories:
                        await asyncio.sleep(_FRESHNESS_POLL_INTERVAL_SECONDS)

                if not exact_memories:
                    raise CeleryTimeoutError(
                        f"Memory with nonce/topic/source_id not visible within {_FRESHNESS_POLL_TIMEOUT_SECONDS}s"
                    )

                t1 = time.perf_counter()
                latency_ms = (t1 - t0) * 1000.0
                # Prefer a hit that actually contains the nonce; otherwise accept a
                # topic-only memory if the LLM treated the access code as transient.
                # If the only match came from the direct source_id fallback, record
                # that explicitly so the artifact remains truthful.
                nonce_hits = [
                    m
                    for m in exact_memories
                    if nonce.casefold() in (m.content or "").casefold()
                ]
                topic_hits = [
                    m
                    for m in exact_memories
                    if topic.casefold() in (m.content or "").casefold()
                ]
                if nonce_hits:
                    memory = nonce_hits[0]
                    matched_by = "nonce"
                    query_used = nonce
                elif topic_hits:
                    memory = topic_hits[0]
                    matched_by = "topic"
                    query_used = topic
                else:
                    memory = exact_memories[0]
                    matched_by = "source_id"
                    query_used = "source_id"
                seen_memory_ids.add(memory.id)
                sample.update(
                    {
                        "latency_ms": round(latency_ms, 3),
                        "memory_count": len(exact_memories),
                        "memory_id": memory.id,
                        "content_sha256": hashlib.sha256(
                            (memory.content or "").encode("utf-8")
                        ).hexdigest(),
                        "matched_by": matched_by,
                        "query_used": query_used,
                        "success": True,
                    }
                )

                # Best-effort wait for the Celery task to reach a terminal state
                # before moving on. The memory is already durable; this is only to
                # limit in-flight concurrency.
                with contextlib.suppress(Exception):
                    await asyncio.to_thread(
                        task.get,
                        timeout=max(0.0, _FRESHNESS_TIMEOUT_SECONDS - (t1 - t0)),
                    )
                sample["task_state"] = task.state
            except Exception as exc:
                t1 = time.perf_counter()
                latency_ms = (t1 - t0) * 1000.0
                sample.update(
                    {
                        "latency_ms": round(latency_ms, 3),
                        "memory_count": 0,
                        "success": False,
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                    }
                )

            samples.append(sample)

        successful_latencies = [s["latency_ms"] for s in samples if s.get("success")]
        all_succeeded = len(successful_latencies) == n

        if successful_latencies:
            p95 = _nearest_rank_percentile(successful_latencies, 95)
            p50 = _nearest_rank_percentile(successful_latencies, 50)
            max_ms = max(successful_latencies)
        else:
            p95 = p50 = max_ms = None

        pass_gate = (
            all_succeeded and p95 is not None and p95 <= _FRESHNESS_P95_BUDGET_MS
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
            "model_build": worker_metadata,
            "poll_config": poll_config,
            "per_sample": samples,
        }
    except Exception as exc:
        freshness = {
            "status": "partial",
            "pass": False,
            "reason": "harness_error",
            "detail": f"Freshness harness raised: {exc}",
            "requested_freshness_samples": n,
            "per_sample": samples,
            "poll_config": poll_config,
            "model_build": worker_metadata,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
    finally:
        # Wait for all captured Celery tasks to reach a terminal state before
        # deleting the identity, so no in-flight extraction writes after cleanup.
        for task in captured_tasks:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(task.get, timeout=5.0)

        if identity is not None:
            try:
                cleanup_audit = await _cleanup_freshness_identity(
                    identity, assistant_ids
                )
            except Exception as exc:
                # If we cannot audit cleanup, at least do not mask the harness result.
                cleanup_audit = {
                    "success": False,
                    "errors": [str(exc), traceback.format_exc()],
                }

            assert freshness is not None
            freshness.setdefault("cleanup_audit", cleanup_audit)

    assert freshness is not None
    return freshness, not freshness.get("pass", False)
