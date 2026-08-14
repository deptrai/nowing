"""Map raw Vietstock JSON into typed Pydantic models."""

from __future__ import annotations

import math
import re
from typing import Any, Literal

from .fetch import VietstockAccessBlockedError, VietstockDecodeError
from .schemas import (
    VietstockFinancialLineItem,
    VietstockFinancialReport,
    VietstockFinancials,
    VietstockKeyRatios,
    VietstockQuote,
)


def _as_float(value: Any) -> float | None:
    """Coerce a scalar value to ``float``; return ``None`` on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    """Coerce a scalar value to ``int``; return ``None`` on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _canonical_period(time: str) -> str:
    """Normalize a period string to ``Q#-YYYY`` or ``YYYY``.

    Handles the shapes seen from CafeF and Vietstock live APIs:
    - ``Q4-2025`` -> ``Q4-2025``
    - ``2025`` -> ``2025``
    - ``31/12/2025`` or ``2025-12-31`` -> ``Q4-2025``
    """
    time = str(time).strip().upper()
    if not time:
        return ""

    if time.startswith("Q"):
        q, y = time[1:].split("-", 1)
        return f"Q{int(q)}-{int(y)}"

    # ISO date: 2025-12-31
    iso_match = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", time)
    if iso_match:
        year, month, _ = iso_match.groups()
        quarter = (int(month) - 1) // 3 + 1
        return f"Q{quarter}-{year}"

    # VN date: 31/12/2025
    vn_match = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", time)
    if vn_match:
        _, month, year = vn_match.groups()
        quarter = (int(month) - 1) // 3 + 1
        return f"Q{quarter}-{year}"

    # Bare year.
    if re.match(r"^\d{4}$", time):
        return time

    # Fallback: keep the original string so the caller can still hash it.
    return time


def _sort_periods(periods: list[str]) -> list[str]:
    """Sort periods by (year, quarter) for stable display."""

    def _key(p: str) -> tuple[int, int]:
        if p.startswith("Q"):
            q, y = p[1:].split("-", 1)
            return int(y), int(q)
        try:
            return int(p), 0
        except ValueError:
            return 0, 0

    return sorted(periods, key=_key)


