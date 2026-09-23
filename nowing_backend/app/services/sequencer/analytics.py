"""Sequence analytics aggregation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SequenceEnrollment, SequenceEvent
from app.services.sequencer.constants import ChannelAnalytics, SequenceAnalytics


class SequencerAnalyticsMixin:
    """Compute per-sequence outreach metrics."""

    async def get_sequence_analytics(
        self,
        session: AsyncSession,
        workspace_id: int,
        sequence_id: UUID,
    ) -> SequenceAnalytics:
        """Calculate and return real-time metrics for a sequence (AC-8)."""
        analytics = SequenceAnalytics()

        # Enrollments count
        enr_stmt = select(
            func.count(SequenceEnrollment.id),
            func.count().filter(
                SequenceEnrollment.status.in_(["scheduled", "executing"])
            ),
            func.count().filter(SequenceEnrollment.status == "responded"),
            func.count().filter(SequenceEnrollment.status == "unsubscribed"),
            func.count().filter(SequenceEnrollment.status == "failed"),
        ).where(
            SequenceEnrollment.sequence_id == sequence_id,
            SequenceEnrollment.workspace_id == workspace_id,
        )
        enr_res = (await session.execute(enr_stmt)).first()
        if enr_res:
            analytics.total_enrolled = enr_res[0] or 0
            analytics.active_scheduled = enr_res[1] or 0
            analytics.responded_count = enr_res[2] or 0
            analytics.unsubscribed_count = enr_res[3] or 0
            analytics.failed_count = enr_res[4] or 0

        # Events count and cost
        ev_stmt = select(
            func.count().filter(SequenceEvent.event_type.in_(["delivered", "sent"])),
            func.coalesce(func.sum(SequenceEvent.cost_micros), 0),
        ).where(
            SequenceEvent.sequence_id == sequence_id,
            SequenceEvent.workspace_id == workspace_id,
        )
        ev_res = (await session.execute(ev_stmt)).first()
        if ev_res:
            analytics.delivered_count = ev_res[0] or 0
            analytics.total_cost_micros = ev_res[1] or 0

        # Per-channel breakdown: aggregate raw events in Python for driver safety.
        cb_stmt = select(
            SequenceEvent.channel, SequenceEvent.event_type, SequenceEvent.cost_micros
        ).where(
            SequenceEvent.sequence_id == sequence_id,
            SequenceEvent.workspace_id == workspace_id,
        )
        cb_res = await session.execute(cb_stmt)
        breakdown: dict[str, dict[str, int]] = {}
        for row in cb_res.all():
            channel = row[0] or "email"
            event_type = row[1] or "sent"
            cost = row[2] or 0
            entry = breakdown.setdefault(
                channel,
                {
                    "sent": 0,
                    "delivered": 0,
                    "opened": 0,
                    "replied": 0,
                    "bounced": 0,
                    "failed": 0,
                    "skipped": 0,
                    "cost_micros": 0,
                },
            )
            if event_type in entry:
                entry[event_type] += 1
            entry["cost_micros"] += cost
        for channel, metrics in breakdown.items():
            analytics.channel_breakdown.append(
                ChannelAnalytics(
                    channel=channel,
                    sent=metrics["sent"],
                    delivered=metrics["delivered"],
                    opened=metrics["opened"],
                    replied=metrics["replied"],
                    bounced=metrics["bounced"],
                    failed=metrics["failed"],
                    skipped=metrics["skipped"],
                    cost_micros=metrics["cost_micros"],
                )
            )

        return analytics
