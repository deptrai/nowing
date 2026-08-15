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

    def _register_defaults(self) -> None:
        """Auto-register all default built-in platform adapters."""
        from app.lead_intelligence.adapters.batdongsan import BatdongsanLeadAdapter
        from app.lead_intelligence.adapters.chotot import ChototLeadAdapter
        from app.lead_intelligence.adapters.enterprise import (
            EnterpriseProcurementLeadAdapter,
        )
        from app.lead_intelligence.adapters.job_market import JobMarketLeadAdapter
        from app.lead_intelligence.adapters.social import SocialLeadAdapter

        self.register(BatdongsanLeadAdapter())
        self.register(ChototLeadAdapter())
        self.register(JobMarketLeadAdapter())
        self.register(EnterpriseProcurementLeadAdapter())
        self.register(SocialLeadAdapter())

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
        ent_keywords = [
            "công ty",
            "cong ty",
            "doanh nghiệp",
            "doanh nghiep",
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

        # Social keywords
        social_keywords = [
            "facebook",
            "twitter",
            "xactions",
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

        # Default fallback: if no specific category matched, return all
        return matched if matched else self.list_all()
