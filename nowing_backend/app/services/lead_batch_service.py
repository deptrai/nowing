"""Batch lead ingestion service (Story 26.1).

Thin wrapper around existing lead-stream upsert and DNC compliance.
All heavy lifting (HMAC, DNC, pg_insert ON CONFLICT) is delegated to
``lead_stream_service.build_lead_upsert_stmt`` and
``DncComplianceService.batch_filter_leads``.
"""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import case, not_, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.config import config
from app.db import Lead, VerifiedContact
from app.lead_intelligence.dnc.normalizer import (
    compute_email_hmac,
    compute_phone_hmac,
    compute_verified_contact_hmac,
    normalize_domain,
    normalize_email,
    normalize_phone_e164,
)
from app.lead_intelligence.dnc.service import DncComplianceService
from app.lead_intelligence.services.lead_stream_service import generate_lead_hmac
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption

logger = logging.getLogger(__name__)


class LeadItemValidationError(ValueError):
    """Raised when a batch item is degenerate or malformed."""


def _reject_degenerate_leads(leads: list[dict[str, Any]]) -> None:
    for idx, lead in enumerate(leads):
        if not any(
            lead.get(field) for field in ("phone", "email", "domain", "company_name")
        ):
            raise LeadItemValidationError(
                f"Lead at index {idx} is degenerate: phone, email, domain and company_name are all empty"
            )


def _truncate_bytes(value: str | None, max_bytes: int) -> str:
    """Truncate a string so its UTF-8 encoded form fits within ``max_bytes``."""
    if not value:
        return ""
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def _clamp_encrypted(value: str | None, max_bytes: int) -> str | None:
    """Clamp an already-encrypted token so it fits a fixed-width DB column.

    Encrypted values (Fernet base64 tokens) can exceed the declared width when
    the plaintext is long. This is a fail-closed regression guard: a truncated
    encrypted token will not decrypt, but it prevents a ``StringDataRight
    TruncationError`` from killing the batch ingest.
    """
    if not value:
        return value
    return _truncate_bytes(value, max_bytes)


def _prepare_lead_record(
    workspace_id: int,
    item: dict[str, Any],
    secret_key: str,
) -> dict[str, Any]:
    """Return a lead dict with the existing stream-compatible ``value_hmac``."""
    company = _truncate_bytes(
        item.get("company_name") or item.get("title") or "Doanh nghiệp", 70
    )
    domain = normalize_domain(item.get("domain"))
    value_hmac = item.get("value_hmac") or generate_lead_hmac(
        workspace_id, company, domain
    )

    return {
        "id": uuid4(),
        "workspace_id": workspace_id,
        "client_id": item.get("client_id") or None,
        "table_id": item.get("table_id"),
        "source": item.get("source", "batch_ingest"),
        "source_url": item.get("source_url"),
        "company_name": company,
        "domain": domain,
        "industry": item.get("industry"),
        "company_size": item.get("company_size"),
        "location": item.get("location"),
        "fit_score": item.get("fit_score", 0.0),
        "intent_score": item.get("intent_score", 0.0),
        "composite_score": item.get("composite_score"),
        "schema_completeness_score": item.get("schema_completeness_score"),
        "needs_enrichment": item.get("needs_enrichment", False),
        "area": item.get("area"),
        "status": item.get("status", "new"),
        "value_hmac": value_hmac,
        "phone": item.get("phone"),
        "email": item.get("email"),
        "tax_id": item.get("tax_id"),
    }


