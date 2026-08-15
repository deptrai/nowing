"""Contact enrichment service (Story 21.3, Task 3).

``EnrichmentService.enrich`` is the synchronous entry point (REST/MCP): it
checks tenant scope, wallet balance and the Redis cache, then creates an
``EnrichmentRequest`` and enqueues ``enrich_lead_task``. The actual provider
waterfall runs asynchronously in ``_run_waterfall`` (Celery worker) so the
request can be returned as ``202 Accepted`` immediately (AC-1).
"""

from __future__ import annotations

import json
import logging
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.canonical.tenant_context import set_request_tenant_context
from app.capabilities.core.types import CapabilityContext
from app.config import config
from app.db import (
    EnrichmentRequest,
    Lead,
    MemorySourceType,
    MemoryType,
    VerifiedContact,
    Workspace,
)
from app.lead_intelligence.enrichment import cache as enrichment_cache
from app.lead_intelligence.enrichment.fallback import FallbackVerifier
from app.lead_intelligence.enrichment.providers import run_waterfall
from app.lead_intelligence.enrichment.schemas import EnrichmentOutput
from app.services import wallet_credit
from app.services.billing_event_service import BillingEventService
from app.services.memory.repository import MemoryRepository
from app.services.pii.redact import redact_pii
from app.services.pii.verified_contact_encryption import (
    VerifiedContactDict,
    VerifiedContactEncryption,
)

logger = logging.getLogger(__name__)


