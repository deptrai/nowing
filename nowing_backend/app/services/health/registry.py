"""Health Probe Registry for discovering and managing probes by category."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import ClassVar

from app.services.health.probe_base import HealthProbe
from app.services.health.probes.chainlens_probe import ChainLensHealthProbe
from app.services.health.probes.connector_probe import ConnectorHealthProbe
from app.services.health.probes.infrastructure_probe import InfrastructureHealthProbe
from app.services.health.probes.messaging_probe import MessagingHealthProbe
from app.services.health.probes.model_probe import ModelHealthProbe
from app.services.health.probes.payment_probe import PaymentHealthProbe
from app.services.health.probes.proxy_probe import ProxyHealthProbe
from app.services.health.probes.scraper_probe import ScraperHealthProbe
from app.services.health.probes.storage_probe import StorageHealthProbe

logger = logging.getLogger(__name__)

# Canonical list of 25 platform scrapers
CANONICAL_SCRAPER_PLATFORMS = [
    ("amazon", "Amazon Product Scraper", "E-Commerce"),
    ("batdongsan", "Batdongsan.com.vn", "Vietnam Real Estate"),
    ("cafef", "CafeF Stock & Financials", "Vietnam Finance"),
    ("chotot", "Cho Tot Marketplace", "Vietnam Classifieds"),
    ("crawler", "General Web Crawler", "Web Scraping"),
    ("google_maps", "Google Maps Local Places", "Search & Places"),
    ("google_search", "Google Search Engine", "Search & Places"),
    ("indeed", "Indeed Job Board", "Recruitment"),
    ("instagram", "Instagram Public Profile", "Social Networks"),
    ("itviec", "ITviec Tech Jobs", "Recruitment"),
    ("linkedin", "LinkedIn B2B & Jobs", "B2B Professional"),
    ("masothue", "MaSoThue Business Registry", "Vietnam Registry"),
    ("muaban_bds", "Muaban.net Real Estate", "Vietnam Real Estate"),
    ("muasamcong", "Mua Sam Cong Public Procurement", "Vietnam Public Tenders"),
    ("reddit", "Reddit Communities", "Social & Forums"),
    ("shopee", "Shopee E-Commerce", "E-Commerce"),
    ("spatial_planning", "Spatial Planning GIS Gateway", "Planning & Zoning"),
    ("telegram", "Telegram Channels & Preview", "Messaging"),
    ("tiktok", "TikTok Video & Profiles", "Social Networks"),
    ("topcv", "TopCV Vietnam Jobs", "Recruitment"),
    ("vietnamworks", "VietnamWorks Jobs", "Recruitment"),
    ("vietstock", "Vietstock Financial Portal", "Vietnam Finance"),
    ("walmart", "Walmart Marketplace", "E-Commerce"),
    ("xactions", "Xactions Social Graph", "B2B Lead Intelligence"),
    ("youtube", "YouTube Videos & Channels", "Video & Media"),
]

CANONICAL_CONNECTORS = [
    ("google_drive", "Google Drive", "Google Workspace"),
    ("google_gmail", "Gmail", "Google Workspace"),
    ("google_calendar", "Google Calendar", "Google Workspace"),
    ("google_sheets", "Google Sheets", "Google Workspace"),
    ("slack", "Slack", "Team Communication"),
    ("discord", "Discord", "Community"),
    ("jira", "Jira Software", "Atlassian"),
    ("confluence", "Confluence Wiki", "Atlassian"),
    ("notion", "Notion Workspace", "Productivity"),
    ("airtable", "Airtable Relational", "Productivity"),
    ("linear", "Linear Issue Tracker", "Developer Tools"),
    ("github", "GitHub Source & PRs", "Developer Tools"),
    ("dropbox", "Dropbox Storage", "Storage & Files"),
    ("clickup", "ClickUp Task Management", "Productivity"),
]


class HealthProbeRegistry:
    """Registry maintaining all active health probes grouped by category."""

    _probes_by_id: ClassVar[dict[str, HealthProbe]] = {}
    _probes_by_category: ClassVar[dict[str, list[HealthProbe]]] = defaultdict(list)
    _initialized: ClassVar[bool] = False
    _init_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    @classmethod
    def register(cls, probe: HealthProbe) -> None:
        """Register a probe instance."""
        cls._probes_by_id[probe.service_id] = probe
        # Replace if existing in category list
        cat_list = cls._probes_by_category[probe.category]
        cls._probes_by_category[probe.category] = [p for p in cat_list if p.service_id != probe.service_id] + [probe]

    @classmethod
    def _ensure_sync(cls) -> None:
        """Synchronously ensure the registry is initialized."""
        if not cls._initialized:
            cls.discover_default_probes()
            cls._initialized = True

    @classmethod
    def get_probe(cls, service_id: str) -> HealthProbe | None:
        """Lookup a probe by its unique service_id."""
        cls._ensure_sync()
        return cls._probes_by_id.get(service_id)

    @classmethod
    def get_probes(cls, category: str | None = None) -> list[HealthProbe]:
        """Get all registered probes, optionally filtered by category."""
        cls._ensure_sync()
        if category:
            return list(cls._probes_by_category.get(category, []))
        return list(cls._probes_by_id.values())

    @classmethod
    def get_categories(cls) -> list[str]:
        """Return list of distinct registered categories."""
        cls._ensure_sync()
        return sorted(cls._probes_by_category.keys())

    @classmethod
    async def ensure_initialized(cls) -> None:
        """Thread-safe async variant of ensure_initialized."""
        if cls._initialized:
            return
        async with cls._init_lock:
            if cls._initialized:
                return
            cls.discover_default_probes()
            cls._initialized = True

    @classmethod
    def reset(cls) -> None:
        """Reset registry for testing purposes."""
        cls._probes_by_id.clear()
        cls._probes_by_category.clear()
        cls._initialized = False

    @classmethod
    def discover_default_probes(cls) -> None:
        """Populate the default probe set across all required categories."""
        # 1. Infrastructure probes
        for component in ["postgres", "redis", "celery", "caddy", "zero"]:
            cls.register(InfrastructureHealthProbe(component=component))

        # 2. LLM / AI Model probes
        cls.register(
            ModelHealthProbe(
                service_id="model/azure-gpt-5",
                service_name="Azure OpenAI GPT-5",
                provider="azure",
                model_id="gpt-5",
                display_group="Chat Models",
            )
        )
        cls.register(
            ModelHealthProbe(
                service_id="model/deepseek-chat",
                service_name="DeepSeek Chat",
                provider="deepseek",
                model_id="deepseek-chat",
                display_group="Chat Models",
            )
        )
        cls.register(
            ModelHealthProbe(
                service_id="model/gemini-1.5-flash",
                service_name="Google Gemini 1.5 Flash",
                provider="gemini",
                model_id="gemini-1.5-flash",
                display_group="Chat Models",
            )
        )
        cls.register(
            ModelHealthProbe(
                service_id="local/vllm",
                service_name="Local vLLM Qwen 14B",
                provider="vllm",
                model_id="qwen",
                display_group="Local Inference",
            )
        )
        cls.register(
            ModelHealthProbe(
                service_id="model/text-embedding-3-small",
                service_name="OpenAI Text Embedding Small",
                provider="openai",
                model_id="text-embedding-3-small",
                display_group="Embedding Models",
            )
        )

        # 3. Scrapers probes (25 canonical platforms)
        for platform, name, group in CANONICAL_SCRAPER_PLATFORMS:
            cls.register(ScraperHealthProbe(platform=platform, service_name=name, display_group=group))

        # 4. SaaS Connectors
        for conn_type, name, group in CANONICAL_CONNECTORS:
            cls.register(ConnectorHealthProbe(connector_type=conn_type, service_name=name, display_group=group))

        # 5. Proxy probe
        cls.register(ProxyHealthProbe())

        # 6. ChainLens Research probe
        cls.register(ChainLensHealthProbe())
        # 7. Messaging
        for msg_provider in ["telegram", "slack", "discord"]:
            cls.register(MessagingHealthProbe(provider=msg_provider))

        # 8. Payment
        cls.register(PaymentHealthProbe(provider="stripe"))

        # 9. Storage
        cls.register(StorageHealthProbe(provider="s3"))

