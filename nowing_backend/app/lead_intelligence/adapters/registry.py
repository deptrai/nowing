"""Dynamic registry and routing for universal lead source adapters (Story 21.15)."""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import ClassVar

from app.lead_intelligence.adapters.base import (
    LeadIntent,
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


_PRICE_KEYWORDS = [
    "tỷ",
    "triệu",
    "đồng",
    "vnđ",
    "vnd",
    "usd",
    "giá bán",
    "giá thuê",
    "giá dưới",
    "giá trên",
    "giá từ",
    "tổng giá",
    "mức giá",
]


_LOCATION_KEYWORDS = [
    "quận",
    "quan",
    "huyện",
    "huyen",
    "phường",
    "phuong",
    "thị trấn",
    "thi tran",
    "thành phố",
    "thanh pho",
    "tỉnh",
    "tinh",
    "hà nội",
    "ha noi",
    "hồ chí minh",
    "ho chi minh",
    "tp.hcm",
    "tphcm",
    "đà nẵng",
    "da nang",
    "hải phòng",
    "hai phong",
    "cần thơ",
    "can tho",
    "huế",
    "nha trang",
    "đà lạt",
]


def _has_keyword(prompt: str, keywords: list[str]) -> bool:
    """Check whether any keyword appears in the prompt (accented or unaccented)."""
    if not prompt:
        return False
    raw_lower = prompt.lower()
    plain = _strip_vietnamese_diacritics(raw_lower)
    return any(k in raw_lower or _strip_vietnamese_diacritics(k) in plain for k in keywords)


def _has_price_reference(prompt: str) -> bool:
    """Detect price references in the prompt."""
    return _has_keyword(prompt, _PRICE_KEYWORDS)


def _has_location_reference(prompt: str) -> bool:
    """Detect location / administrative unit references in the prompt."""
    raw_lower = prompt.lower() if prompt else ""
    plain = _strip_vietnamese_diacritics(raw_lower)
    if any(k in raw_lower or _strip_vietnamese_diacritics(k) in plain for k in _LOCATION_KEYWORDS):
        return True
    # Common two-letter city/province abbreviations used in Vietnamese listings.
    return bool(re.search(r"\b(hn|sg|dn|hp|ct)\b", raw_lower))


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

    def resolve_adapters_for_campaign(self, campaign_spec: Any) -> list[LeadSourceAdapter]:
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

    def resolve_adapters_for_intent(
        self,
        prompt: str,
        intent: LeadIntent | None = None,
    ) -> list[LeadSourceAdapter]:
        """
        Route natural language user query to the most relevant scraper adapters.

        Categories are mutually exclusive with REAL_ESTATE taking precedence,
        because a Vietnamese property query almost always contains location and
        price words that can look like generic keywords. If no specific domain
        signal is found but the prompt contains both a location and a price
        reference, we default to REAL_ESTATE. Broad queries with no signal fall
        back to all registered adapters.

        When ``intent`` is ``sell``, social buyer-demand sources are preferred
        (e.g., Facebook groups of buyers); if none are available or the query is
        clearly BĐS-related, the method falls back to BĐS listing adapters so the
        seller can still see comparable listings.
        """
        raw_lower = (prompt or "").lower()

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

        # Public Procurement keywords — trigger only Mua Sắm Công.
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

        # Enterprise / Tax keywords
        ent_keywords = [
            "mã số thuế",
            "ma so thue",
            "mst",
        ]

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
        ]

        # Select a single category using mutual-exclusion with REAL_ESTATE first.
        selected_category: LeadSourceCategory | None = None
        if _has_keyword(prompt, bds_keywords):
            selected_category = LeadSourceCategory.REAL_ESTATE
        elif _has_keyword(prompt, job_keywords) or re.search(r"\bhr\b", raw_lower):
            selected_category = LeadSourceCategory.JOB_MARKET
        elif (
            _has_keyword(prompt, proc_keywords)
            or _has_keyword(prompt, ent_keywords)
            or re.search(r"\bmuasamcong\b", raw_lower)
            or re.search(r"\bmst\b", raw_lower)
        ):
            selected_category = LeadSourceCategory.ENTERPRISE
        elif _has_keyword(prompt, social_keywords) or re.search(r"\bpost\b", raw_lower):
            selected_category = LeadSourceCategory.SOCIAL
        elif _has_price_reference(prompt) and _has_location_reference(prompt):
            # Default to real estate for queries that only provide location + price.
            selected_category = LeadSourceCategory.REAL_ESTATE

        # Seller intent: try buyer-demand sources first, then fall back to BĐS listings.
        if intent == LeadIntent.SELL:
            social_adapters = self.find_by_category(LeadSourceCategory.SOCIAL)
            bds_adapters: list[LeadSourceAdapter] = []
            if selected_category == LeadSourceCategory.REAL_ESTATE:
                bds_adapters = self.find_by_category(LeadSourceCategory.REAL_ESTATE)
            if social_adapters:
                return social_adapters + bds_adapters
            if selected_category is None:
                selected_category = LeadSourceCategory.REAL_ESTATE
            candidates = self.find_by_category(selected_category)
            if not candidates:
                candidates = self.find_by_category(LeadSourceCategory.REAL_ESTATE)
            return candidates

        if selected_category is None:
            return self.list_all()

        candidates = self.find_by_category(selected_category)

        # Enterprise contains both "enterprise" and "muasamcong"; disambiguate.
        if selected_category == LeadSourceCategory.ENTERPRISE:
            if _has_keyword(prompt, proc_keywords) or re.search(r"\bmuasamcong\b", raw_lower):
                candidates = [a for a in candidates if a.source_name == "muasamcong"]
            elif _has_keyword(prompt, ent_keywords) or re.search(r"\bmst\b", raw_lower):
                candidates = [a for a in candidates if a.source_name == "enterprise"]
            else:
                # Generic enterprise query without a subtype; keep all enterprise adapters.
                pass

        # Job market has overlapping adapters (vn_jobs, job_market, vietnamworks).
        # If the user explicitly names a source, use it; otherwise pick one generic
        # adapter using a priority list to avoid redundant calls.
        if selected_category == LeadSourceCategory.JOB_MARKET and len(candidates) > 1:
            selected = [a for a in candidates if _source_keyword_present(a.source_name, prompt)]
            if not selected:
                for name in _JOB_MARKET_PRIORITY:
                    for a in candidates:
                        if a.source_name == name:
                            selected.append(a)
                            break
                    if selected:
                        break
            candidates = selected if selected else candidates

        # Preserve stable ordering and remove duplicates.
        seen: set[str] = set()
        deduped: list[LeadSourceAdapter] = []
        for a in candidates:
            key = a.source_name.strip().lower()
            if key not in seen:
                seen.add(key)
                deduped.append(a)

        return deduped
