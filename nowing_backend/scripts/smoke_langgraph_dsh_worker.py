"""Local smoke test for the dsh-worker executor.

This script runs real missions through the actual Redis Stream + PostgreSQL
path, but bypasses the HTTP sidecar contract by injecting a fake DshRestClient.
It is intended as a quick local integration smoke, not a full end-to-end with
the FastAPI gateway. The executor is controlled by `DSH_EXECUTOR_ENGINE`.

Usage:
    cd nowing_backend
    DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5434/nowing \
    REDIS_APP_URL=redis://localhost:6380/0 \
    DSH_EXECUTOR_ENGINE=langgraph \
    SMOKE_MISSION_COUNT=10 \
    uv run --active python scripts/smoke_langgraph_dsh_worker.py
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sys
import time
import uuid
from datetime import datetime
from typing import Any

# Ensure repo root is importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from redis.asyncio.client import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    DshMission,
    DshMissionStatus,
    User,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
    async_session_maker,
)
from app.schemas.users import UserCreate
from app.services.dsh_mission_service import DshMissionService
from app.tasks.dsh_worker import DshWorker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class _SmokeDshRestClient:
    """A DshRestClient that talks to the DB/services directly, not HTTP."""

    def __init__(self, session: AsyncSession, chainlens_delay: float = 0.0) -> None:
        self.session = session
        self.chainlens_delay = chainlens_delay
        self._crawl_count = 0

    @staticmethod
    def _mission_to_dict(mission: DshMission) -> dict[str, Any]:
        return {
            "id": str(mission.id),
            "workspace_id": mission.workspace_id,
            "user_id": str(mission.user_id) if mission.user_id else None,
            "mission_type": mission.mission_type,
            "status": mission.status,
            "phase": mission.phase,
            "progress_percent": mission.progress_percent,
            "current_subtask_id": mission.current_subtask_id,
            "retry_count": mission.retry_count,
            "payload": mission.payload or {},
            "checkpoint": mission.checkpoint or {},
            "error": mission.error,
            "started_at": mission.started_at.isoformat() if mission.started_at else None,
            "completed_at": mission.completed_at.isoformat() if mission.completed_at else None,
        }

    async def get_mission(self, mission_id: uuid.UUID) -> dict[str, Any]:
        svc = DshMissionService()
        mission = await svc.get_mission_or_404(self.session, mission_id)
        return self._mission_to_dict(mission)

    async def patch_checkpoint(self, mission_id: uuid.UUID, update: dict[str, Any]) -> dict[str, Any]:
        svc = DshMissionService()
        mission = await svc.get_mission_or_404(self.session, mission_id)
        mission = await svc.update_checkpoint(
            self.session,
            mission,
            checkpoint=update.get("checkpoint"),
            phase=update.get("phase"),
            progress_percent=update.get("progress_percent"),
            current_subtask_id=update.get("current_subtask_id"),
            status=update.get("status"),
            error=update.get("error"),
            completed_at=datetime.fromisoformat(update["completed_at"])
            if update.get("completed_at")
            else None,
        )
        await self.session.commit()
        return self._mission_to_dict(mission)

    async def chainlens_research(self, workspace_id: int, query: str) -> dict[str, Any]:
        self._crawl_count += 1
        if self.chainlens_delay and self._crawl_count == 1:
            logger.info(
                "Smoke: chainlens_research hanging for %.1fs (mission %s)",
                self.chainlens_delay,
                workspace_id,
            )
            await asyncio.sleep(self.chainlens_delay)
        logger.info("Smoke: chainlens_research called for workspace %s", workspace_id)
        return {
            "run_id": f"smoke-run-{uuid.uuid4().hex[:8]}",
            "sources": [
                {
                    "url": "https://smoke.example/acme",
                    "domain": "smoke.example",
                    "company_name": "Acme Smoke",
                    "phone": "+84-123-456-789",
                    "email": "hello@smoke.example",
                    "title": "AI Company",
                    "industry": "AI",
                    "location": "TP HCM",
                    "fit_score": 92.0,
                    "intent_score": 80.0,
                    "composite_score": 88.0,
                },
                {
                    "url": "https://smoke2.example/beta",
                    "domain": "smoke2.example",
                    "company_name": "Beta Smoke",
                    "phone": None,
                    "email": "contact@smoke2.example",
                    "fit_score": 75.0,
                },
            ],
        }

    async def batch_ingest_leads(
        self, workspace_id: int, leads: list[dict[str, Any]]
    ) -> dict[str, Any]:
        logger.info("Smoke: batch_ingest_leads called with %d leads", len(leads))
        mapping: dict[str, str] = {}
        for i, lead in enumerate(leads):
            company = lead.get("company_name") or "Company"
            domain = lead.get("domain") or f"domain-{i}"
            mapping[f"{company}:{domain}"] = str(uuid.uuid4())
        return {"ingested": len(leads), "lead_id_mapping": mapping}

    async def notify_high_fit_lead(
        self, mission_id: uuid.UUID, lead_id: Any, contact_id: Any = None
    ) -> dict[str, Any]:
        logger.info("Smoke: notify_high_fit_lead called for lead %s", lead_id)
        return {"status": "skipped"}

    async def aclose(self) -> None:
        pass


async def _get_or_create_workspace_and_user(session: AsyncSession) -> tuple[uuid.UUID, int]:
    # Look for an existing smoke user.
    result = await session.execute(select(User).where(User.email == "smoke-dsh@example.com"))
    user = result.scalar_one_or_none()

    if user is None:
        from fastapi_users.db import SQLAlchemyUserDatabase

        from app.users import UserManager

        user_db = SQLAlchemyUserDatabase(session, User)
        user_manager = UserManager(user_db)
        user = await user_manager.create(
            UserCreate(email="smoke-dsh@example.com", password="smoke-password-123")
        )
        await session.flush()

    result = await session.execute(select(Workspace).where(Workspace.user_id == user.id))
    workspace = result.scalar_one_or_none()

    if workspace is None:
        workspace = Workspace(
            name="smoke-dsh-workspace",
            description="Temporary workspace for dsh-worker smoke test",
            user_id=user.id,
        )
        session.add(workspace)
        await session.flush()

    result = await session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.user_id == user.id,
                WorkspaceMembership.workspace_id == workspace.id,
            )
        )
    membership = result.scalar_one_or_none()

    if membership is None:
        # Get the default member role.
        result = await session.execute(select(WorkspaceRole).where(WorkspaceRole.name == "member"))
        role = result.scalar_one_or_none()
        if role is None:
            role = WorkspaceRole(name="member", description="Member")
            session.add(role)
            await session.flush()

        membership = WorkspaceMembership(
            user_id=user.id,
            workspace_id=workspace.id,
            workspace_role_id=role.id,
        )
        session.add(membership)
        await session.flush()

    await session.commit()
    return user.id, workspace.id


async def _prepare_mission(
    session: AsyncSession, user_id: uuid.UUID, workspace_id: int
) -> uuid.UUID:
    service = DshMissionService()
    mission = await service.create_mission(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        mission_type="deep_lead_research",
        payload={"query": "Công ty AI tại TP HCM", "workspace_id": workspace_id},
    )
    await session.commit()
    return mission.id


async def _run_worker_once(mission_id: uuid.UUID) -> None:
    from app.redis_client import get_redis_client

    redis_client = await get_redis_client()
    stream = os.environ.get("DSH_STREAM_TASKS", "nowing:dsh:tasks")
    try:
        async with async_session_maker() as session:
            rest_client = _SmokeDshRestClient(session)
            worker = DshWorker(
                redis_client=redis_client,
                rest_client=rest_client,
            )
            # Manually process one cycle via XREADGROUP.
            # This is a minimal smoke, not the production loop.
            worker._running = True
            await worker._ensure_consumer_group(redis_client)

            # Push the mission after the consumer group is created so `>` reads it.
            await redis_client.xadd(stream, {"mission_id": str(mission_id), "attempt": "1"})
            logger.info("Pushed mission %s to Redis stream %s", mission_id, stream)

            for _attempt in range(20):
                messages = await worker._read_new_messages(redis_client)

                if not messages:
                    await asyncio.sleep(0.5)
                    continue

                for msg_id, fields in messages:
                    should_ack = await worker._handle_message(redis_client, msg_id, fields)
                    if should_ack:
                        await redis_client.xack(
                            worker.stream, worker.group, msg_id
                        )
                    logger.info("Processed message %s; should_ack=%s", msg_id, should_ack)
                    return
            raise RuntimeError("Worker did not pick up the mission from Redis")
    finally:
        await redis_client.aclose()


async def _verify_mission(session: AsyncSession, mission_id: uuid.UUID) -> DshMission:
    service = DshMissionService()
    mission = await service.get_mission_or_404(session, mission_id)
    return mission


async def _run_single_mission(
    stream: str, group: str, user_id: uuid.UUID, workspace_id: int, index: int
) -> tuple[float, bool]:
    start = time.perf_counter()
    async with async_session_maker() as session:
        mission_id = await _prepare_mission(session, user_id, workspace_id)
    logger.info("Smoke mission %s created: %s (workspace %s)", index, mission_id, workspace_id)

    os.environ.setdefault("DSH_EXECUTOR_ENGINE", "langgraph")
    await _run_worker_once(mission_id)

    async with async_session_maker() as session:
        mission = await _verify_mission(session, mission_id)

    elapsed = time.perf_counter() - start
    ok = mission.status == DshMissionStatus.SUCCESS.value and mission.phase == "terminal"
    logger.info(
        "Mission %s: status=%s phase=%s progress=%s%% elapsed=%.2fs",
        index,
        mission.status,
        mission.phase,
        mission.progress_percent,
        elapsed,
    )
    return elapsed, ok


async def _get_mission_status(mission_id: uuid.UUID) -> DshMission:
    async with async_session_maker() as session:
        return await _verify_mission(session, mission_id)


async def _poll_mission_at_phase(mission_id: uuid.UUID, timeout: float = 10.0) -> DshMission:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        mission = await _get_mission_status(mission_id)
        if (
            mission.status == DshMissionStatus.RUNNING.value
            and mission.phase == "crawl"
            and mission.progress_percent == 10
        ):
            return mission
        await asyncio.sleep(0.2)
    raise TimeoutError(f"Mission {mission_id} did not reach phase=crawl progress=10")


async def _run_worker_until_crawl(
    mission_id: uuid.UUID, stream: str, chainlens_delay: float
) -> tuple[asyncio.Task, Redis]:
    from app.redis_client import get_redis_client

    redis_client = await get_redis_client()

    async def _loop() -> None:
        async with async_session_maker() as session:
            rest_client = _SmokeDshRestClient(session, chainlens_delay)
            worker = DshWorker(
                redis_client=redis_client,
                rest_client=rest_client,
            )
            worker._running = True
            await worker._ensure_consumer_group(redis_client)

            await redis_client.xadd(stream, {"mission_id": str(mission_id), "attempt": "1"})
            logger.info("Pushed mission %s to %s", mission_id, stream)

            for _ in range(40):
                messages = await worker._read_new_messages(redis_client)
                if not messages:
                    await asyncio.sleep(0.5)
                    continue
                for msg_id, fields in messages:
                    should_ack = await worker._handle_message(redis_client, msg_id, fields)
                    if should_ack:
                        await redis_client.xack(worker.stream, worker.group, msg_id)
                    logger.info("Processed message %s; should_ack=%s", msg_id, should_ack)
                    return
            raise RuntimeError("Worker did not pick up the mission from Redis")

    worker_task = asyncio.create_task(_loop())
    return worker_task, redis_client


async def _resume_mission(mission_id: uuid.UUID, stream: str, group: str) -> bool:
    from app.redis_client import get_redis_client

    redis_client = await get_redis_client()
    try:
        async with async_session_maker() as session:
            rest_client = _SmokeDshRestClient(session, chainlens_delay=0.0)
            worker = DshWorker(
                redis_client=redis_client,
                rest_client=rest_client,
            )
            worker.consumer_name = f"resume-{uuid.uuid4().hex[:8]}"
            worker._running = True
            await worker._ensure_consumer_group(redis_client)

            logger.info("Resuming mission %s via XAUTOCLAIM", mission_id)
            reclaimed = await worker._autoclaim(redis_client)
            logger.info("Reclaimed %s message(s)", len(reclaimed))

            for msg_id, fields in reclaimed:
                parsed = worker._parse_payload(fields)
                if str(parsed.get("mission_id")) != str(mission_id):
                    continue
                should_ack = await worker._handle_message(redis_client, msg_id, fields)
                if should_ack:
                    await redis_client.xack(worker.stream, worker.group, msg_id)
                    logger.info("Resumed mission %s completed", mission_id)
                    return True
            return False
    finally:
        await redis_client.aclose()


async def _run_crash_resume(stream: str, group: str) -> int:
    chainlens_delay = float(os.environ.get("SMOKE_CHAINLENS_DELAY", "2"))

    async with async_session_maker() as session:
        user_id, workspace_id = await _get_or_create_workspace_and_user(session)
        mission_id = await _prepare_mission(session, user_id, workspace_id)
    logger.info("Crash-resume mission created: %s", mission_id)

    from app.redis_client import get_redis_client

    redis_client = await get_redis_client()
    try:
        with contextlib.suppress(Exception):
            await redis_client.xgroup_destroy(stream, group)
        await redis_client.delete(stream)
    finally:
        await redis_client.aclose()

    os.environ.setdefault("DSH_EXECUTOR_ENGINE", "langgraph")
    worker_task, worker_redis = await _run_worker_until_crawl(mission_id, stream, chainlens_delay)
    try:
        logger.info("Waiting for mission to reach phase=crawl progress=10")
        await _poll_mission_at_phase(mission_id, timeout=10)
        logger.info("Killing first worker mid-crawl to simulate crash")
        worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker_task
    except Exception as exc:
        logger.exception("First worker failed: %s", exc)
        worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker_task
        raise
    finally:
        await worker_redis.aclose()

    await asyncio.sleep(1.5)

    redis_client = await get_redis_client()
    try:
        lock_key = DshWorker(redis_client=redis_client)._lock_key(mission_id)
        await redis_client.delete(lock_key)
    finally:
        await redis_client.aclose()

    resumed = await _resume_mission(mission_id, stream, group)
    if not resumed:
        logger.error("Crash resumption FAILED: no message reclaimed")
        return 1

    async with async_session_maker() as session:
        mission = await _verify_mission(session, mission_id)

    logger.info("Mission status: %s", mission.status)
    logger.info("Mission phase: %s", mission.phase)
    logger.info("Mission progress: %s%%", mission.progress_percent)

    if mission.status != DshMissionStatus.SUCCESS.value or mission.phase != "terminal":
        logger.error("Crash resumption FAILED: mission did not reach success/terminal")
        return 1

    logger.info("Crash resumption PASSED: mission completed after worker crash")
    return 0


async def main() -> int:
    stream = os.environ.get("DSH_STREAM_TASKS", "nowing:dsh:tasks")
    group = os.environ.get("DSH_CONSUMER_GROUP", "dsh_workers")

    if os.environ.get("SMOKE_CRASH_RESUME", "").lower() in ("1", "true"):
        return await _run_crash_resume(stream, group)

    count = int(os.environ.get("SMOKE_MISSION_COUNT", "1"))

    async with async_session_maker() as session:
        user_id, workspace_id = await _get_or_create_workspace_and_user(session)

    from app.redis_client import get_redis_client

    redis_client = await get_redis_client()
    try:
        with contextlib.suppress(Exception):
            await redis_client.xgroup_destroy(stream, group)
        await redis_client.delete(stream)
    finally:
        await redis_client.aclose()

    from app.config import config

    logger.info(
        "Running %s sequential DSH missions with %s executor",
        count,
        config.DSH_EXECUTOR_ENGINE,
    )
    overall_start = time.perf_counter()
    times: list[float] = []
    passed = 0
    failed = 0

    for i in range(1, count + 1):
        elapsed, ok = await _run_single_mission(stream, group, user_id, workspace_id, i)
        times.append(elapsed)
        if ok:
            passed += 1
        else:
            failed += 1
            logger.error("Mission %s FAILED", i)

    total = time.perf_counter() - overall_start
    avg = sum(times) / len(times) if times else 0
    p95 = sorted(times)[int(len(times) * 0.95)] if times else 0

    logger.info("=" * 60)
    logger.info("DSH %s batch smoke complete", config.DSH_EXECUTOR_ENGINE)
    logger.info("Total: %s | Passed: %s | Failed: %s", count, passed, failed)
    logger.info("Total wall time: %.2fs", total)
    logger.info("Average mission time: %.2fs", avg)
    logger.info("P95 mission time: %.2fs", p95)
    logger.info("=" * 60)

    if failed:
        logger.error("Batch smoke FAILED: %s of %s missions did not reach success/terminal", failed, count)
        return 1

    logger.info(
        "%s batch smoke PASSED: all %s missions completed end-to-end",
        config.DSH_EXECUTOR_ENGINE,
        count,
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))