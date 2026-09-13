"""``RunService`` — read-only access to automation run history + manual launch."""

from __future__ import annotations

import contextlib
import logging

from fastapi import Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.automations.dispatch.errors import DispatchError, DispatchNotFoundError
from app.automations.dispatch.launch import launch_run
from app.automations.persistence.enums.run_status import RunStatus
from app.automations.persistence.enums.trigger_type import TriggerType
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.run import AutomationRun
from app.automations.persistence.models.trigger import AutomationTrigger
from app.db import Permission, get_async_session
from app.users import get_auth_context
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)


class RunService:
    """Access to ``AutomationRun`` history, plus manual (on-demand) launch."""

    def __init__(self, *, session: AsyncSession, auth: AuthContext) -> None:
        self.session = session
        self.auth = auth

    async def list(
        self,
        *,
        automation_id: int,
        limit: int,
        offset: int,
    ) -> tuple[list[AutomationRun], int]:
        """Return a page of runs for an automation, newest first."""
        await self._authorize(automation_id, Permission.AUTOMATIONS_READ.value)

        base = select(AutomationRun).where(AutomationRun.automation_id == automation_id)
        total = await self.session.scalar(
            select(func.count()).select_from(base.subquery())
        )

        rows = (
            (
                await self.session.execute(
                    base.order_by(AutomationRun.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), int(total or 0)

    async def get(self, *, automation_id: int, run_id: int) -> AutomationRun:
        await self._authorize(automation_id, Permission.AUTOMATIONS_READ.value)
        run = await self.session.get(AutomationRun, run_id)
        if run is None or run.automation_id != automation_id:
            raise HTTPException(status_code=404, detail=f"run {run_id} not found")
        return run

    async def launch(
        self, *, automation_id: int, idempotency_key: str | None = None
    ) -> AutomationRun:
        """Kick off a manual run for an automation with dedup & idempotency protection (Story 30.1).

        Mirrors the Telegram ``_handle_rerun`` pattern: authorize with
        ``AUTOMATIONS_EXECUTE``, build a transient ``MANUAL`` trigger, and
        delegate to ``launch_run`` (resolve + validate + snapshot + enqueue).
        Fire-and-return — the caller does not wait for execution.

        If an ``idempotency_key`` is provided, we first check the database for
        an existing run with that key so the replay survives Redis restarts.
        """
        await self._authorize(automation_id, Permission.AUTOMATIONS_EXECUTE.value)

        # Permanent idempotency lookup (survives Redis restarts)
        if idempotency_key:
            existing_stmt = (
                select(AutomationRun)
                .where(
                    AutomationRun.automation_id == automation_id,
                    AutomationRun.idempotency_key == idempotency_key,
                )
                .order_by(AutomationRun.created_at.desc())
                .limit(1)
            )
            existing_res = await self.session.execute(existing_stmt)
            existing_run = existing_res.scalar_one_or_none()
            if existing_run is not None:
                return existing_run

        # Idempotency & Dedup Lock via Redis (Story 30.1)
        redis = None
        lock_key = None
        lock_acquired = True
        ttl = 60 if idempotency_key else 5
        key_suffix = idempotency_key if idempotency_key else "manual"
        lock_key = f"automation_run_lock:{automation_id}:{key_suffix}"

        try:
            from app.redis_client import get_redis_client

            redis = await get_redis_client()
            res = await redis.set(lock_key, "in_flight", nx=True, ex=ttl)
            lock_acquired = bool(res)
        except Exception as exc:  # automation step error; record failure and continue
            logger.warning(
                "Redis dedup lock unavailable for automation %s: %s",
                automation_id,
                exc,
            )
            lock_acquired = True

        if not lock_acquired and redis is not None:
            # Check if an earlier run with this idempotency key already created an AutomationRun
            if idempotency_key:
                with contextlib.suppress(Exception):
                    cached_val = await redis.get(lock_key)
                    if cached_val and str(cached_val).isdigit():
                        cached_run_id = int(cached_val)
                        cached_run = await self.session.get(AutomationRun, cached_run_id)
                        if cached_run is not None:
                            return cached_run

            from datetime import UTC, datetime, timedelta

            window_start = datetime.now(UTC) - timedelta(seconds=ttl)
            stmt = (
                select(AutomationRun)
                .where(
                    AutomationRun.automation_id == automation_id,
                    AutomationRun.status.in_([RunStatus.PENDING, RunStatus.RUNNING]),
                    AutomationRun.created_at >= window_start,
                )
                .order_by(AutomationRun.created_at.desc())
                .limit(1)
            )
            existing_res = await self.session.execute(stmt)
            existing_run = existing_res.scalar_one_or_none()
            if existing_run is not None:
                return existing_run

            raise HTTPException(
                status_code=409,
                detail=f"An execution for automation {automation_id} is already in progress.",
            )

        trigger = AutomationTrigger(
            automation_id=automation_id,
            type=TriggerType.MANUAL,
            params={},
            static_inputs={},
        )
        try:
            run = await launch_run(
                session=self.session,
                trigger=trigger,
                runtime_inputs={"fired_by": "mcp"},
                idempotency_key=idempotency_key,
            )
            if redis is not None and lock_key:
                with contextlib.suppress(Exception):
                    if idempotency_key:
                        await redis.set(lock_key, str(run.id), ex=ttl)
                    else:
                        await redis.delete(lock_key)
            return run
        except DispatchNotFoundError as exc:
            if redis is not None and lock_key:
                with contextlib.suppress(Exception):
                    await redis.delete(lock_key)
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DispatchError as exc:
            if redis is not None and lock_key:
                with contextlib.suppress(Exception):
                    await redis.delete(lock_key)
            message = str(exc)
            status_code = 404 if "not found" in message.lower() else 400
            raise HTTPException(status_code=status_code, detail=message) from exc
        except Exception:  # automation step error; record failure and continue
            if redis is not None and lock_key:
                with contextlib.suppress(Exception):
                    await redis.delete(lock_key)
            raise

    async def _authorize(self, automation_id: int, permission: str) -> Automation:
        automation = await self.session.get(Automation, automation_id)
        if automation is None:
            raise HTTPException(
                status_code=404, detail=f"automation {automation_id} not found"
            )
        await check_permission(
            self.session,
            self.auth,
            automation.workspace_id,
            permission,
            f"You don't have permission to {permission.split(':')[1]} automations in this workspace",
        )
        return automation


def get_run_service(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> RunService:
    return RunService(session=session, auth=auth)
