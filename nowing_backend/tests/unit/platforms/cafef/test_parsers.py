"""Parser tests for CafeF raw responses."""

from __future__ import annotations

from app.proprietary.platforms.cafef.fetch import (
    _demo_financials,
    _demo_news,
    _demo_quote,
)
from app.proprietary.platforms.cafef.parsers import (
    parse_financials,
    parse_news,
    parse_quote,
)


def test_parse_demo_quote() -> None:
    raw = _demo_quote("VCB")
    q = parse_quote(raw, "VCB")
    assert q.symbol == "VCB"
    assert q.current_price is not None
    assert q.key_ratios.get("pe") is not None


def test_parse_live_quote_envelope() -> None:
    raw = {
        "isSuccess": True,
        "value": {
            "symbol": "FPT",
            "name": "FPT Corp",
            "exchange": "HOSE",
            "price": 95.2,
            "open": 94.0,
            "high": 96.0,
            "low": 93.5,
            "close": 95.0,
            "volume": 1000000,
            "change": 0.2,
            "changePercent": 0.21,
            "keyRatios": {"pe": 15.0},
        },
    }
    q = parse_quote(raw, "FPT")
    assert q.symbol == "FPT"
    assert q.current_price == 95.2
    assert q.key_ratios["pe"] == 15.0


def test_parse_demo_financials() -> None:
    raw = _demo_financials("VCB")
    f = parse_financials(raw, "VCB")
    assert f.symbol == "VCB"
    assert f.balance_sheet.periods
    assert f.income_statement.items
    assert f.cash_flow.key_metrics


def test_parse_live_income_statement() -> None:
    raw = {
        "isSuccess": True,
        "value": {
            "templace": [
                {"code": "10", "name": "Doanh thu thuần"},
                {"code": "60", "name": "Lợi nhuận sau thuế"},
            ],
            "data": [
                {
                    "symbol": "VCB",
                    "time": "Q2-2026",
                    "data": [
                        {"code": "10", "value": 1000},
                        {"code": "60", "value": 200},
                    ],
                },
                {
                    "symbol": "VCB",
                    "time": "Q1-2026",
                    "data": [
                        {"code": "10", "value": 900},
                        {"code": "60", "value": 180},
                    ],
                },
            ],
        },
    }
    f = parse_financials(
        {
            "balance_sheet": _demo_financials("VCB")["balance_sheet"],
            "income_statement": raw,
            "cash_flow": _demo_financials("VCB")["cash_flow"],
        },
        "VCB",
    )
    assert f.income_statement.periods == ["Q1-2026", "Q2-2026"]
    item = next(i for i in f.income_statement.items if i.code == "10")
    assert item.values == [900, 1000]


def test_parse_live_balance_sheet() -> None:
    raw = {
        "isSuccess": True,
        "value": {
            "templace": [
                {
                    "code": "TN",
                    "name": "Tài sản",
                    "data": [
                        {"code": "270", "name": "Tổng tài sản"},
                        {"code": "300", "name": "Nợ phải trả"},
                    ],
                }
            ],
            "data": [
                {
                    "code": "TN",
                    "data": [
                        {
                            "symbol": "VCB",
                            "time": "Q1-2026",
                            "data": [
                                {"code": "270", "value": 5000},
                                {"code": "300", "value": 2000},
                            ],
                        }
                    ],
                }
            ],
        },
    }
    f = parse_financials(
        {
            "balance_sheet": raw,
            "income_statement": _demo_financials("VCB")["income_statement"],
            "cash_flow": _demo_financials("VCB")["cash_flow"],
        },
        "VCB",
    )
    assert f.balance_sheet.periods == ["Q1-2026"]


def test_parse_news() -> None:
    raw = _demo_news("VCB", 3)
    items = parse_news(raw, "VCB")
    assert len(items) == 3
    assert all(i.symbol == "VCB" for i in items)


def test_parse_news_envelope() -> None:
    raw = {
        "isSuccess": True,
        "value": [
            {"title": "A", "url": "https://cafef.vn/a.chn"},
            {"title": "B"},
        ],
    }
    items = parse_news(raw, "FPT")
    assert len(items) == 2
    assert items[0].url == "https://cafef.vn/a.chn"


def test_parse_news_ignores_missing_title() -> None:
    raw = [{"title": "A"}, {"summary": "no title"}]
    items = parse_news(raw, "VCB")
    assert len(items) == 1


def test_parse_price_history_quote() -> None:
    raw = {
        "Data": {
            "Data": [
                {
                    "Symbol": "VCB",
                    "Ngay": "13/08/2026",
                    "GiaDongCua": 59.5,
                    "GiaMoCua": 59.9,
                    "GiaCaoNhat": 60.5,
                    "GiaThapNhat": 59.1,
                    "KhoiLuongKhopLenh": 4579700,
                    "ThayDoi": "-0,20 (-0,34%)",
                }
            ]
        },
        "Success": True,
    }
    q = parse_quote(raw, "VCB")
    assert q.symbol == "VCB"
    assert q.current_price == 59.5
    assert q.open_price == 59.9
    assert q.high == 60.5
    assert q.low == 59.1
    assert q.volume == 4579700
    assert q.change == -0.2
    assert q.change_percent == -0.34


def test_parse_quote_prefers_non_none_key() -> None:
    raw = {"current_price": None, "price": 95.2}
    q = parse_quote(raw, "FPT")
    assert q.current_price == 95.2
