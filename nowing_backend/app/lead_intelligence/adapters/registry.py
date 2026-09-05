"""Dynamic registry and routing for universal lead source adapters (Story 21.15)."""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, ClassVar

from app.lead_intelligence.adapters.base import (
    LeadSourceAdapter,
    LeadSourceCategory,
)

logger = logging.getLogger(__name__)


def _strip_vietnamese_diacritics(text: str) -> str:
    """Normalize and remove Vietnamese accents/diacritics."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    # Replace Vietnamese special 'đ' / 'Đ'
    return stripped.replace("đ", "d").replace("Đ", "D").lower()


_SOURCE_KEYWORDS: dict[str, list[str]] = {
    "vietnamworks": ["vietnamworks", "vietnam works"],
    "vn_jobs": ["vn_jobs", "vn jobs", "vnjobs"],
    "job_market": ["topcv", "itviec", "it viec", "job market"],
    "muasamcong": ["muasamcong", "mua sắm công", "mua sam cong"],
    "muaban_bds": ["muaban_bds", "muaban", "mua bán", "mua ban"],
}


_JOB_MARKET_PRIORITY = ["vn_jobs", "job_market", "vietnamworks"]


def _source_keyword_present(source_name: str, prompt: str) -> bool:
    """Check whether ``prompt`` explicitly names a source adapter."""
    raw_lower = (prompt or "").lower()
    plain = _strip_vietnamese_diacritics(raw_lower)
    for keyword in _SOURCE_KEYWORDS.get(source_name, []):
        keyword_plain = _strip_vietnamese_diacritics(keyword)
        if keyword in raw_lower or keyword_plain in plain:
            return True
    return False


class LeadSourceAdapterRegistry:
    """Central registry for discovering, filtering, and resolving scraper adapters."""

    _instance: ClassVar[LeadSourceAdapterRegistry | None] = None

    def __init__(self) -> None:
        self._adapters: dict[str, LeadSourceAdapter] = {}

    @classmethod
    def get_default(cls) -> LeadSourceAdapterRegistry:
        """Get or initialize singleton default registry."""
        if cls._instance is None:
            registry = cls()
            registry._register_defaults()
            cls._instance = registry
        return cls._instance

    @classmethod
    def get_instance(cls) -> LeadSourceAdapterRegistry:
        """Alias for get_default."""
        return cls.get_default()

    def _register_defaults(self) -> None:
        """Auto-register all default built-in platform adapters."""
        from app.lead_intelligence.adapters.batdongsan import BatdongsanLeadAdapter
        from app.lead_intelligence.adapters.chotot import ChototLeadAdapter
        from app.lead_intelligence.adapters.enterprise import (
            EnterpriseProcurementLeadAdapter,
        )
        from app.lead_intelligence.adapters.job_market import JobMarketLeadAdapter
        from app.lead_intelligence.adapters.muaban_bds import MuabanBdsLeadAdapter
        from app.lead_intelligence.adapters.muasamcong import MuaSamCongLeadAdapter
        from app.lead_intelligence.adapters.social import SocialLeadAdapter
        from app.lead_intelligence.adapters.telegram import TelegramLeadAdapter
        from app.lead_intelligence.adapters.vietnamworks import VietnamWorksLeadAdapter
        from app.lead_intelligence.adapters.vn_jobs import VnJobsLeadAdapter

        self.register(BatdongsanLeadAdapter())
        self.register(ChototLeadAdapter())
        self.register(MuabanBdsLeadAdapter())
        self.register(JobMarketLeadAdapter())
        self.register(VnJobsLeadAdapter())
        self.register(VietnamWorksLeadAdapter())
        self.register(EnterpriseProcurementLeadAdapter())
        self.register(MuaSamCongLeadAdapter())
        self.register(SocialLeadAdapter())
        self.register(TelegramLeadAdapter())

    def register(self, adapter: LeadSourceAdapter) -> None:
        """Register a concrete adapter."""
        key = adapter.source_name.strip().lower()
        self._adapters[key] = adapter
        logger.info(
            "Registered lead adapter: %s [%s]",
            adapter.source_name,
            adapter.category.value,
        )

    def get(self, source_name: str) -> LeadSourceAdapter:
        """Retrieve an adapter by source_name (case-insensitive). Raises KeyError if not found."""
        key = (source_name or "").strip().lower()
        if key not in self._adapters:
            raise KeyError(f"No lead adapter registered for source: '{source_name}'")
        return self._adapters[key]

    def get_adapter(self, source_name: str) -> LeadSourceAdapter:
        """Alias for get."""
        return self.get(source_name)

    def list_all(self) -> list[LeadSourceAdapter]:
        """List all currently registered adapters."""
        return list(self._adapters.values())

    def find_by_category(self, category: LeadSourceCategory) -> list[LeadSourceAdapter]:
        """Find adapters matching a specific domain category."""
        return [a for a in self._adapters.values() if a.category == category]

    def resolve_adapters_for_spec(self, campaign_spec: Any) -> list[LeadSourceAdapter]:
        """
        Dynamically route and select scraper adapters for a structured CampaignSpec.
        Considers explicit target sources, ICP vertical criteria, buying signal triggers,
        intent tags, and source budget constraints.
        """
        # 1. Handle explicit target_sources if provided
        target_sources = getattr(campaign_spec, "target_sources", None) or []
        excluded_sources = {
            s.lower().strip() for s in (getattr(campaign_spec, "excluded_sources", None) or [])
        }

        if target_sources:
            selected: list[LeadSourceAdapter] = []
            for src_name in target_sources:
                key = src_name.lower().strip()
                if key in self._adapters and key not in excluded_sources:
                    selected.append(self._adapters[key])
            return selected

        # 2. Check source budgets for zero/negative allocations
        budget_sources = getattr(campaign_spec, "source_budgets", None) or []
        for b in budget_sources:
            if getattr(b, "max_leads", 1) <= 0:
                excluded_sources.add(getattr(b, "source_name", "").lower().strip())

        matched_adapters: list[LeadSourceAdapter] = []

        # 3. Resolve via ICP target_categories
        icp_criteria = getattr(campaign_spec, "icp_criteria", None)
        if icp_criteria is not None:
            target_categories = getattr(icp_criteria, "target_categories", []) or []
            for cat in target_categories:
                for a in self.find_by_category(cat):
                    if a not in matched_adapters and a.source_name.lower() not in excluded_sources:
                        matched_adapters.append(a)

            # Check target industries & keywords for vertical intent
            target_industries = [
                i.lower() for i in (getattr(icp_criteria, "target_industries", []) or [])
            ]
            target_keywords = [
                k.lower() for k in (getattr(icp_criteria, "target_keywords", []) or [])
            ]
            all_text = " ".join(target_industries + target_keywords)
            if all_text:
                raw_lower = all_text.lower()
                plain_lower = _strip_vietnamese_diacritics(raw_lower)
                # Only add if specifically matched keywords
                bds_keywords = [
                    "bđs", "bds", "bất động sản", "bat dong san", "nhà đất", "nha dat",
                    "chung cư", "chung cu", "biệt thự", "biet thu", "căn hộ", "can ho",
                    "mặt bằng", "mat bang", "nhà phố", "nha pho", "đất nền", "dat nen",
                    "cho thuê", "cho thue", "ocean park", "vinhome", "vinhomes",
                ]
                if any(k in raw_lower or k in plain_lower for k in bds_keywords):
                    for a in self.find_by_category(LeadSourceCategory.REAL_ESTATE):
                        if a not in matched_adapters and a.source_name.lower() not in excluded_sources:
                            matched_adapters.append(a)

                job_keywords = [
                    "tuyển dụng", "tuyen dung", "tuyen", "hiring", "developer", "engineer",
                    "nhân sự", "nhan su", "việc làm", "viec lam", "topcv", "itviec",
                    "vietnamworks", "vn_jobs", "vnjobs", "recruitment", "software",
                    "information technology", "công nghệ thông tin", "lap trinh",
                ]
                if any(k in raw_lower or k in plain_lower for k in job_keywords) or re.search(r"\bhr\b", raw_lower):
                    for a in self.find_by_category(LeadSourceCategory.JOB_MARKET):
                        if a not in matched_adapters and a.source_name.lower() not in excluded_sources:
                            matched_adapters.append(a)

        # 4. Resolve via buying signal triggers and intent tags
        signal_triggers = [
            s.lower().strip() for s in (getattr(campaign_spec, "signal_triggers", []) or [])
        ]
        intent_tags = [
            t.lower().strip() for t in (getattr(campaign_spec, "intent_tags", []) or [])
        ]
        all_signals = set(signal_triggers + intent_tags)

        if "hiring" in all_signals or "recruitment" in all_signals or "jobs" in all_signals:
            for a in self.find_by_category(LeadSourceCategory.JOB_MARKET):
                if a not in matched_adapters and a.source_name.lower() not in excluded_sources:
                    matched_adapters.append(a)

        if "tender" in all_signals or "bidding" in all_signals or "procurement" in all_signals or "muasamcong" in all_signals:
            for a in self.find_by_category(LeadSourceCategory.ENTERPRISE):
                if a.source_name == "muasamcong" and a not in matched_adapters and a.source_name.lower() not in excluded_sources:
                    matched_adapters.append(a)

        if "enterprise" in all_signals or "funding" in all_signals or "tax" in all_signals or "mst" in all_signals:
            for a in self.find_by_category(LeadSourceCategory.ENTERPRISE):
                if a.source_name == "enterprise" and a not in matched_adapters and a.source_name.lower() not in excluded_sources:
                    matched_adapters.append(a)

        if "real_estate" in all_signals or "bds" in all_signals or "property" in all_signals:
            for a in self.find_by_category(LeadSourceCategory.REAL_ESTATE):
                if a not in matched_adapters and a.source_name.lower() not in excluded_sources:
                    matched_adapters.append(a)

        if "social" in all_signals or "community" in all_signals or "telegram" in all_signals:
            for a in self.find_by_category(LeadSourceCategory.SOCIAL):
                if a not in matched_adapters and a.source_name.lower() not in excluded_sources:
                    matched_adapters.append(a)

        # 5. If query is provided and nothing or few matched, check query intent
        query = getattr(campaign_spec, "query", "") or ""
        if not matched_adapters and query:
            matched_adapters = self.resolve_adapters_for_intent(query)

        # 6. Fallback: if still empty, return all registered non-excluded adapters
        if not matched_adapters:
            matched_adapters = [
                a for a in self.list_all() if a.source_name.lower() not in excluded_sources
            ]
        else:
            matched_adapters = [
                a for a in matched_adapters if a.source_name.lower() not in excluded_sources
            ]

        # Prioritize and deduplicate JOB_MARKET adapters if multiple are present
        by_category: dict[LeadSourceCategory, list[LeadSourceAdapter]] = {}
        for a in matched_adapters:
            by_category.setdefault(a.category, []).append(a)

        deduped: list[LeadSourceAdapter] = []
        for category, adapters in by_category.items():
            if category == LeadSourceCategory.JOB_MARKET and len(adapters) > 1 and query:
                selected: list[LeadSourceAdapter] = [
                    a for a in adapters if _source_keyword_present(a.source_name, query)
                ]
                if not selected:
                    for name in _JOB_MARKET_PRIORITY:
                        for a in adapters:
                            if a.source_name == name:
                                selected.append(a)
                                break
                        if selected:
                            break
                if selected:
                    deduped.extend(selected)
                else:
                    deduped.extend(adapters)
            else:
                deduped.extend(adapters)

        return deduped

    def resolve_adapters_for_intent(self, prompt: str) -> list[LeadSourceAdapter]:
        """
        Route natural language user query to the most relevant scraper adapters.
        Supports accented and non-accented Vietnamese with boundary matching.
        Falls back to all available adapters if query is broad or multi-intent.
        """
        raw_lower = (prompt or "").lower()
        plain_lower = _strip_vietnamese_diacritics(raw_lower)
        matched: list[LeadSourceAdapter] = []

        # Real Estate keywords (accented + unaccented)
        bds_keywords = [
            "bđs",
            "bds",
            "bất động sản",
            "bat dong san",
            "nhà đất",
            "nha dat",
            "chung cư",
            "chung cu",
            "biệt thự",
            "biet thu",
            "căn hộ",
            "can ho",
            "mặt bằng",
            "mat bang",
            "nhà phố",
            "nha pho",
            "đất nền",
            "dat nen",
            "cho thuê",
            "cho thue",
            "ocean park",
            "vinhome",
            "vinhomes",
        ]
        if any(k in raw_lower or k in plain_lower for k in bds_keywords):
            for a in self.find_by_category(LeadSourceCategory.REAL_ESTATE):
                if a not in matched:
                    matched.append(a)

        # Recruitment / Hiring keywords
        job_keywords = [
            "tuyển dụng",
            "tuyen dung",
            "tuyen",
            "hiring",
            "developer",
            "engineer",
            "nhân sự",
            "nhan su",
            "việc làm",
            "viec lam",
            "topcv",
            "itviec",
            "vietnamworks",
            "vn_jobs",
            "vnjobs",
            "recruitment",
        ]
        # Check boundary words or substrings
        if any(k in raw_lower or k in plain_lower for k in job_keywords) or re.search(
            r"\bhr\b", raw_lower
        ):
            for a in self.find_by_category(LeadSourceCategory.JOB_MARKET):
                if a not in matched:
                    matched.append(a)

        # Public Procurement keywords — trigger only Mua Sắm Công, not the
        # Masothue enterprise directory.
        proc_keywords = [
            "muasamcong",
            "mua sắm công",
            "mua sam cong",
            "gói thầu",
            "goi thau",
            "đấu thầu",
            "dau thau",
            "dự thầu",
            "du thau",
            "chủ đầu tư",
            "chu dau tu",
        ]
        if any(
            k in raw_lower or k in plain_lower for k in proc_keywords
        ) or re.search(r"\bmuasamcong\b", raw_lower):
            for a in self.find_by_category(LeadSourceCategory.ENTERPRISE):
                if a.source_name == "muasamcong" and a not in matched:
                    matched.append(a)

        # Enterprise / Tax keywords
        ent_keywords = [
            "mã số thuế",
            "ma so thue",
            "mst",
        ]
        if any(k in raw_lower or k in plain_lower for k in ent_keywords) or re.search(
            r"\bmst\b", raw_lower
        ):
            for a in self.find_by_category(LeadSourceCategory.ENTERPRISE):
                if a.source_name == "enterprise" and a not in matched:
                    matched.append(a)

        # Social & Telegram keywords
        social_keywords = [
            "facebook",
            "twitter",
            "xactions",
            "telegram",
            "tele",
            "tg",
            "kênh telegram",
            "userbot",
            "mạng xã hội",
            "mang xa hoi",
            "group",
            "nhóm",
            "nhom",
            "bài đăng",
            "bai dang",
            "môi giới",
            "moi gioi",
        ]

        if any(
            k in raw_lower or k in plain_lower for k in social_keywords
        ) or re.search(r"\bpost\b", raw_lower):
            for a in self.find_by_category(LeadSourceCategory.SOCIAL):
                if a not in matched:
                    matched.append(a)

        # ponytail: job-market category now has multiple overlapping adapters
        # (vn_jobs aggregate, job_market direct, vietnamworks direct). For a
        # generic job query we want one call; for an explicit source keyword we
        # select that source (or all explicitly named sources). Upgrade path:
        # richer per-source keyword model.
        if not matched:
            matched = self.list_all()

        by_category: dict[LeadSourceCategory, list[LeadSourceAdapter]] = {}
        for a in matched:
            by_category.setdefault(a.category, []).append(a)

        deduped: list[LeadSourceAdapter] = []
        for category, adapters in by_category.items():
            if category == LeadSourceCategory.JOB_MARKET and len(adapters) > 1:
                selected: list[LeadSourceAdapter] = [
                    a for a in adapters if _source_keyword_present(a.source_name, prompt)
                ]
                if not selected:
                    for name in _JOB_MARKET_PRIORITY:
                        for a in adapters:
                            if a.source_name == name:
                                selected.append(a)
                                break
                        if selected:
                            break
                if selected:
                    deduped.extend(selected)
                else:
                    deduped.extend(adapters)
            else:
                deduped.extend(adapters)

        return deduped

    @classmethod
    def calculate_location_coverage_score(
        cls,
        adapter: LeadSourceAdapter,
        location_profile: Any | None,
    ) -> float:
        """Calculate a 0.0 - 1.0 coverage score for an adapter based on location targeting (AC-2)."""
        if location_profile is None:
            return 1.0

        p_code = (
            getattr(location_profile, "province_code", None)
            or (
                location_profile.get("province_code")
                if isinstance(location_profile, dict)
                else None
            )
            or ""
        ).upper().strip()

        if not p_code:
            return 1.0

        supported = getattr(adapter, "supported_provinces", ["*"]) or ["*"]
        coverage_map = getattr(adapter, "coverage_quality_by_location", {}) or {}

        quality_scores = {
            "high": 1.0,
            "medium": 0.7,
            "low": 0.4,
            "none": 0.0,
        }

        # Check district override if present
        d_codes = (
            getattr(location_profile, "district_codes", [])
            or (
                location_profile.get("district_codes")
                if isinstance(location_profile, dict)
                else []
            )
            or []
        )
        district_score = None
        for dc in d_codes:
            if dc in coverage_map:
                q = coverage_map[dc]
                score = (
                    quality_scores.get(str(q).lower(), 0.7)
                    if isinstance(q, str)
                    else float(q)
                )
                if district_score is None or score > district_score:
                    district_score = score
        if district_score is not None:
            return district_score

        # Check province in coverage map
        if p_code in coverage_map:
            q = coverage_map[p_code]
            return (
                quality_scores.get(str(q).lower(), 0.7)
                if isinstance(q, str)
                else float(q)
            )

        # Check if province is supported directly
        if p_code in supported:
            return 0.7

        # Check if nationwide adapter
        if "*" in supported:
            return 0.6

        return 0.0

    def resolve_adapters_for_campaign(
        self,
        prompt: Any = "",
        category: LeadSourceCategory | None = None,
        location_profile: Any | None = None,
    ) -> tuple[list[LeadSourceAdapter], bool]:
        """Resolve, composite-rank, and return candidate adapters with fallback warning (AC-2).

        Accepts either a ``CampaignSpec`` object or a (prompt, category, location_profile)
        keyword argument set. Always returns a tuple of (ranked adapters, location_fallback).
        """
        campaign_spec = None
        if not isinstance(prompt, str) and (hasattr(prompt, "__dict__") or isinstance(prompt, dict)):
            campaign_spec = prompt
            query_text = str(getattr(campaign_spec, "query", "") or "")
            icp_criteria = getattr(campaign_spec, "icp_criteria", None)
            if icp_criteria is not None:
                category = category or getattr(icp_criteria, "target_categories", [None])[0] if getattr(icp_criteria, "target_categories", []) else category
            location_profile = location_profile or getattr(campaign_spec, "location_profile", None)
        else:
            query_text = str(prompt or "")

        candidates = self.resolve_adapters_for_spec(campaign_spec) if campaign_spec is not None else []
        if not candidates:
            if category:
                candidates = self.find_by_category(category)
            if not candidates:
                candidates = self.resolve_adapters_for_intent(query_text)
        if not candidates:
            candidates = self.list_all()

        # Compute composite scores (0.4 location + 0.4 vertical + 0.2 cost)
        ranked: list[tuple[float, LeadSourceAdapter]] = []
        any_location_match = False

        for a in candidates:
            loc_score = self.calculate_location_coverage_score(a, location_profile)
            if loc_score > 0.0:
                any_location_match = True

            # Vertical relevance score (1.0 if category matches exactly, 0.8 otherwise)
            vert_score = 1.0 if (category and a.category == category) else 0.8

            # Cost efficiency score (default baseline 0.8 for internal scrapers)
            cost_score = 0.8

            composite = (loc_score * 0.4) + (vert_score * 0.4) + (cost_score * 0.2)
            ranked.append((composite, a))

        # Re-order candidate adapters descending by composite score
        ranked.sort(key=lambda x: x[0], reverse=True)

        location_fallback = bool(location_profile and not any_location_match)

        # Apply priority/quota hints based on composite score bands
        for idx, (_, a) in enumerate(ranked):
            a.priority = max(1, min(10, 10 - idx))
            a.lead_quota = max(10, 100 - idx * 10)

        return [a for _, a in ranked], location_fallback

