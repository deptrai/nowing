"""Multi-Key Entity Deduplication & DNC Compliance Pipeline (Story 21.15)."""

from __future__ import annotations

import hashlib
import hmac
import logging

from pydantic import BaseModel, ConfigDict, Field

from app.lead_intelligence.adapters.base import (
    ContactCandidate,
    NormalizedLead,
    normalize_vietnamese_phone,
)
from app.lead_intelligence.confidence.gate import ConfidenceGate
from app.lead_intelligence.dnc.normalizer import (
    hash_phone_hmac,
    normalize_phone_e164,
)

logger = logging.getLogger(__name__)

FREE_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "yahoo.com",
        "outlook.com",
        "hotmail.com",
        "icloud.com",
        "zoho.com",
        "mail.com",
        "proton.me",
        "protonmail.com",
        "yandex.com",
        "gmx.com",
        "fastmail.com",
        "live.com",
        "me.com",
    }
)


def compute_phone_hmac(phone: str, secret: str = "nowing_default_lead_secret") -> str:
    """
    Compute deterministic Keyed SHA-256 HMAC for phone numbers.
    Zero-PII compliant with Decree 13/2023/NĐ-CP (Personal Data Protection).
    """
    normalized = normalize_vietnamese_phone(phone)
    if not normalized:
        return ""
    key_bytes = secret.encode("utf-8")
    msg_bytes = normalized.encode("utf-8")
    return hmac.new(key_bytes, msg_bytes, hashlib.sha256).hexdigest()


class DeduplicationResult(BaseModel):
    """Result of multi-key entity deduplication and attribute merging."""

    model_config = ConfigDict(from_attributes=True)

    unified_leads: list[NormalizedLead] = Field(default_factory=list)
    total_raw: int = 0
    total_deduplicated: int = 0


class DncComplianceResult(BaseModel):
    """Result of DNC blacklist and consent filtering."""

    model_config = ConfigDict(from_attributes=True)

    compliant_leads: list[NormalizedLead] = Field(default_factory=list)
    dnc_suppressed_leads: list[NormalizedLead] = Field(default_factory=list)


