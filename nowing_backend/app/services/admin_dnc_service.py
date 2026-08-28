"""Service for managing Global DNC Blacklist and PII exclusion registry (Story 25.6)."""

from __future__ import annotations

import csv
import io
import logging
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import AuditEvent, GlobalDncRecord
from app.lead_intelligence.dnc.normalizer import (
    hash_phone_hmac,
    normalize_domain,
    normalize_email,
    normalize_phone_e164,
    normalize_tax_id,
)
from app.lead_intelligence.dnc.service import DncComplianceService

logger = logging.getLogger(__name__)

MAX_CSV_ROWS = 50_000


def _mask_value(record_type: str, canonical: str) -> str:
    """Generate masked display representation of sensitive PII."""
    if record_type == "phone":
        # Convert +84908123456 -> 0908 *** 456
        digits = (
            canonical.replace("+84", "0")
            if canonical.startswith("+84")
            else canonical.lstrip("+")
        )
        if len(digits) >= 9:
            return f"{digits[:4]} *** {digits[-3:]}"
        return f"{digits[:2]} *** {digits[-2:]}" if len(digits) > 4 else "***"
    elif record_type == "email":
        parts = canonical.split("@")
        if len(parts) == 2:
            name, domain = parts
            masked_name = f"{name[:2]}***" if len(name) > 2 else f"{name[:1]}***"
            return f"{masked_name}@{domain}"
        return "***@***"
    elif record_type == "tax_id":
        if len(canonical) >= 6:
            return f"{canonical[:3]}***{canonical[-3:]}"
        return f"{canonical[:2]}***"
    return canonical


