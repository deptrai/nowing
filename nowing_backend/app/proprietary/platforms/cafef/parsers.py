"""Map raw CafeF JSON into typed Pydantic models."""

from __future__ import annotations

from typing import Any

from .fetch import CafeFAccessBlockedError, CafeFDecodeError
from .schemas import (
    CafeFFinancialLineItem,
    CafeFFinancialReport,
    CafeFFinancials,
    CafeFNewsItem,
    CafeFQuote,
)


def _parse_period(time: str) -> tuple[int, int]:
    """Parse ``Q2-2026`` -> (2026, 2) or ``2026`` -> (2026, 0)."""
    if time.startswith("Q"):
        q, y = time[1:].split("-")
        return int(y), int(q)
    return int(time), 0


def _sort_periods(periods: list[str]) -> list[str]:
    return sorted(periods, key=lambda p: _parse_period(p))


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_name_map(templace: list[dict[str, Any]]) -> dict[str, str]:
    """Flatten grouped or flat templates into ``code -> name``."""
    name_map: dict[str, str] = {}
    if not templace:
        return name_map

    # Grouped template: list of groups each with a nested ``data`` list.
    if isinstance(templace[0], dict) and "data" in templace[0] and isinstance(
        templace[0]["data"], list
    ):
        for group in templace:
            for item in group.get("data") or []:
                if isinstance(item, dict):
                    code = item.get("code")
                    if code is not None:
                        name_map[str(code)] = item.get("name", "")
    else:
        # Flat template: list of items with ``code`` and ``name``.
        for item in templace:
            if isinstance(item, dict):
                code = item.get("code")
                if code is not None:
                    name_map[str(code)] = item.get("name", "")
    return name_map