class EnrichmentService:
    """Create, process and cache contact-enrichment requests."""

    def __init__(self) -> None:
        self.billing = BillingEventService()
        self.cipher = VerifiedContactEncryption()

    async def enrich(
        self,
        session: AsyncSession,
        ctx: CapabilityContext,
        lead_id: UUID,
        requested_count: int = 5,
    ) -> EnrichmentOutput:
        """Enqueue enrichment for one lead (AC-1/AC-5/AC-9/AC-10)."""
        await set_request_tenant_context(
            session,
            workspace_id=ctx.workspace_id,
            client_id=getattr(ctx, "client_id", None) or None,
        )
        workspace = await session.get(Workspace, ctx.workspace_id)
        if workspace is None:
            return self._degraded(["workspace_not_found"])

        client_id = getattr(ctx, "client_id", None) or None
        lead = await self._fetch_lead(session, ctx.workspace_id, client_id, lead_id)
        if lead is None:
            return self._degraded(["lead_not_found"])

        cached_ids = enrichment_cache.get_cached_contact_ids(
            ctx.workspace_id, client_id, lead_id
        )
        if cached_ids is not None:
            contacts = await self._fetch_contacts_by_ids(
                session, ctx.workspace_id, client_id, cached_ids
            )
            return EnrichmentOutput(
                enrichment_request_id=None,
                lead_id=lead_id,
                contact_count=len(contacts),
                cost_micros=0,
                verified_contact_ids=[c.id for c in contacts],
                degraded=False,
                status="completed",
            )

        total_cost = self._estimated_cost(requested_count)
        try:
            await wallet_credit.check_balance(
                session,
                user_id=workspace.user_id,
                required_micros=total_cost,
            )
        except wallet_credit.InsufficientCreditsError:
            return self._degraded(["insufficient_wallet"])
        except Exception as exc:  # pragma: no cover - wallet is external
            logger.warning("enrichment wallet check failed: %s", exc)
            return self._degraded(["wallet_check_failed"])

        request = EnrichmentRequest(
            id=uuid4(),
            workspace_id=ctx.workspace_id,
            client_id=client_id,
            lead_id=lead_id,
            status="pending",
            provider_results={},
            cost_micros=0,
            contact_count=0,
            requested_count=requested_count,
        )
        session.add(request)
        await session.flush()

        reasons: list[str] = []
        inline_status: str | None = None  # pragma: no mutate
        try:
            await self._enqueue(request.id, ctx.workspace_id, client_id)
        except Exception as exc:  # pragma: no cover - celery may be absent
            logger.warning("enrichment task enqueue failed: %s", exc)
            try:
                inline_output = await self._run_waterfall(session, request.id)
                inline_status = inline_output.status
            except Exception as inline_exc:  # pragma: no cover - provider error
                logger.exception(
                    "inline enrichment failed for request %s: %s",
                    request.id,
                    inline_exc,
                )
                await self._mark_failed(
                    session, request.id, ctx.workspace_id, client_id
                )
                inline_status = "failed"
            reasons.append("celery_unavailable")
        else:
            await session.commit()

        return EnrichmentOutput(
            enrichment_request_id=request.id,
            lead_id=lead_id,
            contact_count=0,
            cost_micros=0,
            verified_contact_ids=[],
            degraded=bool(reasons),
            degradation_reasons=reasons,
            status=inline_status if reasons else "pending",
        )

    async def _run_waterfall(
        self,
        session: AsyncSession,
        request_id: UUID,
    ) -> EnrichmentOutput:
        """Run the provider waterfall for a pending request (Task 3.1)."""
        request = await session.get(EnrichmentRequest, request_id)
        if request is None:
            return self._degraded(["request_not_found"])
        await set_request_tenant_context(
            session,
            workspace_id=request.workspace_id,
            client_id=request.client_id,
        )

        request.status = "processing"
        await session.flush()

        lead = await session.get(Lead, request.lead_id)
        if lead is None:
            request.status = "completed"
            request.provider_results = {
                "provider": "none",
                "degraded": True,
                "reasons": ["lead_not_found"],
            }
            await session.flush()
            await session.commit()
            return self._degraded(["lead_not_found"])

        workspace = await session.get(Workspace, request.workspace_id)
        owner_user_id = workspace.user_id if workspace is not None else None

        contacts, provider = await run_waterfall(lead, request.requested_count)
        reasons: list[str] = []

        if not contacts:
            fallback = FallbackVerifier()
            contacts = await fallback.find_contacts(lead, request.requested_count)
            if contacts:
                provider = "fallback"
            else:
                reasons.append("provider_unavailable")
                reasons.append("fallback_no_results")

        if not contacts:
            request.status = "completed"
            request.provider_results = {
                "provider": "none",
                "degraded": True,
                "reasons": reasons,
            }
            await session.flush()
            await session.commit()
            return self._degraded(reasons)

        created_count = min(len(contacts), request.requested_count)
        cost_micros = self._estimated_cost(created_count)
        contact_ids: list[UUID] = []
        lead_consent_status, lead_legal_basis = lead.consent_status, lead.legal_basis
        for item in contacts[:created_count]:
            encrypted = self.cipher.encrypt_contact(item)
            consent_status = item.get("consent_status") or lead_consent_status
            legal_basis = item.get("legal_basis") or lead_legal_basis
            if lead_consent_status is None and consent_status is not None:
                lead_consent_status = consent_status
                lead_legal_basis = legal_basis
            contact = VerifiedContact(
                id=uuid4(),
                workspace_id=request.workspace_id,
                client_id=request.client_id,
                lead_id=request.lead_id,
                enrichment_request_id=request.id,
                name=encrypted.get("name"),
                title=encrypted.get("title"),
                email=encrypted.get("email"),
                phone=encrypted.get("phone"),
                verification_status=item.get("verification_status", "unverified"),
                confidence=item.get("confidence", 0.0),
                source_provider=item.get("source_provider", provider),
                consent=consent_status == "explicit",
                consent_status=consent_status,
                legal_basis=legal_basis,
            )
            session.add(contact)
            await session.flush()
            contact_ids.append(contact.id)

        request.status = "completed"
        request.contact_count = len(contact_ids)
        request.cost_micros = cost_micros
        request.provider_results = self._redacted_results(provider, reasons, contacts)
        await session.flush()

        lead.enriched = True
        lead.consent_status = lead_consent_status
        lead.legal_basis = lead_legal_basis

        try:
            await self._record_billing(
                session,
                enrichment_request_id=request.id,
                workspace_id=request.workspace_id,
                client_id=request.client_id,
                user_id=owner_user_id,
                cost_micros=cost_micros,
            )
        except Exception as exc:  # pragma: no cover - wallet is external
            logger.exception(
                "billing failed for enrichment request %s: %s", request.id, exc
            )
            session.add(request)
            request.status = "failed"
            request.provider_results = self._redacted_results(
                provider, ["billing_failed"], contacts
            )
            await session.flush()
            await session.commit()
            return self._degraded(["billing_failed"])

        await self._write_memory(session, request, contacts, owner_user_id)

        enrichment_cache.set_cached_contact_ids(
            request.workspace_id,
            request.client_id,
            request.lead_id,
            contact_ids,
        )
        await session.commit()

        return EnrichmentOutput(
            enrichment_request_id=request.id,
            lead_id=request.lead_id,
            contact_count=len(contact_ids),
            cost_micros=cost_micros,
            verified_contact_ids=contact_ids,
            degraded=False,
            degradation_reasons=[],
            status="completed",
        )

    async def get_contacts(
        self,
        session: AsyncSession,
        *,  # pragma: no mutate
        workspace_id: int,
        client_id: str | None,  # pragma: no mutate  # pragma: no mutate
        lead_id: UUID,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[VerifiedContact]:
        """Return decrypted verified contacts for a lead (AC-6)."""
        await set_request_tenant_context(
            session, workspace_id=workspace_id, client_id=client_id
        )
        stmt = select(VerifiedContact).where(
            VerifiedContact.workspace_id == workspace_id,
            VerifiedContact.lead_id == lead_id,
        )
        if client_id is not None:
            stmt = stmt.where(VerifiedContact.client_id == client_id)
        stmt = (
            stmt.order_by(VerifiedContact.created_at.desc()).offset(offset).limit(limit)
        )
        result = await session.execute(stmt)
        contacts = list(result.scalars().all())
        return [self._decrypt_contact(c) for c in contacts]

    async def list_enrichment_requests(
        self,
        session: AsyncSession,
        *,  # pragma: no mutate
        workspace_id: int,
        client_id: str | None,  # pragma: no mutate
        lead_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EnrichmentRequest]:
        """List enrichment requests for one lead (newest first, AC-8)."""
        await set_request_tenant_context(
            session, workspace_id=workspace_id, client_id=client_id
        )
        stmt = select(EnrichmentRequest).where(
            EnrichmentRequest.workspace_id == workspace_id,
            EnrichmentRequest.lead_id == lead_id,
        )
        if client_id is not None:
            stmt = stmt.where(EnrichmentRequest.client_id == client_id)
        stmt = (
            stmt.order_by(EnrichmentRequest.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _mark_failed(
        self,
        session: AsyncSession,
        request_id: UUID | str,
        workspace_id: int,
        client_id: str | None,  # pragma: no mutate
    ) -> None:
        """Mark a request ``failed`` and persist (unhandled task errors)."""
        # Rollback clears the transaction-scoped tenant GUCs, so the context
        # must be restored before the request row can be read under RLS.
        await session.rollback()
        await set_request_tenant_context(
            session, workspace_id=workspace_id, client_id=client_id
        )
        request = await session.get(EnrichmentRequest, request_id)
        if request is None:
            return
        request.status = "failed"
        await session.commit()

    async def _fetch_lead(
        self,
        session: AsyncSession,
        workspace_id: int,
        client_id: str | None,  # pragma: no mutate
        lead_id: UUID,
    ) -> Lead | None:  # pragma: no mutate
        stmt = select(Lead).where(
            Lead.workspace_id == workspace_id,
            Lead.id == lead_id,
        )
        if client_id is not None:
            stmt = stmt.where(Lead.client_id == client_id)
        return (await session.execute(stmt)).scalar_one_or_none()

    async def _fetch_contacts_by_ids(
        self,
        session: AsyncSession,
        workspace_id: int,
        client_id: str | None,  # pragma: no mutate
        contact_ids: list[UUID],
    ) -> list[VerifiedContact]:
        if not contact_ids:
            return []
        stmt = select(VerifiedContact).where(
            VerifiedContact.workspace_id == workspace_id,
            VerifiedContact.id.in_(contact_ids),
        )
        if client_id is not None:
            stmt = stmt.where(VerifiedContact.client_id == client_id)
        return list((await session.execute(stmt)).scalars().all())

    async def _enqueue(
        self,
        request_id: UUID,
        workspace_id: int,
        client_id: str | None,  # pragma: no mutate
    ) -> None:
        from app.tasks.celery_tasks.enrichment_tasks import enrich_lead_task

        enrich_lead_task.delay(str(request_id), workspace_id, client_id)

    async def _record_billing(
        self,
        session: AsyncSession,
        *,  # pragma: no mutate
        enrichment_request_id: UUID,
        workspace_id: int,
        client_id: str | None,  # pragma: no mutate
        user_id: UUID | None,  # pragma: no mutate
        cost_micros: int,
    ) -> None:
        if user_id is None:
            return
        try:
            await self.billing.record_contact_enrichment(
                session,
                enrichment_request_id=enrichment_request_id,
                workspace_id=workspace_id,
                client_id=client_id,
                user_id=user_id,
                cost_micros=cost_micros,
            )
        except Exception as exc:
            logger.exception(
                "failed to record contact enrichment billing for %s: %s",
                enrichment_request_id,
                exc,
            )
            await session.rollback()
            # Rollback clears the transaction-scoped tenant GUCs; restore them
            # so the caller can re-attach the request row under RLS.
            await set_request_tenant_context(
                session, workspace_id=workspace_id, client_id=client_id
            )
            raise

    async def _write_memory(
        self,
        session: AsyncSession,
        request: EnrichmentRequest,
        contacts: list[VerifiedContactDict],
        user_id: UUID | None = None,  # pragma: no mutate
    ) -> None:
        raw_summary = json.dumps(
            {
                "lead_id": str(request.lead_id),
                "provider": contacts[0].get("source_provider", "unknown")
                if contacts
                else "none",
                "contact_count": len(contacts),
                "confidence": (
                    round(
                        sum(float(c.get("confidence") or 0.0) for c in contacts)
                        / len(contacts),
                        4,
                    )
                    if contacts
                    else 0.0
                ),
            },
            default=str,
            ensure_ascii=False,
        )
        redacted = redact_pii(raw_summary, context="lead_enrichment")

        repo = MemoryRepository(session)
        await repo.create_memory(
            workspace_id=request.workspace_id,
            content=redacted.text,
            type=MemoryType.SEMANTIC,
            source_type=MemorySourceType.ENRICHMENT,
            source_uuid=request.id,
            source_entity_type="enrichment_request",
            tags=["enriched_contact"],
            confidence=0.9,
            created_by_id=user_id,
            client_id=request.client_id,
        )

    def _redacted_results(
        self,
        provider: str,
        reasons: list[str],
        contacts: list[VerifiedContactDict],
    ) -> dict:
        raw = json.dumps(
            {
                "provider": provider,
                "degraded": bool(reasons),
                "reasons": reasons,
                "contact_count": len(contacts),
            },
            default=str,
            ensure_ascii=False,
        )
        redacted = redact_pii(raw, context="lead_enrichment")
        try:
            return json.loads(redacted.text)
        except (ValueError, TypeError):
            return {"provider": provider, "degraded": bool(reasons), "reasons": reasons}

    def _decrypt_contact(self, contact: VerifiedContact) -> VerifiedContact:
        try:
            decrypted = self.cipher.decrypt_contact(
                {
                    "name": contact.name,
                    "title": contact.title,
                    "email": contact.email,
                    "phone": contact.phone,
                }
            )
            contact.name = decrypted.get("name")
            contact.title = decrypted.get("title")
            contact.email = decrypted.get("email")
            contact.phone = decrypted.get("phone")
        except Exception as exc:  # pragma: no cover - corruption in DB
            logger.exception(
                "failed to decrypt verified contact %s: %s", contact.id, exc
            )
            contact.name = None
            contact.title = None
            contact.email = None
            contact.phone = None
        return contact

    def _estimated_cost(self, contact_count: int) -> int:
        capped = min(contact_count, config.CONTACT_ENRICHMENT_MAX_CONTACTS_PER_LEAD)
        return int(config.CONTACT_ENRICHMENT_MICROS_PER_CONTACT or 0) * capped

    @staticmethod
    def _degraded(reasons: list[str]) -> EnrichmentOutput:
        return EnrichmentOutput(
            enrichment_request_id=None,
            lead_id=None,
            contact_count=0,
            cost_micros=0,
            verified_contact_ids=[],
            degraded=True,
            degradation_reasons=reasons,
            status="failed",
        )