class AdminDncService:
    """Handles global DNC records querying, insertion, CSV import, and audit logging."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.secret_key = getattr(config, "SECRET_KEY", "")

    def canonicalize_and_hash(
        self, record_type: str, value: str
    ) -> tuple[str, str, str]:
        """Normalize, hash via HMAC-SHA256, and produce display masked value."""
        canonical: str | None = None
        if record_type == "phone":
            canonical = normalize_phone_e164(value)
        elif record_type == "domain":
            canonical = normalize_domain(value)
        elif record_type == "email":
            canonical = normalize_email(value)
        elif record_type == "tax_id":
            canonical = normalize_tax_id(value)

        if not canonical:
            raise ValueError(
                f"Invalid format for {record_type}: value could not be normalized"
            )

        hmac_hash = hash_phone_hmac(canonical, secret_key=self.secret_key)
        masked = _mask_value(record_type, canonical)
        return canonical, hmac_hash, masked

    async def list_global_dnc_records(
        self,
        *,
        record_type: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List global DNC records with pagination and filtering."""
        clamped_limit = max(1, min(200, limit))
        clamped_offset = max(0, offset)

        conditions = []
        if record_type:
            conditions.append(GlobalDncRecord.record_type == record_type)
        if search:
            conditions.append(
                GlobalDncRecord.value.ilike(f"%{search}%")
                | GlobalDncRecord.reason.ilike(f"%{search}%")
            )

        count_stmt = select(func.count(GlobalDncRecord.id))
        if conditions:
            count_stmt = count_stmt.where(*conditions)
        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar() or 0

        stmt = select(GlobalDncRecord)
        if conditions:
            stmt = stmt.where(*conditions)
        stmt = (
            stmt.order_by(GlobalDncRecord.created_at.desc())
            .limit(clamped_limit)
            .offset(clamped_offset)
        )

        rows = (await self.session.execute(stmt)).scalars().all()

        return {
            "items": rows,
            "total": total,
            "limit": clamped_limit,
            "offset": clamped_offset,
        }

    async def add_global_dnc_record(
        self,
        *,
        record_type: str,
        value: str,
        reason: str | None,
        source: str = "admin_manual",
        actor_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        endpoint: str | None = None,
    ) -> GlobalDncRecord:
        """Add a single global DNC entry, log audit event, and invalidate Redis cache."""
        _canonical, hmac_hash, masked = self.canonicalize_and_hash(record_type, value)

        stmt = select(GlobalDncRecord).where(
            GlobalDncRecord.record_type == record_type,
            GlobalDncRecord.value_hmac == hmac_hash,
        )
        res = await self.session.execute(stmt)
        if hasattr(res, "scalars"):
            scalars_res = res.scalars()
            existing = (
                scalars_res.first() if hasattr(scalars_res, "first") else None
            )
        else:
            existing = None

        if existing:
            entry = existing
            old_values = {
                "reason": entry.reason,
                "source": entry.source,
                "value": entry.value,
            }
            entry.reason = reason or "Opt-out requested"
            entry.source = source
            entry.value = masked
            action = "global_dnc.update"
            diff = {
                "record_id": str(entry.id),
                "record_type": record_type,
                "old": old_values,
                "new": {
                    "reason": entry.reason,
                    "source": entry.source,
                    "value": entry.value,
                },
                "value_hmac": hmac_hash,
                "endpoint": endpoint,
            }
        else:
            entry = GlobalDncRecord(
                id=uuid.uuid4(),
                record_type=record_type,
                value=masked,
                value_hmac=hmac_hash,
                reason=reason or "Opt-out requested",
                source=source,
            )
            self.session.add(entry)
            action = "global_dnc.add"
            diff = {
                "record_id": str(entry.id) if entry.id else None,
                "record_type": record_type,
                "masked_value": masked,
                "value_hmac": hmac_hash,
                "reason": reason,
                "endpoint": endpoint,
            }

        await self.session.flush()

        # Audit Event (INV-25.2)
        audit = AuditEvent(
            action=action,
            actor_id=actor_id,
            subject_id=None,
            ip_address=ip_address,
            user_agent=user_agent,
            diff_payload=diff,
        )
        self.session.add(audit)
        await self.session.flush()

        return entry

    async def invalidate_cache(self) -> None:
        """Helper to safely invalidate Redis global DNC cache."""
        compliance_service = DncComplianceService(secret_key=self.secret_key)
        await compliance_service.invalidate_global_cache()

    async def import_dnc_csv(
        self,
        *,
        csv_content: str,
        source: str = "csv_import",
        actor_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        endpoint: str | None = None,
    ) -> dict[str, Any]:
        """Bulk import CSV rows (record_type, value, reason) with deduplication."""
        # Strip UTF-8 BOM if present
        clean_csv = csv_content.lstrip("\ufeff")
        reader = csv.DictReader(io.StringIO(clean_csv))

        if not reader.fieldnames:
            raise ValueError("CSV file is empty or has no header row")

        normalized_fieldnames = {
            name.strip().lower(): name for name in reader.fieldnames
        }
        if "value" not in normalized_fieldnames:
            raise ValueError("CSV header must contain a 'value' column")
        if "record_type" not in normalized_fieldnames:
            raise ValueError("CSV header must contain a 'record_type' column")

        imported_count = 0
        skipped_count = 0
        failed_count = 0
        errors: list[str] = []

        valid_types = {"phone", "domain", "email", "tax_id"}
        entries_to_insert: list[dict[str, Any]] = []
        seen_in_batch: set[tuple[str, str]] = set()
        total_rows = 0

        for idx, row in enumerate(reader, start=2):
            # Skip blank lines (csv.DictReader yields empty dicts for them)
            if not any(v.strip() for v in row.values() if v):
                continue

            total_rows += 1
            if total_rows > MAX_CSV_ROWS:
                raise ValueError(f"CSV file exceeds the maximum of {MAX_CSV_ROWS} rows")

            r_type = (
                row.get(normalized_fieldnames.get("record_type", "record_type"), "")
                .strip()
                .lower()
            )
            val = row.get(normalized_fieldnames.get("value", "value"), "").strip()
            reason_col = normalized_fieldnames.get("reason", "reason")
            reason = (row.get(reason_col, "") or "Bulk CSV import").strip()

            if not r_type or not val:
                failed_count += 1
                errors.append(f"Row {idx}: missing record_type or value")
                continue

            if r_type not in valid_types:
                failed_count += 1
                errors.append(f"Row {idx}: invalid record_type")
                continue

            try:
                _canonical, hmac_hash, masked = self.canonicalize_and_hash(r_type, val)
                if (r_type, hmac_hash) in seen_in_batch:
                    skipped_count += 1
                    continue
                seen_in_batch.add((r_type, hmac_hash))

                entries_to_insert.append(
                    {
                        "id": uuid.uuid4(),
                        "record_type": r_type,
                        "value": masked,
                        "value_hmac": hmac_hash,
                        "reason": reason,
                        "source": source,
                    }
                )
            except ValueError as exc:
                failed_count += 1
                errors.append(f"Row {idx}: {exc}")

        if entries_to_insert:
            stmt = (
                pg_insert(GlobalDncRecord)
                .values(entries_to_insert)
                .on_conflict_do_nothing(constraint="uq_global_dnc_entry")
            )
            res = await self.session.execute(stmt)
            imported_count = res.rowcount or 0
            skipped_count += len(entries_to_insert) - imported_count

            # Audit Event — note the total CSV rows, not just successfully parsed rows
            audit = AuditEvent(
                action="global_dnc.add",
                actor_id=actor_id,
                subject_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                diff_payload={
                    "import_source": "csv",
                    "total_rows": total_rows,
                    "parsed_for_insert": len(entries_to_insert),
                    "imported_count": imported_count,
                    "skipped_count": skipped_count,
                    "failed_count": failed_count,
                    "endpoint": endpoint,
                },
            )
            self.session.add(audit)
            await self.session.flush()

        return {
            "imported_count": imported_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "errors": errors,
        }

    async def delete_global_dnc_record(
        self,
        *,
        record_id: uuid.UUID,
        actor_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        endpoint: str | None = None,
    ) -> bool:
        """Delete global DNC entry, record audit log, and invalidate cache."""
        record = await self.session.get(GlobalDncRecord, record_id)
        if not record:
            return False

        r_type = record.record_type
        v_hmac = record.value_hmac

        await self.session.delete(record)

        audit = AuditEvent(
            action="global_dnc.remove",
            actor_id=actor_id,
            subject_id=None,
            ip_address=ip_address,
            user_agent=user_agent,
            diff_payload={
                "record_id": str(record_id),
                "record_type": r_type,
                "value_hmac": v_hmac,
                "endpoint": endpoint,
            },
        )
        self.session.add(audit)
        await self.session.flush()

        return True
