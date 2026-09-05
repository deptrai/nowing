"""Compiler logic transforming template user parameters into AlertRuleCreate payloads."""

from __future__ import annotations

from typing import Any

from app.alerts.schemas import AlertRuleCreate
from app.alerts.templates.models import AlertTemplate


class TemplateCompilationError(ValueError):
    """Raised when template parameters fail validation or compilation."""


def compile_template(
    template: AlertTemplate,
    *,
    name: str,
    parameters: dict[str, Any],
    schedule: str | None = None,
    notification_channels: list[str] | None = None,
    resolved_capability_id: str | None = None,
    workspace_id: int = 1,
) -> AlertRuleCreate:
    """Compile user parameters into a valid AlertRuleCreate payload."""
    tid = template.template_id
    params = parameters or {}

    # Validate required parameters
    for p in template.parameters:
        if p.required and p.name not in params:
            raise TemplateCompilationError(f"Missing required parameter '{p.name}' for template '{tid}'")

    cap_id = resolved_capability_id or template.required_capability
    sched = schedule or template.default_schedule
    channels = notification_channels or ["in_app"]

    query: dict[str, Any] = {}
    threshold: dict[str, Any] | None = None
    diff_strategy = template.diff_strategy

    if tid == "stock_price_threshold":
        symbol = str(params.get("symbol") or "").upper().strip()
        if not symbol:
            raise TemplateCompilationError("Stock ticker symbol cannot be empty")
        price_threshold = params.get("price_threshold")
        if price_threshold is None:
            raise TemplateCompilationError("price_threshold is required for stock price alerts")
        try:
            threshold_val = float(price_threshold)
            if threshold_val <= 0:
                raise TemplateCompilationError("price_threshold must be a positive number greater than 0")
        except (ValueError, TypeError) as exc:
            raise TemplateCompilationError(f"Invalid price_threshold numeric value: {price_threshold}") from exc

        direction = str(params.get("direction") or "below").lower()
        if direction not in ("above", "below"):
            raise TemplateCompilationError("direction must be 'above' or 'below'")

        query = {"symbol": symbol, "include_financials": False}
        threshold = {
            "field": "price",
            "value": threshold_val,
            "direction": direction,
        }

    elif tid == "news_topic_monitoring":
        entity_name = str(params.get("entity_name") or "").strip()
        if not entity_name:
            raise TemplateCompilationError("entity_name cannot be empty for news topic monitoring")
        entity_type = str(params.get("entity_type") or "all")
        limit = int(params.get("limit") or 10)

        query = {
            "entity_name": entity_name,
            "entity_type": entity_type,
            "workspace_id": workspace_id,
            "limit": limit,
        }
        threshold = None

    elif tid == "company_status_change":
        company_query = str(params.get("query") or "").strip()
        if not company_query:
            raise TemplateCompilationError("Tax code or company name query cannot be empty")
        search_type = str(params.get("search_type") or "auto")

        query = {
            "query": company_query,
            "search_type": search_type,
            "resolve_detail": True,
            "max_items": 5,
        }
        threshold = None

    elif tid == "ecommerce_price_drop":
        keyword = str(params.get("keyword") or "").strip()
        if not keyword:
            raise TemplateCompilationError("keyword cannot be empty for ecommerce price drop alerts")
        percent_drop = float(params.get("percent_drop") or 0.05)
        # Normalize e.g. 5 or 10 into 0.05 or 0.10 if user enters 5 instead of 0.05
        if percent_drop > 1.0:
            percent_drop = percent_drop / 100.0
        if percent_drop <= 0:
            raise TemplateCompilationError("percent_drop must be greater than 0")
        absolute_delta = params.get("absolute_delta")
        abs_delta_val = float(absolute_delta) if absolute_delta is not None else None

        query = {
            "keyword": keyword,
            "limit": int(params.get("limit") or 20),
        }
        threshold = {
            "field": "price",
            "percent_delta": percent_drop,
        }
        if abs_delta_val is not None:
            threshold["absolute_delta"] = abs_delta_val

    elif tid == "competitor_item_tracking":
        keyword = str(params.get("keyword") or "").strip()
        if not keyword:
            raise TemplateCompilationError("keyword cannot be empty for competitor item tracking")
        min_price = params.get("min_price")
        max_price = params.get("max_price")

        query = {
            "keyword": keyword,
            "limit": int(params.get("limit") or 20),
        }
        if min_price is not None:
            query["min_price"] = float(min_price)
        if max_price is not None:
            query["max_price"] = float(max_price)
        threshold = None

    else:
        # Fallback generic mapping
        query = dict(params)
        threshold = None

    return AlertRuleCreate(
        name=name,
        capability_id=cap_id,
        query=query,
        schedule=sched,
        diff_strategy=diff_strategy,
        threshold=threshold,
        notification_channels=channels,
        enabled=True,
    )
