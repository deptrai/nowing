"""Tests for wallet-cohort classification heuristic (Story 10.1.4 AC4).

Heuristic priority order (high → low): insider > cex > dex > smart_money > retail.
Empty/no-label wallets fall through to "unknown".
"""

import pytest

from app.agents.new_chat.tools.nansen_smart_money import _classify_cohort


@pytest.mark.parametrize("label,expected", [
    # ── insider (highest priority — supply unlocks are critical) ──
    ("Team Treasury Multisig", "insider"),
    ("Vesting Contract", "insider"),
    ("Founder Wallet", "insider"),
    ("Token Deployer", "insider"),
    ("ETH Mint Address", "insider"),

    # ── cex ──
    ("Binance 14", "cex"),
    ("Coinbase Cold", "cex"),
    ("Kraken Hot Wallet", "cex"),
    ("OKX Exchange", "cex"),
    ("Bybit Trading", "cex"),
    ("Huobi 5", "cex"),
    ("KuCoin", "cex"),
    ("Gate.io", "cex"),

    # ── dex ──
    ("Uniswap V3 Router", "dex"),
    ("PancakeSwap Factory", "dex"),
    ("Sushiswap V2 Pair", "dex"),
    ("Curve 3Pool", "dex"),
    ("Balancer Vault", "dex"),
    ("1inch Aggregation Router", "dex"),
    ("AMM Pool", "dex"),

    # ── smart_money ──
    ("a16z Fund", "smart_money"),
    ("Multicoin Capital", "smart_money"),
    ("Paradigm Ventures", "smart_money"),
    ("Jump Trading", "smart_money"),
    ("Wintermute Trading", "smart_money"),
    ("Dragonfly Capital", "smart_money"),
    ("Pantera Ventures", "smart_money"),

    # ── retail / unknown (label-only or generic) ──
    ("0xabc123def", "retail"),  # short addr-like label
    ("Anonymous Whale", "retail"),
    ("", "unknown"),
    (None, "unknown"),
    ("   ", "unknown"),

    # ── priority enforcement: insider beats cex when both keywords present ──
    ("Binance Team Treasury", "insider"),  # "team" beats "binance"
    ("Coinbase Vesting Contract", "insider"),  # "vesting" beats "coinbase"

    # ── priority: cex beats dex when both present (rare) ──
    ("Binance DEX", "cex"),  # "binance" beats "dex" — Binance is CEX-first

    # ── case insensitivity ──
    ("BINANCE COLD STORAGE", "cex"),
    ("uniswap router", "dex"),
    ("A16Z VENTURES", "smart_money"),

    # ── word-boundary protection (substring traps) ──
    # Pre-fix bugs: "Mintable" matched "mint" (insider), "Refund Address"
    # matched "fund" (smart_money), "PancakeSwap Exchange" matched "exchange"
    # (cex). Word-boundary regex prevents all three.
    ("Mintable", "retail"),
    ("Refund Address", "retail"),
    ("PancakeSwap Exchange", "dex"),
    ("SushiSwap Exchange", "dex"),
    ("Steam Wallet", "retail"),
    ("Insurance Fund", "smart_money"),  # 'fund' is whole word here — still hits
])
def test_classify_cohort_heuristic(label, expected):
    assert _classify_cohort(label) == expected


def test_classify_cohort_empty_string_returns_unknown():
    assert _classify_cohort("") == "unknown"


def test_classify_cohort_none_returns_unknown():
    assert _classify_cohort(None) == "unknown"


def test_classify_cohort_whitespace_returns_unknown():
    assert _classify_cohort("   \t\n") == "unknown"
