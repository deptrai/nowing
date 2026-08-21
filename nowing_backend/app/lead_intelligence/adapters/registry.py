"""Dynamic registry and routing for universal lead source adapters (Story 21.15)."""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import ClassVar

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

        # Enterprise / Public Procurement keywords
        # ponytail: "công ty" / "doanh nghiệp" are too generic and collide with
        # job-market queries; keep explicit enterprise/tax/procurement terms.
        ent_keywords = [
            "mã số thuế",
            "ma so thue",
            "gói thầu",
            "goi thau",
            "đấu thầu",
            "dau thau",
            "mua sắm công",
            "mua sam cong",
            "dự thầu",
            "du thau",
            "chủ đầu tư",
            "chu dau tu",
        ]
        if any(k in raw_lower or k in plain_lower for k in ent_keywords) or re.search(
            r"\bmst\b", raw_lower
        ):
            for a in self.find_by_category(LeadSourceCategory.ENTERPRISE):
                if a not in matched:
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
