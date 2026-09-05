"""Unit tests for Vertical Alert Rule Templates (Story 6.11)."""

from __future__ import annotations

import pytest

from app.alerts.templates.compiler import (
    TemplateCompilationError,
    compile_template,
)
from app.alerts.templates.models import AlertTemplate
from app.alerts.templates.registry import (
    VerticalAlertTemplateRegistry,
)


def test_registry_initializes_five_canonical_templates() -> None:
    """Registry should contain the 5 canonical templates specified in AC-1."""
    templates = VerticalAlertTemplateRegistry.list_templates()
    template_ids = {t.template_id for t in templates}

    expected_ids = {
        "news_topic_monitoring",
        "stock_price_threshold",
        "company_status_change",
        "ecommerce_price_drop",
        "competitor_item_tracking",
    }
    assert expected_ids.issubset(template_ids)


def test_template_availability_reflects_capability_registry() -> None:
    """Registered capabilities have is_available=True; missing have is_available=False."""
    templates = VerticalAlertTemplateRegistry.list_templates()
    by_id = {t.template_id: t for t in templates}

    # cafef.scrape is registered in CapabilityRegistry
    stock_tmpl = by_id["stock_price_threshold"]
    assert stock_tmpl.is_available is True
    assert stock_tmpl.unavailable_reason is None

    # Custom template requiring an unregistered capability
    custom_tmpl = AlertTemplate(
        template_id="custom_unregistered",
        name="Custom Unregistered",
        description="Testing missing capability",
        category="custom",
        required_capability="unregistered.nonexistent",
        fallback_capabilities=[],
        diff_strategy="new_items",
        default_schedule="daily",
        parameters=[],
    )
    VerticalAlertTemplateRegistry.register(custom_tmpl)

    updated_templates = VerticalAlertTemplateRegistry.list_templates()
    by_id_updated = {t.template_id: t for t in updated_templates}
    assert by_id_updated["custom_unregistered"].is_available is False
    assert "not registered" in (by_id_updated["custom_unregistered"].unavailable_reason or "")


def test_compile_stock_price_threshold_success() -> None:
    """Stock template compiles symbol, price_threshold, direction into AlertRuleCreate."""
    tmpl = VerticalAlertTemplateRegistry.get_template("stock_price_threshold")
    assert tmpl is not None

    rule_create = compile_template(
        tmpl,
        name="Vinamilk Drop",
        parameters={
            "symbol": "VNM",
            "price_threshold": "65000",
            "direction": "below",
        },
        schedule="daily",
        notification_channels=["in_app", "telegram"],
    )

    assert rule_create.name == "Vinamilk Drop"
    assert rule_create.capability_id == "cafef.scrape"
    assert rule_create.schedule == "daily"
    assert rule_create.diff_strategy == "threshold_cross"
    assert rule_create.query == {"symbol": "VNM", "include_financials": False}
    assert rule_create.threshold == {
        "field": "price",
        "value": 65000.0,
        "direction": "below",
    }
    assert rule_create.notification_channels == ["in_app", "telegram"]


def test_compile_stock_price_threshold_missing_param_raises() -> None:
    """Missing required symbol or threshold should raise TemplateCompilationError."""
    tmpl = VerticalAlertTemplateRegistry.get_template("stock_price_threshold")
    assert tmpl is not None

    with pytest.raises(TemplateCompilationError, match="Missing required parameter 'symbol'"):
        compile_template(
            tmpl,
            name="Vinamilk Drop",
            parameters={"price_threshold": 65000},
        )


def test_compile_stock_price_threshold_invalid_number_raises() -> None:
    """Invalid numeric price_threshold should raise TemplateCompilationError."""
    tmpl = VerticalAlertTemplateRegistry.get_template("stock_price_threshold")
    assert tmpl is not None

    with pytest.raises(TemplateCompilationError, match="Invalid price_threshold"):
        compile_template(
            tmpl,
            name="Vinamilk Drop",
            parameters={
                "symbol": "VNM",
                "price_threshold": "not_a_number",
                "direction": "below",
            },
        )


def test_compile_news_topic_monitoring() -> None:
    """News template compiles entity_name, entity_type, workspace_id, limit."""
    tmpl = VerticalAlertTemplateRegistry.get_template("news_topic_monitoring")
    assert tmpl is not None

    rule_create = compile_template(
        tmpl,
        name="VinFast News",
        parameters={
            "entity_name": "VinFast",
            "entity_type": "organization",
        },
        workspace_id=42,
    )

    assert rule_create.name == "VinFast News"
    assert rule_create.capability_id == "news.entity_search"
    assert rule_create.diff_strategy == "new_items"
    assert rule_create.query["entity_name"] == "VinFast"
    assert rule_create.query["entity_type"] == "organization"
    assert rule_create.query["workspace_id"] == 42
    assert rule_create.query["limit"] == 10
    assert rule_create.threshold is None


def test_compile_company_status_change() -> None:
    """Company template compiles tax code or company query for masothue."""
    tmpl = VerticalAlertTemplateRegistry.get_template("company_status_change")
    assert tmpl is not None

    rule_create = compile_template(
        tmpl,
        name="Company Alert FPT",
        parameters={"query": "0101248141"},
        schedule="weekly",
    )

    assert rule_create.name == "Company Alert FPT"
    assert rule_create.capability_id == "masothue.scrape"
    assert rule_create.schedule == "weekly"
    assert rule_create.query["query"] == "0101248141"
    assert rule_create.query["search_type"] == "auto"


def test_compile_ecommerce_price_drop() -> None:
    """Ecommerce price drop template compiles keyword and percent_delta."""
    tmpl = VerticalAlertTemplateRegistry.get_template("ecommerce_price_drop")
    assert tmpl is not None

    rule_create = compile_template(
        tmpl,
        name="Shopee iPhone 16 Price Drop",
        parameters={"keyword": "iPhone 16", "percent_drop": 0.10},
    )

    assert rule_create.name == "Shopee iPhone 16 Price Drop"
    assert rule_create.capability_id == "ecommerce.search_products"
    assert rule_create.diff_strategy == "price_change"
    assert rule_create.query["keyword"] == "iPhone 16"
    assert rule_create.threshold == {"field": "price", "percent_delta": 0.10}


def test_compile_competitor_item_tracking() -> None:
    """Competitor tracking template compiles keyword and price filters."""
    tmpl = VerticalAlertTemplateRegistry.get_template("competitor_item_tracking")
    assert tmpl is not None

    rule_create = compile_template(
        tmpl,
        name="Competitor Brand Tracking",
        parameters={"keyword": "Sony Headphones", "min_price": 500000, "max_price": 5000000},
    )

    assert rule_create.name == "Competitor Brand Tracking"
    assert rule_create.diff_strategy == "new_items"
    assert rule_create.query["keyword"] == "Sony Headphones"
    assert rule_create.query["min_price"] == 500000.0
    assert rule_create.query["max_price"] == 5000000.0