def _normalize_ratio(value: Any) -> float | None:
    """Parse a human-readable ratio string into a normalized ``float``.

    Handles Vietnamese and English decimal markers, percent/x suffixes,
    and sentinel values such as ``N/A``, ``NaN``, and ``Inf``.
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f

    s = str(value).strip().replace(" ", "")

    # Strip common suffixes first so the numeric part can be parsed.
    for suffix in ("%", "x", "X"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
            break

    if s.lower() in {"n/a", "nan", "inf", "-inf", "none", ""}:
        return None

    # Normalize decimal separators.  We treat a trailing comma as the
    # decimal separator and an embedded dot as a thousands separator when
    # both are present, which covers both ``1.234,5`` and ``12,5``.
    if "," in s:
        s = s.replace(".", "").replace(",", ".") if "." in s else s.replace(",", ".")

    try:
        f = float(s)
    except (TypeError, ValueError) as exc:
        raise VietstockDecodeError(f"unsupported ratio format: {value!r}") from exc

    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _normalize_ratios(raw: Any) -> dict[str, float | None]:
    """Normalize a raw key-ratios mapping to ``pe``, ``pb``, ``roe``, ``roa``."""
    if not raw:
        return {}
    if not isinstance(raw, dict):
        raise VietstockDecodeError(f"unsupported ratio format: {raw!r}")

    out: dict[str, float | None] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            continue
        # Remove non-alpha characters and lower-case, e.g. "P/E" -> "pe".
        normalized = re.sub(r"[^a-zA-Z]", "", key).lower()
        if normalized in {"pe", "pb", "roe", "roa"}:
            out[normalized] = _normalize_ratio(value)
    return out


def _get(raw: dict[str, Any], *keys: str) -> Any:
    """Return the first present, non-None value from *raw* for *keys*."""
    for key in keys:
        if key in raw and raw[key] is not None:
            return raw[key]
    return None


# Component names inside Vietstock's ``financeinfo`` (ReportType=BCTQ) payload.
_VIETSTOCK_COMPONENT_NAMES = {
    "balance_sheet": "Báo cáo tình hình tài chính",
    "income_statement": "Kết quả kinh doanh",
    "cash_flow": "Báo cáo lưu chuyển tiền tệ",
}


# Map a line-item key from a financial statement to an internal metric name.
_VIETSTOCK_KEY_METRICS = {
    "balance_sheet": {
        "Tổng tài sản": "tong_tai_san",
        "Nợ phải trả": "no_phai_tra",
        "Vốn chủ sở hữu": "von_chu_so_huu",
    },
    "income_statement": {
        "Doanh thu thuần": "doanh_thu_thuan",
        "Lợi nhuận gộp": "loi_nhuan_gop",
        "LNST của CĐ cty mẹ ": "loi_nhuan_sau_thue",
        "LNST thu nhập DN": "loi_nhuan_sau_thue_cong_ty_me",
    },
    "cash_flow": {
        "Lưu chuyển tiền thuần từ HĐKD": "luu_chuyen_tu_hdkd",
        "Tiền và tương đương tiền cuối kỳ": "tien_cuoi_ky",
    },
}


def _period_from_meta(meta: dict[str, Any]) -> str:
    """Build a canonical period from a Vietstock period metadata object."""
    year = _as_int(meta.get("YearPeriod"))
    term = meta.get("TermCode")
    if year and term:
        return f"{term}-{year}"
    return _canonical_period(str(meta.get("TermName", "")))


def _sort_periods_meta(metas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort Vietstock period metadata chronologically."""

    def _key(m: dict[str, Any]) -> tuple[int, int]:
        year = _as_int(m.get("YearPeriod")) or 0
        # ReportTermID ordering roughly matches calendar ordering.
        order = _as_int(m.get("ReportTermID")) or 0
        return (year, order)

    return sorted(metas, key=_key)


def parse_quote(raw: dict[str, Any] | None, symbol: str) -> VietstockQuote:
    """Map a raw quote JSON to ``VietstockQuote``."""
    if raw is None:
        raise VietstockDecodeError("quote response is None")
    if not isinstance(raw, dict):
        raise VietstockDecodeError("quote response is not a JSON object")

    # Live envelope: unwrap if present.
    if "isSuccess" in raw:
        if raw.get("isSuccess") is False:
            errors = raw.get("errors")
            raise VietstockAccessBlockedError(f"Vietstock quote API error: {errors}")
        value = raw.get("value")
        if not isinstance(value, dict) or not value:
            raise VietstockAccessBlockedError(
                f"Vietstock quote returned an empty value for {symbol}"
            )
        raw = value

    # Build key ratios directly from top-level quote fields when available,
    # falling back to an embedded ``key_ratios`` object for demo/synthetic data.
    key_ratios_raw = _get(raw, "key_ratios", "keyRatios") or {}
    if isinstance(key_ratios_raw, dict) and key_ratios_raw:
        key_ratios = _normalize_ratios(key_ratios_raw)
    else:
        key_ratios = {
            "pe": _as_float(_get(raw, "PE", "pe")),
            "pb": _as_float(_get(raw, "PB", "pb")),
            "roe": _as_float(_get(raw, "ROE", "roe")),
            "roa": _as_float(_get(raw, "ROA", "roa")),
        }

    # Convert the ASP.NET ``/Date(...)/`` string if present.
    timestamp_raw = _get(
        raw, "timestamp", "tradingDate", "TradingDate", "date", "Ngay"
    )
    timestamp: str | None = None
    if isinstance(timestamp_raw, str):
        timestamp = timestamp_raw

    return VietstockQuote(
        symbol=symbol.upper(),
        name=_get(raw, "name", "shortName", "companyName", "StockName"),
        exchange=_get(raw, "exchange", "floor", "Exchange"),
        current_price=_as_float(
            _get(
                raw,
                "current_price",
                "price",
                "lastPrice",
                "LastPrice",
                "closePrice",
                "ClosePrice",
                "GiaDongCua",
            )
        ),
        open_price=_as_float(
            _get(raw, "open_price", "open", "OpenPrice", "openPrice", "GiaMoCua")
        ),
        high=_as_float(_get(raw, "high", "HighPrice", "highPrice", "HighestPrice", "GiaCaoNhat")),
        low=_as_float(_get(raw, "low", "LowPrice", "lowPrice", "LowestPrice", "GiaThapNhat")),
        close=_as_float(
            _get(
                raw,
                "close",
                "ClosePrice",
                "closePrice",
                "LastPrice",
                "lastPrice",
                "GiaDongCua",
            )
        ),
        volume=_as_float(_get(raw, "volume", "totalVolume", "TotalVol", "KhoiLuongKhopLenh")),
        change=_as_float(_get(raw, "change", "Change", "changePrice")),
        change_percent=_as_float(
            _get(raw, "change_percent", "changePercent", "percentChange", "PerChange")
        ),
        timestamp=timestamp,
        key_ratios=VietstockKeyRatios(**key_ratios),
        source_url=_get(raw, "source_url", "sourceUrl"),
    )


