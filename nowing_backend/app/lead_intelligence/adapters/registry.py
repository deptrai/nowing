"""Dynamic registry and routing for universal lead source adapters (Story 21.15)."""

from __future__ import annotations

import logging
from typing import ClassVar

from app.lead_intelligence.adapters.base import (
    LeadSourceAdapter,
    LeadSourceCategory,
)

logger = logging.getLogger(__name__)


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
        self._adapters[adapter.source_name] = adapter
        logger.info(
            "Registered lead adapter: %s [%s]",
            adapter.source_name,
            adapter.category.value,
        )

    def get(self, source_name: str) -> LeadSourceAdapter:
        """Retrieve an adapter by source_name. Raises KeyError if not found."""
        if source_name not in self._adapters:
            raise KeyError(f"No lead adapter registered for source: '{source_name}'")
        return self._adapters[source_name]

    def list_all(self) -> list[LeadSourceAdapter]:
        """List all currently registered adapters."""
        return list(self._adapters.values())

    def find_by_category(self, category: LeadSourceCategory) -> list[LeadSourceAdapter]:
        """Find adapters matching a specific domain category."""
        return [a for a in self._adapters.values() if a.category == category]

    def resolve_adapters_for_intent(self, prompt: str) -> list[LeadSourceAdapter]:
        """
        Route natural language user query to the most relevant scraper adapters.
        Falls back to all available adapters if query is broad or multi-intent.
        """
        prompt_lower = (prompt or "").lower()
        matched: list[LeadSourceAdapter] = []

        # Real Estate keywords
        bds_keywords = [
            "bđs",
            "bất động sản",
            "nhà đất",
            "chung cư",
            "biệt thự",
            "căn hộ",
            "mặt bằng",
            "nhà phố",
            "đất nền",
            "cho thuê",
            "ocean park",
        ]
        if any(k in prompt_lower for k in bds_keywords):
            for a in self.find_by_category(LeadSourceCategory.REAL_ESTATE):
                if a not in matched:
                    matched.append(a)

        # Recruitment / Hiring keywords
        job_keywords = [
            "tuyển dụng",
            "tuyển",
            "hiring",
            "developer",
            "engineer",
            "nhân sự",
            "việc làm",
            "topcv",
            "itviec",
            "hr",
        ]
        if any(k in prompt_lower for k in job_keywords):
            for a in self.find_by_category(LeadSourceCategory.JOB_MARKET):
                if a not in matched:
                    matched.append(a)

        # Enterprise / Public Procurement keywords
        ent_keywords = [
            "công ty",
            "doanh nghiệp",
            "mã số thuế",
            "mst",
            "gói thầu",
            "đấu thầu",
            "mua sắm công",
            "dự thầu",
            "chủ đầu tư",
        ]
        if any(k in prompt_lower for k in ent_keywords):
            for a in self.find_by_category(LeadSourceCategory.ENTERPRISE):
                if a not in matched:
                    matched.append(a)

        # Social keywords
        social_keywords = [
            "facebook",
            "twitter",
            "xactions",
            "mạng xã hội",
            "group",
            "nhóm",
            "bài đăng",
            "post",
            "môi giới",
        ]
        if any(k in prompt_lower for k in social_keywords):
            for a in self.find_by_category(LeadSourceCategory.SOCIAL):
                if a not in matched:
                    matched.append(a)

        # Default fallback: if no specific category matched, return all
        return matched if matched else self.list_all()
