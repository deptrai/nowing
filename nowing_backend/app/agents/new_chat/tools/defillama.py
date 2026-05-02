"""DeFiLlama tools for Nowing deep agent.

Provides 5 tools for fetching DeFi data from DeFiLlama APIs:
- get_defillama_protocol: TVL + chain breakdown for a single protocol
- get_defillama_tvl_overview: Top protocols by TVL
- get_defillama_yields: Yield pools sorted by APY
- get_defillama_stablecoins: Stablecoins by market cap
- get_defillama_bridges: Bridges by volume

All tools are stateless (NFR-CS4) and use httpx.AsyncClient for non-blocking I/O.
Leverages @crypto_tool_decorator for global resilience (Circuit Breaker, Pacing, Error Handling).
"""

import logging
import re
from typing import Any

import httpx
from langchain_core.tools import tool

from .utils import crypto_tool_decorator

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-_.]{0,63}$", re.IGNORECASE)


def _clamp_limit(limit: int, hi: int = 100) -> int:
    return max(1, min(int(limit), hi))


def create_defillama_protocol_tool():
    """Factory: get_defillama_protocol — TVL + chain breakdown for one protocol."""

    @tool
    @crypto_tool_decorator("defillama")
    async def get_defillama_protocol(protocol_slug: str) -> dict[str, Any]:
        """Get TVL, chain breakdown, and market metrics for a DeFi protocol.

        Use when the user asks for TVL, market cap, FDV, or chain distribution
        for a specific protocol (e.g. "Uniswap TVL", "Aave on Ethereum").

        Args:
            protocol_slug: DeFiLlama protocol slug (e.g. "uniswap", "aave", "lido").

        Returns:
            Dict with tvl, chains list, mcap, fdv, audit_links, or {"error": ...}.
        """
        if not _SLUG_RE.match(protocol_slug or ""):
            return {"error": f"Invalid protocol slug: {protocol_slug!r}"}
        url = f"https://api.llama.fi/protocol/{protocol_slug}"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url)
        if resp.status_code == 404:
            return {"error": f"Protocol '{protocol_slug}' not found", "status": 404}
        resp.raise_for_status()
        data = resp.json()

        # Extract chain TVL breakdown
        chain_tvls = data.get("chainTvls", {})
        chains = [
            {"chain": chain, "tvl": vals.get("tvl", 0) if isinstance(vals, dict) else 0}
            for chain, vals in chain_tvls.items()
            if chain not in ("staking", "borrowed", "pool2")
        ]

        return {
            "name": data.get("name"),
            "slug": protocol_slug,
            "symbol": data.get("symbol"),
            "category": data.get("category"),
            "tvl": data.get("tvl", 0),
            "chains": chains,
            "mcap": data.get("mcap"),
            "fdv": data.get("fdv"),
            "change_1d": data.get("change_1d"),
            "change_7d": data.get("change_7d"),
            "audit_links": data.get("audit_links", []),
            "description": data.get("description", ""),
            "url": data.get("url", ""),
            "twitter": data.get("twitter", ""),
        }

    return get_defillama_protocol