def _values_from_line_item(
    item: dict[str, Any], num_periods: int
) -> list[float | None]:
    """Extract ``Value1``..``ValueN`` fields from a Vietstock line item."""
    return [_as_float(item.get(f"Value{i}")) for i in range(1, num_periods + 1)]


def _build_financial_report(
    periods_meta: list[dict[str, Any]],
    lines: list[dict[str, Any]],
    statement_type: Literal["balance_sheet", "income_statement", "cash_flow"],
    source_url: str | None = None,
) -> VietstockFinancialReport:
    """Convert a list of Vietstock period metadata + line items to a report."""
    periods_meta = _sort_periods_meta(periods_meta)
    periods = [_canonical_period(_period_from_meta(m)) for m in periods_meta]
    num_periods = len(periods)

    items: list[VietstockFinancialLineItem] = []
    for it in lines:
        if not isinstance(it, dict):
            continue
        code = str(it.get("ReportNormID", ""))
        name = str(it.get("Name", it.get("NameEn", "")))
        if not name:
            continue
        values = _values_from_line_item(it, num_periods)
        items.append(
            VietstockFinancialLineItem(code=code, name=name, values=values)
        )

    key_metrics: dict[str, list[float | None]] = {}
    metric_map = _VIETSTOCK_KEY_METRICS.get(statement_type, {})
    for it in lines:
        if not isinstance(it, dict):
            continue
        name = str(it.get("Name", "")).strip()
        if name in metric_map:
            key_metrics[metric_map[name]] = _values_from_line_item(it, num_periods)

    unit = "VND"  # Vietstock returns absolute VND; caller can scale if needed.
    return VietstockFinancialReport(
        statement_type=statement_type,
        periods=_sort_periods(periods),
        items=items,
        key_metrics=key_metrics,
        unit=unit,
        source_url=source_url,
    )


