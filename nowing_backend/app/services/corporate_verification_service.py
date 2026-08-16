"""B2B Corporate Tax Code (MST) & Official Registry Verification Engine (Story 24.2 / INV-24.3).

Features:
- Multi-attribute Fuzzy Match: Levenshtein Ratio * 0.5 + City Match * 0.3 + District Match * 0.2 >= 0.85
- Corporate Profile Parsing: Tax ID, Legal Representative, Charter Capital (in VND), Company Status, Rep Phone
- Redis Caching Layer: 7-day TTL (enrich:corp:*)
- Circuit Breaker: 3 consecutive upstream failures trip for 10 minutes (600s) on key circuit_breaker:scraper:masothue
- Fail-closed fallback to stale cache when circuit breaker is OPEN
"""

from __future__ import annotations

import difflib
import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import Lead

logger = logging.getLogger(__name__)

# Constants (INV-24.3 / AC-1 / AC-3)
CIRCUIT_BREAKER_KEY = "circuit_breaker:scraper:masothue"
CIRCUIT_BREAKER_THRESHOLD = 3
CIRCUIT_BREAKER_COOLDOWN_SECONDS = 600  # 10 minutes (600s)
CORPORATE_CACHE_TTL_SECONDS = 7 * 24 * 3600  # 7 days (604,800s)
REDIS_CORP_CACHE_PREFIX = "enrich:corp:"
AUTO_LINK_CONFIDENCE_THRESHOLD = 0.85

_redis_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis | None:
    """Return singleton async Redis client for corporate verification caching and breaker."""
    global _redis_client
    if not getattr(config, "REDIS_APP_URL", None):
        return None
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(
                config.REDIS_APP_URL, decode_responses=True
            )
        except Exception as exc:
            logger.warning("[CorporateVerification] Failed to init Redis client: %s", exc)
            return None
    return _redis_client


# ─────────────────────────────────────────────────────────────
# 1. Multi-Attribute Fuzzy Matching & Capital Parsing Helpers
# ─────────────────────────────────────────────────────────────

def _clean_admin_name(name: str | None) -> str:
    """Remove Vietnamese administrative prefixes and punctuation for resilient geo-matching."""
    if not name:
        return ""
    s = name.strip().lower()
    # Normalize common abbreviations and prefixes
    prefixes = [
        "thành phố",
        "thanh pho",
        "tp.",
        "tp ",
        "tỉnh",
        "tinh",
        "quận",
        "quan",
        "huyện",
        "huyen",
        "thị xã",
        "thi xa",
        "tx.",
        "tx ",
        "phường",
        "phuong",
        "xã",
        "xa",
        "q.",
        "q ",
        "h.",
        "h ",
        "p.",
        "p ",
    ]
    for p in prefixes:
        if s.startswith(p):
            s = s[len(p) :].strip()
            break
    return s.strip()


def _match_admin_unit(unit_a: str | None, unit_b: str | None) -> float:
    """Evaluate similarity between two administrative units (city or district)."""
    if not unit_a or not unit_b:
        return 0.0
    clean_a = _clean_admin_name(unit_a)
    clean_b = _clean_admin_name(unit_b)
    if not clean_a or not clean_b:
        return 0.0
    if clean_a == clean_b or clean_a in clean_b or clean_b in clean_a:
        return 1.0
    ratio = difflib.SequenceMatcher(None, clean_a, clean_b).ratio()
    return 1.0 if ratio >= 0.80 else 0.0


