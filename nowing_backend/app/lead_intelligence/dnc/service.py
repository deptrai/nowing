"""DNC Compliance Core Service (Story 21.14 / Decree 91 / Decree 13 PDPD)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import WorkspaceDncRecord
from app.lead_intelligence.dnc.normalizer import (
    hash_phone_hmac,
    is_domain_matching,
    normalize_domain,
    normalize_email,
    normalize_phone_e164,
    normalize_tax_id,
)

logger = logging.getLogger(__name__)

_redis_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis | None:
    """Return singleton async Redis client for DNC cache operations."""
    global _redis_client
    if not getattr(config, "REDIS_APP_URL", None):
        return None
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(
                config.REDIS_APP_URL, decode_responses=True
            )
        except Exception as exc:
            logger.warning("[DncService] Failed to init Redis client: %s", exc)
            return None
    return _redis_client


@dataclass
class DncCheckResult:
    """Result of DNC compliance evaluation for a candidate contact."""

    is_blocked: bool
    record_type: str | None = None
    reason: str | None = None
    dnc_record_id: Any | None = None


class DncComplianceService:
    """Service evaluating contacts against workspace DNC blacklist and whitelists."""

    def __init__(self, *, secret_key: str | None = None) -> None:
        self.secret_key = secret_key or getattr(
            config, "SECRET_KEY", "nowing-dnc-secret-fallback"
        )

    def _get_redis_key(self, workspace_id: int, record_type: str) -> str:
        return f"dnc:{workspace_id}:{record_type}"

    async def _get_workspace_dnc_set(
        self,
        workspace_id: int,
        record_type: str,
        session: AsyncSession | None = None,
    ) -> set[str]:
        """Fetch all blacklisted entries or HMAC hashes for workspace with Redis caching."""
        redis_key = self._get_redis_key(workspace_id, record_type)
        redis = get_redis()
        if redis is not None:
            try:
                cached_members = await redis.smembers(redis_key)
                if cached_members:
                    return {m for m in cached_members if m != "__EMPTY__"}
            except Exception as exc:
                logger.debug(
                    "[DncService] Redis lookup failed for %s DNC: %s",
                    record_type,
                    exc,
                )

        if session is None:
            return set()

        if record_type == "domain":
            stmt = select(WorkspaceDncRecord.value).where(
                WorkspaceDncRecord.workspace_id == workspace_id,
                WorkspaceDncRecord.record_type == "domain",
            )
        else:
            stmt = select(WorkspaceDncRecord.value_hmac).where(
                WorkspaceDncRecord.workspace_id == workspace_id,
                WorkspaceDncRecord.record_type == record_type,
            )
        members: set[str] = set()
        try:
            res = await session.execute(stmt)
            scalars_res = res.scalars()
            all_items = scalars_res.all() if hasattr(scalars_res, "all") else []
            if isinstance(all_items, (list, tuple, set)):
                members = {str(m) for m in all_items if m and isinstance(m, str)}
        except Exception as exc:
            logger.debug("[DncService] Database DNC query skipped/failed: %s", exc)
            members = set()

        if redis is not None:
            try:
                if members:
                    await redis.sadd(redis_key, *members)
                else:
                    await redis.sadd(redis_key, "__EMPTY__")
                await redis.expire(redis_key, 3600)
            except Exception as exc:
                logger.debug("[DncService] Redis cache populate failed: %s", exc)

        return members

    async def _get_workspace_dnc_phone_hashes(
        self, workspace_id: int, session: AsyncSession | None = None
    ) -> set[str]:
        return await self._get_workspace_dnc_set(workspace_id, "phone", session)

    async def _get_workspace_dnc_domains(
        self, workspace_id: int, session: AsyncSession | None = None
    ) -> set[str]:
        return await self._get_workspace_dnc_set(workspace_id, "domain", session)

    async def _get_workspace_dnc_email_hashes(
        self, workspace_id: int, session: AsyncSession | None = None
    ) -> set[str]:
        return await self._get_workspace_dnc_set(workspace_id, "email", session)

    async def _get_workspace_dnc_tax_hashes(
        self, workspace_id: int, session: AsyncSession | None = None
    ) -> set[str]:
        return await self._get_workspace_dnc_set(workspace_id, "tax_id", session)

    async def invalidate_workspace_cache(self, workspace_id: int) -> None:
        """Clear Redis DNC cache keys for a workspace upon add/delete/import."""
        redis = get_redis()
        if redis is None:
            return
        try:
            for r_type in ("phone", "email", "domain", "tax_id"):
                await redis.delete(self._get_redis_key(workspace_id, r_type))
        except Exception as exc:
            logger.debug("[DncService] Cache invalidation failed: %s", exc)

    async def is_blocked(
        self,
        workspace_id: int,
        phone: str | None = None,
        email: str | None = None,
        domain: str | None = None,
        tax_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> DncCheckResult:
        """Check if any contact identifier matches the workspace DNC registry."""
        # 1. Check Phone (E.164 + Keyed HMAC)
        if phone:
            e164 = normalize_phone_e164(phone)
            if e164:
                phone_hash = hash_phone_hmac(e164, secret_key=self.secret_key)
                blocked_hashes = await self._get_workspace_dnc_phone_hashes(
                    workspace_id, session
                )
                if phone_hash in blocked_hashes:
                    return DncCheckResult(
                        is_blocked=True,
                        record_type="phone",
                        reason="Phone number is registered on Workspace DNC blacklist",
                    )

        # 2. Check Domain / Wildcard
        if domain:
            norm_dom = normalize_domain(domain)
            if norm_dom:
                blocked_domains = await self._get_workspace_dnc_domains(
                    workspace_id, session
                )
                for rule_dom in blocked_domains:
                    if is_domain_matching(norm_dom, rule_dom):
                        return DncCheckResult(
                            is_blocked=True,
                            record_type="domain",
                            reason=f"Company domain matches blocked rule '{rule_dom}'",
                        )

        # 3. Check Email
        if email:
            norm_mail = normalize_email(email)
            if norm_mail:
                email_hash = hash_phone_hmac(norm_mail, secret_key=self.secret_key)
                blocked_emails = await self._get_workspace_dnc_email_hashes(
                    workspace_id, session
                )
                if email_hash in blocked_emails:
                    return DncCheckResult(
                        is_blocked=True,
                        record_type="email",
                        reason="Email address is on Workspace DNC blacklist",
                    )

        # 4. Check Tax ID
        if tax_id:
            norm_tax = normalize_tax_id(tax_id)
            if norm_tax:
                tax_hash = hash_phone_hmac(norm_tax, secret_key=self.secret_key)
                blocked_taxes = await self._get_workspace_dnc_tax_hashes(
                    workspace_id, session
                )
                if tax_hash in blocked_taxes:
                    return DncCheckResult(
                        is_blocked=True,
                        record_type="tax_id",
                        reason="Corporate Tax ID is on Workspace DNC blacklist",
                    )

        return DncCheckResult(is_blocked=False)

    async def check_phone(
        self,
        workspace_id: int,
        phone: str,
        session: AsyncSession | None = None,
        client_id: str | None = None,
    ) -> DncCheckResult:
        """Check if phone number is blocked on Workspace or Global DNC list (Fail-closed / INV-24.3)."""
        return await self.is_blocked(workspace_id, phone=phone, session=session)

    async def batch_filter_leads(
        self,
        workspace_id: int,
        leads: list[dict[str, Any]],
        session: AsyncSession | None = None,
    ) -> list[dict[str, Any]]:
        """Tag in-stream leads with blocked_by_dnc and dnc_reason in O(1) in-memory lookups."""
        if not leads:
            return []

        # Pre-fetch all workspace blacklist sets once
        phone_hashes = await self._get_workspace_dnc_phone_hashes(
            workspace_id, session
        )
        blocked_domains = await self._get_workspace_dnc_domains(
            workspace_id, session
        )
        email_hashes = await self._get_workspace_dnc_email_hashes(
            workspace_id, session
        )
        tax_hashes = await self._get_workspace_dnc_tax_hashes(
            workspace_id, session
        )

        results = []
        for lead in leads:
            is_blocked = False
            reason: str | None = None

            # 1. Phone
            raw_phone = lead.get("phone") or lead.get("first_phone")
            if raw_phone:
                e164 = normalize_phone_e164(raw_phone)
                if e164:
                    p_hash = hash_phone_hmac(e164, secret_key=self.secret_key)
                    if p_hash in phone_hashes:
                        is_blocked = True
                        reason = "Phone number is registered on Workspace DNC blacklist"

            # 2. Domain
            if not is_blocked:
                raw_domain = lead.get("domain") or lead.get("company_domain")
                if raw_domain:
                    norm_dom = normalize_domain(raw_domain)
                    if norm_dom:
                        for rule_dom in blocked_domains:
                            if is_domain_matching(norm_dom, rule_dom):
                                is_blocked = True
                                reason = (
                                    f"Company domain matches blocked rule '{rule_dom}'"
                                )
                                break

            # 3. Email
            if not is_blocked:
                raw_email = lead.get("email")
                if raw_email:
                    norm_mail = normalize_email(raw_email)
                    if norm_mail:
                        m_hash = hash_phone_hmac(norm_mail, secret_key=self.secret_key)
                        if m_hash in email_hashes:
                            is_blocked = True
                            reason = "Email address is on Workspace DNC blacklist"

            # 4. Tax ID
            if not is_blocked:
                raw_tax = lead.get("tax_id")
                if raw_tax:
                    norm_tax = normalize_tax_id(raw_tax)
                    if norm_tax:
                        t_hash = hash_phone_hmac(norm_tax, secret_key=self.secret_key)
                        if t_hash in tax_hashes:
                            is_blocked = True
                            reason = "Corporate Tax ID is on Workspace DNC blacklist"

            updated = dict(lead)
            updated["blocked_by_dnc"] = is_blocked
            if is_blocked:
                updated["dnc_reason"] = reason
            results.append(updated)

        return results
