"""Signal detection service for lead intelligence."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import (
    Memory,
    MemorySourceType,
    MemoryType,
    SignalEvent,
)
from app.lead_intelligence.signals.schemas import (
    SignalEventRead,
    SignalInput,
    SignalOutput,
)
from app.services import pii, wallet_credit
from app.services.billing_event_service import record_signal_scan
from app.services.jobs_aggregator.schemas import VnJobAggregateInput

logger = logging.getLogger(__name__)

SIGNAL_TYPES = {"funding", "hiring", "tech_stack", "executive_move", "news"}


class SignalDetectionService:
    """Detect buying-intent signals for a company and persist them."""

    async def detect(
        self,
        session: AsyncSession,
        ctx: Any,
        input: SignalInput,
        signal_type: str,
    ) -> SignalOutput:
        """Run signal detection for ``signal_type`` and return the output."""
        if signal_type not in SIGNAL_TYPES:
            raise ValueError(f"unknown signal_type: {signal_type}")

        cost_per_item = config.SIGNAL_SCAN_MICROS_PER_SIGNAL

        # Wallet pre-check: if the owner cannot afford a single unit, fail fast.
        if cost_per_item > 0 and ctx and getattr(ctx, "user_id", None):
            try:
                await wallet_credit.check_balance(session, ctx.user_id, cost_per_item)
            except wallet_credit.InsufficientCreditsError:
                return SignalOutput(
                    items=[],
                    cost_micros=0,
                    degraded=True,
                    degradation_reasons=["insufficient_wallet"],
                )

        raw_items: list[dict[str, Any]] = []
        degradation_reasons: list[str] = []

        try:
            if signal_type == "funding":
                raw_items, reasons = await self._detect_funding(input)
                degradation_reasons.extend(reasons)
            elif signal_type == "hiring":
                raw_items, reasons = await self._detect_hiring(input, ctx)
                degradation_reasons.extend(reasons)
            elif signal_type == "tech_stack":
                raw_items, reasons = await self._detect_tech_stack(input)
                degradation_reasons.extend(reasons)
            elif signal_type == "news":
                raw_items, reasons = await self._detect_news(input)
                degradation_reasons.extend(reasons)
            elif signal_type == "executive_move":
                raw_items, reasons = await self._detect_executive_move(input)
                degradation_reasons.extend(reasons)
        except wallet_credit.InsufficientCreditsError:
            return SignalOutput(
                items=[],
                cost_micros=0,
                degraded=True,
                degradation_reasons=["insufficient_wallet"],
            )

        workspace_id = ctx.workspace_id if ctx else 1
        client_id = getattr(ctx, "client_id", None) if ctx else None

        items: list[SignalEventRead] = []
        persisted: list[SignalEvent] = []

        # Pre-compute the total estimated cost so we can fail fast if needed.
        total_cost = len(raw_items) * cost_per_item
        if total_cost > 0 and ctx and getattr(ctx, "user_id", None):
            try:
                await wallet_credit.check_balance(session, ctx.user_id, total_cost)
            except wallet_credit.InsufficientCreditsError:
                return SignalOutput(
                    items=[],
                    cost_micros=0,
                    degraded=True,
                    degradation_reasons=["insufficient_wallet"],
                )

        for raw in raw_items:
            signal = await self._persist_signal(
                session,
                workspace_id=workspace_id,
                client_id=client_id,
                input=input,
                signal_type=signal_type,
                raw=raw,
            )
            if signal is None:
                continue
            persisted.append(signal)
            items.append(
                SignalEventRead(
                    id=signal.id,
                    workspace_id=signal.workspace_id,
                    client_id=signal.client_id,
                    company_name=signal.company_name,
                    signal_type=signal.signal_type,
                    source_url=signal.source_url,
                    chunk_id=signal.chunk_id,
                    confidence=signal.confidence,
                    detected_at=signal.detected_at,
                    processed=signal.processed,
                )
            )

        # If we degraded but found no concrete items, surface one synthetic item
        # so callers still see the failure signal.
        if degradation_reasons and not items:
            signal = await self._persist_signal(
                session,
                workspace_id=workspace_id,
                client_id=client_id,
                input=input,
                signal_type=signal_type,
                raw={"confidence": 0.0, "source_url": None, "degraded": True},
            )
            if signal is not None:
                items.append(
                    SignalEventRead(
                        id=signal.id,
                        workspace_id=signal.workspace_id,
                        client_id=signal.client_id,
                        company_name=signal.company_name,
                        signal_type=signal.signal_type,
                        source_url=signal.source_url,
                        chunk_id=signal.chunk_id,
                        confidence=signal.confidence,
                        detected_at=signal.detected_at,
                        processed=signal.processed,
                    )
                )
                persisted.append(signal)

        # Charge one BillingEvent per persisted signal item.
        for signal in persisted:
            if ctx and getattr(ctx, "user_id", None):
                try:
                    await record_signal_scan(
                        session,
                        signal_event_id=signal.id,
                        workspace_id=workspace_id,
                        client_id=client_id,
                        user_id=ctx.user_id,
                        cost_micros=cost_per_item,
                    )
                except Exception as exc:
                    logger.exception("Billing event failed for signal %s", signal.id)
                    degradation_reasons.append(str(exc))

        degraded = bool(degradation_reasons) or any(
            r.get("degraded") for r in raw_items
        )

        return SignalOutput(
            items=items,
            cost_micros=len(items) * cost_per_item,
            degraded=degraded,
            degradation_reasons=degradation_reasons or None,
        )

    async def _persist_signal(
        self,
        session: AsyncSession,
        *,
        workspace_id: int,
        client_id: str | None,
        input: SignalInput,
        signal_type: str,
        raw: dict[str, Any],
    ) -> SignalEvent | None:
        """Create a SignalEvent and its redacted Memory row."""

        confidence = max(0.0, min(100.0, float(raw.get("confidence", 0.0))))
        if confidence < input.confidence_threshold:
            return None

        detected_at: datetime = raw.get("detected_at") or datetime.now(UTC)
        if isinstance(detected_at, str):
            try:
                detected_at = datetime.fromisoformat(detected_at)
            except ValueError:
                detected_at = datetime.now(UTC)

        source_url = raw.get("source_url")
        if source_url:
            source_url = str(source_url)[:4096]

        company_name = str(raw.get("company_name", input.company_name)).strip()

        # Idempotency: if the exact same signal already exists, skip it.
        existing = (
            await session.execute(
                select(SignalEvent).where(
                    SignalEvent.workspace_id == workspace_id,
                    SignalEvent.client_id == client_id,
                    SignalEvent.company_name == company_name,
                    SignalEvent.signal_type == signal_type,
                    SignalEvent.source_url == source_url,
                    SignalEvent.detected_at == detected_at,
                )
            )
        ).scalar_one_or_none()

        if existing is not None:
            return existing

        signal = SignalEvent(
            id=uuid4(),
            workspace_id=workspace_id,
            client_id=client_id,
            company_name=company_name,
            signal_type=signal_type,
            source_url=source_url,
            chunk_id=raw.get("chunk_id"),
            confidence=confidence,
            detected_at=detected_at,
            processed=False,
        )
        session.add(signal)
        await session.flush()

        # Build a redacted summary memory.
        summary = self._build_summary(signal, raw)
        redacted = pii.redact.redact_pii(summary, context="lead_enrichment")

        memory = Memory(
            workspace_id=workspace_id,
            client_id=client_id,
            created_by_id=None,
            type=MemoryType.SEMANTIC,
            content=redacted.text,
            embedding=[0.0] * config.embedding_model_instance.dimension,
            source_type=MemorySourceType.SIGNAL,
            source_uuid=signal.id,
            source_entity_type="SignalEvent",
            source_capability=f"{signal_type}.signal",
            source_input=input.model_dump(),
            tags=["lead_signal"],
            confidence=signal.confidence,
        )
        session.add(memory)

        # For now signal scans do not use a separate LLM charge.
        # TokenUsage for "llm_reasoning" is recorded only if a summariser is added.

        return signal

    def _build_summary(self, signal: SignalEvent, raw: dict[str, Any]) -> str:
        """Create a human-readable (but not PII-laden) signal summary."""
        if signal.signal_type == "funding":
            funding_total = raw.get("funding_total")
            announced_on = raw.get(
                "announced_on", signal.detected_at.date().isoformat()
            )
            total_str = f" ${funding_total:,.0f}" if funding_total else ""
            return (
                f"{signal.company_name} raised{total_str} in funding on {announced_on}."
            )
        if signal.signal_type == "hiring":
            count = raw.get("job_count", 0)
            return f"{signal.company_name} has {count} open roles."
        if signal.signal_type == "tech_stack":
            techs = raw.get("tech_stack", [])
            return f"{signal.company_name} site signals tech stack: {', '.join(techs[:10])}."
        if signal.signal_type == "news":
            return raw.get("summary") or f"{signal.company_name} mentioned in news."
        if signal.signal_type == "executive_move":
            return (
                raw.get("summary")
                or f"{signal.company_name} executive change detected."
            )
        return f"{signal.company_name} {signal.signal_type} signal."

    async def _detect_funding(
        self, input: SignalInput
    ) -> tuple[list[dict[str, Any]], list[str]]:
        reasons: list[str] = []
        if not config.CRUNCHBASE_API_KEY:
            reasons.append("crunchbase_api_key_missing")
            return [
                {
                    "company_name": input.company_name,
                    "confidence": 0.0,
                    "source_url": None,
                }
            ], reasons

        url = (
            "https://api.crunchbase.com/api/v4/searches/organizations"
            f"?query={input.company_name}"
            "&field_ids=funding_total,announced_on,website_url"
        )
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    url,
                    headers={"X-cb-user-key": config.CRUNCHBASE_API_KEY},
                )
        except httpx.TimeoutException:
            reasons.append("crunchbase.timeout")
            return [], reasons
        except Exception as exc:
            reasons.append(f"crunchbase.error: {exc}")
            return [], reasons

        if resp.status_code >= 500:
            reasons.append("crunchbase.5xx")
            return [], reasons
        if resp.status_code != 200:
            reasons.append(f"crunchbase.http_{resp.status_code}")
            return [], reasons

        try:
            data = resp.json()
        except Exception as exc:
            reasons.append(f"crunchbase.json_error: {exc}")
            return [], reasons

        items: list[dict[str, Any]]
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            if "entities" in data:
                items = data["entities"]
            elif "items" in data:
                items = data["items"]
            else:
                items = []
        else:
            items = []

        # Convert confidence to a normalized 0-100 float.
        results: list[dict[str, Any]] = []
        for item in items:
            results.append(
                {
                    "company_name": item.get("name", input.company_name),
                    "funding_total": item.get("funding_total"),
                    "announced_on": item.get("announced_on"),
                    "source_url": item.get("source_url") or item.get("website_url"),
                    "confidence": float(item.get("confidence", 85.0)),
                }
            )
        return results, reasons

    async def _detect_hiring(
        self, input: SignalInput, ctx: Any
    ) -> tuple[list[dict[str, Any]], list[str]]:
        reasons: list[str] = []
        try:
            from app.services.jobs_aggregator import aggregate_jobs

            job_input = VnJobAggregateInput(keyword=input.company_name)
            raw = await asyncio.wait_for(aggregate_jobs(job_input, ctx), timeout=2.0)
        except TimeoutError:
            reasons.append("hiring.aggregate_timeout")
            return [], reasons
        except Exception as exc:
            logger.exception("hiring detection failed for %s", input.company_name)
            reasons.append(f"hiring.aggregate_error: {exc}")
            return [], reasons

        if raw is None:
            return [], reasons

        if isinstance(raw, dict):
            degraded = raw.get("degraded", False)
            if degraded:
                reasons.extend(raw.get("degradation_reasons", []))
                return [], reasons
            source_items = raw.get("items", [])
        else:
            source_items = getattr(raw, "items", [])
            if getattr(raw, "degraded", False):
                reasons.extend(getattr(raw, "degradation_reasons", []) or [])
                return [], reasons

        results: list[dict[str, Any]] = []
        for listing in source_items:
            if isinstance(listing, dict):
                company = listing.get("company_name") or input.company_name
                results.append(
                    {
                        "company_name": company,
                        "job_count": 1,
                        "source_url": listing.get("source_url") or listing.get("url"),
                        "confidence": float(listing.get("confidence_score", 70.0)),
                    }
                )
            else:
                results.append(
                    {
                        "company_name": getattr(
                            listing, "company_name", input.company_name
                        ),
                        "job_count": 1,
                        "source_url": getattr(listing, "source_url", None),
                        "confidence": float(getattr(listing, "confidence_score", 70.0)),
                    }
                )
        return results, reasons

    async def _detect_tech_stack(
        self, input: SignalInput
    ) -> tuple[list[dict[str, Any]], list[str]]:
        reasons: list[str] = []
        domain = (
            input.domain or f"https://{input.company_name.lower().replace(' ', '')}.com"
        )
        if not domain.startswith(("http://", "https://")):
            domain = f"https://{domain}"

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(domain)
        except httpx.TimeoutException:
            reasons.append("website.timeout")
            return [], reasons
        except Exception as exc:
            reasons.append(f"website.error: {exc}")
            return [], reasons

        if resp.status_code >= 500:
            reasons.append("website.5xx")
            return [], reasons
        if resp.status_code != 200:
            reasons.append(f"website.http_{resp.status_code}")
            return [], reasons

        # Naive tech-stack keyword scan.
        html = resp.text.lower()
        techs: list[str] = []
        for tech in [
            "react",
            "next.js",
            "vue",
            "angular",
            "django",
            "fastapi",
            "flask",
            "spring",
            "laravel",
            "node.js",
            "python",
            "go",
            "rust",
            "php",
            "java",
            "kotlin",
            "swift",
        ]:
            if tech in html:
                techs.append(tech)

        return [
            {
                "company_name": input.company_name,
                "tech_stack": techs,
                "source_url": str(resp.url),
                "confidence": 60.0 if techs else 0.0,
            }
        ], reasons

    async def _detect_news(
        self, input: SignalInput
    ) -> tuple[list[dict[str, Any]], list[str]]:
        reasons: list[str] = []
        if not config.NEWSAPI_KEY:
            reasons.append("newsapi_api_key_missing")
            return [
                {
                    "company_name": input.company_name,
                    "confidence": 0.0,
                    "source_url": None,
                }
            ], reasons

        from urllib.parse import quote

        url = (
            "https://newsapi.org/v2/everything"
            f"?q={quote(input.company_name)}"
            f"&apiKey={config.NEWSAPI_KEY}"
            f"&from={datetime.now(UTC) - timedelta(days=input.lookback_days):%Y-%m-%d}"
        )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
        except httpx.TimeoutException:
            reasons.append("newsapi.timeout")
            return [], reasons
        except Exception as exc:
            reasons.append(f"newsapi.error: {exc}")
            return [], reasons

        if resp.status_code >= 500:
            reasons.append("newsapi.5xx")
            return [], reasons
        if resp.status_code != 200:
            reasons.append(f"newsapi.http_{resp.status_code}")
            return [], reasons

        try:
            data = resp.json()
        except Exception as exc:
            reasons.append(f"newsapi.json_error: {exc}")
            return [], reasons

        articles = data.get("articles", []) if isinstance(data, dict) else []
        results: list[dict[str, Any]] = []
        for article in articles:
            if not isinstance(article, dict):
                continue
            results.append(
                {
                    "company_name": input.company_name,
                    "summary": article.get("description") or article.get("title", ""),
                    "source_url": article.get("url"),
                    "confidence": 75.0,
                }
            )
        return results, reasons

    async def _detect_executive_move(
        self, input: SignalInput
    ) -> tuple[list[dict[str, Any]], list[str]]:
        if not config.SIGNAL_EXECUTIVE_MOVE_ENABLED:
            return (
                [],
                ["executive_move deferred pending ToS review"],
            )
        # Placeholder: real implementation requires LinkedIn/company-page scraping.
        return [
            {
                "company_name": input.company_name,
                "confidence": 0.0,
                "source_url": None,
            }
        ], []
