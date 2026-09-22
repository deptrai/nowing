from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

import app.config.decision as decision_config
from app.db import (
    TokenUsage,
)
from app.models.admin_health import AdminHealthAlert

from ._helpers import _clamp_window, _make_time_bucket_expr

logger = logging.getLogger(__name__)

_DECISION_USAGE_TYPE = "decision"
_COST_ALERT_SERVICE_ID = "decision.jev_daily_cost"


class DecisionTelemetryMixin:
    """Decision-call (Jev / llm_json) telemetry for platform superadmins.

    Decision ``TokenUsage`` rows are identified by
    ``usage_type == "decision"``; ``call_details`` carries ``task`` /
    ``model`` / ``backend`` and — once an admin labels a row — the
    ``correct`` ground-truth flag. Latency comes from the real
    ``e2e_ms`` column so ``percentile_cont`` stays clean.
    """

    def _decision_filters(
        self, cutoff: datetime, workspace_id: int | None = None
    ) -> list[Any]:
        return [
            *self._token_filters(cutoff, workspace_id),
            TokenUsage.usage_type == _DECISION_USAGE_TYPE,
        ]

    @staticmethod
    def _jsonb_str_expr(key: str, label: str) -> Any:
        """Trimmed ``call_details->>key`` bucketed to ``'unknown'`` when blank."""
        return func.coalesce(
            func.nullif(func.trim(TokenUsage.call_details[key].as_string()), ""),
            "unknown",
        ).label(label)

    @staticmethod
    def _median_ms_expr() -> Any:
        """Median (p50) decision latency over the real ``e2e_ms`` column."""
        return func.percentile_cont(0.5).within_group(TokenUsage.e2e_ms.asc())

    async def get_decision_telemetry(
        self,
        window_hours: int,
        workspace_id: int | None = None,
    ) -> dict[str, Any]:
        """Aggregate decision-call volume, latency, accuracy, cost, and drift.

        Accuracy is ``correct / labeled`` over rows where
        ``call_details ? 'correct'`` — ``None`` (never 0.0) when nothing
        is labeled yet. Reading this endpoint may insert ONE deduped
        ``AdminHealthAlert`` when today's UTC decision cost breaches
        ``DECISION_DAILY_COST_ALERT_USD``; every other query is read-only.
        """
        window_hours = _clamp_window(window_hours)
        cutoff = self._cutoff(window_hours)
        granularity = self._granularity(window_hours)
        filters = self._decision_filters(cutoff, workspace_id)

        has_correct = TokenUsage.call_details.has_key("correct")
        # Text comparison, not CAST(... AS BOOLEAN): a non-bool JSON value
        # (e.g. "yes", 1) would raise in the cast and 500 the endpoint.
        # `->>` never raises; only JSON true / "true" count as correct.
        is_correct = TokenUsage.call_details["correct"].as_string() == "true"

        totals_stmt = select(
            func.count(TokenUsage.id).label("calls"),
            func.coalesce(func.sum(TokenUsage.cost_micros), 0).label("cost_micros"),
            self._median_ms_expr().label("median_ms"),
            func.count(TokenUsage.id).filter(has_correct).label("labeled"),
            func.count(TokenUsage.id).filter(is_correct).label("correct"),
        ).where(*filters)
        totals = (await self.session.execute(totals_stmt)).one()

        bucket_expr = _make_time_bucket_expr(granularity)
        task_expr = self._jsonb_str_expr("task", "task")
        daily_stmt = (
            select(
                bucket_expr.label("period"),
                task_expr,
                func.count(TokenUsage.id).label("calls"),
                self._median_ms_expr().label("median_ms"),
                func.coalesce(func.sum(TokenUsage.cost_micros), 0).label(
                    "cost_micros"
                ),
            )
            .where(*filters)
            .group_by(bucket_expr, task_expr)
            .order_by(bucket_expr.asc(), task_expr.asc())
        )
        daily_rows = (await self.session.execute(daily_stmt)).all()

        task_col = self._jsonb_str_expr("task", "task")
        by_task_stmt = (
            select(
                task_col,
                func.count(TokenUsage.id).label("calls"),
                self._median_ms_expr().label("median_ms"),
                func.coalesce(func.sum(TokenUsage.cost_micros), 0).label(
                    "cost_micros"
                ),
                func.coalesce(func.sum(TokenUsage.prompt_tokens), 0).label(
                    "input_tokens"
                ),
                func.coalesce(func.sum(TokenUsage.completion_tokens), 0).label(
                    "output_tokens"
                ),
            )
            .where(*filters)
            .group_by(task_col)
            .order_by(func.count(TokenUsage.id).desc())
        )
        task_rows = (await self.session.execute(by_task_stmt)).all()

        model_col = self._jsonb_str_expr("model", "model")
        backend_col = self._jsonb_str_expr("backend", "backend")
        models_stmt = (
            select(
                model_col,
                backend_col,
                func.count(TokenUsage.id).label("calls"),
                func.min(TokenUsage.created_at).label("first_seen"),
                func.max(TokenUsage.created_at).label("last_seen"),
            )
            .where(*filters)
            .group_by(model_col, backend_col)
            .order_by(func.max(TokenUsage.created_at).desc())
        )
        model_rows = (await self.session.execute(models_stmt)).all()

        # Today's UTC decision spend — evaluated on read so the first
        # dashboard view after a breach fires the (deduped) alert; no
        # Celery beat needed (see spec Design Notes).
        today_start = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        today_filters = [
            TokenUsage.created_at >= today_start,
            TokenUsage.usage_type == _DECISION_USAGE_TYPE,
        ]
        if workspace_id is not None:
            today_filters.append(TokenUsage.workspace_id == workspace_id)
        today_stmt = select(
            func.coalesce(func.sum(TokenUsage.cost_micros), 0).label("cost_micros")
        ).where(*today_filters)
        today_row = (await self.session.execute(today_stmt)).one()
        today_cost_micros = int(today_row.cost_micros)

        threshold_usd = decision_config.DECISION_DAILY_COST_ALERT_USD
        exceeded = today_cost_micros > threshold_usd * 1_000_000
        if exceeded:
            await self._maybe_insert_cost_alert(today_cost_micros, threshold_usd)

        labeled = int(totals.labeled)
        correct = int(totals.correct)
        pinned_model = decision_config.DECISION_JEV_MODEL
        jev_models = {row.model for row in model_rows if row.backend == "jev"}
        drift_detected = len(jev_models) > 1 or any(
            model != pinned_model for model in jev_models
        )

        return {
            "window_hours": window_hours,
            "workspace_id": workspace_id,
            "total_calls": int(totals.calls),
            "total_cost_micros": int(totals.cost_micros),
            "median_latency_ms": (
                float(totals.median_ms) if totals.median_ms is not None else None
            ),
            "labeled": labeled,
            "correct": correct,
            "accuracy": (correct / labeled) if labeled > 0 else None,
            "pinned_model": pinned_model,
            "drift_detected": drift_detected,
            "daily": [
                {
                    "period": row.period,
                    "task": str(row.task),
                    "calls": int(row.calls),
                    "median_latency_ms": (
                        float(row.median_ms)
                        if row.median_ms is not None
                        else None
                    ),
                    "cost_micros": int(row.cost_micros),
                }
                for row in daily_rows
            ],
            "by_task": [
                {
                    "task": str(row.task),
                    "calls": int(row.calls),
                    "median_latency_ms": (
                        float(row.median_ms)
                        if row.median_ms is not None
                        else None
                    ),
                    "cost_micros": int(row.cost_micros),
                    "input_tokens": int(row.input_tokens),
                    "output_tokens": int(row.output_tokens),
                }
                for row in task_rows
            ],
            "models": [
                {
                    "model": str(row.model),
                    "backend": str(row.backend),
                    "calls": int(row.calls),
                    "first_seen": row.first_seen,
                    "last_seen": row.last_seen,
                }
                for row in model_rows
            ],
            "cost_alert": {
                "threshold_usd": threshold_usd,
                "today_cost_micros": today_cost_micros,
                "exceeded": exceeded,
            },
        }

    async def _maybe_insert_cost_alert(
        self, today_cost_micros: int, threshold_usd: float
    ) -> bool:
        """Insert one ``AdminHealthAlert`` unless an open/acknowledged
        alert with the same ``service_id`` already exists (dedupe).

        Failures degrade to a warning — an alert-insert error must never
        break the read endpoint.
        """
        try:
            # Transaction-scoped advisory lock serializes check-then-insert
            # per service_id — two concurrent reads can't both pass the
            # dedupe SELECT and double-insert (TOCTOU). Released by the
            # commit below (or by session close on rollback).
            await self.session.execute(
                select(
                    func.pg_advisory_xact_lock(
                        func.hashtext(_COST_ALERT_SERVICE_ID)
                    )
                )
            )
            existing = (
                await self.session.execute(
                    select(AdminHealthAlert.id)
                    .where(
                        AdminHealthAlert.service_id == _COST_ALERT_SERVICE_ID,
                        AdminHealthAlert.status.in_(["open", "acknowledged"]),
                    )
                    .limit(1)
                )
            ).first()
            if existing is not None:
                return False
            self.session.add(
                AdminHealthAlert(
                    service_id=_COST_ALERT_SERVICE_ID,
                    status="open",
                    severity="high",
                    message=(
                        "Decision daily cost "
                        f"${today_cost_micros / 1_000_000:.4f} exceeded the "
                        f"${threshold_usd:.2f} threshold (UTC today)"
                    ),
                )
            )
            await self.session.commit()
            return True
        except Exception:
            logger.warning(
                "Failed to insert decision cost alert", exc_info=True
            )
            return False

    async def label_decision(
        self, usage_id: int, correct: bool
    ) -> dict[str, Any] | None:
        """Merge ``{"correct": bool}`` into a decision row's call_details.

        ``call_details`` is reassigned as a new dict — JSONB in-place
        mutation tracking is off. Returns ``None`` when the id is missing
        or not a decision row (the route maps that to 404).
        """
        stmt = select(TokenUsage).where(
            TokenUsage.id == usage_id,
            TokenUsage.usage_type == _DECISION_USAGE_TYPE,
        )
        record = (await self.session.execute(stmt)).scalar_one_or_none()
        if record is None:
            return None
        details = dict(record.call_details or {})
        details["correct"] = bool(correct)
        record.call_details = details
        await self.session.commit()
        return {"usage_id": usage_id, "correct": bool(correct)}
