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

    key_ratios_raw = _get(raw, "key_ratios", "keyRatios") or {}
    if not isinstance(key_ratios_raw, dict):
        key_ratios_raw = {}

    try:
        key_ratios = _normalize_ratios(key_ratios_raw)
    except VietstockDecodeError:
        raise VietstockDecodeError(
            f"unsupported ratio format in quote for {symbol}"
        ) from None

    return VietstockQuote(
        symbol=symbol.upper(),
        name=_get(raw, "name", "shortName", "companyName"),
        exchange=_get(raw, "exchange", "floor"),
        current_price=_as_float(
            _get(raw, "current_price", "price", "lastPrice", "closePrice", "GiaDongCua")
        ),
        open_price=_as_float(_get(raw, "open_price", "open", "openPrice", "GiaMoCua")),
        high=_as_float(_get(raw, "high", "highPrice", "GiaCaoNhat")),
        low=_as_float(_get(raw, "low", "lowPrice", "GiaThapNhat")),
        close=_as_float(_get(raw, "close", "closePrice", "GiaDongCua")),
        volume=_as_float(_get(raw, "volume", "totalVolume", "KhoiLuongKhopLenh")),
        change=_as_float(_get(raw, "change", "changePrice")),
        change_percent=_as_float(
            _get(raw, "change_percent", "changePercent", "percentChange")
        ),
        timestamp=_get(raw, "timestamp", "tradingDate", "date", "Ngay"),
        key_ratios=VietstockKeyRatios(**key_ratios),
        source_url=_get(raw, "source_url", "sourceUrl"),
    )


def parse_financial_statement(
    raw: Any,
    symbol: str,
    statement_type: Literal["balance_sheet", "income_statement", "cash_flow"],
) -> VietstockFinancialReport:
    """Map one raw financial statement to ``VietstockFinancialReport``."""
    if raw is None:
        raise VietstockDecodeError(f"{statement_type} response is None")

    if isinstance(raw, VietstockFinancialReport):
        return raw

    if isinstance(raw, dict):
        if not raw:
            return VietstockFinancialReport(statement_type=statement_type)

        # Live API envelope: unwrap and continue.
        if "isSuccess" in raw:
            if raw.get("isSuccess") is False:
                errors = raw.get("errors")
                raise VietstockAccessBlockedError(
                    f"Vietstock {statement_type} API error: {errors}"
                )
            value = raw.get("value")
            if not isinstance(value, dict) or not value:
                raise VietstockAccessBlockedError(
                    f"Vietstock {statement_type} returned an empty value"
                )
            return parse_financial_statement(value, symbol, statement_type)

        if "periods" in raw:
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

    raise VietstockDecodeError(f"unexpected {statement_type} payload type")


def parse_financials(raw: dict[str, Any] | None, symbol: str) -> VietstockFinancials:
    """Map one raw financials envelope to ``VietstockFinancials``."""
    if raw is None:
        raise VietstockDecodeError("financials response is None")
    if not isinstance(raw, dict):
        raise VietstockDecodeError("financials response is not a JSON object")

    def _parse_report(name: str) -> VietstockFinancialReport:
        payload = raw.get(name)
        if payload is None:
            return VietstockFinancialReport(statement_type=name)  # type: ignore[arg-type]
        return parse_financial_statement(payload, symbol, name)  # type: ignore[arg-type]

    return VietstockFinancials(
        symbol=symbol.upper(),
        balance_sheet=_parse_report("balance_sheet"),
        income_statement=_parse_report("income_statement"),
        cash_flow=_parse_report("cash_flow"),
    )