def _build_batch_upsert_stmt(leads: list[dict[str, Any]]) -> Any:
    """Build deterministic, deadlock-free bulk upsert for ``leads``.

    In-memory dedup by (workspace_id, value_hmac) and sorted by value_hmac ASC
    before lock acquisition.
    """
    if not leads:
        return None

    unique: dict[tuple[int, str], dict[str, Any]] = {}
    for lead in leads:
        key = (lead["workspace_id"], lead["value_hmac"])
        existing = unique.get(key)
        if existing is None:
            unique[key] = lead
        else:
            # Keep the record with the higher fit_score on conflict
            if (lead.get("fit_score") or 0) > (existing.get("fit_score") or 0):
                unique[key] = lead

    sorted_leads = sorted(unique.values(), key=lambda x: x["value_hmac"])

    # Only keep columns that exist on ``Lead``; phone/email are stored in
    # ``verified_contacts``.
    lead_columns = set(Lead.__table__.columns.keys())
    lead_rows = [
        {k: v for k, v in lead.items() if k in lead_columns} for lead in sorted_leads
    ]

    stmt = pg_insert(Lead).values(lead_rows)
    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=["workspace_id", "value_hmac"],
        set_={
            "fit_score": func.greatest(Lead.fit_score, stmt.excluded.fit_score),
            "composite_score": func.greatest(
                func.coalesce(Lead.composite_score, 0),
                func.coalesce(stmt.excluded.composite_score, 0),
            ),
            "schema_completeness_score": func.greatest(
                func.coalesce(Lead.schema_completeness_score, 0),
                func.coalesce(stmt.excluded.schema_completeness_score, 0),
            ),
            "needs_enrichment": func.coalesce(
                stmt.excluded.needs_enrichment, Lead.needs_enrichment
            ),
            "area": func.coalesce(stmt.excluded.area, Lead.area),
            "company_name": stmt.excluded.company_name,
            "domain": stmt.excluded.domain,
            "client_id": stmt.excluded.client_id,
            "table_id": func.coalesce(stmt.excluded.table_id, Lead.table_id),
            "source_url": func.coalesce(stmt.excluded.source_url, Lead.source_url),
            "industry": func.coalesce(stmt.excluded.industry, Lead.industry),
            "location": func.coalesce(stmt.excluded.location, Lead.location),
            "intent_score": stmt.excluded.intent_score,
            "status": case(
                (
                    Lead.status.in_(
                        ["blacklisted", "withdrawn", "opted_out", "lost", "won"]
                    ),
                    Lead.status,
                ),
                else_=stmt.excluded.status,
            ),
            "updated_at": func.now(),
        },
    ).returning(Lead.id, Lead.value_hmac)
    return upsert_stmt


def _build_contacts_upsert_stmt(contacts: list[dict[str, Any]]) -> Any:
    """Build deterministic, deadlock-free bulk upsert for ``verified_contacts``.

    In-memory dedup by (workspace_id, value_hmac) and sorted by value_hmac ASC
    before lock acquisition. The DO UPDATE guard refuses to overwrite contacts
    that have been opted out (withdrawn / invalid).
    """
    if not contacts:
        return None

    unique: dict[tuple[int, str], dict[str, Any]] = {}
    for contact in contacts:
        key = (contact["workspace_id"], contact["value_hmac"])
        existing = unique.get(key)
        if existing is None:
            unique[key] = contact
        else:
            # Keep the record with the higher confidence on conflict.
            if (contact.get("confidence") or 0) > (existing.get("confidence") or 0):
                unique[key] = contact

    sorted_contacts = sorted(unique.values(), key=lambda x: x["value_hmac"])

    stmt = pg_insert(VerifiedContact).values(sorted_contacts)
    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=["workspace_id", "value_hmac"],
        set_={
            "name": stmt.excluded.name,
            "title": stmt.excluded.title,
            "email": stmt.excluded.email,
            "phone": stmt.excluded.phone,
            "phone_hmac": stmt.excluded.phone_hmac,
            "email_hmac": stmt.excluded.email_hmac,
            "external_chat_ids": stmt.excluded.external_chat_ids,
            "confidence": stmt.excluded.confidence,
            "source_provider": stmt.excluded.source_provider,
        },
        where=not_(
            or_(
                VerifiedContact.consent_status == "withdrawn",
                VerifiedContact.is_valid.is_(False),
            )
        ),
    )
    return upsert_stmt


