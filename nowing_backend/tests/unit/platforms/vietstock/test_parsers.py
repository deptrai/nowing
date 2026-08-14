"""Vietstock parser tests — normalize financial statements and ratios."""

from __future__ import annotations

import pytest

from app.proprietary.platforms.vietstock.parsers import (
    _normalize_ratio,
    _normalize_ratios,
    parse_financials,
    parse_quote,
)

pytestmark = pytest.mark.unit


def test_parse_quote_returns_exact_fields() -> None:
    """Mirror: should return VietstockQuote with exact fields."""
    raw = {
        "symbol": "VNM",
        "current_price": 75000.0,
        "open": 74000.0,
        "high": 76000.0,
        "low": 73500.0,
        "close": 75000.0,
        "volume": 1_000_000,
        "change": 1000.0,
        "change_percent": 1.35,
        "key_ratios": {"pe": 15.2, "pb": 2.1, "roe": 18.5, "roa": 10.2},
    }
    quote = parse_quote(raw, "VNM")
    assert quote.symbol == "VNM"
    assert quote.current_price == 75000.0
    assert quote.key_ratios.pe == 15.2
    assert quote.key_ratios.pb == 2.1
    assert quote.key_ratios.roe == 18.5
    assert quote.key_ratios.roa == 10.2


def test_parse_quote_does_not_return_raw_html() -> None:
    """Mirror: should NOT return raw HTML in quote."""
    raw = {
        "symbol": "VNM",
        "current_price": 75000.0,
        "key_ratios": {"pe": "15.2"},
        "raw_response": "<html>...",
    }
    quote = parse_quote(raw, "VNM")
    assert not hasattr(quote, "raw_response")


def test_parse_financials_returns_three_statements() -> None:
    """Mirror: should return balance_sheet, income_statement, cash_flow."""
    raw = {
        "balance_sheet": {"periods": ["Q4-2025"], "items": []},
        "income_statement": {"periods": ["Q4-2025"], "items": []},
        "cash_flow": {"periods": ["Q4-2025"], "items": []},
    }
    financials = parse_financials(raw, "VNM")
    assert financials.balance_sheet is not None
    assert financials.income_statement is not None
    assert financials.cash_flow is not None


def test_normalize_ratio_decimal_string() -> None:
    """Arithmetic: should compute 12.5 from '12.5'."""
    assert _normalize_ratio("12.5") == 12.5


def test_normalize_ratio_comma_decimal() -> None:
    """Arithmetic: should compute 12.5 from '12,5'."""
    assert _normalize_ratio("12,5") == 12.5


def test_normalize_ratio_with_x_suffix() -> None:
    """Arithmetic: should compute 12.5 from '12.5x'."""
    assert _normalize_ratio("12.5x") == 12.5


def test_normalize_ratio_with_percent() -> None:
    """Arithmetic: should compute 18.5 from '18.5%'."""
    assert _normalize_ratio("18.5%") == 18.5


def test_normalize_ratio_none() -> None:
    """Edge: None should return None."""
    assert _normalize_ratio(None) is None


def test_normalize_ratio_na_string() -> None:
    """Edge: 'N/A' should return None."""
    assert _normalize_ratio("N/A") is None


def test_normalize_ratio_nan_inf() -> None:
    """Edge: 'NaN' and 'Inf' should return None."""
    assert _normalize_ratio("NaN") is None
    assert _normalize_ratio("Inf") is None


def test_normalize_ratio_negative_pe() -> None:
    """Boundary: negative P/E is valid for loss-making company."""
    assert _normalize_ratio("-15.2") == -15.2


def test_normalize_ratios_all_fields() -> None:
    """Arithmetic: should compute pe, pb, roe, roa correctly."""
    raw = {"PE": "15.2", "PB": "2,1", "ROE": "18.5%", "ROA": "10.2x"}
    ratios = _normalize_ratios(raw)
    assert ratios["pe"] == 15.2
    assert ratios["pb"] == 2.1
    assert ratios["roe"] == 18.5
    assert ratios["roa"] == 10.2


def test_parse_quote_raises_on_malformed_input() -> None:
    """Error message: should raise VietstockParseError with message containing 'unsupported ratio format'."""
    raw = {"symbol": "VNM", "key_ratios": {"pe": {"nested": "object"}}}
    with pytest.raises(Exception) as exc:
        parse_quote(raw, "VNM")
    assert "unsupported" in str(exc.value).lower()


def test_parse_financials_returns_empty_items() -> None:
    """Edge: zero statements should not crash."""
    raw = {
        "balance_sheet": {"periods": [], "items": []},
        "income_statement": {"periods": [], "items": []},
        "cash_flow": {"periods": [], "items": []},
    }
    financials = parse_financials(raw, "VNM")
    assert financials.balance_sheet.periods == []