def create_defillama_tvl_overview_tool():
    """Factory: get_defillama_tvl_overview — top protocols by TVL."""

    @tool
    @crypto_tool_decorator("defillama")
    async def get_defillama_tvl_overview(
        chain: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Get top DeFi protocols ranked by Total Value Locked (TVL).

        Use when the user asks for "top DeFi protocols", "highest TVL", or
        wants an overview of the DeFi ecosystem.

        Args:
            chain: Optional chain filter (e.g. "Ethereum", "BSC"). None = all chains.
            limit: Number of protocols to return (default 20, max 100).

        Returns:
            Dict with total_protocols count and protocols list, or {"error": ...}.
        """
        limit = _clamp_limit(limit)
        url = "https://api.llama.fi/protocols"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url)
        resp.raise_for_status()
        all_protocols: list[dict] = resp.json()

        # Optional chain filter
        if chain:
            chain_lower = chain.lower()
            all_protocols = [
                p for p in all_protocols
                if any(c.lower() == chain_lower for c in (p.get("chains") or []))
            ]

        # Sort by TVL descending, take limit
        sorted_protos = sorted(
            all_protocols,
            key=lambda p: float(p.get("tvl") or 0),
            reverse=True,
        )[:limit]

        protocols = [
            {
                "name": p.get("name"),
                "slug": p.get("slug"),
                "category": p.get("category"),
                "chains": p.get("chains", []),
                "tvl": p.get("tvl", 0),
                "change_1d": p.get("change_1d"),
                "change_7d": p.get("change_7d"),
                "mcap": p.get("mcap"),
            }
            for p in sorted_protos
        ]

        return {
            "total_protocols": len(protocols),
            "chain_filter": chain,
            "protocols": protocols,
        }

    return get_defillama_tvl_overview


def create_defillama_yields_tool():
    """Factory: get_defillama_yields — yield pools sorted by APY."""

    @tool
    @crypto_tool_decorator("defillama")
    async def get_defillama_yields(
        symbol: str | None = None,
        min_tvl: float = 0,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Get DeFi yield pools sorted by APY from DeFiLlama Yields.

        Use when the user asks for "best yields", "highest APY", or
        wants to compare farming opportunities.

        Args:
            symbol: Optional token symbol filter (e.g. "ETH", "USDC"). None = all.
            min_tvl: Minimum pool TVL in USD (default 0 = no filter).
            limit: Number of pools to return (default 20).

        Returns:
            Dict with pools list sorted by APY descending, or {"error": ...}.
        """
        limit = _clamp_limit(limit)
        min_tvl = max(0.0, float(min_tvl))
        url = "https://yields.llama.fi/pools"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        all_pools: list[dict] = data.get("data", [])

        # Apply filters
        if symbol:
            sym_upper = symbol.upper()
            all_pools = [p for p in all_pools if sym_upper in (p.get("symbol") or "").upper()]
        if min_tvl > 0:
            all_pools = [p for p in all_pools if float(p.get("tvlUsd") or 0) >= min_tvl]

        # Sort by APY descending
        sorted_pools = sorted(
            all_pools,
            key=lambda p: float(p.get("apy") or 0),
            reverse=True,
        )[:limit]

        pools = [
            {
                "pool_id": p.get("pool"),
                "project": p.get("project"),
                "chain": p.get("chain"),
                "symbol": p.get("symbol"),
                "tvl_usd": p.get("tvlUsd", 0),
                "apy": p.get("apy", 0),
                "apy_base": p.get("apyBase", 0),
                "apy_reward": p.get("apyReward", 0),
                "il_risk": p.get("ilRisk"),
                "stablecoin": p.get("stablecoin", False),
            }
            for p in sorted_pools
        ]

        return {
            "total_pools": len(pools),
            "symbol_filter": symbol,
            "min_tvl_filter": min_tvl,
            "pools": pools,
        }

    return get_defillama_yields


def create_defillama_stablecoins_tool():
    """Factory: get_defillama_stablecoins — stablecoins by market cap."""

    @tool
    @crypto_tool_decorator("defillama")
    async def get_defillama_stablecoins(limit: int = 20) -> dict[str, Any]:
        """Get top stablecoins ranked by market cap from DeFiLlama.

        Use when the user asks about stablecoin dominance, USDC vs USDT,
        or wants an overview of the stablecoin market.

        Args:
            limit: Number of stablecoins to return (default 20).

        Returns:
            Dict with stablecoins list, or {"error": ...}.
        """
        limit = _clamp_limit(limit)
        url = "https://stablecoins.llama.fi/stablecoins?includePrices=true"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        all_stables: list[dict] = data.get("peggedAssets", [])

        # Sort by circulating supply (market cap proxy)
        sorted_stables = sorted(
            all_stables,
            key=lambda s: float((s.get("circulating") or {}).get("peggedUSD", 0)),
            reverse=True,
        )[:limit]

        stablecoins = [
            {
                "name": s.get("name"),
                "symbol": s.get("symbol"),
                "peg_type": s.get("pegType"),
                "peg_mechanism": s.get("pegMechanism"),
                "circulating_usd": (s.get("circulating") or {}).get("peggedUSD", 0),
                "price": s.get("price"),
                "chains": list((s.get("chainCirculating") or {}).keys()),
            }
            for s in sorted_stables
        ]

        return {
            "total_stablecoins": len(stablecoins),
            "stablecoins": stablecoins,
        }

    return get_defillama_stablecoins


def create_defillama_bridges_tool():
    """Factory: get_defillama_bridges — bridges by volume."""

    @tool
    @crypto_tool_decorator("defillama")
    async def get_defillama_bridges(limit: int = 20) -> dict[str, Any]:
        """Get top cross-chain bridges ranked by 24h volume from DeFiLlama.

        Use when the user asks about bridge volumes, cross-chain activity,
        or wants to compare bridging protocols.

        Args:
            limit: Number of bridges to return (default 20).

        Returns:
            Dict with bridges list sorted by volume, or {"error": ...}.
        """
        limit = _clamp_limit(limit)
        url = "https://bridges.llama.fi/bridges?includeChains=true"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        all_bridges: list[dict] = data.get("bridges", [])

        # Sort by 24h volume
        sorted_bridges = sorted(
            all_bridges,
            key=lambda b: float(b.get("lastDailyVolume") or 0),
            reverse=True,
        )[:limit]

        bridges = [
            {
                "id": b.get("id"),
                "name": b.get("displayName") or b.get("name"),
                "chains": b.get("chains", []),
                "volume_24h": b.get("lastDailyVolume", 0),
                "volume_7d": b.get("weeklyVolume", 0),
                "volume_1m": b.get("monthlyVolume", 0),
                "current_day_volume": b.get("currentDayVolume", 0),
            }
            for b in sorted_bridges
        ]

        return {
            "total_bridges": len(bridges),
            "bridges": bridges,
        }

    return get_defillama_bridges