class LeadBatchService:
    """Batch ingestion orchestrator for leads and their PII contacts."""

    def __init__(self) -> None:
        self._cipher = VerifiedContactEncryption()
        self._dnc = DncComplianceService(secret_key=config.SECRET_KEY)

    async def ingest_batch(
        self,
        session: AsyncSession,
        workspace_id: int,
        leads: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Ingest a batch of leads with DNC filtering, dedup, and PII encryption.

        Returns a summary dict matching ``BatchLeadIngestResponse``.
        """
        started_at = time.monotonic()

        _reject_degenerate_leads(leads)

        # 1. Prepare lead records with canonical HMAC
        prepared = [
            _prepare_lead_record(workspace_id, item, config.SECRET_KEY)
            for item in leads
        ]

        # 2. DNC batch check (fail-closed)
        dnc_leads = await self._dnc.batch_filter_leads(
            workspace_id,
            [
                {
                    "phone": p.get("phone"),
                    "email": p.get("email"),
                    "domain": p.get("domain"),
                }
                for p in prepared
            ],
            session=session,
        )

        blocked_hmacs = set()
        non_blocked: list[dict[str, Any]] = []
        for lead, dnc in zip(prepared, dnc_leads, strict=True):
            if dnc.get("blocked_by_dnc"):
                lead["status"] = "blacklisted"
                blocked_hmacs.add(lead["value_hmac"])
            non_blocked.append(lead)

        # 3. Bulk upsert leads (all, including blacklisted)
        upsert_stmt = _build_batch_upsert_stmt(non_blocked)
        hmac_to_id: dict[str, UUID] = {}
        if upsert_stmt is not None:
            result = await session.execute(upsert_stmt)
            for row in result.all():
                hmac_to_id[row.value_hmac] = row.id

        # 4. Insert encrypted verified_contacts for non-blacklisted leads
        contacts_to_insert: list[dict[str, Any]] = []
        for lead, dnc in zip(prepared, dnc_leads, strict=True):
            if dnc.get("blocked_by_dnc"):
                continue
            lead_id = hmac_to_id.get(lead["value_hmac"])
            if lead_id is None:
                continue
            if not any(
                [lead.get("phone"), lead.get("email"), lead.get("external_chat_ids")]
            ):
                continue

            domain = lead.get("domain")
            contact_hmac = compute_verified_contact_hmac(
                lead.get("phone"),
                lead.get("email"),
                domain,
                company_name=lead.get("company_name"),
            )
            if contact_hmac is None:
                # Degenerate: no phone, email, or domain to deduplicate by.
                continue

            # Encrypt additional chat/social handles while preserving structure.
            raw_external_chat_ids = lead.get("external_chat_ids") or {}
            encrypted_external_chat_ids = {
                channel: _clamp_encrypted(self._cipher.encrypt(value), 500)
                for channel, value in raw_external_chat_ids.items()
                if value
            }

            contact_name = _truncate_bytes(
                lead.get("contact_name") or lead.get("company_name") or "", 70
            )
            contact_title = _truncate_bytes(lead.get("title") or "", 70)
            contact_email = _truncate_bytes(lead.get("email") or "", 70)
            contact_phone = _truncate_bytes(lead.get("phone") or "", 30)
            contact = {
                "id": uuid4(),
                "workspace_id": workspace_id,
                "client_id": lead.get("client_id"),
                "lead_id": lead_id,
                "name": _clamp_encrypted(self._cipher.encrypt(contact_name), 200),
                "title": _clamp_encrypted(self._cipher.encrypt(contact_title), 200),
                "email": _clamp_encrypted(self._cipher.encrypt(contact_email), 255) if contact_email else None,
                "phone": _clamp_encrypted(self._cipher.encrypt(contact_phone), 200) if contact_phone else None,
                "verification_status": "verified",
                "confidence": 0.0,
                "source_provider": "batch_ingest",
                "consent": True,
                "consent_status": "legitimate_interest",
                "legal_basis": "legitimate_interest",
                "is_valid": True,
                "is_unlocked": False,
                "pii_access_audit_logs": [],
                "value_hmac": contact_hmac,
                "phone_hmac": compute_phone_hmac(
                    normalize_phone_e164(lead.get("phone"))
                ),
                "email_hmac": compute_email_hmac(normalize_email(lead.get("email"))),
                "external_chat_ids": encrypted_external_chat_ids,
            }
            contacts_to_insert.append(contact)

        if contacts_to_insert:
            contact_upsert = _build_contacts_upsert_stmt(contacts_to_insert)
            if contact_upsert is not None:
                await session.execute(contact_upsert)

        execution_time_ms = (time.monotonic() - started_at) * 1000

        accepted = [not dnc.get("blocked_by_dnc") for dnc in dnc_leads]
        accepted_lead_ids = [
            hmac_to_id[lead["value_hmac"]]
            for lead, dnc, ok in zip(prepared, dnc_leads, accepted, strict=True)
            if ok and lead["value_hmac"] in hmac_to_id
        ]

        return {
            "ingested_count": len(prepared) - len(blocked_hmacs),
            "skipped_blacklisted_count": len(blocked_hmacs),
            "failed_count": 0,
            "execution_time_ms": execution_time_ms,
            "lead_ids": list(hmac_to_id.values()),
            "lead_id_mapping": hmac_to_id,
            # ponytail: downstream orchestrators need these to filter response
            # without recomputing HMACs. Not part of the public API response.
            "blocked_hmacs": blocked_hmacs,
            "accepted_lead_ids": accepted_lead_ids,
            "accepted": accepted,
        }
