"""Outcome-Based Pricing and Attribution Service (Story 21.7 / AD-42 / AD-48 / FR-69).

Manages $0 Chat invariants, first-touch attribution, outcome event recording,
and credit wallet debits for qualified business outcomes.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    BillingEvent,
    Lead,
    OutcomeEvent,
    PricingPlan,
)
from app.schemas.outcome_pricing import PricingPlanUpdate
from app.services import wallet_credit

logger = logging.getLogger(__name__)

# Default standard tariffs in USD micros ($1.00 == 1_000_000 micros)
DEFAULT_MEETING_BOOKED_MICROS = 2_000_000  # 50 credits ($2.00 / 50,000đ)
DEFAULT_PHONE_UNLOCK_MICROS = 60_000  # 1.5 credits ($0.06 / 1,500đ)
DEFAULT_LEAD_ENRICHED_MICROS = 40_000  # 1.0 credit ($0.04 / 1,000đ)
DEFAULT_DEEP_RESEARCH_MICROS = 200_000  # 5.0 credits ($0.20 / 5,000đ)

ZERO_COST_ACTIONS = {
    "standard_chat_turn",
    "table_transform",
    "csv_export",
    "sequence_create",
    "sequence_enroll",
    "prompt_generate",
}


class OutcomePricingService:
    """Handles outcome-based billing and first-touch attribution."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def is_zero_cost_action(self, action_type: str) -> bool:
        """Verify if an action is free under the $0 Chat & Sequencer policy."""
        return action_type in ZERO_COST_ACTIONS

    async def _find_earliest_sequence_enrollment(self, lead_id: UUID) -> UUID | None:
        """Find earliest sequence ID associated with this lead if sequence tables exist."""
        # Query if sequence enrollment table exists, else None
        return None

    async def resolve_first_touch_attribution(self, lead_id: UUID) -> str:
        """Determine first-touch attribution for an outcome."""
        seq_id = await self._find_earliest_sequence_enrollment(lead_id)
        if seq_id:
            return f"sequence:{seq_id}"

        # Fallback to lead source
        stmt = select(Lead).where(Lead.id == lead_id)
        result = await self.session.execute(stmt)
        lead = result.scalar_one_or_none()
        if lead and lead.source:
            return f"source:{lead.source}"

        return "direct_chat"

    async def get_workspace_rate(self, workspace_id: int, event_type: str) -> int:
        """Retrieve rate in micros for a specific event type from workspace pricing plan."""
        stmt = select(PricingPlan).where(PricingPlan.workspace_id == workspace_id)
        result = await self.session.execute(stmt)
        plan = result.scalar_one_or_none()

        if plan and plan.outcome_rates_json:
            normalized_key = event_type.replace("outcome_", "")
            if normalized_key in plan.outcome_rates_json:
                return int(plan.outcome_rates_json[normalized_key])
            if event_type in plan.outcome_rates_json:
                return int(plan.outcome_rates_json[event_type])

        defaults = {
            "meeting_booked": DEFAULT_MEETING_BOOKED_MICROS,
            "outcome_meeting_booked": DEFAULT_MEETING_BOOKED_MICROS,
            "phone_unlock": DEFAULT_PHONE_UNLOCK_MICROS,
            "lead_enriched": DEFAULT_LEAD_ENRICHED_MICROS,
            "outcome_lead_enriched": DEFAULT_LEAD_ENRICHED_MICROS,
            "deep_research": DEFAULT_DEEP_RESEARCH_MICROS,
        }
        return defaults.get(event_type, DEFAULT_MEETING_BOOKED_MICROS)

    async def record_meeting_booked(
        self,
        workspace_id: int,
        lead_id: UUID,
        user_id: UUID | None,
        attribution: str | None = None,
        metadata: dict[str, Any] | None = None,
        client_id: str | None = None,
    ) -> OutcomeEvent:
        """Record a qualified meeting booked outcome with atomic wallet debit and BillingEvent."""
        # 1. Validate lead exists and belongs to this workspace
        lead_stmt = select(Lead).where(
            Lead.id == lead_id,
            Lead.workspace_id == workspace_id,
        )
        lead_result = await self.session.execute(lead_stmt)
        lead = lead_result.scalar_one_or_none()
        if not lead:
            raise ValueError(f"Lead {lead_id} not found in workspace {workspace_id}.")

        # 2. Check deduplication / idempotency
        dedup_stmt = select(OutcomeEvent).where(
            OutcomeEvent.workspace_id == workspace_id,
            OutcomeEvent.lead_id == lead_id,
            OutcomeEvent.event_type == "outcome_meeting_booked",
        )
        existing_outcome = (await self.session.execute(dedup_stmt)).scalar_one_or_none()
        if existing_outcome:
            logger.info(
                "Meeting outcome already recorded for lead %s in workspace %d, returning existing event %s",
                lead_id,
                workspace_id,
                existing_outcome.id,
            )
            return existing_outcome

        rate = await self.get_workspace_rate(workspace_id, "meeting_booked")

        # 3. Pre-check wallet balance
        if user_id:
            await wallet_credit.check_balance(self.session, user_id, rate)

        # 4. Resolve attribution
        if not attribution:
            attribution = await self.resolve_first_touch_attribution(lead_id)

        seq_id = None
        if attribution and attribution.startswith("sequence:"):
            try:
                seq_id = UUID(attribution.split(":", 1)[1])
            except ValueError:
                seq_id = None

        # 5. Create OutcomeEvent
        outcome = OutcomeEvent(
            id=uuid4(),
            workspace_id=workspace_id,
            client_id=client_id,
            event_type="outcome_meeting_booked",
            lead_id=lead_id,
            sequence_id=seq_id,
            attribution=attribution,
            cost_micros=rate,
            outcome_metadata=metadata or {},
        )
        self.session.add(outcome)

        # 6. Create BillingEvent (Canonical ledger per AD-42 / AD-48)
        billing = BillingEvent(
            id=uuid4(),
            workspace_id=workspace_id,
            client_id=client_id,
            user_id=user_id,
            event_entity_type="outcome_event",
            event_type="outcome_meeting_booked",
            event_id=outcome.id,
            cost_micros=rate,
            currency="USD",
            cost_basis="actual",
        )
        self.session.add(billing)

        # 7. Apply wallet debit
        if user_id:
            await wallet_credit.apply_debit(self.session, user_id, rate)

        await self.session.commit()
        logger.info(
            "Recorded OutcomeEvent meeting booked for lead %s, debited %d micros (User %s)",
            lead_id,
            rate,
            user_id,
        )
        return outcome

    async def get_or_create_workspace_plan(self, workspace_id: int) -> PricingPlan:
        """Retrieve existing PricingPlan or create default outcome-based plan."""
        stmt = select(PricingPlan).where(PricingPlan.workspace_id == workspace_id)
        result = await self.session.execute(stmt)
        plan = result.scalar_one_or_none()

        if not plan:
            plan = PricingPlan(
                id=uuid4(),
                workspace_id=workspace_id,
                plan_type="outcome",
                seat_price=0,
                outcome_rates_json={
                    "meeting_booked": DEFAULT_MEETING_BOOKED_MICROS,
                    "phone_unlock": DEFAULT_PHONE_UNLOCK_MICROS,
                    "lead_enriched": DEFAULT_LEAD_ENRICHED_MICROS,
                },
                billing_period="monthly",
                is_active=True,
            )
            self.session.add(plan)
            try:
                await self.session.commit()
            except Exception:
                await self.session.rollback()
                stmt = select(PricingPlan).where(
                    PricingPlan.workspace_id == workspace_id
                )
                result = await self.session.execute(stmt)
                plan = result.scalar_one()

        return plan

    async def update_workspace_plan(
        self,
        workspace_id: int,
        update_data: PricingPlanUpdate,
    ) -> PricingPlan:
        """Update workspace pricing plan configuration."""
        plan = await self.get_or_create_workspace_plan(workspace_id)

        if update_data.plan_type is not None:
            plan.plan_type = update_data.plan_type
        if update_data.seat_price is not None:
            plan.seat_price = update_data.seat_price
        if update_data.outcome_rates_json is not None:
            plan.outcome_rates_json = update_data.outcome_rates_json
        if update_data.billing_period is not None:
            plan.billing_period = update_data.billing_period

        await self.session.commit()
        return plan
