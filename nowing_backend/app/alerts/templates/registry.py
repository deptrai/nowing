"""Registry and catalog for Vertical Alert Rule Templates (Story 6.11)."""

from __future__ import annotations

import logging
from typing import ClassVar

from app.alerts.templates.models import (
    AlertTemplate,
    AlertTemplateParameter,
    AlertTemplateRead,
)
from app.capabilities.core.store import CapabilityRegistry

logger = logging.getLogger(__name__)


def _is_capability_available(name: str) -> bool:
    try:
        CapabilityRegistry.get(name)
        return True
    except KeyError:
        return False


class VerticalAlertTemplateRegistry:
    """Registry maintaining canonical vertical alert rule templates."""

    _templates: ClassVar[dict[str, AlertTemplate]] = {}

    @classmethod
    def register(cls, template: AlertTemplate) -> None:
        cls._templates[template.template_id] = template

    @classmethod
    def get_template(cls, template_id: str) -> AlertTemplate | None:
        cls._ensure_initialized()
        return cls._templates.get(template_id)

    @classmethod
    def list_templates(cls) -> list[AlertTemplateRead]:
        """List all templates with live capability availability status."""
        cls._ensure_initialized()
        items: list[AlertTemplateRead] = []

        for tmpl in cls._templates.values():
            available = _is_capability_available(tmpl.required_capability)
            active_cap = tmpl.required_capability

            if not available:
                for fb in tmpl.fallback_capabilities:
                    if _is_capability_available(fb):
                        available = True
                        active_cap = fb
                        break

            reason = None if available else f"Required capability '{tmpl.required_capability}' is not registered or unavailable"

            items.append(
                AlertTemplateRead(
                    template_id=tmpl.template_id,
                    name=tmpl.name,
                    description=tmpl.description,
                    category=tmpl.category,
                    required_capability=active_cap,
                    diff_strategy=tmpl.diff_strategy,
                    default_schedule=tmpl.default_schedule,
                    parameters=tmpl.parameters,
                    is_available=available,
                    unavailable_reason=reason,
                )
            )
        return items

    @classmethod
    def _ensure_initialized(cls) -> None:
        if cls._templates:
            return

        # 1. News Topic Monitoring
        cls.register(
            AlertTemplate(
                template_id="news_topic_monitoring",
                name="News Topic & Entity Monitoring",
                description="Receive automated alerts when new articles mention a tracked company, person, or keyword.",
                category="news",
                required_capability="news.entity_search",
                fallback_capabilities=["news.rss", "google_search.scrape"],
                diff_strategy="new_items",
                default_schedule="daily",
                parameters=[
                    AlertTemplateParameter(
                        name="entity_name",
                        label="Topic or Entity Name",
                        description="Company, keyword, or person to track (e.g. VinFast, FPT)",
                        type="string",
                        required=True,
                    ),
                    AlertTemplateParameter(
                        name="entity_type",
                        label="Entity Type",
                        description="Filter entity category",
                        type="select",
                        required=False,
                        default="all",
                        options=[
                            {"value": "all", "label": "All Types"},
                            {"value": "organization", "label": "Companies & Organizations"},
                            {"value": "person", "label": "People & Executives"},
                            {"value": "location", "label": "Locations"},
                        ],
                    ),
                ],
            )
        )

        # 2. Stock Price Threshold
        cls.register(
            AlertTemplate(
                template_id="stock_price_threshold",
                name="Stock Price Threshold Crossing",
                description="Monitor Vietnamese stock tickers and alert when price moves above or below target value.",
                category="finance",
                required_capability="cafef.scrape",
                fallback_capabilities=["vietstock.scrape"],
                diff_strategy="threshold_cross",
                default_schedule="daily",
                parameters=[
                    AlertTemplateParameter(
                        name="symbol",
                        label="Stock Ticker Symbol",
                        description="3-letter ticker on HOSE/HNX/UPCoM (e.g. VNM, FPT, HPG)",
                        type="string",
                        required=True,
                    ),
                    AlertTemplateParameter(
                        name="price_threshold",
                        label="Price Threshold (VND)",
                        description="Target price level in VND (e.g. 65000)",
                        type="number",
                        required=True,
                    ),
                    AlertTemplateParameter(
                        name="direction",
                        label="Trigger Direction",
                        description="Alert when price crosses above or below",
                        type="select",
                        required=True,
                        default="below",
                        options=[
                            {"value": "below", "label": "Falls Below (<= Threshold)"},
                            {"value": "above", "label": "Rises Above (>= Threshold)"},
                        ],
                    ),
                ],
            )
        )

        # 3. Company Status Change
        cls.register(
            AlertTemplate(
                template_id="company_status_change",
                name="Corporate Registry Status Change",
                description="Track Vietnamese business status, legal representative, and tax status changes via masothue.com.",
                category="company",
                required_capability="masothue.scrape",
                diff_strategy="threshold_cross",
                default_schedule="weekly",
                parameters=[
                    AlertTemplateParameter(
                        name="query",
                        label="Tax Code or Company Name",
                        description="10 or 13-digit Tax Code (MST) or exact business name",
                        type="string",
                        required=True,
                    ),
                ],
            )
        )

        # 4. E-commerce Price Drop
        cls.register(
            AlertTemplate(
                template_id="ecommerce_price_drop",
                name="E-Commerce Price Drop Alert",
                description="Detect price drops on Shopee products matching a specific keyword or SKU.",
                category="ecommerce",
                required_capability="ecommerce.search_products",
                fallback_capabilities=["shopee.scrape"],
                diff_strategy="price_change",
                default_schedule="daily",
                parameters=[
                    AlertTemplateParameter(
                        name="keyword",
                        label="Product Search Keyword",
                        description="Product title, brand, or SKU identifier",
                        type="string",
                        required=True,
                    ),
                    AlertTemplateParameter(
                        name="percent_drop",
                        label="Minimum Price Drop Percentage",
                        description="Fraction of price drop to trigger alert (e.g. 0.05 for 5%)",
                        type="number",
                        required=False,
                        default=0.05,
                    ),
                ],
            )
        )

        # 5. Competitor Item Tracking
        cls.register(
            AlertTemplate(
                template_id="competitor_item_tracking",
                name="Competitor Product & SKU Tracking",
                description="Discover new competitor listings and variant changes in real time.",
                category="ecommerce",
                required_capability="ecommerce.search_products",
                fallback_capabilities=["shopee.scrape"],
                diff_strategy="new_items",
                default_schedule="daily",
                parameters=[
                    AlertTemplateParameter(
                        name="keyword",
                        label="Competitor Brand or Category Keyword",
                        description="E.g. brand name, category query",
                        type="string",
                        required=True,
                    ),
                    AlertTemplateParameter(
                        name="min_price",
                        label="Min Price Filter (VND)",
                        type="number",
                        required=False,
                    ),
                    AlertTemplateParameter(
                        name="max_price",
                        label="Max Price Filter (VND)",
                        type="number",
                        required=False,
                    ),
                ],
            )
        )
