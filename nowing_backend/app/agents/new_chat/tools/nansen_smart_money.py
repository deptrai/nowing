"""Nansen smart money tools for Nowing deep agent.

Provides 3 tools for Nansen on-chain intelligence:
- get_nansen_smart_money: Top smart-money wallets + 24h net flow for a token
- get_nansen_wallet_label: Human-readable label for a wallet address
- get_nansen_token_god_mode: Holder distribution by cohort (smart money,
  exchanges, retail, etc.)

All tools return {"source_domain": "nansen.ai", ...} so
SourceAttributionMiddleware emits citation events (AC1, Story 9-UX-1).

All tools return {"error": "..."} on failure — never raise to callers.
On 401/403 they return {"error": "...", "status": 401} so callers can
distinguish missing-key from transient errors (AC13).

Environment variables:
    NANSEN_API_KEY — Required (paid tier $150/mo Pro or higher).

Rate limits (AC14):
    Free tier: ~100 req/min (not available publicly).
    Paid tier: 500 req/min Pro.
    Default budget: 100 req/min (conservative — safe for both tiers).
"""

import logging
import math
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from langchain_core.tools import tool

from ..middleware.circuit_breaker import circuit_breaker
from ._rate_limiter import _ApiRateLimiter

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0
_NANSEN_BASE = "https://api.nansen.ai/api/v1"
_EVM_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")

# AC14: per-tool rate limiter — 100 calls/min (Nansen paid tier is 500,
# but we cap conservatively and let ops raise via NANSEN_RATE_LIMIT env).
_nansen_rate_limit = int(os.getenv("NANSEN_RATE_LIMIT", "100"))
_nansen_rl = _ApiRateLimiter(max_calls=_nansen_rate_limit, window_seconds=60.0, name="nansen")


def _api_key() -> str | None:
    return os.getenv("NANSEN_API_KEY", "").strip() or None


# ─── Story 10.1.4: wallet cohort classification ──────────────────────────────
#
# Maps a free-text `address_label` to one of: smart_money / cex / dex / retail /
# insider / unknown. Used by Sankey to color-code nodes and compute
# cohort_summary aggregates.
#
# Priority (high → low): insider > cex > dex > smart_money > retail.
# Higher-priority keywords win when multiple match (e.g. "Binance Team Treasury"
# → insider, not cex — supply-unlock signals are more critical than CEX flow).
# Word-boundary matching prevents substring false positives (e.g. "Hummingbot
# Trader" must not match "bot" → not in keyword list anyway).

_COHORT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "insider",
        ("team", "treasury", "vesting", "founder", "deployer", "mint"),
    ),
    (
        "cex",
        (
            # Named CEXes only — "exchange" was removed because it false-positives
            # on DEX labels like "PancakeSwap Exchange" / "SushiSwap Exchange".
            "binance", "coinbase", "kraken", "okx", "bybit", "bitfinex",
            "kucoin", "huobi", "gate.io",
        ),
    ),
    (
        "dex",
        (
            "uniswap", "pancakeswap", "sushiswap", "curve", "balancer",
            "1inch", "router", "amm",
        ),
    ),
    (
        "smart_money",
        (
            "fund", "capital", "ventures", "a16z", "paradigm", "multicoin",
            "jump", "wintermute", "dragonfly", "pantera",
        ),
    ),
)

# Pre-compiled word-boundary patterns per cohort. Substring matching would
# false-positive on "Mintable" → insider, "Refund Address" → smart_money,
# "PancakeSwap Exchange" → cex. `\b` requires alphanumeric boundary so
# `mint` matches "mint" / "mint contract" but not "mintable" / "wintermute".
_COHORT_PATTERNS: tuple[tuple[str, "re.Pattern[str]"], ...] = tuple(
    (cohort, re.compile(r"\b(?:" + "|".join(re.escape(kw) for kw in keywords) + r")\b"))
    for cohort, keywords in _COHORT_KEYWORDS
)


def _classify_cohort(label: str | None) -> str:
    """Classify a wallet label into a cohort category.

    Args:
        label: Free-text label (e.g. "Binance 14", "a16z Fund"). May be None,
            empty, or whitespace.

    Returns:
        One of "smart_money", "cex", "dex", "retail", "insider", "unknown".
        Empty/None labels return "unknown". Addr-like labels (starting with 0x
        or no semantic content) return "retail".
    """
    if not isinstance(label, str) or not label.strip():
        return "unknown"

    haystack = label.lower()

    for cohort, pattern in _COHORT_PATTERNS:
        if pattern.search(haystack):
            return cohort

    # Addr-like or generic label → retail (background activity, no signal)
    return "retail"