class EntityDeduplicationService:
    """Service to cluster, deduplicate, and merge lead entities across multiple scrapers."""

    def compute_cluster_keys(self, lead: NormalizedLead, secret_key: str) -> list[str]:
        """Generate deduplication match keys for a lead record."""
        keys: list[str] = []

        # 1. Phone HMAC key
        if lead.primary_phone:
            phone_digest = compute_phone_hmac(lead.primary_phone, secret=secret_key)
            if phone_digest:
                keys.append(f"phone:{phone_digest}")

        for candidate in lead.contact_candidates:
            if candidate.channel == "phone" and candidate.value:
                phone_digest = compute_phone_hmac(candidate.value, secret=secret_key)
                if phone_digest:
                    k = f"phone:{phone_digest}"
                    if k not in keys:
                        keys.append(k)

        # 2. Tax ID key (Mã số thuế) — must be valid 10-14 chars
        if lead.tax_id:
            cleaned_tax = lead.tax_id.strip().upper()
            if (
                len(cleaned_tax) in (10, 13, 14)
                and cleaned_tax.replace("-", "").isalnum()
            ):
                keys.append(f"tax:{cleaned_tax}")

        # 3. Canonical Domain key (exclude generic consumer email domains)
        if lead.canonical_domain:
            cleaned_domain = lead.canonical_domain.strip().lower()
            if cleaned_domain not in FREE_EMAIL_DOMAINS and "." in cleaned_domain:
                keys.append(f"domain:{cleaned_domain}")

        # 4. Primary Email key
        if lead.primary_email and "@" in lead.primary_email:
            cleaned_email = lead.primary_email.strip().lower()
            keys.append(f"email:{cleaned_email}")

        return keys

    def deduplicate_leads(
        self,
        leads: list[NormalizedLead],
        secret_key: str = "nowing_default_lead_secret",
    ) -> DeduplicationResult:
        """
        Deduplicate raw multi-source lead streams using connected components clustering.
        Merges missing attributes and boosts confidence score for multi-source leads.
        """
        if not leads:
            return DeduplicationResult(
                unified_leads=[], total_raw=0, total_deduplicated=0
            )

        # Build disjoint set / graph of matching keys
        key_to_lead_indices: dict[str, list[int]] = {}
        for idx, lead in enumerate(leads):
            keys = self.compute_cluster_keys(lead, secret_key)
            for k in keys:
                key_to_lead_indices.setdefault(k, []).append(idx)

        # Group indices using BFS
        visited: set[int] = set()
        clusters: list[list[int]] = []

        for i in range(len(leads)):
            if i in visited:
                continue
            cluster: list[int] = []
            queue = [i]
            visited.add(i)

            while queue:
                current_idx = queue.pop(0)
                cluster.append(current_idx)
                current_lead = leads[current_idx]
                for k in self.compute_cluster_keys(current_lead, secret_key):
                    for neighbor_idx in key_to_lead_indices.get(k, []):
                        if neighbor_idx not in visited:
                            visited.add(neighbor_idx)
                            queue.append(neighbor_idx)

            clusters.append(cluster)

        # Merge clusters into unified leads
        unified_list: list[NormalizedLead] = []
        for cluster_indices in clusters:
            cluster_leads = [leads[idx] for idx in cluster_indices]
            merged_lead = self._merge_cluster(cluster_leads)
            unified_list.append(merged_lead)

        return DeduplicationResult(
            unified_leads=unified_list,
            total_raw=len(leads),
            total_deduplicated=len(unified_list),
        )

    def _merge_cluster(self, cluster_leads: list[NormalizedLead]) -> NormalizedLead:
        """Merge a group of matching NormalizedLead records into one enriched record."""
        if len(cluster_leads) == 1:
            return cluster_leads[0]

        # Base entity is the one with the highest schema completeness.
        sorted_by_conf = sorted(
            cluster_leads,
            key=lambda x: x.schema_completeness_score or 0.0,
            reverse=True,
        )
        base = sorted_by_conf[0]

        # Aggregate unique sources
        all_sources = list(
            dict.fromkeys(s for item in sorted_by_conf for s in item.sources)
        )

        # Union candidate contacts
        all_candidates: list[ContactCandidate] = []
        seen_cand_vals: set[str] = set()
        for item in sorted_by_conf:
            for c in item.contact_candidates:
                if c.value not in seen_cand_vals:
                    seen_cand_vals.add(c.value)
                    all_candidates.append(c)

        # Merge non-null attributes strictly preferring the most complete leads.
        title = next((item.title for item in sorted_by_conf if item.title), base.title)
        company_name = next(
            (item.company_name for item in sorted_by_conf if item.company_name),
            base.company_name,
        )
        primary_phone = next(
            (item.primary_phone for item in sorted_by_conf if item.primary_phone),
            base.primary_phone,
        )
        primary_email = next(
            (item.primary_email for item in sorted_by_conf if item.primary_email),
            base.primary_email,
        )
        tax_id = next(
            (item.tax_id for item in sorted_by_conf if item.tax_id), base.tax_id
        )
        canonical_domain = next(
            (item.canonical_domain for item in sorted_by_conf if item.canonical_domain),
            base.canonical_domain,
        )
        contact_name = next(
            (item.contact_name for item in sorted_by_conf if item.contact_name),
            base.contact_name,
        )
        legal_rep = next(
            (item.legal_rep for item in sorted_by_conf if item.legal_rep),
            base.legal_rep,
        )
        address = next(
            (item.address for item in sorted_by_conf if item.address), base.address
        )
        city = next((item.city for item in sorted_by_conf if item.city), base.city)
        price = next(
            (item.price for item in sorted_by_conf if item.price is not None),
            base.price,
        )
        area = next(
            (item.area for item in sorted_by_conf if item.area is not None), base.area
        )
        source_url = next(
            (item.source_url for item in sorted_by_conf if item.source_url),
            base.source_url,
        )

        # Boost confidence score for multi-source corroboration
        multi_source_bonus = (len(all_sources) - 1) * 15.0
        boosted_score = min(100.0, base.confidence_score + multi_source_bonus)

        merged_lead = NormalizedLead(
            source_name=base.source_name,
            source_id=base.source_id,
            title=title,
            company_name=company_name,
            primary_phone=primary_phone,
            primary_email=primary_email,
            tax_id=tax_id,
            canonical_domain=canonical_domain,
            contact_name=contact_name,
            legal_rep=legal_rep,
            address=address,
            city=city,
            price=price,
            area=area,
            source_url=source_url,
            confidence_score=boosted_score,
            sources=all_sources,
            contact_candidates=all_candidates,
            raw_data=base.raw_data,
        )

        # Recompute schema completeness from the merged fields.
        ConfidenceGate.score(merged_lead)
        return merged_lead

    def _check_dnc_batch(
        self,
        phones: list[str],
        workspace_id: int,
        secret_key: str,
        workspace_hashes: set[str],
        global_hashes: set[str],
    ) -> dict[str, bool]:
        """Check phone numbers against pre-loaded DNC hashes using keyed HMAC-SHA256."""
        result: dict[str, bool] = {}
        for raw_phone in phones:
            e164 = normalize_phone_e164(raw_phone)
            if e164:
                phone_hash = hash_phone_hmac(e164, secret_key=secret_key)
                result[raw_phone] = (
                    phone_hash in workspace_hashes or phone_hash in global_hashes
                )
            else:
                result[raw_phone] = False
        return result

    def apply_dnc_compliance(
        self,
        leads: list[NormalizedLead],
        workspace_id: int,
        suppress_dnc: bool = True,
        secret_key: str | None = None,
        workspace_dnc_hashes: set[str] | None = None,
        global_dnc_hashes: set[str] | None = None,
    ) -> DncComplianceResult:
        """Filter out contacts on National Do-Not-Call (DNC) or Workspace Blacklist.

        Callers with an active database session should pre-fetch DNC hashes via
        ``DncComplianceService`` and pass them in; otherwise the method falls back
        to an empty hash set and all leads are treated as compliant. This keeps the
        service synchronous and usable from sync benchmark scripts while the real
        DNC gate in ``LeadBatchService`` runs against the database.
        """
        all_phones = [item.primary_phone for item in leads if item.primary_phone]
        dnc_map = self._check_dnc_batch(
            all_phones,
            workspace_id,
            secret_key=secret_key or "",
            workspace_hashes=workspace_dnc_hashes or set(),
            global_hashes=global_dnc_hashes or set(),
        )

        compliant: list[NormalizedLead] = []
        suppressed: list[NormalizedLead] = []

        for item in leads:
            is_dnc = bool(item.primary_phone and dnc_map.get(item.primary_phone, False))
            if is_dnc:
                suppressed.append(item)
                if not suppress_dnc:
                    compliant.append(item)
            else:
                compliant.append(item)

        return DncComplianceResult(
            compliant_leads=compliant,
            dnc_suppressed_leads=suppressed,
        )
