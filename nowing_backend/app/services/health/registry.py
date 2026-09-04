"""Health Probe Registry for discovering and managing probes by category."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import ClassVar

from sqlalchemy import and_, or_, select

from app.capabilities.core.store import CapabilityRegistry
from app.config import config
from app.db import async_session_maker
from app.models.connectors import Connection
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

# Canonical seed lists used when dynamic sources are unavailable.
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


def _platform_from_capability_name(name: str) -> str:
    """Map a capability name like 'cafef.scrape' to a platform slug."""
    first_part = name.split(".", 1)[0].lower()
    # Map composite namespaces to canonical platform slugs.
    aliases = {
        "b2b": "xactions",
        "ecommerce": "amazon",
        "google_maps": "google_maps",
        "google_search": "google_search",
        "realestate": "spatial_planning",
        "recruitment": "linkedin",
        "vn_bds": "batdongsan",
        "vn_jobs": "topcv",
    }
    return aliases.get(first_part, first_part)


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
        """Synchronously ensure the registry is initialized with at least seed data."""
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
        """Thread-safe async variant that also discovers DB- and config-backed probes."""
        if cls._initialized:
            return
        async with cls._init_lock:
            if cls._initialized:
                return
            # Seed first, then overlay dynamic discovery.
            cls.discover_default_probes()
            await cls._discover_dynamic_probes()
            cls._initialized = True

    @classmethod
    def reset(cls) -> None:
        """Reset registry for testing purposes."""
        cls._probes_by_id.clear()
        cls._probes_by_category.clear()
        cls._initialized = False

    @classmethod
    def _register_infrastructure_probes(cls) -> None:
        for component in ["postgres", "redis", "celery", "caddy", "zero"]:
            cls.register(InfrastructureHealthProbe(component=component))

    @classmethod
    def _register_model_probes(cls) -> None:
        """Discover model probes from in-memory global config/catalog."""
        global_models = getattr(config, "GLOBAL_MODELS", []) or []
        if not global_models:
            # Seed with a safe default set when no catalog is configured.
            global_models = [
                {"model_id": "azure-gpt-5", "display_name": "Azure OpenAI GPT-5", "provider": "azure"},
                {"model_id": "deepseek-chat", "display_name": "DeepSeek Chat", "provider": "deepseek"},
                {"model_id": "gemini-1.5-flash", "display_name": "Google Gemini 1.5 Flash", "provider": "gemini"},
                {"model_id": "qwen", "display_name": "Local vLLM Qwen 14B", "provider": "vllm"},
                {"model_id": "text-embedding-3-small", "display_name": "OpenAI Text Embedding Small", "provider": "openai"},
            ]

        seen_ids = set()
        for model in global_models:
            model_id = str(model.get("model_id") or "")
            provider = str(model.get("provider") or model.get("litellm_provider") or "openai")
            display_name = model.get("display_name") or model_id
            service_id = f"model/{model_id}" if provider != "vllm" else f"local/{model_id}"
            if service_id in seen_ids:
                continue
            seen_ids.add(service_id)
            cls.register(
                ModelHealthProbe(
                    service_id=service_id,
                    service_name=display_name,
                    provider=provider,
                    model_id=model_id,
                    display_group=model.get("role", "Chat Models") if isinstance(model.get("role"), str) else "Chat Models",
                )
            )

    @classmethod
    def _register_scraper_probes(cls, capability_platforms: set[str]) -> None:
        """Register scraper probes, overlaying seed list with discovered capabilities."""
        registered_platforms: set[str] = set()

        for cap in CapabilityRegistry.all():
            platform = _platform_from_capability_name(cap.name)
            if platform in registered_platforms:
                continue
            if any(p == platform for p, _, _ in CANONICAL_SCRAPER_PLATFORMS):
                name = next((n for p, n, _ in CANONICAL_SCRAPER_PLATFORMS if p == platform), platform.replace("_", " ").title())
                group = next((g for p, _, g in CANONICAL_SCRAPER_PLATFORMS if p == platform), "Platform Scrapers")
            else:
                name = cap.description or platform.replace("_", " ").title()
                group = "Platform Scrapers"
            cls.register(ScraperHealthProbe(platform=platform, service_name=name, display_group=group))
            registered_platforms.add(platform)

        for platform, name, group in CANONICAL_SCRAPER_PLATFORMS:
            if platform not in registered_platforms and platform not in capability_platforms:
                cls.register(ScraperHealthProbe(platform=platform, service_name=name, display_group=group))
                registered_platforms.add(platform)

    @classmethod
    async def _register_connector_probes(cls) -> None:
        """Discover active connector probes from the database, falling back to seed list."""
        db_types: set[str] = set()
        try:
            async with async_session_maker() as session:
                stmt = select(Connection.provider).where(
                    and_(
                        Connection.enabled.is_(True),
                        or_(
                            Connection.api_key.isnot(None),
                            Connection.extra.isnot(None),
                        ),
                    )
                ).distinct()
                res = await session.execute(stmt)
                db_types = {str(row[0]).lower() for row in res.fetchall() if row[0]}
        except Exception as exc:
            logger.warning("Failed to discover connector probes from DB: %s", exc)

        seed_by_type = {t: (n, g) for t, n, g in CANONICAL_CONNECTORS}

        for conn_type in db_types:
            name, group = seed_by_type.get(conn_type, (conn_type.replace("_", " ").title(), "SaaS Connectors"))
            cls.register(ConnectorHealthProbe(connector_type=conn_type, service_name=name, display_group=group))

        for conn_type, name, group in CANONICAL_CONNECTORS:
            if conn_type not in db_types:
                cls.register(ConnectorHealthProbe(connector_type=conn_type, service_name=name, display_group=group))

    @classmethod
    def _register_messaging_payment_storage_proxy_research(cls) -> None:
        cls.register(ProxyHealthProbe())
        cls.register(ChainLensHealthProbe())
        for msg_provider in ["telegram", "slack", "discord"]:
            cls.register(MessagingHealthProbe(provider=msg_provider))
        cls.register(PaymentHealthProbe(provider="stripe"))
        cls.register(StorageHealthProbe(provider="s3"))

    @classmethod
    async def _discover_dynamic_probes(cls) -> None:
        """Overlay dynamic scraper/model/connector discovery on top of seed data."""
        capability_platforms = {
            _platform_from_capability_name(cap.name) for cap in CapabilityRegistry.all()
        }

        # Scraper discovery happens synchronously; re-register in case capabilities changed.
        # Reset scraper category so we do not keep stale probes.
        cls._probes_by_category["scraper"] = [p for p in cls._probes_by_category.get("scraper", []) if False]
        for probe in list(cls._probes_by_id.values()):
            if probe.category == "scraper":
                del cls._probes_by_id[probe.service_id]
        cls._register_scraper_probes(capability_platforms)

        # Model discovery from config.
        for probe in list(cls._probes_by_id.values()):
            if probe.category == "model":
                del cls._probes_by_id[probe.service_id]
        cls._probes_by_category["model"] = []
        cls._register_model_probes()

        # Connector discovery from DB.
        for probe in list(cls._probes_by_id.values()):
            if probe.category == "connector":
                del cls._probes_by_id[probe.service_id]
        cls._probes_by_category["connector"] = []
        await cls._register_connector_probes()

    @classmethod
    def discover_default_probes(cls) -> None:
        """Populate the default probe set across all required categories.

        This synchronous method is used for fast sync access. The async
        ``ensure_initialized`` path overlays dynamic discovery from the DB and
        CapabilityRegistry.
        """
        cls._register_infrastructure_probes()
        cls._register_model_probes()
        cls._register_scraper_probes(set())
        cls._register_messaging_payment_storage_proxy_research()