# Redis-backed circuit breaker — wrap calls so a Redis outage cannot bring
# the tool down (fail-open: assume circuit closed if we can't read state).
async def _safe_circuit_is_open(name: str) -> bool:
    try:
        return await circuit_breaker.is_open(name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("circuit_breaker.is_open failed for %s: %s", name, exc)
        return False


async def _safe_circuit_record_failure(name: str) -> None:
    try:
        await circuit_breaker.record_failure(name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("circuit_breaker.record_failure failed for %s: %s", name, exc)


async def _safe_circuit_record_success(name: str) -> None:
    try:
        await circuit_breaker.record_success(name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("circuit_breaker.record_success failed for %s: %s", name, exc)


def _auth_headers() -> dict[str, str]:
    key = _api_key()
    if not key:
        return {}
    return {"apiKey": key}


def _unavailable_error(status: int) -> dict[str, Any]:
    """Return structured error for 401/403/429/503 responses (AC13)."""
    messages = {
        401: "Nansen API key missing or invalid. Add NANSEN_API_KEY to .env.",
        403: "Nansen API key does not have access to this endpoint (paid tier required).",
        429: "Nansen rate limit exceeded. Reduce request frequency or upgrade plan.",
        503: "Nansen API is currently unavailable (circuit breaker open).",
    }
    return {
        "error": messages.get(status, f"Nansen API returned HTTP {status}"),
        "status": status,
        "source_domain": "nansen.ai",
    }


def create_nansen_smart_money_tool():
    """Factory: get_nansen_smart_money — smart-money wallet flows for a token."""

    @tool
    async def get_nansen_smart_money(token_address: str) -> dict[str, Any]:
        """Get raw smart-money wallet data for a token (text/analysis only).

        IMPORTANT: If the user asks to "show", "visualize", or "display" smart
        money flow as a chart or diagram, use get_smart_money_flow instead —
        it returns Sankey-ready visualization data and triggers the UI chart.
        Use THIS tool only when the user wants a text summary or analysis of
        who is accumulating/selling (not a visual flow diagram).

        Returns the top wallets labeled "Smart Money" by Nansen, their
        accumulating vs. distributing flags, and the 24-hour net flow.

        Use when the user asks who is accumulating/selling a token, what
        smart money is doing, or wants whale flow data as plain text.

        Args:
            token_address: EVM token contract address (0x...) OR token symbol (e.g., 'PEPE').

        Returns:
            Dict with smart_money_wallets (list), net_flow_24h_usd (float),
            signal ("accumulating" | "distributing" | "neutral"),
            source_domain "nansen.ai", or {"error": ..., "status": ...}.
        """
        if not _EVM_ADDRESS_RE.match(token_address or ""):
            from app.connectors.dexscreener_connector import DexScreenerConnector
            connector = DexScreenerConnector()
            pairs, err = await connector.search_pairs(token_address)
            if pairs:
                evm_pairs = [p for p in pairs if str(p.get("baseToken", {}).get("address", "")).startswith("0x")]
                if evm_pairs:
                    best_pair = max(evm_pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                    token_address = best_pair.get("baseToken", {}).get("address", token_address)
            if not _EVM_ADDRESS_RE.match(token_address or ""):
                return {"error": f"Invalid EVM address or unresolved symbol: {token_address!r}", "source_domain": "nansen.ai"}
        if not _api_key():
            return _unavailable_error(401)

        # AC3: Circuit Breaker check
        if await _safe_circuit_is_open("nansen"):
            return _unavailable_error(503)

        await _nansen_rl.acquire()
        url = f"{_NANSEN_BASE}/tgm/who-bought-sold"
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(hours=24)
        body = {
            "chain": "ethereum",
            "token_address": token_address,
            "date": {
                "from": yesterday.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            "pagination": {"page": 1, "per_page": 30},
        }
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(url, json=body, headers=_auth_headers())
            if resp.status_code in (401, 403, 429):
                return _unavailable_error(resp.status_code)

            # 404 = token not tracked by Nansen (not an API failure)
            if resp.status_code == 404:
                await _safe_circuit_record_success("nansen")
                return {
                    "source_domain": "nansen.ai",
                    "token_address": token_address,
                    "smart_money_wallets": [],
                    "net_flow_24h_usd": 0.0,
                    "signal": "neutral",
                    "wallet_count": 0,
                }

            # AC3: Record failure for 5xx
            if resp.status_code >= 500:
                await _safe_circuit_record_failure("nansen")
                return {"error": f"Nansen API error: {resp.status_code}", "source_domain": "nansen.ai", "status": resp.status_code}

            resp.raise_for_status()
            data = resp.json()

            # AC3: Record success
            await _safe_circuit_record_success("nansen")

            items = data.get("data") or []
            net_flow = 0.0
            wallets = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                try:
                    bought = float(item.get("bought_volume_usd") or 0)
                    sold = float(item.get("sold_volume_usd") or 0)
                except (TypeError, ValueError):
                    continue
                net = bought - sold
                if not math.isfinite(net):
                    continue
                net_flow += net
                addr = item.get("address", "") if isinstance(item.get("address"), str) else ""
                raw_label_value = item.get("address_label")
                raw_label = raw_label_value.strip() if isinstance(raw_label_value, str) else ""
                label = raw_label or (addr[:8] if addr else "") or "Unknown"
                if net > 0:
                    direction = "accumulating"
                elif net < 0:
                    direction = "distributing"
                else:
                    direction = "neutral"
                wallets.append({
                    "address": addr,
                    "label": label,
                    "tag": "",
                    "net_flow_usd": net,
                    "direction": direction,
                    "cohort": _classify_cohort(raw_label),
                })

            if net_flow > 0:
                signal = "accumulating"
            elif net_flow < 0:
                signal = "distributing"
            else:
                signal = "neutral"

            return {
                "source_domain": "nansen.ai",
                "token_address": token_address,
                "smart_money_wallets": wallets,
                "net_flow_24h_usd": net_flow,
                "signal": signal,
                "wallet_count": len(wallets),
            }
        except (httpx.TimeoutException, httpx.RequestError):
            logger.warning("nansen smart_money timeout/network error for %s", token_address)
            await _safe_circuit_record_failure("nansen")
            return {"error": "Nansen API timeout or network error", "source_domain": "nansen.ai"}
        except httpx.HTTPStatusError as exc:
            logger.warning("nansen smart_money HTTP error %s for %s", exc.response.status_code, token_address)
            if exc.response.status_code >= 500:
                await _safe_circuit_record_failure("nansen")
            return {"error": f"Nansen API error: {exc.response.status_code}", "source_domain": "nansen.ai", "status": exc.response.status_code}
        except Exception as exc:
            logger.exception("nansen smart_money unexpected error for %s", token_address)
            return {"error": f"Unexpected error: {exc}", "source_domain": "nansen.ai"}

    return get_nansen_smart_money


def create_nansen_wallet_label_tool():
    """Factory: get_nansen_wallet_label — human-readable label for a wallet."""

    @tool
    async def get_nansen_wallet_label(address: str) -> dict[str, Any]:
        """Get the Nansen label for a wallet address.

        Nansen maintains labels for ~200K known wallets including
        exchanges (e.g. "Binance Hot Wallet"), funds (e.g. "a16z"),
        protocols (e.g. "Ethereum Foundation"), and market makers.

        Use when you have a wallet address and want to identify it,
        or when building the whale-tracker section of a report.

        Args:
            address: EVM wallet address (0x...).

        Returns:
            Dict with address, label, entity_type, entity_tag,
            source_domain "nansen.ai", or {"error": ..., "status": ...}.
        """
        if not _EVM_ADDRESS_RE.match(address or ""):
            return {"error": f"Invalid EVM address: {address!r}", "source_domain": "nansen.ai"}
        if not _api_key():
            return _unavailable_error(401)

        # AC3: Circuit Breaker check
        if await _safe_circuit_is_open("nansen"):
            return _unavailable_error(503)

        await _nansen_rl.acquire()
        url = f"{_NANSEN_BASE}/wallet/label"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    url,
                    params={"address": address},
                    headers=_auth_headers(),
                )
            if resp.status_code in (401, 403, 429):
                return _unavailable_error(resp.status_code)
            
            # AC3: Record failure for 5xx
            if resp.status_code >= 500:
                await _safe_circuit_record_failure("nansen")
                return {"error": f"Nansen API error: {resp.status_code}", "source_domain": "nansen.ai", "status": resp.status_code}

            if resp.status_code == 404:
                # Unknown wallet — return short address, not an error
                # Note: successes reset failure count
                await _safe_circuit_record_success("nansen")
                short = f"{address[:6]}...{address[-4:]}"
                return {
                    "source_domain": "nansen.ai",
                    "address": address,
                    "label": short,
                    "entity_type": "unknown",
                    "entity_tag": "",
                }
            resp.raise_for_status()
            data = resp.json().get("data", {})
            
            # AC3: Record success
            await _safe_circuit_record_success("nansen")

            return {
                "source_domain": "nansen.ai",
                "address": address,
                "label": data.get("label") or f"{address[:6]}...{address[-4:]}",
                "entity_type": data.get("entityType", "unknown"),
                "entity_tag": data.get("entityTag", ""),
            }
        except (httpx.TimeoutException, httpx.RequestError):
            logger.warning("nansen wallet_label timeout/network error for %s", address)
            await _safe_circuit_record_failure("nansen")
            return {"error": "Nansen API timeout or network error", "source_domain": "nansen.ai"}
        except httpx.HTTPStatusError as exc:
            logger.warning("nansen wallet_label HTTP error %s for %s", exc.response.status_code, address)
            if exc.response.status_code >= 500:
                await _safe_circuit_record_failure("nansen")
            return {"error": f"Nansen API error: {exc.response.status_code}", "source_domain": "nansen.ai", "status": exc.response.status_code}
        except Exception as exc:
            logger.exception("nansen wallet_label unexpected error for %s", address)
            return {"error": f"Unexpected error: {exc}", "source_domain": "nansen.ai"}

    return get_nansen_wallet_label


def create_nansen_token_god_mode_tool():
    """Factory: get_nansen_token_god_mode — holder distribution by cohort."""

    @tool
    async def get_nansen_token_god_mode(token_address: str) -> dict[str, Any]:
        """Get holder distribution by wallet cohort for a token (Nansen God Mode).

        Returns breakdown of token holdings by cohort: smart money,
        exchanges, retail, VCs / funds, protocol treasuries. Useful for
        understanding concentration risk and who controls the float.

        Use when user asks about holder distribution, concentration risk,
        or which type of investors dominate a token's cap table.

        Args:
            token_address: EVM token contract address (0x...) OR token symbol (e.g., 'PEPE').

        Returns:
            Dict with cohort_breakdown (list), top_10_concentration_pct (float),
            total_holders (int), source_domain "nansen.ai",
            or {"error": ..., "status": ...}.
        """
        if not _EVM_ADDRESS_RE.match(token_address or ""):
            from app.connectors.dexscreener_connector import DexScreenerConnector
            connector = DexScreenerConnector()
            pairs, err = await connector.search_pairs(token_address)
            if pairs:
                evm_pairs = [p for p in pairs if str(p.get("baseToken", {}).get("address", "")).startswith("0x")]
                if evm_pairs:
                    best_pair = max(evm_pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                    token_address = best_pair.get("baseToken", {}).get("address", token_address)
            if not _EVM_ADDRESS_RE.match(token_address or ""):
                return {"error": f"Invalid EVM address or unresolved symbol: {token_address!r}", "source_domain": "nansen.ai"}
        if not _api_key():
            return _unavailable_error(401)

        # AC3: Circuit Breaker check
        if await _safe_circuit_is_open("nansen"):
            return _unavailable_error(503)

        await _nansen_rl.acquire()
        url = f"{_NANSEN_BASE}/token/god-mode"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    url,
                    params={"address": token_address},
                    headers=_auth_headers(),
                )
            if resp.status_code in (401, 403, 429):
                return _unavailable_error(resp.status_code)
            
            # AC3: Record failure for 5xx
            if resp.status_code >= 500:
                await _safe_circuit_record_failure("nansen")
                return {"error": f"Nansen API error: {resp.status_code}", "source_domain": "nansen.ai", "status": resp.status_code}
                
            resp.raise_for_status()
            data = resp.json().get("data", {})
            
            # AC3: Record success
            await _safe_circuit_record_success("nansen")

            cohorts = data.get("cohorts", [])
            top10 = data.get("top10ConcentrationPct", 0.0)
            total = data.get("totalHolders", 0)

            return {
                "source_domain": "nansen.ai",
                "token_address": token_address,
                "cohort_breakdown": [
                    {
                        "cohort": c.get("name", ""),
                        "holder_count": c.get("holderCount", 0),
                        "balance_pct": c.get("balancePct", 0.0),
                        "description": c.get("description", ""),
                    }
                    for c in cohorts
                ],
                "top_10_concentration_pct": top10,
                "total_holders": total,
            }
        except (httpx.TimeoutException, httpx.RequestError):
            logger.warning("nansen god_mode timeout/network error for %s", token_address)
            await _safe_circuit_record_failure("nansen")
            return {"error": "Nansen API timeout or network error", "source_domain": "nansen.ai"}
        except httpx.HTTPStatusError as exc:
            logger.warning("nansen god_mode HTTP error %s for %s", exc.response.status_code, token_address)
            if exc.response.status_code >= 500:
                await _safe_circuit_record_failure("nansen")
            return {"error": f"Nansen API error: {exc.response.status_code}", "source_domain": "nansen.ai", "status": exc.response.status_code}
        except Exception as exc:
            logger.exception("nansen god_mode unexpected error for %s", token_address)
            return {"error": f"Unexpected error: {exc}", "source_domain": "nansen.ai"}

    return get_nansen_token_god_mode

