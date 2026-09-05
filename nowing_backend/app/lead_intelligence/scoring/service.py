"""Lead scoring service (Story 21.2)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.core.types import CapabilityContext
from app.config import config
from app.db import (
    Lead,
    LeadScore,
    MemorySourceType,
    MemoryType,
    SignalEvent,
    Workspace,
)
from app.lead_intelligence.scoring.rubric import (
    DEFAULT_FIT_WEIGHTS,
    DEFAULT_INTENT_WEIGHTS,
    blend_location_fit_score,
    clamp_score,
    classify,
    compute_trend,
    days_ago,
    default_icp_criteria,
    recency_multiplier,
)
from app.lead_intelligence.scoring.schemas import (
    LeadScoreInput,
    LeadScoreOutput,
    LeadScoreRead,
)
from app.services import wallet_credit
from app.services.billing_event_service import BillingEventService
from app.services.memory.repository import MemoryRepository
from app.services.pii.redact import redact_pii

logger = logging.getLogger(__name__)


class LeadScoringService:
    """Compute and persist composite fit + intent scores for leads."""

    def __init__(self) -> None:
        self.billing = BillingEventService()

    async def score(
        self,
        session: AsyncSession,
        ctx: CapabilityContext,
        inp: LeadScoreInput,
    ) -> LeadScoreOutput:
        """Score leads and return ``LeadScoreOutput``."""
        workspace = await session.get(Workspace, ctx.workspace_id)
        if workspace is None:
            return LeadScoreOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reasons=["workspace_not_found"],
            )

        client_id = getattr(ctx, "client_id", None) or None
        leads = await self._fetch_leads(
            session, ctx.workspace_id, client_id, inp.lead_ids
        )
        if not leads:
            return LeadScoreOutput(
                items=[],
                cost_micros=0,
                degraded=False,
            )

        cost_per_call = getattr(config, "LEAD_SCORING_MICROS_PER_CALL", 0) or 0
        total_cost = cost_per_call * len(leads)

        try:
            await wallet_credit.check_balance(
                session,
                user_id=workspace.user_id,
                required_micros=total_cost,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("lead scoring wallet check failed: %s", exc)
            return LeadScoreOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reasons=["insufficient_wallet"],
            )

        signals = await self._fetch_signals(session, ctx.workspace_id, client_id, leads)
        converted = await self._fetch_converted_leads(
            session, ctx.workspace_id, client_id, leads
        )
        icp_criteria = workspace.icp_criteria or default_icp_criteria()

        items: list[LeadScoreRead] = []
        for lead in leads:
            lead_signals = signals.get(lead.id, [])
            converted_leads = [c for c in converted if c.id != lead.id]

            raw_fit, fit_factors = await self._fit_score(lead, icp_criteria)
            raw_intent, intent_factors = await self._intent_score(lead_signals)
            converted_similarity = await self._converted_similarity(
                session,
                lead,
                converted_leads,
            )

            fit_score = clamp_score(raw_fit)
            intent_score = clamp_score(raw_intent)
            composite = clamp_score(0.5 * fit_score + 0.5 * intent_score)
            classification = classify(composite)

            previous_score = await self._previous_score(session, lead.id)
            previous_value = (
                previous_score.score if previous_score is not None else None
            )
            trend = compute_trend(previous_value, composite)

            factors_json = {
                **fit_factors,
                **intent_factors,
                "converted_similarity": converted_similarity,
            }

            lead_score = LeadScore(
                id=uuid4(),
                workspace_id=ctx.workspace_id,
                client_id=client_id,
                lead_id=lead.id,
                previous_score_id=previous_score.id
                if previous_score is not None
                else None,
                company_name=lead.company_name,
                score=composite,
                fit_score=fit_score,
                intent_score=intent_score,
                classification=classification,
                factors_json=factors_json,
                trend=trend,
                converted_similarity=converted_similarity,
                computed_at=datetime.now(UTC),
            )
            session.add(lead_score)
            await session.flush()

            await self._record_billing(
                session,
                workspace_id=ctx.workspace_id,
                client_id=client_id,
                user_id=workspace.user_id,
                lead_score_id=lead_score.id,
                cost_micros=cost_per_call,
            )

            await self._write_memory(
                session,
                ctx,
                lead_score,
                fit_factors,
                intent_factors,
            )

            items.append(
                LeadScoreRead(
                    id=lead_score.id,
                    workspace_id=lead_score.workspace_id,
                    client_id=lead_score.client_id,
                    lead_id=lead_score.lead_id,
                    company_name=lead_score.company_name,
                    score=lead_score.score,
                    fit_score=lead_score.fit_score,
                    intent_score=lead_score.intent_score,
                    classification=lead_score.classification,
                    factors_json=lead_score.factors_json,
                    trend=lead_score.trend,
                    converted_similarity=lead_score.converted_similarity,
                    previous_score_id=lead_score.previous_score_id,
                    computed_at=lead_score.computed_at,
                )
            )

        return LeadScoreOutput(
            items=items,
            cost_micros=total_cost,
            degraded=False,
        )

    async def _fetch_leads(
        self,
        session: AsyncSession,
        workspace_id: int,
        client_id: str | None,
        lead_ids: list[UUID] | None,
    ) -> list[Lead]:
        """Return leads to score, scoped by workspace/client and optional IDs."""
        stmt = select(Lead).where(Lead.workspace_id == workspace_id)
        if client_id is not None:
            stmt = stmt.where(Lead.client_id == client_id)
        if lead_ids:
            stmt = stmt.where(Lead.id.in_(lead_ids))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _fetch_signals(
        self,
        session: AsyncSession,
        workspace_id: int,
        client_id: str | None,
        leads: list[Lead],
    ) -> dict[UUID, list[SignalEvent]]:
        """Return signal events grouped by lead id."""
        company_names = {lead.company_name for lead in leads if lead.company_name}
        if not company_names:
            return {}

        stmt = select(SignalEvent).where(
            SignalEvent.workspace_id == workspace_id,
            SignalEvent.company_name.in_(list(company_names)),
        )
        if client_id is not None:
            stmt = stmt.where(SignalEvent.client_id == client_id)
        result = await session.execute(stmt)
        rows = list(result.scalars().all())

        by_company: dict[str, list[SignalEvent]] = {}
        for row in rows:
            by_company.setdefault(row.company_name, []).append(row)

        by_lead: dict[UUID, list[SignalEvent]] = {}
        for lead in leads:
            by_lead[lead.id] = by_company.get(lead.company_name, [])
        return by_lead

    async def _fetch_converted_leads(
        self,
        session: AsyncSession,
        workspace_id: int,
        client_id: str | None,
        leads: list[Lead],
    ) -> list[Lead]:
        """Return converted leads in the same workspace, excluding current batch."""
        stmt = select(Lead).where(
            Lead.workspace_id == workspace_id,
            Lead.status == "converted",
        )
        if client_id is not None:
            stmt = stmt.where(Lead.client_id == client_id)
        converted_ids = {lead.id for lead in leads if lead.status == "converted"}
        if converted_ids:
            stmt = stmt.where(Lead.id.notin_(converted_ids))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _previous_score(
        self,
        session: AsyncSession,
        lead_id: UUID,
    ) -> LeadScore | None:
        """Return the most recent prior ``LeadScore`` for a lead."""
        result = await session.execute(
            select(LeadScore)
            .where(LeadScore.lead_id == lead_id)
            .order_by(LeadScore.computed_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _fit_score(
        self,
        lead: Lead,
        icp_criteria: dict[str, Any],
    ) -> tuple[float, dict[str, Any]]:
        """Compute fit score from firmographics and ICP match."""
        weights = icp_criteria.get("weights") or DEFAULT_FIT_WEIGHTS
        normalized = self._normalize_weights({k: float(v) for k, v in weights.items()})

        score = 0.0
        factors: dict[str, Any] = {}

        company_size = lead.company_size or ""
        target_sizes = icp_criteria.get("target_company_sizes") or {}
        if target_sizes and company_size:
            factors["company_size"] = 15.0
            score += 15.0 * normalized.get("company_size", 0.0)
        else:
            factors["company_size"] = 10.0

        industry = lead.industry or ""
        target_industries = icp_criteria.get("target_industries") or []
        if industry and target_industries and industry in target_industries:
            factors["industry"] = 20.0
            score += 20.0 * normalized.get("industry", 0.0)
        else:
            factors["industry"] = 0.0

        location = lead.location or ""
        target_locations = icp_criteria.get("target_locations") or []
        if location and target_locations and location in target_locations:
            factors["location"] = 20.0
            score += 20.0 * normalized.get("location", 0.0)
        else:
            factors["location"] = 0.0

        tech_stack = set(lead.tech_stack or [])
        target_tech = icp_criteria.get("target_tech_stack") or []
        matches = tech_stack & set(target_tech)
        if target_tech and matches:
            match_score = min(20.0, 20.0 * len(matches) / max(1, len(target_tech)))
            factors["tech_stack"] = match_score
            score += match_score * normalized.get("tech_stack", 0.0)
        else:
            factors["tech_stack"] = 0.0

        # ICP alignment is a catch-all; default to neutral when missing criteria.
        if target_industries or target_locations or target_tech or target_sizes:
            factors["icp"] = 15.0
            score += 15.0 * normalized.get("icp", 0.0)
        else:
            factors["icp"] = 10.0
            score += 10.0 * normalized.get("icp", 0.0)

        # Blend location match score from pre-filter if available (AC-4)
        location_match_score = getattr(lead, "location_match_score", None)
        if location_match_score is not None:
            score = blend_location_fit_score(score, float(location_match_score))
            factors["location_match"] = float(location_match_score)

        return clamp_score(score), factors

    def _normalize_weights(self, weights: dict[str, float]) -> dict[str, float]:
        """Normalize weights to sum to 1.0."""
        total = sum(weights.values())
        if total <= 0:
            return dict.fromkeys(weights, 0.0)
        return {k: v / total for k, v in weights.items()}

    async def _intent_score(
        self,
        signals: list[SignalEvent],
    ) -> tuple[float, dict[str, Any]]:
        """Compute intent score from signal strength and recency."""
        if not signals:
            return 0.0, {"signal_strength": 0.0, "recency": 0.0}

        total = 0.0
        for signal in signals:
            signal_type = signal.signal_type or "news"
            weight = DEFAULT_INTENT_WEIGHTS.get(signal_type, 5.0)
            age = days_ago(signal.detected_at)
            multiplier = recency_multiplier(age)
            total += signal.confidence * (weight / 100.0) * multiplier

        score = clamp_score(total)
        factors = {
            "signal_strength": score,
            "recency": min(
                100.0,
                sum(recency_multiplier(days_ago(s.detected_at)) for s in signals)
                / len(signals)
                * 100,
            ),
        }
        return score, factors

    async def _converted_similarity(
        self,
        session: AsyncSession,
        lead: Lead,
        converted_leads: list[Lead],
    ) -> float | None:
        """RAG-based similarity against converted leads.

        Falls back to rule-based name/domain overlap when RAG is unavailable.
        """
        if not converted_leads:
            return None

        # Simple rule-based fallback: industry/tech_stack/location overlap.
        scores: list[float] = []
        for converted in converted_leads:
            score = 0.0
            if (
                lead.industry
                and converted.industry
                and lead.industry == converted.industry
            ):
                score += 40.0
            if (
                lead.location
                and converted.location
                and lead.location == converted.location
            ):
                score += 20.0
            lead_tech = set(lead.tech_stack or [])
            conv_tech = set(converted.tech_stack or [])
            if lead_tech and conv_tech:
                overlap = len(lead_tech & conv_tech) / max(
                    len(lead_tech), len(conv_tech)
                )
                score += 40.0 * overlap
            scores.append(score)

        if not scores:
            return None
        return clamp_score(sum(scores) / len(scores))

    async def _record_billing(
        self,
        session: AsyncSession,
        workspace_id: int,
        client_id: str | None,
        user_id: UUID,
        lead_score_id: UUID,
        cost_micros: int,
    ) -> None:
        """Record a billing event for a scored lead."""
        if cost_micros <= 0:
            return
        try:
            await self.billing.record_lead_scoring(
                session,
                lead_score_id=lead_score_id,
                workspace_id=workspace_id,
                client_id=client_id,
                user_id=user_id,
                cost_micros=cost_micros,
            )
        except Exception:
            logger.exception(
                "failed to record lead scoring billing for %s", lead_score_id
            )

    async def _write_memory(
        self,
        session: AsyncSession,
        ctx: CapabilityContext,
        lead_score: LeadScore,
        fit_factors: dict[str, Any],
        intent_factors: dict[str, Any],
    ) -> None:
        """Persist a redacted summary of the score as a Memory row."""
        raw_summary = json.dumps(
            {
                "company_name": lead_score.company_name,
                "score": lead_score.score,
                "fit": fit_factors,
                "intent": intent_factors,
            },
            default=str,
            ensure_ascii=False,
        )
        redacted = redact_pii(raw_summary, context="lead_enrichment")

        repo = MemoryRepository(session)
        await repo.create_memory(
            workspace_id=ctx.workspace_id,
            content=redacted.text,
            type=MemoryType.SEMANTIC,
            source_type=MemorySourceType.LEAD_SCORE,
            source_uuid=lead_score.id,
            source_entity_type="lead_score",
            tags=["lead_score"],
            confidence=lead_score.score / 100.0,
            created_by_id=getattr(ctx, "user_id", None),
            client_id=getattr(ctx, "client_id", None),
        )