def _strip_vietnamese_accents(text: str | None) -> str:
    """Normalize and strip Vietnamese diacritics for resilient string matching."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in normalized if not unicodedata.combining(c))
    # Replace special D with d
    stripped = stripped.replace("đ", "d").replace("Đ", "D")
    return stripped.lower().strip()


def compute_multi_attribute_match_score(
    lead_name: str | None,
    lead_city: str | None,
    lead_district: str | None,
    registry_name: str | None,
    registry_city: str | None,
    registry_district: str | None,
) -> float:
    """Compute composite confidence score: Levenshtein * 0.5 + City * 0.3 + District * 0.2."""
    if not lead_name or not registry_name:
        return 0.0

    clean_lead = _strip_vietnamese_accents(lead_name)
    clean_reg = _strip_vietnamese_accents(registry_name)
    if not clean_lead or not clean_reg:
        return 0.0

    # Common corporate prefix normalization (công ty cổ phần -> ctcp, tnhh -> tnhh)
    lead_norm = re.sub(r"\b(cong ty co phan|ctcp|cong ty tnhh|tnhh|tap doan)\b", "", clean_lead).strip()
    reg_norm = re.sub(r"\b(cong ty co phan|ctcp|cong ty tnhh|tnhh|tap doan)\b", "", clean_reg).strip()
    if lead_norm and reg_norm:
        raw_ratio = difflib.SequenceMatcher(None, clean_lead, clean_reg).ratio()
        core_ratio = difflib.SequenceMatcher(None, lead_norm, reg_norm).ratio()
        name_ratio = max(raw_ratio, core_ratio)
    else:
        name_ratio = difflib.SequenceMatcher(None, clean_lead, clean_reg).ratio()

    city_score = _match_admin_unit(lead_city, registry_city)
    district_score = _match_admin_unit(lead_district, registry_district)

    total_score = (name_ratio * 0.5) + (city_score * 0.3) + (district_score * 0.2)
    return round(total_score, 4)


def parse_charter_capital_vnd(val: Any) -> int | None:
    """Parse charter capital string, currency format, or number into integer VND."""
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return int(val) if val > 0 else None
    if not isinstance(val, str):
        return None

    s = val.strip()
    if not s or s.lower() in ("chưa đăng ký", "chua dang ky", "n/a", "none", "null", "chưa rõ", "chua ro"):
        return None

    # Match Vietnamese text units (e.g., "13 nghìn tỷ", "20 tỷ", "500 triệu", "1.5 tỷ đồng")
    unit_pattern = r"^([\d\.,\s]+?)\s*(nghìn\s*tỷ|nghin\s*ty|tỷ|ty|triệu|trieu|nghìn|nghin|k|m|b)(?:\s*đồng|\s*vnd|\s*vnđ)?$"
    match = re.search(unit_pattern, s, re.IGNORECASE)
    if match:
        num_part = match.group(1).replace(" ", "")
        if "," in num_part and "." in num_part:
            num_part = num_part.replace(".", "").replace(",", ".")
        elif "," in num_part:
            num_part = num_part.replace(",", ".")
        try:
            val_f = float(num_part)
            unit_str = match.group(2).lower()
            if ("nghìn" in unit_str and "tỷ" in unit_str) or ("nghin" in unit_str and "ty" in unit_str):
                mult = 1_000_000_000_000
            elif "tỷ" in unit_str or "ty" in unit_str or unit_str == "b":
                mult = 1_000_000_000
            elif "triệu" in unit_str or "trieu" in unit_str or unit_str == "m":
                mult = 1_000_000
            elif "nghìn" in unit_str or "nghin" in unit_str or unit_str == "k":
                mult = 1_000
            else:
                mult = 1
            return int(val_f * mult)
        except ValueError:
            pass

    # Extract digits from formatted numbers (e.g. "13.000.000.000.000 VNĐ", "287,360,000,000 VND")
    digits = re.sub(r"[^\d]", "", s)
    if digits:
        try:
            parsed = int(digits)
            return parsed if parsed > 0 else None
        except ValueError:
            return None

    return None


# ─────────────────────────────────────────────────────────────
# 2. Data Models
# ─────────────────────────────────────────────────────────────

@dataclass
class CorporateProfile:
    tax_id: str
    company_name: str
    legal_representative: str | None = None
    charter_capital_vnd: int | None = None
    company_status: str | None = None
    is_active: bool = True
    address: str | None = None
    city: str | None = None
    district: str | None = None
    phone: str | None = None
    rep_phone: str | None = None
    international_name: str | None = None
    short_name: str | None = None
    industry: str | None = None
    date_of_incorporation: str | None = None


@dataclass
class CorporateMatchResult:
    tax_id: str | None = None
    is_verified: bool = False
    confidence: float = 0.0
    requires_manual_confirmation: bool = False
    legal_representative: str | None = None
    charter_capital_vnd: int | None = None
    company_status: str | None = None
    profile: CorporateProfile | None = None
    is_cached: bool = False
    degraded: bool = False
    degradation_reason: str | None = None


# ─────────────────────────────────────────────────────────────
# 3. Default Masothue Scraper Client Wrapper
# ─────────────────────────────────────────────────────────────

class DefaultMasothueClient:
    """Default client wrapping proprietary masothue scraper with rotating proxy pool."""

    async def search_company(
        self,
        query: str,
        city: str | None = None,
        district: str | None = None,
        proxy: str | None = None,
    ) -> list[dict[str, Any]]:
        from app.proprietary.platforms.masothue.schemas import MasothueSearchInput
        from app.proprietary.platforms.masothue.scraper import scrape_masothue

        inp = MasothueSearchInput(
            query=query,
            search_type="auto",
            max_pages=1,
            max_items=5,
            resolve_detail=True,
            include_phone=True,
        )
        out = await scrape_masothue(inp)
        results = []
        for item in out.items:
            results.append({
                "tax_id": item.tax_code or item.taxId,
                "company_name": item.name,
                "international_name": item.international_name,
                "short_name": item.short_name,
                "legal_representative": item.representative,
                "charter_capital_vnd": parse_charter_capital_vnd(item.charter_capital),
                "company_status": item.status,
                "is_active": (item.status or "").lower().startswith("đang hoạt động"),
                "address": item.address,
                "city": item.city,
                "district": item.district,
                "phone": item.phone,
                "rep_phone": getattr(item, "rep_phone", None) or item.phone,
                "industry": item.main_business,
                "date_of_incorporation": getattr(item, "founding_date", None),
            })
        return results

    async def get_company_by_tax_id(
        self, tax_id: str, proxy: str | None = None
    ) -> dict[str, Any] | None:
        res = await self.search_company(query=tax_id, proxy=proxy)
        for r in res:
            if (r.get("tax_id") or "").replace("-", "").strip() == tax_id.replace("-", "").strip():
                return r
        return res[0] if res else None


# ─────────────────────────────────────────────────────────────
# 4. Corporate Verification Service
# ─────────────────────────────────────────────────────────────

class CorporateVerificationService:
    """B2B Corporate Tax Code (MST) & Official Registry Verification Engine."""

    def __init__(
        self,
        session: AsyncSession,
        masothue_client: Any | None = None,
        redis_client: aioredis.Redis | None = None,
    ) -> None:
        self.session = session
        self.masothue_client = masothue_client or DefaultMasothueClient()
        self._redis = redis_client
        self.consecutive_failures = 0

    def _get_redis(self) -> aioredis.Redis | None:
        if self._redis is not None:
            return self._redis
        return get_redis()

    def _dict_to_profile(self, d: dict[str, Any]) -> CorporateProfile:
        return CorporateProfile(
            tax_id=d.get("tax_id") or "",
            company_name=d.get("company_name") or "",
            legal_representative=d.get("legal_representative"),
            charter_capital_vnd=parse_charter_capital_vnd(d.get("charter_capital_vnd")),
            company_status=d.get("company_status"),
            is_active=d.get("is_active", True),
            address=d.get("address"),
            city=d.get("city"),
            district=d.get("district"),
            phone=d.get("phone"),
            rep_phone=d.get("rep_phone"),
            international_name=d.get("international_name"),
            short_name=d.get("short_name"),
            industry=d.get("industry"),
            date_of_incorporation=d.get("date_of_incorporation"),
        )

    def _parse_location(self, location: str | None) -> tuple[str | None, str | None]:
        """Extract city and district from location string (e.g. 'Cầu Giấy, Hà Nội')."""
        if not location:
            return None, None
        parts = [p.strip() for p in location.split(",") if p.strip()]
        if len(parts) >= 2:
            return parts[-1], parts[0]  # city, district
        if len(parts) == 1:
            return parts[0], None
        return None, None

    async def _is_circuit_breaker_open(self) -> bool:
        redis = self._get_redis()
        if redis is None:
            return self.consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD
        try:
            val = await redis.get(CIRCUIT_BREAKER_KEY)
            return val == "open" or self.consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD
        except Exception as exc:
            logger.debug("[CorporateVerification] Breaker check failed: %s", exc)
            return False

    async def _record_failure_and_trip_if_needed(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
            redis = self._get_redis()
            if redis is not None:
                try:
                    await redis.set(
                        CIRCUIT_BREAKER_KEY, "open", ex=CIRCUIT_BREAKER_COOLDOWN_SECONDS
                    )
                    logger.warning(
                        "[CorporateVerification] Circuit breaker TRIPPED for %ss after %s failures",
                        CIRCUIT_BREAKER_COOLDOWN_SECONDS,
                        self.consecutive_failures,
                    )
                except Exception as exc:
                    logger.debug("[CorporateVerification] Failed setting breaker key: %s", exc)

    async def _record_success(self) -> None:
        self.consecutive_failures = 0

    async def get_corporate_profile_by_tax_id(
        self, tax_id: str, force_refresh: bool = False
    ) -> CorporateProfile | None:
        """Lookup corporate profile by exact Tax Code (MST) with 7-day Redis caching."""
        if not tax_id:
            return None

        clean_tax = tax_id.strip().replace("-", "")
        redis = self._get_redis()
        cache_key = f"{REDIS_CORP_CACHE_PREFIX}tax:{clean_tax}"

        # 1. Check 7-Day Redis Cache
        if redis is not None and not force_refresh:
            try:
                cached = await redis.get(cache_key)
                if cached:
                    logger.info("[CorporateVerification] Cache Hit for MST %s", clean_tax)
                    return self._dict_to_profile(json.loads(cached))
            except Exception as exc:
                logger.debug("[CorporateVerification] Redis cache read failed: %s", exc)

        # 2. Query Upstream Registry with Failure & Circuit Breaker Tracking
        try:
            raw_data = await self.masothue_client.get_company_by_tax_id(clean_tax)
            await self._record_success()
        except Exception as exc:
            await self._record_failure_and_trip_if_needed()
            raise exc

        if not raw_data:
            return None

        profile = self._dict_to_profile(raw_data)

        # 3. Write to 7-Day Redis Cache
        if redis is not None:
            try:
                await redis.set(
                    cache_key, json.dumps(raw_data), ex=CORPORATE_CACHE_TTL_SECONDS
                )
            except Exception as exc:
                logger.debug("[CorporateVerification] Redis cache write failed: %s", exc)

        return profile

    async def verify_company(
        self,
        company_name: str,
        city: str | None = None,
        district: str | None = None,
        tax_id: str | None = None,
        force_refresh: bool = False,
    ) -> CorporateMatchResult:
        """Run multi-attribute fuzzy verification against official company registries."""
        redis = self._get_redis()

        # Check Circuit Breaker
        breaker_open = await self._is_circuit_breaker_open()

        # If MST is provided directly
        if tax_id:
            clean_tax = tax_id.strip().replace("-", "")
            if breaker_open and redis is not None:
                try:
                    cached = await redis.get(f"{REDIS_CORP_CACHE_PREFIX}tax:{clean_tax}")
                    if cached:
                        data = json.loads(cached)
                        prof = self._dict_to_profile(data)
                        return CorporateMatchResult(
                            tax_id=prof.tax_id,
                            is_verified=True,
                            confidence=1.0,
                            legal_representative=prof.legal_representative,
                            charter_capital_vnd=prof.charter_capital_vnd,
                            company_status=prof.company_status,
                            profile=prof,
                            is_cached=True,
                        )
                except Exception:
                    pass
                return CorporateMatchResult(
                    is_verified=False,
                    degraded=True,
                    degradation_reason="circuit_breaker_open",
                )

            try:
                profile = await self.get_corporate_profile_by_tax_id(
                    clean_tax, force_refresh=force_refresh
                )
                if profile:
                    score = compute_multi_attribute_match_score(
                        company_name, city, district, profile.company_name, profile.city, profile.district
                    )
                    is_ver = score >= AUTO_LINK_CONFIDENCE_THRESHOLD or profile.tax_id == clean_tax
                    return CorporateMatchResult(
                        tax_id=profile.tax_id,
                        is_verified=is_ver,
                        confidence=max(score, 0.98 if is_ver else score),
                        requires_manual_confirmation=not is_ver,
                        legal_representative=profile.legal_representative,
                        charter_capital_vnd=profile.charter_capital_vnd,
                        company_status=profile.company_status,
                        profile=profile,
                        is_cached=False,
                    )
            except Exception as exc:
                logger.warning("[CorporateVerification] Error verifying by tax_id %s: %s", tax_id, exc)

        # Lookup by Company Name
        name_hash = hashlib.sha256(company_name.strip().upper().encode("utf-8")).hexdigest()
        name_cache_key = f"{REDIS_CORP_CACHE_PREFIX}name:{name_hash}"

        if breaker_open:
            if redis is not None:
                try:
                    cached = await redis.get(name_cache_key)
                    if cached:
                        data = json.loads(cached)
                        prof = self._dict_to_profile(data)
                        score = compute_multi_attribute_match_score(
                            company_name, city, district, prof.company_name, prof.city, prof.district
                        )
                        is_ver = score >= AUTO_LINK_CONFIDENCE_THRESHOLD
                        return CorporateMatchResult(
                            tax_id=prof.tax_id,
                            is_verified=is_ver,
                            confidence=score,
                            requires_manual_confirmation=not is_ver,
                            legal_representative=prof.legal_representative,
                            charter_capital_vnd=prof.charter_capital_vnd,
                            company_status=prof.company_status,
                            profile=prof,
                            is_cached=True,
                        )
                except Exception:
                    pass
            return CorporateMatchResult(
                is_verified=False,
                degraded=True,
                degradation_reason="circuit_breaker_open",
            )

        # Check Cache
        if redis is not None and not force_refresh:
            try:
                cached = await redis.get(name_cache_key)
                if cached:
                    data = json.loads(cached)
                    prof = self._dict_to_profile(data)
                    score = compute_multi_attribute_match_score(
                        company_name, city, district, prof.company_name, prof.city, prof.district
                    )
                    is_ver = score >= AUTO_LINK_CONFIDENCE_THRESHOLD
                    return CorporateMatchResult(
                        tax_id=prof.tax_id,
                        is_verified=is_ver,
                        confidence=score,
                        requires_manual_confirmation=not is_ver,
                        legal_representative=prof.legal_representative,
                        charter_capital_vnd=prof.charter_capital_vnd,
                        company_status=prof.company_status,
                        profile=prof,
                        is_cached=True,
                    )
            except Exception as exc:
                logger.debug("[CorporateVerification] Redis cache lookup failed: %s", exc)

        # Query Masothue search
        try:
            candidates = await self.masothue_client.search_company(
                query=company_name, city=city, district=district
            )
            await self._record_success()
        except Exception as exc:
            await self._record_failure_and_trip_if_needed()
            logger.warning("[CorporateVerification] Upstream query failed: %s", exc)
            return CorporateMatchResult(
                is_verified=False,
                degraded=True,
                degradation_reason="upstream_error",
            )

        if not candidates:
            return CorporateMatchResult(
                is_verified=False,
                confidence=0.0,
                requires_manual_confirmation=False,
            )

        # Evaluate Multi-Attribute Scores across all candidates
        best_cand: dict[str, Any] | None = None
        best_score = -1.0

        for cand in candidates:
            c_name = cand.get("company_name") or cand.get("name")
            c_city = cand.get("city")
            c_dist = cand.get("district")
            score = compute_multi_attribute_match_score(
                company_name, city, district, c_name, c_city, c_dist
            )
            if score > best_score:
                best_score = score
                best_cand = cand

        if not best_cand or best_score < 0.0:
            return CorporateMatchResult(
                is_verified=False,
                confidence=0.0,
                requires_manual_confirmation=False,
            )

        prof = self._dict_to_profile(best_cand)

        # Cache best candidate
        if redis is not None:
            try:
                await redis.set(
                    name_cache_key, json.dumps(best_cand), ex=CORPORATE_CACHE_TTL_SECONDS
                )
                if prof.tax_id:
                    await redis.set(
                        f"{REDIS_CORP_CACHE_PREFIX}tax:{prof.tax_id}",
                        json.dumps(best_cand),
                        ex=CORPORATE_CACHE_TTL_SECONDS,
                    )
            except Exception as exc:
                logger.debug("[CorporateVerification] Redis cache write failed: %s", exc)

        is_verified = best_score >= AUTO_LINK_CONFIDENCE_THRESHOLD
        return CorporateMatchResult(
            tax_id=prof.tax_id,
            is_verified=is_verified,
            confidence=best_score,
            requires_manual_confirmation=not is_verified,
            legal_representative=prof.legal_representative,
            charter_capital_vnd=prof.charter_capital_vnd,
            company_status=prof.company_status,
            profile=prof,
            is_cached=False,
        )

    async def verify_lead_corporate_info(
        self,
        *,
        workspace_id: int,
        lead_id: UUID,
        force_refresh: bool = False,
    ) -> CorporateMatchResult:
        """Enrich a lead entity with verified corporate MST, legal rep, and capital (AD-31 / INV-24.3)."""
        lead = await self.session.get(Lead, lead_id)
        if not lead or lead.workspace_id != workspace_id:
            return CorporateMatchResult(
                is_verified=False,
                degraded=True,
                degradation_reason="lead_not_found_or_tenant_mismatch",
            )

        city, district = self._parse_location(lead.location)

        match_res = await self.verify_company(
            company_name=lead.company_name,
            city=city,
            district=district,
            tax_id=getattr(lead, "tax_id", None),
            force_refresh=force_refresh,
        )

        if match_res.is_verified and match_res.profile:
            lead.tax_id = match_res.profile.tax_id
            lead.legal_representative = match_res.profile.legal_representative
            lead.charter_capital_vnd = match_res.profile.charter_capital_vnd
            lead.company_status = match_res.profile.company_status
            lead.enriched = True
            await self.session.flush()

        return match_res
