"""Service for workspace health and adoption analytics (Story 29.2, AD-52)."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import String, cast, func, join, select, union
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    AgentActionLog,
    Memory,
    SearchSourceConnector,
    TokenUsage,
    Workspace,
    WorkspaceHealthDaily,
    WorkspaceLimit,
    WorkspaceMembership,
)
from app.models.documents import Document
from app.models.scraper import ScraperPlatformAccount
from app.schemas.workspace_health import (
    CoverageGapItem,
    CoverageGapsResponse,
    MetricCardSummary,
    QuotaProgressItem,
    SourceBreakdownResponse,
    SourceTimelineSample,
    TopSourceItem,
    WorkspaceHealthDailyPoint,
    WorkspaceHealthRange,
    WorkspaceHealthSummaryResponse,
)
from app.services.workspace_limits import WorkspaceLimitService
from app.tenant_context import set_request_tenant_context

logger = logging.getLogger(__name__)

# Fallback monthly credits per plan tier if not explicitly configured on WorkspaceLimit
PLAN_DEFAULT_MONTHLY_CREDITS = {
    "free": 500_000,
    "team": 5_000_000,
    "growth": 25_000_000,
    "enterprise": None,
}

TIER_PROGRESSION = {
    "free": "Team",
    "team": "Growth",
    "growth": "Enterprise",
    "enterprise": None,
}


class WorkspaceHealthService:
    """Provides methods to roll up and query workspace health & adoption analytics."""

    @staticmethod
    async def refresh_workspace_health_daily(
        session: AsyncSession,
        target_date: date,
        workspace_id: int | None = None,
    ) -> list[WorkspaceHealthDaily]:
        """Aggregate and upsert daily health metrics for one or all workspaces (AC-1)."""
        if workspace_id is not None:
            workspace_ids = [workspace_id]
        else:
            stmt = select(Workspace.id).order_by(Workspace.id)
            res = await session.execute(stmt)
            workspace_ids = list(res.scalars().all())

        results: list[WorkspaceHealthDaily] = []
        for wid in workspace_ids:
            item = await WorkspaceHealthService._rollup_for_workspace_date(
                session, wid, target_date
            )
            results.append(item)

        await session.commit()
        return results

    @staticmethod
    async def _rollup_for_workspace_date(
        session: AsyncSession,
        workspace_id: int,
        target_date: date,
        persist: bool = True,
    ) -> WorkspaceHealthDaily:
        """Roll up metrics for a specific workspace and target date."""
        await set_request_tenant_context(session, workspace_id=workspace_id)

        day_start = datetime.combine(target_date, time.min, tzinfo=UTC)
        day_end = datetime.combine(target_date, time.max, tzinfo=UTC)
        wau_start = day_start - timedelta(days=6)

        # 1. Active members DAU (target_date)
        token_users = (
            select(TokenUsage.user_id)
            .where(
                TokenUsage.workspace_id == workspace_id,
                TokenUsage.created_at >= day_start,
                TokenUsage.created_at <= day_end,
                TokenUsage.user_id.is_not(None),
            )
        )
        memory_users = (
            select(Memory.created_by_id)
            .where(
                Memory.workspace_id == workspace_id,
                Memory.created_at >= day_start,
                Memory.created_at <= day_end,
                Memory.created_by_id.is_not(None),
            )
        )
        action_users = (
            select(AgentActionLog.user_id)
            .where(
                AgentActionLog.workspace_id == workspace_id,
                AgentActionLog.created_at >= day_start,
                AgentActionLog.created_at <= day_end,
                AgentActionLog.user_id.is_not(None),
            )
        )
        dau_union = union(token_users, memory_users, action_users).subquery()
        dau_res = await session.execute(select(func.count()).select_from(dau_union))
        active_members_dau = dau_res.scalar() or 0

        # 2. Active members WAU (trailing 7 days)
        token_wau = (
            select(TokenUsage.user_id)
            .where(
                TokenUsage.workspace_id == workspace_id,
                TokenUsage.created_at >= wau_start,
                TokenUsage.created_at <= day_end,
                TokenUsage.user_id.is_not(None),
            )
        )
        memory_wau = (
            select(Memory.created_by_id)
            .where(
                Memory.workspace_id == workspace_id,
                Memory.created_at >= wau_start,
                Memory.created_at <= day_end,
                Memory.created_by_id.is_not(None),
            )
        )
        action_wau = (
            select(AgentActionLog.user_id)
            .where(
                AgentActionLog.workspace_id == workspace_id,
                AgentActionLog.created_at >= wau_start,
                AgentActionLog.created_at <= day_end,
                AgentActionLog.user_id.is_not(None),
            )
        )
        wau_union = union(token_wau, memory_wau, action_wau).subquery()
        wau_res = await session.execute(select(func.count()).select_from(wau_union))
        active_members_wau = max(wau_res.scalar() or 0, active_members_dau)

        # 3. Total members in workspace as of target_date
        total_members_stmt = select(func.count(WorkspaceMembership.id)).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.joined_at <= day_end,
        )
        total_members_res = await session.execute(total_members_stmt)
        total_members = total_members_res.scalar() or 0

        # 4. Total memories (cumulative up to day_end)
        total_mem_stmt = select(func.count(Memory.id)).where(
            Memory.workspace_id == workspace_id,
            Memory.created_at <= day_end,
            (Memory.archived_at.is_(None) | (Memory.archived_at > day_end)),
        )
        total_mem_res = await session.execute(total_mem_stmt)
        total_memories = total_mem_res.scalar() or 0

        # 5. Memory growth count (created on target_date)
        mem_growth_stmt = select(func.count(Memory.id)).where(
            Memory.workspace_id == workspace_id,
            Memory.created_at >= day_start,
            Memory.created_at <= day_end,
        )
        mem_growth_res = await session.execute(mem_growth_stmt)
        memory_growth_count = mem_growth_res.scalar() or 0

        # 6. Queries breakdown (recall, remember, research)
        recall_stmt = select(func.count(AgentActionLog.id)).where(
            AgentActionLog.workspace_id == workspace_id,
            AgentActionLog.created_at >= day_start,
            AgentActionLog.created_at <= day_end,
            AgentActionLog.tool_name.ilike("%recall%"),
        )
        recall_res = await session.execute(recall_stmt)
        recall_queries = recall_res.scalar() or 0

        remember_stmt = select(func.count(AgentActionLog.id)).where(
            AgentActionLog.workspace_id == workspace_id,
            AgentActionLog.created_at >= day_start,
            AgentActionLog.created_at <= day_end,
            AgentActionLog.tool_name.ilike("%remember%"),
        )
        remember_res = await session.execute(remember_stmt)
        remember_queries = remember_res.scalar() or 0

        research_stmt = select(func.count(AgentActionLog.id)).where(
            AgentActionLog.workspace_id == workspace_id,
            AgentActionLog.created_at >= day_start,
            AgentActionLog.created_at <= day_end,
            (
                AgentActionLog.tool_name.ilike("%research%")
                | AgentActionLog.tool_name.ilike("%chainlens%")
            ),
        )
        research_res = await session.execute(research_stmt)
        research_queries = research_res.scalar() or 0

        # 7. Credits consumed
        credits_stmt = select(func.coalesce(func.sum(TokenUsage.cost_micros), 0)).where(
            TokenUsage.workspace_id == workspace_id,
            TokenUsage.created_at >= day_start,
            TokenUsage.created_at <= day_end,
        )
        credits_res = await session.execute(credits_stmt)
        credits_consumed_micros = int(credits_res.scalar() or 0)

        # 8. Cost per turn
        total_queries = recall_queries + remember_queries + research_queries
        if total_queries > 0:
            cost_per_turn_micros = credits_consumed_micros // total_queries
        else:
            cost_per_turn_micros = 0

        # 9. Top sources by connector and by memory source type
        top_sources = await WorkspaceHealthService._build_top_sources(
            session, workspace_id, day_end
        )

        # 10. Coverage gaps
        gap_count = await WorkspaceHealthService._count_coverage_gaps(
            session, workspace_id, day_end
        )

        record = WorkspaceHealthDaily(
            workspace_id=workspace_id,
            date=target_date,
            active_members_dau=active_members_dau,
            active_members_wau=active_members_wau,
            total_members=total_members,
            total_memories=total_memories,
            memory_growth_count=memory_growth_count,
            recall_queries=recall_queries,
            remember_queries=remember_queries,
            research_queries=research_queries,
            credits_consumed_micros=credits_consumed_micros,
            cost_per_turn_micros=cost_per_turn_micros,
            top_sources=top_sources,
            source_coverage_gap_count=gap_count,
        )

        if persist:
            # Idempotent upsert for daily rollup.
            upsert_stmt = pg_insert(WorkspaceHealthDaily).values(
                workspace_id=record.workspace_id,
                date=record.date,
                active_members_dau=record.active_members_dau,
                active_members_wau=record.active_members_wau,
                total_members=record.total_members,
                total_memories=record.total_memories,
                memory_growth_count=record.memory_growth_count,
                recall_queries=record.recall_queries,
                remember_queries=record.remember_queries,
                research_queries=record.research_queries,
                credits_consumed_micros=record.credits_consumed_micros,
                cost_per_turn_micros=record.cost_per_turn_micros,
                top_sources=record.top_sources,
                source_coverage_gap_count=record.source_coverage_gap_count,
                updated_at=datetime.now(UTC),
            ).on_conflict_do_update(
                index_elements=["workspace_id", "date"],
                set_={
                    "active_members_dau": record.active_members_dau,
                    "active_members_wau": record.active_members_wau,
                    "total_members": record.total_members,
                    "total_memories": record.total_memories,
                    "memory_growth_count": record.memory_growth_count,
                    "recall_queries": record.recall_queries,
                    "remember_queries": record.remember_queries,
                    "research_queries": record.research_queries,
                    "credits_consumed_micros": record.credits_consumed_micros,
                    "cost_per_turn_micros": record.cost_per_turn_micros,
                    "top_sources": record.top_sources,
                    "source_coverage_gap_count": record.source_coverage_gap_count,
                    "updated_at": datetime.now(UTC),
                },
            )
            await session.execute(upsert_stmt)
            await session.flush()

        return record

    @staticmethod
    async def _count_coverage_gaps(
        session: AsyncSession,
        workspace_id: int,
        reference_time: datetime,
    ) -> int:
        """Count enabled connectors with zero non-archived documents in trailing 30 days."""
        trailing_30d = reference_time - timedelta(days=30)

        connectors_stmt = select(SearchSourceConnector.id, SearchSourceConnector.connector_type).where(
            SearchSourceConnector.workspace_id == workspace_id
        )
        connectors_res = await session.execute(connectors_stmt)
        connector_rows = list(connectors_res.all())

        gap_count = 0
        for conn_id, ctype in connector_rows:
            doc_count_stmt = select(func.count(Document.id)).where(
                Document.workspace_id == workspace_id,
                Document.connector_id == conn_id,
                Document.created_at >= trailing_30d,
                Document.created_at <= reference_time,
                Document.archived_at.is_(None),
            )
            res = await session.execute(doc_count_stmt)
            if (res.scalar() or 0) == 0:
                gap_count += 1

        return gap_count

    @staticmethod
    async def _build_top_sources(
        session: AsyncSession,
        workspace_id: int,
        reference_time: datetime,
    ) -> list[dict[str, Any]]:
        """Rank connectors by the number of non-archived documents created up to reference_time.

        Returns a JSON-serializable list of dicts matching `TopSourceItem`.
        """
        stmt = (
            select(
                SearchSourceConnector.connector_type,
                func.coalesce(func.count(Document.id), 0).label("doc_count"),
            )
            .select_from(SearchSourceConnector)
            .join(
                Document,
                (Document.connector_id == SearchSourceConnector.id)
                & (Document.workspace_id == workspace_id)
                & (Document.created_at <= reference_time)
                & (Document.archived_at.is_(None)),
                isouter=True,
            )
            .where(SearchSourceConnector.workspace_id == workspace_id)
            .group_by(SearchSourceConnector.id, SearchSourceConnector.connector_type)
            .order_by(func.coalesce(func.count(Document.id), 0).desc())
        )
        res = await session.execute(stmt)

        top_sources: list[dict[str, Any]] = []
        for ctype, doc_count in res.all():
            ctype_val = ctype.value if hasattr(ctype, "value") else str(ctype)
            top_sources.append(
                {
                    "source_type": ctype_val,
                    "memory_count": int(doc_count or 0),
                    "query_count": 0,
                    "cost_micros": None,
                }
            )

        return top_sources

    @staticmethod
    async def get_health_summary(
        session: AsyncSession,
        workspace_id: int,
        date_range: WorkspaceHealthRange | str = WorkspaceHealthRange.RANGE_30D,
        start_date: date | None = None,
        end_date: date | None = None,
        is_public_snapshot: bool = False,
    ) -> WorkspaceHealthSummaryResponse:
        """Generate full health summary with sparklines, change %, and live overlay (AC-2)."""
        await set_request_tenant_context(session, workspace_id=workspace_id)
        today = datetime.now(UTC).date()

        # Resolve date boundaries
        if date_range == WorkspaceHealthRange.RANGE_7D or date_range == "7d":
            start = today - timedelta(days=6)
            end = today
            range_str = "7d"
        elif date_range == WorkspaceHealthRange.RANGE_90D or date_range == "90d":
            start = today - timedelta(days=89)
            end = today
            range_str = "90d"
        elif date_range == WorkspaceHealthRange.RANGE_CUSTOM or date_range == "custom":
            if not start_date or not end_date:
                raise HTTPException(
                    status_code=400,
                    detail="start_date and end_date are required for custom date_range",
                )
            if start_date > end_date:
                raise HTTPException(
                    status_code=400,
                    detail="start_date cannot be greater than end_date",
                )
            if (end_date - start_date).days > 365:
                raise HTTPException(
                    status_code=400,
                    detail="custom date_range cannot exceed 365 days",
                )
            start = start_date
            end = end_date
            range_str = "custom"
        else:  # Default 30d
            start = today - timedelta(days=29)
            end = today
            range_str = "30d"

        # 1. Fetch pre-aggregated historical points up to yesterday
        hist_end = min(end, today - timedelta(days=1))
        historical_stmt = (
            select(WorkspaceHealthDaily)
            .where(
                WorkspaceHealthDaily.workspace_id == workspace_id,
                WorkspaceHealthDaily.date >= start,
                WorkspaceHealthDaily.date <= hist_end,
            )
            .order_by(WorkspaceHealthDaily.date.asc())
        )
        hist_res = await session.execute(historical_stmt)
        hist_rows = {row.date: row for row in hist_res.scalars().all()}

        # 2. Compute live overlay for today if requested range covers today
        live_today: WorkspaceHealthDailyPoint | None = None
        if end >= today:
            live_record = await WorkspaceHealthService._rollup_for_workspace_date(
                session, workspace_id, today, persist=False
            )
            live_today = WorkspaceHealthDailyPoint(
                date=today.isoformat(),
                active_members_dau=live_record.active_members_dau
                if not is_public_snapshot
                else None,
                active_members_wau=live_record.active_members_wau
                if not is_public_snapshot
                else None,
                total_members=live_record.total_members,
                total_memories=live_record.total_memories,
                memory_growth_count=live_record.memory_growth_count,
                recall_queries=live_record.recall_queries,
                remember_queries=live_record.remember_queries,
                research_queries=live_record.research_queries,
                query_volume=live_record.recall_queries
                + live_record.remember_queries
                + live_record.research_queries,
                credits_consumed_micros=live_record.credits_consumed_micros
                if not is_public_snapshot
                else None,
                cost_per_turn_micros=live_record.cost_per_turn_micros
                if not is_public_snapshot
                else None,
            )

        # 3. Assemble daily points list spanning start..end
        daily_metrics: list[WorkspaceHealthDailyPoint] = []
        curr = start
        while curr <= end:
            if curr == today and live_today is not None:
                daily_metrics.append(live_today)
            elif curr in hist_rows:
                r = hist_rows[curr]
                daily_metrics.append(
                    WorkspaceHealthDailyPoint(
                        date=curr.isoformat(),
                        active_members_dau=r.active_members_dau
                        if not is_public_snapshot
                        else None,
                        active_members_wau=r.active_members_wau
                        if not is_public_snapshot
                        else None,
                        total_members=r.total_members,
                        total_memories=r.total_memories,
                        memory_growth_count=r.memory_growth_count,
                        recall_queries=r.recall_queries,
                        remember_queries=r.remember_queries,
                        research_queries=r.research_queries,
                        query_volume=r.recall_queries
                        + r.remember_queries
                        + r.research_queries,
                        credits_consumed_micros=r.credits_consumed_micros
                        if not is_public_snapshot
                        else None,
                        cost_per_turn_micros=r.cost_per_turn_micros
                        if not is_public_snapshot
                        else None,
                    )
                )
            else:
                # Fill missing dates with zero/carry-forward
                daily_metrics.append(
                    WorkspaceHealthDailyPoint(
                        date=curr.isoformat(),
                        active_members_dau=0 if not is_public_snapshot else None,
                        active_members_wau=0 if not is_public_snapshot else None,
                        total_members=0,
                        total_memories=0,
                        memory_growth_count=0,
                        recall_queries=0,
                        remember_queries=0,
                        research_queries=0,
                        query_volume=0,
                        credits_consumed_micros=0 if not is_public_snapshot else None,
                        cost_per_turn_micros=0 if not is_public_snapshot else None,
                    )
                )
            curr += timedelta(days=1)

        # 4. Fetch 14-day trailing points for sparklines
        spark_start = today - timedelta(days=13)
        spark_hist_stmt = (
            select(WorkspaceHealthDaily)
            .where(
                WorkspaceHealthDaily.workspace_id == workspace_id,
                WorkspaceHealthDaily.date >= spark_start,
                WorkspaceHealthDaily.date < today,
            )
            .order_by(WorkspaceHealthDaily.date.asc())
        )
        spark_res = await session.execute(spark_hist_stmt)
        spark_rows = {row.date: row for row in spark_res.scalars().all()}

        dau_spark: list[float | int] = []
        wau_spark: list[float | int] = []
        mem_spark: list[float | int] = []
        growth_spark: list[float | int] = []
        qv_spark: list[float | int] = []
        cred_spark: list[float | int] = []
        cpt_spark: list[float | int] = []

        for offset in range(14):
            d = spark_start + timedelta(days=offset)
            if d == today and live_today is not None:
                dau_spark.append(live_today.active_members_dau or 0)
                wau_spark.append(live_today.active_members_wau or 0)
                mem_spark.append(live_today.total_memories)
                growth_spark.append(live_today.memory_growth_count)
                qv_spark.append(live_today.query_volume)
                cred_spark.append(live_today.credits_consumed_micros or 0)
                cpt_spark.append(live_today.cost_per_turn_micros or 0)
            elif d in spark_rows:
                sr = spark_rows[d]
                dau_spark.append(sr.active_members_dau)
                wau_spark.append(sr.active_members_wau)
                mem_spark.append(sr.total_memories)
                growth_spark.append(sr.memory_growth_count)
                qv_spark.append(sr.recall_queries + sr.remember_queries + sr.research_queries)
                cred_spark.append(sr.credits_consumed_micros)
                cpt_spark.append(sr.cost_per_turn_micros)
            else:
                dau_spark.append(0)
                wau_spark.append(0)
                mem_spark.append(0)
                growth_spark.append(0)
                qv_spark.append(0)
                cred_spark.append(0)
                cpt_spark.append(0)

        # Calculate 7-day change percentage
        def _calc_change(current_7d: list[float | int], prev_7d: list[float | int]) -> float | None:
            sum_curr = sum(current_7d)
            sum_prev = sum(prev_7d)
            if sum_prev == 0:
                return 0.0 if sum_curr == 0 else 100.0
            return round(((sum_curr - sum_prev) / sum_prev) * 100, 1)

        def _calc_cpt_change(
            curr_qv: list[float | int],
            curr_cred: list[float | int],
            prev_qv: list[float | int],
            prev_cred: list[float | int],
        ) -> float | None:
            """Weighted 7-day cost-per-turn change using total credits / total queries."""
            prev_q = sum(prev_qv)
            curr_q = sum(curr_qv)
            prev_cpt = (sum(prev_cred) // prev_q) if prev_q > 0 else 0
            curr_cpt = (sum(curr_cred) // curr_q) if curr_q > 0 else 0
            if prev_cpt == 0:
                return 0.0 if curr_cpt == 0 else 100.0
            return round(((curr_cpt - prev_cpt) / prev_cpt) * 100, 1)

        prev_7_dau = dau_spark[:7]
        curr_7_dau = dau_spark[7:]
        prev_7_growth = growth_spark[:7]
        curr_7_growth = growth_spark[7:]
        prev_7_qv = qv_spark[:7]
        curr_7_qv = qv_spark[7:]
        prev_7_cred = cred_spark[:7]
        curr_7_cred = cred_spark[7:]
        prev_7_cpt = cpt_spark[:7]
        curr_7_cpt = cpt_spark[7:]

        # For WAU, split sparkline into prev/curr 7-day windows
        prev_7_wau = wau_spark[:7]
        curr_7_wau = wau_spark[7:]

        # For total_memories cumulative metric, compare current value vs value 7 days ago
        mem_change_pct: float | None = None
        if mem_spark[6] > 0:
            mem_change_pct = round(((mem_spark[13] - mem_spark[6]) / mem_spark[6]) * 100, 1)
        elif mem_spark[13] > 0:
            mem_change_pct = 100.0
        else:
            mem_change_pct = 0.0

        # For total_members cumulative metric, compute 7-day change similarly
        member_spark: list[float | int] = [
            p.total_members if p.total_members is not None else 0
            for p in daily_metrics[-14:]
        ]
        member_change_pct: float | None = None
        if len(member_spark) >= 14 and member_spark[6] > 0:
            member_change_pct = round(
                ((member_spark[13] - member_spark[6]) / member_spark[6]) * 100, 1
            )
        elif len(member_spark) >= 14 and member_spark[13] > 0:
            member_change_pct = 100.0
        else:
            member_change_pct = 0.0

        # Totals in requested date range
        sum_recall = sum(p.recall_queries for p in daily_metrics)
        sum_remember = sum(p.remember_queries for p in daily_metrics)
        sum_research = sum(p.research_queries for p in daily_metrics)
        sum_qv = sum(p.query_volume for p in daily_metrics)
        sum_growth = sum(p.memory_growth_count for p in daily_metrics)
        latest_total_members = daily_metrics[-1].total_members if daily_metrics else 0
        latest_total_memories = daily_metrics[-1].total_memories if daily_metrics else 0
        latest_dau = daily_metrics[-1].active_members_dau if daily_metrics else 0
        latest_wau = daily_metrics[-1].active_members_wau if daily_metrics else 0
        sum_credits = sum(p.credits_consumed_micros or 0 for p in daily_metrics)
        avg_cpt = (sum_credits // sum_qv) if sum_qv > 0 else 0

        # 5. Top sources & Coverage gaps count
        reference_time = datetime.combine(end, time.max, tzinfo=UTC)
        raw_top_sources = await WorkspaceHealthService._build_top_sources(
            session, workspace_id, reference_time
        )
        top_sources = [
            TopSourceItem(
                source_type=src["source_type"],
                memory_count=src["memory_count"],
                query_count=src["query_count"],
                cost_micros=None if is_public_snapshot else 0,
            )
            for src in raw_top_sources
        ]

        gap_count = await WorkspaceHealthService._count_coverage_gaps(
            session, workspace_id, reference_time
        )

        # 6. Quota Progress (HD-2)
        quota_progress: list[QuotaProgressItem] | None = None
        if not is_public_snapshot:
            quota_progress = await WorkspaceHealthService._get_quota_progress(
                session, workspace_id
            )

        return WorkspaceHealthSummaryResponse(
            workspace_id=workspace_id,
            date_range=range_str,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            is_public_snapshot=is_public_snapshot,
            total_members=MetricCardSummary(
                current_value=latest_total_members,
                change_pct=member_change_pct,
                sparkline=member_spark,
            ),
            total_memories=MetricCardSummary(
                current_value=latest_total_memories,
                change_pct=mem_change_pct,
                sparkline=mem_spark,
            ),
            active_members_dau=MetricCardSummary(
                current_value=latest_dau,
                change_pct=_calc_change(curr_7_dau, prev_7_dau),
                sparkline=dau_spark,
            )
            if not is_public_snapshot
            else None,
            active_members_wau=MetricCardSummary(
                current_value=latest_wau,
                change_pct=_calc_change(curr_7_wau, prev_7_wau),
                sparkline=wau_spark,
            )
            if not is_public_snapshot
            else None,
            memory_growth_count=MetricCardSummary(
                current_value=sum_growth,
                change_pct=_calc_change(curr_7_growth, prev_7_growth),
                sparkline=growth_spark,
            ),
            query_volume=MetricCardSummary(
                current_value=sum_qv,
                change_pct=_calc_change(curr_7_qv, prev_7_qv),
                sparkline=qv_spark,
            ),
            credits_consumed_micros=MetricCardSummary(
                current_value=sum_credits,
                change_pct=_calc_change(curr_7_cred, prev_7_cred),
                sparkline=cred_spark,
            )
            if not is_public_snapshot
            else None,
            cost_per_turn_micros=MetricCardSummary(
                current_value=avg_cpt,
                change_pct=_calc_cpt_change(curr_7_qv, curr_7_cred, prev_7_qv, prev_7_cred),
                sparkline=cpt_spark,
            )
            if not is_public_snapshot
            else None,
            recall_queries=sum_recall,
            remember_queries=sum_remember,
            research_queries=sum_research,
            top_sources=top_sources,
            source_coverage_gap_count=gap_count,
            quota_progress=quota_progress,
            daily_metrics=daily_metrics,
        )

    @staticmethod
    async def _get_quota_progress(
        session: AsyncSession,
        workspace_id: int,
    ) -> list[QuotaProgressItem]:
        """Compute quota utilization and tier upgrade recommendations (AC-5, HD-2)."""
        limits = await WorkspaceLimitService.get_effective_limits(session, workspace_id)
        plan_tier = limits.plan_tier or "free"
        next_tier = TIER_PROGRESSION.get(plan_tier.lower())

        items: list[QuotaProgressItem] = []

        # 1. Memory count
        mem_count = await WorkspaceLimitService.count_memories(session, workspace_id)
        mem_limit = limits.max_memory_count
        mem_util = round((mem_count / mem_limit) * 100, 1) if mem_limit else None
        mem_status = "alert" if (mem_util and mem_util >= 100) else ("warning" if (mem_util and mem_util >= 80) else "normal")
        items.append(
            QuotaProgressItem(
                metric="memory_count",
                label="Memory Count",
                current_value=mem_count,
                limit_value=mem_limit,
                utilization_pct=mem_util,
                status=mem_status,
                recommended_tier=next_tier if mem_status in ("warning", "alert") else None,
            )
        )

        # 2. Monthly credits
        month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        credits_stmt = select(func.coalesce(func.sum(TokenUsage.cost_micros), 0)).where(
            TokenUsage.workspace_id == workspace_id,
            TokenUsage.created_at >= month_start,
        )
        credits_res = await session.execute(credits_stmt)
        current_monthly_credits = int(credits_res.scalar() or 0)
        credits_limit = getattr(limits, "max_monthly_credits", None) or PLAN_DEFAULT_MONTHLY_CREDITS.get(plan_tier.lower())
        credits_util = round((current_monthly_credits / credits_limit) * 100, 1) if credits_limit else None
        credits_status = "alert" if (credits_util and credits_util >= 100) else ("warning" if (credits_util and credits_util >= 80) else "normal")
        items.append(
            QuotaProgressItem(
                metric="monthly_credits",
                label="Monthly Credits (micros)",
                current_value=current_monthly_credits,
                limit_value=credits_limit,
                utilization_pct=credits_util,
                status=credits_status,
                recommended_tier=next_tier if credits_status in ("warning", "alert") else None,
            )
        )

        # 3. Storage bytes
        storage_bytes = await WorkspaceLimitService.sum_storage_bytes(session, workspace_id)
        storage_limit = limits.max_storage_bytes
        storage_util = round((storage_bytes / storage_limit) * 100, 1) if storage_limit else None
        storage_status = "alert" if (storage_util and storage_util >= 100) else ("warning" if (storage_util and storage_util >= 80) else "normal")
        items.append(
            QuotaProgressItem(
                metric="storage_bytes",
                label="Storage Volume (Bytes)",
                current_value=storage_bytes,
                limit_value=storage_limit,
                utilization_pct=storage_util,
                status=storage_status,
                recommended_tier=next_tier if storage_status in ("warning", "alert") else None,
            )
        )

        return items

    @staticmethod
    async def get_source_drilldown(
        session: AsyncSession,
        workspace_id: int,
        source_type: str,
        is_public_snapshot: bool = False,
    ) -> SourceBreakdownResponse:
        """Get drilldown for a specific source with recent timeline samples (AC-3, HD-5)."""
        await set_request_tenant_context(session, workspace_id=workspace_id)

        # Check memories for this source_type
        count_stmt = select(func.count(Memory.id)).where(
            Memory.workspace_id == workspace_id,
            func.lower(cast(Memory.source_type, String)) == source_type.lower(),
            Memory.archived_at.is_(None),
        )
        count_res = await session.execute(count_stmt)
        total_memories = count_res.scalar() or 0

        # Also check if connector exists for this source
        conn_stmt = select(func.count(SearchSourceConnector.id)).where(
            SearchSourceConnector.workspace_id == workspace_id,
            func.lower(cast(SearchSourceConnector.connector_type, String))
            == source_type.lower(),
        )
        conn_res = await session.execute(conn_stmt)
        has_connector = (conn_res.scalar() or 0) > 0

        if total_memories == 0 and not has_connector:
            raise HTTPException(
                status_code=404,
                detail=f"Source type '{source_type}' not found for workspace {workspace_id}",
            )

        # Recent 5 timeline samples
        samples_stmt = (
            select(Memory)
            .where(
                Memory.workspace_id == workspace_id,
                func.lower(cast(Memory.source_type, String))
                == source_type.lower(),
                Memory.archived_at.is_(None),
            )
            .order_by(Memory.created_at.desc())
            .limit(5)
        )
        samples_res = await session.execute(samples_stmt)
        recent_samples = [
            SourceTimelineSample(
                id=m.id,
                content=m.content[:300] if m.content else "",
                created_at=m.created_at,
                confidence=m.confidence,
                tags=m.tags or [],
            )
            for m in samples_res.scalars().all()
        ]

        return SourceBreakdownResponse(
            workspace_id=workspace_id,
            source_type=source_type,
            total_memories=total_memories,
            query_volume=0,
            cost_micros=None,
            recent_samples=recent_samples,
        )

    @staticmethod
    async def get_coverage_gaps(
        session: AsyncSession,
        workspace_id: int,
    ) -> CoverageGapsResponse:
        """Identify enabled connectors with 0 non-archived documents in trailing 30 days (AC-4, HD-4)."""
        await set_request_tenant_context(session, workspace_id=workspace_id)
        trailing_30d = datetime.now(UTC) - timedelta(days=30)

        # Check configured connectors
        connectors_stmt = select(SearchSourceConnector).where(
            SearchSourceConnector.workspace_id == workspace_id
        )
        connectors_res = await session.execute(connectors_stmt)
        connectors = list(connectors_res.scalars().all())

        gaps: list[CoverageGapItem] = []
        for conn in connectors:
            c_name = (
                conn.connector_type.value
                if hasattr(conn.connector_type, "value")
                else str(conn.connector_type)
            )
            doc_stmt = select(func.count(Document.id)).where(
                Document.workspace_id == workspace_id,
                Document.connector_id == conn.id,
                Document.created_at >= trailing_30d,
                Document.archived_at.is_(None),
            )
            doc_res = await session.execute(doc_stmt)
            count = doc_res.scalar() or 0
            if count == 0:
                gaps.append(
                    CoverageGapItem(
                        source_type=c_name,
                        enabled_since=conn.created_at,
                        last_synced_at=conn.last_indexed_at,
                        remediation_action="Trigger manual sync or verify connector credentials",
                        configure_url=f"/dashboard/{workspace_id}/connectors",
                    )
                )

        return CoverageGapsResponse(gaps=gaps, total_gaps=len(gaps))
