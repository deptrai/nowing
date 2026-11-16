"""Batch lead ingestion service (Story 26.1).

Thin wrapper around existing lead-stream upsert and DNC compliance.
All heavy lifting (HMAC, DNC, pg_insert ON CONFLICT) is delegated to
``lead_stream_service.build_lead_upsert_stmt`` and
``DncComplianceService.batch_filter_leads``.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import case, not_, or_, select, text
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
from app.models.workspaces import VerticalClient, WorkspaceTable
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption

logger = logging.getLogger(__name__)


class LeadItemValidationError(ValueError):
    """Raised when a batch item is degenerate or malformed.

    Carries the structured reject-all payload so callers can return
    ``{status:'failed', rejected_indexes:[...], reason_map:{idx: reason}}``
    without re-deriving which rows failed.
    """

    def __init__(
        self,
        message: str,
        *,
        rejected_indexes: list[int] | None = None,
        reason_map: dict[int, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.rejected_indexes = rejected_indexes or []
        self.reason_map = reason_map or {}

    def as_payload(self) -> dict[str, Any]:
        return {
            "status": "failed",
            "rejected_indexes": list(self.rejected_indexes),
            "reason_map": {
                str(idx): reason for idx, reason in self.reason_map.items()
            },
        }


def _reject_degenerate_leads(leads: list[dict[str, Any]]) -> None:
    """Reject the whole batch when any lead is degenerate (collect-all).

    A lead with no phone, email, domain and company_name carries no
    dedupe key, so letting the rest of the batch through would silently drop
    rows. Collect every failing index and reject-all (AD-4).
    """
    reason_map: dict[int, str] = {}
    for idx, lead in enumerate(leads):
        if not any(
            lead.get(field) for field in ("phone", "email", "domain", "company_name")
        ):
            reason_map[idx] = (
                "degenerate lead: phone, email, domain and company_name are all empty"
            )
    if reason_map:
        raise LeadItemValidationError(
            "Batch rejected: "
            f"{len(reason_map)} degenerate lead(s) at indexes "
            f"{sorted(reason_map)}",
            rejected_indexes=sorted(reason_map),
            reason_map=reason_map,
        )


def _prepare_lead_record(
    workspace_id: int,
    item: dict[str, Any],
    secret_key: str,
) -> dict[str, Any]:
    """Return a lead dict with the existing stream-compatible ``value_hmac``."""
    company = item.get("company_name") or item.get("title") or "Doanh nghiệp"
    domain = normalize_domain(item.get("domain"))
    value_hmac = item.get("value_hmac") or generate_lead_hmac(
        workspace_id, company, domain
    )

    extra_metadata = item.get("extra_metadata")
    if extra_metadata is None:
        extra_metadata = item.get("metadata") or {}

    # Story 42.7: ``save_leads`` passes ``table_id`` as a str UUID — coerce
    # valid str UUIDs so the Never rule (valid caller table preserved) covers
    # that path; invalid values are treated as absent → default table.
    raw_table_id = item.get("table_id")
    table_id: UUID | str | None = raw_table_id
    if isinstance(raw_table_id, str) and raw_table_id:
        try:
            table_id = UUID(raw_table_id)
        except ValueError:
            table_id = None

    return {
        "id": uuid4(),
        "workspace_id": workspace_id,
        # Normalize: non-str / empty client_id would break grouping + key DDL.
        "client_id": str(item.get("client_id") or "default"),
        "table_id": table_id,
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
        "extra_metadata": extra_metadata,
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
            # JSONB top-level merge: excluded keys win, existing keys preserved.
            # Plain coalesce(excluded, existing) would wipe metadata whenever an
            # item carries an empty-or-new dict instead of the full old payload.
            "extra_metadata": func.coalesce(
                Lead.extra_metadata, text("'{}'::jsonb")
            ).concat(func.coalesce(stmt.excluded.extra_metadata, text("'{}'::jsonb"))),
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

    async def _null_nonexistent_client_ids(
        self, session: AsyncSession, contacts: list[dict[str, Any]]
    ) -> None:
        """Null out verified_contacts client_id values missing from vertical_clients.

        Leads may carry synthetic client ids ("default", campaign slugs) while
        verified_contacts enforces an FK on client_id — resolve real ids once
        per batch so a fake id cannot abort the whole insert.
        """
        candidate_ids = {c["client_id"] for c in contacts if c.get("client_id")}
        if not candidate_ids:
            return
        valid_client_ids = set(
            (
                await session.execute(
                    select(VerticalClient.client_id).where(
                        VerticalClient.client_id.in_(candidate_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
        for c in contacts:
            if c["client_id"] not in valid_client_ids:
                c["client_id"] = None

    async def _resolve_lead_table_ids(
        self,
        session: AsyncSession,
        workspace_id: int,
        leads: list[dict[str, Any]],
    ) -> None:
        """Assign a ``table_id`` to every lead row missing a valid one (Story 42.7).

        Leads are grouped by ``client_id``; each group resolves to a default
        ``WorkspaceTable`` keyed ``key = client_id`` (fallback ``"default"``),
        get-or-created race-safe via ``INSERT ... ON CONFLICT (workspace_id,
        key) DO NOTHING`` + re-SELECT. Caller-provided ``table_id`` values are
        preserved when they point at an existing row; stale (deleted) ids fall
        back to the default table instead of crashing the FK.
        """
        if not leads:
            return

        # 1. Which candidate table_ids actually exist? (stale detection)
        candidate_ids = {
            lead["table_id"] for lead in leads if isinstance(lead.get("table_id"), UUID)
        }
        existing_ids: set[UUID] = set()
        if candidate_ids:
            existing_ids = set(
                (
                    await session.execute(
                        select(WorkspaceTable.id).where(
                            WorkspaceTable.id.in_(candidate_ids),
                            WorkspaceTable.workspace_id == workspace_id,
                        )
                    )
                )
                .scalars()
                .all()
            )

        # 2. Group rows needing the default table by client_id. Keys are
        # casefolded so "Acme" and "acme" share one table, and bounded so an
        # arbitrarily long client_id cannot blow past the Text/varchar DDL.
        needs_key: dict[str, list[dict[str, Any]]] = {}
        for lead in leads:
            table_id = lead.get("table_id")
            if isinstance(table_id, UUID) and table_id in existing_ids:
                continue  # valid caller-provided table: keep it (Never rule)
            raw_key = str(lead.get("client_id") or "default").casefold()
            key = (
                raw_key
                if len(raw_key) <= 128
                else hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
            )
            needs_key.setdefault(key, []).append(lead)

        if not needs_key:
            return

        # 3. Which keys already have a default table?
        existing_keys = set(
            (
                await session.execute(
                    select(WorkspaceTable.key).where(
                        WorkspaceTable.workspace_id == workspace_id,
                        WorkspaceTable.key.in_(list(needs_key)),
                    )
                )
            )
            .scalars()
            .all()
        )

        # 4. Get-or-create per missing key (race-safe).
        key_to_id: dict[str, UUID] = {}
        missing_keys = [k for k in needs_key if k not in existing_keys]
        if missing_keys:
            insert_stmt = (
                pg_insert(WorkspaceTable)
                .values(
                    [
                        {
                            "id": uuid4(),
                            "workspace_id": workspace_id,
                            "name": ("Leads" if k == "default" else k)[:200],
                            "key": k,
                        }
                        for k in sorted(missing_keys)
                    ]
                )
                .on_conflict_do_nothing(index_elements=["workspace_id", "key"])
                .returning(WorkspaceTable.id, WorkspaceTable.key)
            )
            result = await session.execute(insert_stmt)
            for row in result.all():
                key_to_id[row.key] = row.id

        # 5. Re-SELECT for rows lost to a concurrent insert (race window).
        unresolved_keys = [k for k in needs_key if k not in key_to_id]
        if unresolved_keys:
            resolved = (
                await session.execute(
                    select(WorkspaceTable.key, WorkspaceTable.id).where(
                        WorkspaceTable.workspace_id == workspace_id,
                        WorkspaceTable.key.in_(unresolved_keys),
                    )
                )
            ).all()
            for row in resolved:
                key_to_id[row.key] = row.id

        default_id = key_to_id.get("default")
        for key, rows in needs_key.items():
            # Unconditional: an unresolved key must never leave a stale (FK
            # dangling) table_id on the row — default (or None) is safer.
            table_id = key_to_id.get(key, default_id)
            for lead in rows:
                lead["table_id"] = table_id

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

        # 1b. DNC batch check (fail-closed)
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

        # 1c. Resolve default tables per client_id AFTER the DNC filter so a
        # fully-blacklisted batch never creates empty WorkspaceTables
        # (absent/stale table_id → get-or-create keyed table, Story 42.7).
        await self._resolve_lead_table_ids(session, workspace_id, non_blocked)

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
            if not any([lead.get("phone"), lead.get("email")]):
                continue

            domain = lead.get("domain")
            contact_hmac = compute_verified_contact_hmac(
                lead.get("phone"), lead.get("email"), domain
            )
            if contact_hmac is None:
                # Degenerate: no phone, email, or domain to deduplicate by.
                continue

            contact = {
                "id": uuid4(),
                "workspace_id": workspace_id,
                "client_id": lead.get("client_id"),
                "lead_id": lead_id,
                "name": self._cipher.encrypt(
                    lead.get("contact_name") or lead.get("company_name")
                ),
                "title": self._cipher.encrypt(lead.get("title")),
                "email": self._cipher.encrypt(lead.get("email")),
                "phone": self._cipher.encrypt(lead.get("phone")),
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
            }
            contacts_to_insert.append(contact)

        if contacts_to_insert:
            await self._null_nonexistent_client_ids(session, contacts_to_insert)

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