def _extract_period_values(
    data: list[dict[str, Any]],
    name_map: dict[str, str],
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """Turn nested CafeF report data into ``{period: {code: value}}``.

    Handles two shapes:
    - flat: list of ``{time, data: [{code, value}]}`` entries (income statement)
    - grouped: list of ``{code, data: [{time, data: [...]}]}`` groups (balance/cash)
    """
    by_period: dict[str, dict[str, Any]] = {}

    def ingest_period_list(entries: list[dict[str, Any]]) -> None:
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            time = entry.get("time")
            if not time:
                continue
            values = by_period.setdefault(str(time), {})
            for row in entry.get("data") or []:
                if isinstance(row, dict):
                    code = row.get("code")
                    if code is not None:
                        values[str(code)] = row.get("value")

    if not data:
        return [], by_period

    # Grouped shape.
    if isinstance(data[0], dict) and "data" in data[0] and isinstance(
        data[0].get("data"), list
    ) and data[0].get("data") and isinstance(data[0]["data"][0], dict) and "time" in data[0]["data"][0]:
        for group in data:
            ingest_period_list(group.get("data") or [])
    else:
        # Flat shape.
        ingest_period_list(data)

    periods = _sort_periods(list(by_period.keys()))
    return periods, by_period


def parse_financials(raw: dict[str, Any] | None, symbol: str) -> CafeFFinancials:
    """Map one raw financials envelope to ``CafeFFinancials``."""
    if raw is None:
        raise CafeFDecodeError("financials response is None")

    def _parse_report(name: str) -> CafeFFinancialReport:
        payload = raw.get(name)
        if payload is None:
            raise CafeFDecodeError(f"missing {name} in financials response")

        # Already normalized (demo / downstream) -> build directly.
        if isinstance(payload, dict) and "periods" in payload:
            return CafeFFinancialReport(**payload)

        # Live CafeF envelope: ``{"isSuccess": bool, "value": {...}}``.
        if isinstance(payload, dict) and "isSuccess" in payload:
            if payload.get("isSuccess") is False:
                errors = payload.get("errors")
                raise CafeFAccessBlockedError(f"CafeF {name} API error: {errors}")
            value = payload.get("value")
            if not isinstance(value, dict) or not value:
                raise CafeFAccessBlockedError(
                    f"CafeF {name} returned an empty value"
                )
            payload = value

        if not isinstance(payload, dict):
            raise CafeFDecodeError(f"unexpected {name} payload type")

        templace = payload.get("templace") or []
        data = payload.get("data") or []
        name_map = _build_name_map(templace)
        periods, by_period = _extract_period_values(data, name_map)

        items: list[CafeFFinancialLineItem] = []
        for code in sorted(name_map):
            values = [by_period.get(period, {}).get(code) for period in periods]
            items.append(
                CafeFFinancialLineItem(
                    code=code,
                    name=name_map[code],
                    values=values,
                )
            )

        return CafeFFinancialReport(
            periods=periods,
            items=items,
            key_metrics={},
            unit=payload.get("unit") or "VND",
            source_url=None,
        )

    return CafeFFinancials(
        symbol=symbol.upper(),
        balance_sheet=_parse_report("balance_sheet"),
        income_statement=_parse_report("income_statement"),
        cash_flow=_parse_report("cash_flow"),
    )


def parse_quote(raw: dict[str, Any] | None, symbol: str) -> CafeFQuote:
    """Map a raw quote JSON to ``CafeFQuote``."""
    if raw is None:
        raise CafeFDecodeError("quote response is None")

    # Live envelope, unwrap if present.
    if isinstance(raw, dict) and "isSuccess" in raw:
        if raw.get("isSuccess") is False:
            errors = raw.get("errors")
            raise CafeFAccessBlockedError(f"CafeF quote API error: {errors}")
        value = raw.get("value")
        if not isinstance(value, dict) or not value:
            raise CafeFAccessBlockedError(
                f"CafeF quote returned an empty value for {symbol}"
            )
        raw = value

    def _get(*keys: str) -> Any:
        for key in keys:
            if key in raw:
                return raw[key]
        return None

    key_ratios = _get("key_ratios", "keyRatios") or {}
    if not isinstance(key_ratios, dict):
        key_ratios = {}

    return CafeFQuote(
        symbol=symbol.upper(),
        name=_get("name", "shortName", "companyName"),
        exchange=_get("exchange", "floor"),
        current_price=_as_float(_get("current_price", "price", "lastPrice", "close")),
        open_price=_as_float(_get("open_price", "open", "openPrice")),
        high=_as_float(_get("high", "highPrice")),
        low=_as_float(_get("low", "lowPrice")),
        close=_as_float(_get("close", "closePrice")),
        volume=_as_float(_get("volume", "totalVolume", "vol")),
        change=_as_float(_get("change", "changePrice")),
        change_percent=_as_float(_get("change_percent", "changePercent", "percentChange")),
        timestamp=_get("timestamp", "tradingDate", "date"),
        key_ratios={
            k: _as_float(v)
            for k, v in key_ratios.items()
        },
        source_url=_get("source_url", "sourceUrl"),
    )


def _news_items_from(raw: Any) -> list[dict[str, Any]]:
    """Normalize a news response into a flat list of article dicts."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        if raw.get("isSuccess"):
            value = raw.get("value")
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                return value.get("data") or []
        return raw.get("data") or []
    return []


def parse_news(raw: Any, symbol: str) -> list[CafeFNewsItem]:
    """Map a raw news response to ``CafeFNewsItem`` instances."""
    items: list[CafeFNewsItem] = []
    for article in _news_items_from(raw):
        if not isinstance(article, dict):
            continue
        title = article.get("title")
        if not title:
            continue
        items.append(
            CafeFNewsItem(
                title=str(title),
                url=article.get("url") or article.get("link"),
                published_at=article.get("published_at")
                or article.get("publishedAt")
                or article.get("pubDate"),
                summary=article.get("summary") or article.get("description"),
                source=article.get("source") or "cafef",
                symbol=symbol.upper(),
            )
        )
    return items
