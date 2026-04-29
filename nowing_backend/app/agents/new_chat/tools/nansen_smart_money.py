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
import os
import re
from typing import Any

import httpx
from langchain_core.tools import tool

from ._rate_limiter import _ApiRateLimiter

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0
_NANSEN_BASE = "https://api.nansen.ai/v1"
_EVM_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")

# AC14: per-tool rate limiter — 100 calls/min (Nansen paid tier is 500,
# but we cap conservatively and let ops raise via NANSEN_RATE_LIMIT env).
_nansen_rate_limit = int(os.getenv("NANSEN_RATE_LIMIT", "100"))
_nansen_rl = _ApiRateLimiter(max_calls=_nansen_rate_limit, window_seconds=60.0, name="nansen")


def _api_key() -> str | None:
    return os.getenv("NANSEN_API_KEY", "").strip() or None


def _auth_headers() -> dict[str, str]:
    key = _api_key()
    if not key:
        return {}
    return {"x-api-key": key}


def _unavailable_error(status: int) -> dict[str, Any]:
    """Return structured error for 401/403/429 responses (AC13)."""
    messages = {
        401: "Nansen API key missing or invalid. Add NANSEN_API_KEY to .env.",
        403: "Nansen API key does not have access to this endpoint (paid tier required).",
        429: "Nansen rate limit exceeded. Reduce request frequency or upgrade plan.",
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
        """Get smart-money wallet flows and accumulation signals for a token.

        Returns the top wallets labeled "Smart Money" by Nansen, their
        accumulating vs. distributing flags, and the 24-hour net flow
        (USD and token amount).

        Use when the user asks who is accumulating/selling a token, what
        smart money is doing, or wants whale flow data.

        Args:
            token_address: EVM token contract address (0x...).

        Returns:
            Dict with smart_money_wallets (list), net_flow_24h_usd (float),
            signal ("accumulating" | "distributing" | "neutral"),
            source_domain "nansen.ai", or {"error": ..., "status": ...}.
        """
        if not _EVM_ADDRESS_RE.match(token_address or ""):
            return {"error": f"Invalid EVM address: {token_address!r}", "source_domain": "nansen.ai"}
        if not _api_key():
            return _unavailable_error(401)

        await _nansen_rl.acquire()
        url = f"{_NANSEN_BASE}/token/smart-money"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    url,
                    params={"address": token_address},
                    headers=_auth_headers(),
                )
            if resp.status_code in (401, 403, 429):
                return _unavailable_error(resp.status_code)
            resp.raise_for_status()
            data = resp.json()

            wallets = data.get("data", {}).get("wallets", [])
            net_flow = data.get("data", {}).get("netFlow24hUsd", 0.0)

            # Derive signal from net flow
            if net_flow > 0:
                signal = "accumulating"
            elif net_flow < 0:
                signal = "distributing"
            else:
                signal = "neutral"

            return {
                "source_domain": "nansen.ai",
                "token_address": token_address,
                "smart_money_wallets": [
                    {
                        "address": w.get("address", ""),
                        "label": w.get("label", "Unknown Wallet"),
                        "tag": w.get("entityTag", ""),
                        "net_flow_usd": w.get("netFlowUsd", 0.0),
                        "direction": "accumulating" if w.get("netFlowUsd", 0) > 0 else "distributing",
                    }
                    for w in wallets[:10]  # top 10
                ],
                "net_flow_24h_usd": net_flow,
                "signal": signal,
                "wallet_count": len(wallets),
            }
        except httpx.TimeoutException:
            logger.warning("nansen smart_money timeout for %s", token_address)
            return {"error": "Nansen API timeout", "source_domain": "nansen.ai"}
        except httpx.HTTPStatusError as exc:
            logger.warning("nansen smart_money HTTP error %s for %s", exc.response.status_code, token_address)
            return {"error": f"Nansen API error: {exc.response.status_code}", "source_domain": "nansen.ai"}
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
            if resp.status_code == 404:
                # Unknown wallet — return short address, not an error
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

            return {
                "source_domain": "nansen.ai",
                "address": address,
                "label": data.get("label") or f"{address[:6]}...{address[-4:]}",
                "entity_type": data.get("entityType", "unknown"),
                "entity_tag": data.get("entityTag", ""),
            }
        except httpx.TimeoutException:
            logger.warning("nansen wallet_label timeout for %s", address)
            return {"error": "Nansen API timeout", "source_domain": "nansen.ai"}
        except httpx.HTTPStatusError as exc:
            logger.warning("nansen wallet_label HTTP error %s for %s", exc.response.status_code, address)
            return {"error": f"Nansen API error: {exc.response.status_code}", "source_domain": "nansen.ai"}
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
            token_address: EVM token contract address (0x...).

        Returns:
            Dict with cohort_breakdown (list), top_10_concentration_pct (float),
            total_holders (int), source_domain "nansen.ai",
            or {"error": ..., "status": ...}.
        """
        if not _EVM_ADDRESS_RE.match(token_address or ""):
            return {"error": f"Invalid EVM address: {token_address!r}", "source_domain": "nansen.ai"}
        if not _api_key():
            return _unavailable_error(401)

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
            resp.raise_for_status()
            data = resp.json().get("data", {})

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
        except httpx.TimeoutException:
            logger.warning("nansen god_mode timeout for %s", token_address)
            return {"error": "Nansen API timeout", "source_domain": "nansen.ai"}
        except httpx.HTTPStatusError as exc:
            logger.warning("nansen god_mode HTTP error %s for %s", exc.response.status_code, token_address)
            return {"error": f"Nansen API error: {exc.response.status_code}", "source_domain": "nansen.ai"}
        except Exception as exc:
            logger.exception("nansen god_mode unexpected error for %s", token_address)
            return {"error": f"Unexpected error: {exc}", "source_domain": "nansen.ai"}

    return get_nansen_token_god_mode