def _unwrap_financials(
    raw: Any, source_url: str | None = None
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Extract period metadata and component tables from a real API payload.

    Vietstock ``financeinfo`` returns either a two-element list
    ``[periods_meta, reports_dict]`` or the inner reports dict directly.
    """
    reports: dict[str, list[dict[str, Any]]] = {}
    periods_meta: list[dict[str, Any]] = []

    if isinstance(raw, list) and len(raw) >= 2:
        periods_meta = raw[0] if isinstance(raw[0], list) else []
        reports = raw[1] if isinstance(raw[1], dict) else {}
    elif isinstance(raw, dict):
        # Demo envelope: each statement already has its own table.
        if all(isinstance(v, list) and len(v) >= 2 for v in raw.values()):
            # Real envelope returned as a dict of statement lists.
            first = next(iter(raw.values()))
            periods_meta = first[0] if isinstance(first[0], list) else []
            reports = {}
            for key, value in raw.items():
                component = _VIETSTOCK_COMPONENT_NAMES.get(key, key)
                reports[component] = value[1] if isinstance(value[1], dict) else {}
        else:
            reports = raw

    return periods_meta, reports


def parse_financial_statement(
    raw: Any,
    symbol: str,
    statement_type: Literal["balance_sheet", "income_statement", "cash_flow"],
    *,
    _periods_meta: list[dict[str, Any]] | None = None,
    _source_url: str | None = None,
) -> VietstockFinancialReport:
    """Map one raw financial statement to ``VietstockFinancialReport``."""
    if raw is None:
        raise VietstockDecodeError(f"{statement_type} response is None")

    if isinstance(raw, VietstockFinancialReport):
        return raw

    if isinstance(raw, dict) and not raw:
        return VietstockFinancialReport(statement_type=statement_type)

    # Demo/synthetic envelope with periods/items.
    if isinstance(raw, dict) and "periods" in raw:
        items: list[VietstockFinancialLineItem] = []
        for it in raw.get("items") or []:
            if isinstance(it, VietstockFinancialLineItem):
                items.append(it)
            elif isinstance(it, dict):
                values_raw = it.get("values")
                if not isinstance(values_raw, list):
                    values_raw = []
                items.append(
                    VietstockFinancialLineItem(
                        code=str(it.get("code", "")),
                        name=str(it.get("name", "")),
                        values=[_as_float(v) for v in values_raw],
                    )
                )

        key_metrics: dict[str, list[float | None]] = {}
        for metric, values in (raw.get("key_metrics") or {}).items():
            if isinstance(values, list):
                key_metrics[str(metric)] = [_as_float(v) for v in values]

        return VietstockFinancialReport(
            statement_type=statement_type,
            periods=_sort_periods(
                [_canonical_period(p) for p in raw.get("periods") or []]
            ),
            items=items,
            key_metrics=key_metrics,
            unit=str(raw.get("unit") or "VND"),
            source_url=raw.get("source_url"),
        )

    # Real Vietstock envelope: list of line items keyed by component name.
    if isinstance(raw, list):
        lines = raw
    elif isinstance(raw, dict):
        component = _VIETSTOCK_COMPONENT_NAMES.get(statement_type, "")
        lines = raw.get(component, [])
        if not isinstance(lines, list):
            lines = []
    else:
        raise VietstockDecodeError(f"unexpected {statement_type} payload type")

    return _build_financial_report(
        _periods_meta or [],
        lines,
        statement_type,
        source_url=_source_url,
    )


def parse_financials(raw: dict[str, Any] | None, symbol: str) -> VietstockFinancials:
    """Map one raw financials envelope to ``VietstockFinancials``."""
    if raw is None:
        raise VietstockDecodeError("financials response is None")
    if not isinstance(raw, (dict, list)):
        raise VietstockDecodeError("financials response is not JSON")

    source_url = raw.get("source_url") if isinstance(raw, dict) else None
    periods_meta, reports = _unwrap_financials(raw, source_url=source_url)

    def _parse_report(name: str) -> VietstockFinancialReport:
        component = _VIETSTOCK_COMPONENT_NAMES.get(name, "")
        payload = reports.get(component, [])
        if not isinstance(payload, (dict, list)):
            payload = []
        return parse_financial_statement(
            payload,
            symbol,
            name,  # type: ignore[arg-type]
            _periods_meta=periods_meta,
            _source_url=source_url,
        )

    return VietstockFinancials(
        symbol=symbol.upper(),
        balance_sheet=_parse_report("balance_sheet"),
        income_statement=_parse_report("income_statement"),
        cash_flow=_parse_report("cash_flow"),
    )
