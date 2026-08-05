"""``RunService`` — read-only access to automation run history + manual launch."""

from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.automations.dispatch.errors import DispatchError
from app.automations.dispatch.launch import launch_run
from app.automations.persistence.enums.trigger_type import TriggerType
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.run import AutomationRun
from app.automations.persistence.models.trigger import AutomationTrigger
from app.db import Permission, get_async_session
from app.users import get_auth_context
from app.utils.rbac import check_permission


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

    async def launch(self, *, automation_id: int) -> AutomationRun:
        """Kick off a manual run for an automation, returning the PENDING run.

        Mirrors the Telegram ``_handle_rerun`` pattern: authorize with
        ``AUTOMATIONS_EXECUTE``, build a transient ``MANUAL`` trigger, and
        delegate to ``launch_run`` (resolve + validate + snapshot + enqueue).
        Fire-and-return — the caller does not wait for execution.
        """
        await self._authorize(automation_id, Permission.AUTOMATIONS_EXECUTE.value)
        trigger = AutomationTrigger(
            automation_id=automation_id,
            type=TriggerType.MANUAL,
            params={},
            static_inputs={},
        )
        try:
            return await launch_run(
                session=self.session,
                trigger=trigger,
                runtime_inputs={"fired_by": "mcp"},
            )
        except DispatchError as exc:
            message = str(exc)
            if "not found" in message:
                raise HTTPException(status_code=404, detail=message) from exc
            raise HTTPException(status_code=400, detail=message) from exc

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
