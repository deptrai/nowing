"""Enrollment creation and scheduling queries for sequence campaigns."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    Lead,
    Sequence,
    SequenceEnrollment,
    SequenceRun,
    SequenceStep,
)
from app.services.sequencer.scheduling import calculate_step_eta

logger = logging.getLogger(__name__)


class SequencerEnrollmentMixin:
    """Create and query sequence enrollments, and execute their scheduled steps."""

    # AD-25 / AD-49: lead consent statuses that allow outbound communication
    ENROLLABLE_CONSENT_STATUSES = {"granted", "confirmed", "opted_in"}

    async def enroll_leads(
        self,
        session: AsyncSession,
        workspace_id: int,
        sequence_id: UUID,
        lead_ids: list[UUID],
        *,
        triggered_by_alert_rule_id: UUID | None = None,
        user_id: UUID | None = None,
    ) -> list[SequenceEnrollment]:
        """Enroll multiple leads into a sequence, creating a SequenceRun if needed."""
        sequence = (
            await session.execute(
                select(Sequence).where(
                    Sequence.id == sequence_id,
                    Sequence.workspace_id == workspace_id,
                    Sequence.status == "active",
                )
            )
        ).scalar_one_or_none()
        if not sequence:
            raise ValueError(
                f"Active sequence {sequence_id} not found in workspace {workspace_id}"
            )

        run = SequenceRun(
            workspace_id=workspace_id,
            client_id=sequence.client_id,
            sequence_id=sequence_id,
            triggering_alert_rule_id=triggered_by_alert_rule_id,
            status="running",
        )
        session.add(run)
        await session.flush()

        enrollments: list[SequenceEnrollment] = []
        for lead_id in lead_ids:
            lead = await session.get(Lead, lead_id)
            if not lead:
                continue
            enr = await self.enroll_lead(
                session=session,
                workspace_id=workspace_id,
                sequence_id=sequence_id,
                lead=lead,
                triggering_alert_rule_id=triggered_by_alert_rule_id,
                sequence_run_id=run.id,
            )
            if enr:
                enrollments.append(enr)

        return enrollments

    async def enroll_lead(
        self,
        session: AsyncSession,
        workspace_id: int,
        sequence_id: UUID,
        lead: Lead | UUID,
        *,
        triggering_alert_rule_id: UUID | None = None,
        sequence_run_id: UUID | None = None,
        client_id: str | None = None,
    ) -> tuple[SequenceRun, SequenceEnrollment] | SequenceEnrollment | None:
        """Enroll a single lead into a sequence after verifying consent (AC-4 / AD-25 / AD-49)."""
        if isinstance(lead, (UUID, str)):
            lead_obj = (
                await session.execute(
                    select(Lead).where(
                        Lead.id == lead, Lead.workspace_id == workspace_id
                    )
                )
            ).scalar_one_or_none()
        else:
            lead_obj = lead

        if not lead_obj:
            logger.warning(
                "Enrollment rejected: Lead %s not found in workspace %s",
                lead,
                workspace_id,
            )
            return None

        if lead_obj.workspace_id != workspace_id:
            logger.warning(
                "Enrollment rejected: Lead %s workspace mismatch", lead_obj.id
            )
            return None

        # AC-4: Consent & Legal Basis gate
        if (
            lead_obj.consent_status not in self.ENROLLABLE_CONSENT_STATUSES
            or not lead_obj.legal_basis
        ):
            logger.info(
                "Rejecting enrollment: Lead %s lacks consent (%s) or legal basis",
                lead_obj.id,
                lead_obj.consent_status,
            )
            return None

        # Check existing active enrollment
        existing = (
            await session.execute(
                select(SequenceEnrollment).where(
                    SequenceEnrollment.sequence_id == sequence_id,
                    SequenceEnrollment.lead_id == lead_obj.id,
                    SequenceEnrollment.workspace_id == workspace_id,
                    SequenceEnrollment.status.in_(["scheduled", "executing", "paused"]),
                )
            )
        ).scalar_one_or_none()
        if existing:
            return existing

        # Create run if not provided and alert rule triggered
        created_run: SequenceRun | None = None
        if not sequence_run_id:
            created_run = SequenceRun(
                workspace_id=workspace_id,
                client_id=lead_obj.client_id or client_id,
                sequence_id=sequence_id,
                triggering_alert_rule_id=triggering_alert_rule_id,
                status="running",
            )
            session.add(created_run)
            await session.flush()
            sequence_run_id = created_run.id

        # Calculate initial scheduled_at
        initial_eta = calculate_step_eta(delay_seconds=0)

        enrollment = SequenceEnrollment(
            workspace_id=workspace_id,
            client_id=lead_obj.client_id or client_id,
            sequence_id=sequence_id,
            lead_id=lead_obj.id,
            sequence_run_id=sequence_run_id,
            current_step=1,
            status="scheduled",
            scheduled_at=initial_eta,
            version=0,
        )
        session.add(enrollment)
        await session.flush()

        if created_run:
            return (created_run, enrollment)
        return enrollment

    async def get_due_enrollments(
        self,
        session: AsyncSession,
        workspace_id: int | None = None,
    ) -> list[SequenceEnrollment]:
        """Query enrollments due for execution, scoped to a workspace if provided."""
        now_dt = datetime.now(UTC)
        filters = [
            SequenceEnrollment.status == "scheduled",
            SequenceEnrollment.scheduled_at <= now_dt,
        ]
        if workspace_id is not None:
            filters.append(SequenceEnrollment.workspace_id == workspace_id)
        stmt = select(SequenceEnrollment).where(*filters)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def evaluate_pending_enrollments(self, session: AsyncSession) -> int:
        """Celery Beat worker dispatcher: query due enrollments and enqueue tasks (AC-3)."""
        now_dt = datetime.now(UTC)
        workspace_stmt = (
            select(SequenceEnrollment.workspace_id)
            .where(
                SequenceEnrollment.status == "scheduled",
                SequenceEnrollment.scheduled_at <= now_dt,
            )
            .distinct()
        )
        workspace_result = await session.execute(workspace_stmt)
        workspace_ids = list(workspace_result.scalars().all())

        dispatched_count = 0
        for ws_id in workspace_ids:
            due_enrollments = await self.get_due_enrollments(
                session, workspace_id=ws_id
            )
            for enrollment in due_enrollments:
                try:
                    from app.automations.tasks.sequence_tasks import (
                        execute_sequence_step,
                    )

                    execute_sequence_step.delay(
                        enrollment_id=str(enrollment.id),
                        workspace_id=ws_id,
                    )
                    dispatched_count += 1
                except Exception:
                    logger.exception(
                        "Failed to dispatch Celery task for enrollment %s",
                        enrollment.id,
                    )

        return dispatched_count

    async def execute_enrollment_step(
        self,
        session: AsyncSession,
        enrollment_id: UUID,
        workspace_id: int,
    ) -> Any:
        """Execute the current step for an enrollment under Redis distributed lock (AC-5, AC-6)."""
        from app.redis_client import get_redis_client
        from app.tenant_context import set_request_tenant_context

        redis_client = await get_redis_client()
        lock_key = f"sequence:lock:enrollment:{workspace_id}:{enrollment_id}"

        async with redis_client.lock(
            lock_key, timeout=10.0, blocking=True, blocking_timeout=3.0
        ):
            # Fetch enrollment with fresh data. Celery worker must bypass RLS for the initial
            # read because client_id is not known until the row is loaded.
            enrollment = (
                await session.execute(
                    select(SequenceEnrollment).where(
                        SequenceEnrollment.id == enrollment_id,
                        SequenceEnrollment.workspace_id == workspace_id,
                    )
                )
            ).scalar_one_or_none()

            if enrollment:
                await set_request_tenant_context(
                    session,
                    workspace_id=workspace_id,
                    client_id=enrollment.client_id,
                )

            if not enrollment or enrollment.status not in ("scheduled", "executing"):
                logger.info(
                    "Enrollment %s not eligible for execution (status=%s)",
                    enrollment_id,
                    getattr(enrollment, "status", None),
                )
                return None

            current_version = enrollment.version

            # CAS transition to executing
            stmt = (
                update(SequenceEnrollment)
                .where(
                    SequenceEnrollment.id == enrollment_id,
                    SequenceEnrollment.workspace_id == workspace_id,
                    SequenceEnrollment.version == current_version,
                )
                .values(
                    status="executing",
                    version=current_version + 1,
                    updated_at=datetime.now(UTC),
                )
            )
            res = await session.execute(stmt)
            if res.rowcount == 0:
                logger.info(
                    "CAS check failed on enrollment %s; skipping concurrent execution",
                    enrollment_id,
                )
                return None

            enrollment.version = current_version + 1
            enrollment.status = "executing"

            # Load sequence and current step
            sequence = await session.get(
                Sequence, (enrollment.sequence_id, workspace_id)
            )
            if not sequence or sequence.status != "active":
                enrollment.status = "paused"
                await session.commit()
                return None

            step = (
                await session.execute(
                    select(SequenceStep).where(
                        SequenceStep.sequence_id == enrollment.sequence_id,
                        SequenceStep.workspace_id == workspace_id,
                        SequenceStep.step_order == enrollment.current_step,
                        SequenceStep.is_enabled.is_(True),
                    )
                )
            ).scalar_one_or_none()

            if not step:
                # No more steps -> mark sequence completed
                enrollment.status = "completed"
                enrollment.scheduled_at = None
                enrollment.updated_at = datetime.now(UTC)
                await session.commit()
                return None

            lead = await session.get(Lead, enrollment.lead_id)
            if not lead:
                enrollment.status = "failed"
                await session.commit()
                return None

            # Route by step_type
            if step.step_type in ("send_email", "send_zalo", "send_telegram"):
                return await self._handle_send_step(
                    session, sequence, step, enrollment, lead
                )
            elif step.step_type == "wait":
                return await self._handle_wait_step(session, sequence, step, enrollment)
            elif step.step_type == "condition":
                return await self._handle_condition_step(
                    session, sequence, step, enrollment, lead
                )
            else:
                logger.warning(
                    "Unsupported step type %s; skipping to next step", step.step_type
                )
                await self._advance_to_next_step(session, sequence, step, enrollment)
                await session.commit()
                return None

    async def _handle_wait_step(
        self,
        session: AsyncSession,
        sequence: Sequence,
        step: SequenceStep,
        enrollment: SequenceEnrollment,
    ) -> Any:
        """Handle wait step: calculate delay ETA and advance."""
        delay = step.wait_duration_seconds or 86400  # Default 1 day
        next_eta = calculate_step_eta(delay)

        from app.db import SequenceEvent

        event = SequenceEvent(
            workspace_id=enrollment.workspace_id,
            client_id=enrollment.client_id,
            enrollment_id=enrollment.id,
            sequence_id=sequence.id,
            step_id=step.id,
            event_type="delivered",
            event_subtype="wait_scheduled",
            channel=step.channel,
            cost_micros=0,
        )
        session.add(event)

        await self._advance_to_next_step(
            session, sequence, step, enrollment, next_eta=next_eta
        )
        await session.commit()
        return event

    async def _handle_condition_step(
        self,
        session: AsyncSession,
        sequence: Sequence,
        step: SequenceStep,
        enrollment: SequenceEnrollment,
        lead: Lead,
    ) -> Any:
        """Handle condition branching step."""
        from app.db import SequenceEvent
        from app.services.sequencer.templates import evaluate_condition_step

        context = {
            "has_replied": enrollment.status == "responded",
            "opened": enrollment.status
            in (
                "responded",
                "executing",
            ),  # opened/delivered are not tracked per-event yet
            "delivered": enrollment.status in ("responded", "executing", "scheduled"),
            "lead_status": getattr(lead, "status", ""),
        }
        next_step_order = evaluate_condition_step(step.condition_config or {}, context)

        event = SequenceEvent(
            workspace_id=enrollment.workspace_id,
            client_id=enrollment.client_id,
            enrollment_id=enrollment.id,
            sequence_id=sequence.id,
            step_id=step.id,
            event_type="delivered",
            event_subtype="condition_evaluated",
            channel=step.channel,
            cost_micros=0,
            event_metadata={"next_step_order": next_step_order},
        )
        session.add(event)

        if next_step_order is not None:
            enrollment.current_step = next_step_order
            enrollment.status = "scheduled"
            enrollment.scheduled_at = calculate_step_eta(0)
        else:
            enrollment.status = "completed"
            enrollment.scheduled_at = None

        enrollment.version += 1
        enrollment.updated_at = datetime.now(UTC)
        await session.commit()
        return event

    async def _advance_to_next_step(
        self,
        session: AsyncSession,
        sequence: Sequence,
        current_step: SequenceStep,
        enrollment: SequenceEnrollment,
        next_eta: datetime | None = None,
    ) -> None:
        """Advance enrollment to next step or mark completed."""
        next_step = (
            (
                await session.execute(
                    select(SequenceStep)
                    .where(
                        SequenceStep.sequence_id == sequence.id,
                        SequenceStep.workspace_id == sequence.workspace_id,
                        SequenceStep.step_order > current_step.step_order,
                        SequenceStep.is_enabled.is_(True),
                    )
                    .order_by(SequenceStep.step_order.asc())
                )
            )
            .scalars()
            .first()
        )

        if next_step:
            enrollment.current_step = next_step.step_order
            enrollment.status = "scheduled"
            delay = (
                next_step.wait_duration_seconds or 0
                if next_step.step_type == "wait"
                else 0
            )
            enrollment.scheduled_at = next_eta or calculate_step_eta(delay)
        else:
            enrollment.status = "completed"
            enrollment.scheduled_at = None

        enrollment.version += 1
        enrollment.last_event_at = datetime.now(UTC)
        enrollment.updated_at = datetime.now(UTC)
