"""Smart money flow wrapper tool.

Wraps the raw Nansen smart money data to provide Sankey-ready visualization data.

Wallet cohorts (per Nansen taxonomy) used as Sankey node labels:
- smart_money: top-tier traders historically profitable
- cex: centralized exchange hot/cold wallets (Binance, Coinbase, etc.)
- dex: decentralized exchange pools / routers
- retail: small holders (heuristically classified)
- insider: addresses linked to founders/team/treasury

Each wallet's `net_flow_usd` over the last 24h becomes a Sankey link to/from the
synthetic "Market" node, with sign indicating accumulation (Market→wallet) vs
distribution (wallet→Market).
"""

import asyncio
import re
from typing import Any

from langchain_core.tools import tool

from app.connectors.dexscreener_connector import DexScreenerConnector

from .nansen_smart_money import create_nansen_smart_money_tool

_EVM_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
_DEXSCREENER_RESOLVE_TIMEOUT = 10.0
_NANSEN_INVOKE_TIMEOUT = 30.0
_MAX_WALLETS_IN_SANKEY = 30


def create_smart_money_flow_tool():
    """Factory: get_smart_money_flow."""

    nansen_tool = create_nansen_smart_money_tool()

    @tool
    async def get_smart_money_flow(token_address: str, chain: str = "ethereum") -> dict[str, Any]:
        """Get smart money flow visualized as a Sankey diagram.

        Transforms the raw Nansen smart money output into a structured format
        (nodes and links) representing 24h USD value flows, ready for UI display.

        Args:
            token_address: EVM token contract address (0x...) OR a token symbol (e.g., 'PEPE').
            chain: Target chain — currently only "ethereum" is supported (Nansen scope).

        Returns:
            Dict containing 'nodes', 'links', 'net_flow_amount', 'currency',
            and 'source_domain', or an error dict.
        """
        if not token_address or not isinstance(token_address, str):
            return {"error": "token_address is required", "source_domain": "nansen.ai"}

        normalized = token_address.strip()
        if chain and chain != "ethereum":
            return {"error": f"chain '{chain}' not supported; only 'ethereum'", "source_domain": "nansen.ai"}

        # Resolve symbol → address upfront so the cache key (downstream) is stable.
        # On failure, surface a clear error rather than falling through with a symbol —
        # the inner tool would otherwise resolve again, doubling DexScreener calls.
        if not _EVM_ADDRESS_RE.match(normalized):
            try:
                connector = DexScreenerConnector()
                pairs, err = await asyncio.wait_for(
                    connector.search_pairs(normalized),
                    timeout=_DEXSCREENER_RESOLVE_TIMEOUT,
                )
            except asyncio.TimeoutError:
                return {"error": f"DexScreener resolve timed out for {normalized!r}", "source_domain": "nansen.ai"}

            if err or not pairs:
                return {
                    "error": f"Could not resolve symbol {normalized!r} to an EVM address",
                    "source_domain": "nansen.ai",
                }

            evm_pairs = [p for p in pairs if str(p.get("baseToken", {}).get("address", "")).startswith("0x")]
            if not evm_pairs:
                return {
                    "error": f"No EVM pair found for symbol {normalized!r}",
                    "source_domain": "nansen.ai",
                }

            def _liquidity(p: dict) -> float:
                try:
                    return float(p.get("liquidity", {}).get("usd", 0) or 0)
                except (TypeError, ValueError):
                    return 0.0

            best_pair = max(evm_pairs, key=_liquidity)
            normalized = best_pair.get("baseToken", {}).get("address", normalized)

        # Call the underlying nansen tool with a resolved address (cache-key consistent).
        try:
            res = await asyncio.wait_for(
                nansen_tool.ainvoke({"token_address": normalized}),
                timeout=_NANSEN_INVOKE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            return {"error": "Nansen smart money fetch timed out", "source_domain": "nansen.ai"}
        except Exception as exc:  # noqa: BLE001 — tool must never raise
            return {"error": f"Nansen smart money fetch failed: {exc}", "source_domain": "nansen.ai"}

        if not isinstance(res, dict):
            return {"error": "Nansen tool returned non-dict response", "source_domain": "nansen.ai"}

        if "error" in res:
            return {
                "error": res["error"],
                "source_domain": res.get("source_domain", "nansen.ai"),
                "status": res.get("status"),
            }

        wallets = res.get("smart_money_wallets") or []
        try:
            net_flow_usd = float(res.get("net_flow_24h_usd") or 0)
        except (TypeError, ValueError):
            net_flow_usd = 0.0

        # Empty result: still return a valid Sankey shape so FE doesn't break.
        if not wallets:
            return {
                "source_domain": "nansen.ai",
                "nodes": [{"id": "Market"}],
                "links": [],
                "net_flow_amount": net_flow_usd,
                "currency": "USD",
            }

        # Cap to keep Sankey readable; sort by abs(flow) so the largest movers stay.
        def _abs_flow(w: dict) -> float:
            try:
                return abs(float(w.get("net_flow_usd") or 0))
            except (TypeError, ValueError):
                return 0.0

        wallets = sorted(wallets, key=_abs_flow, reverse=True)[:_MAX_WALLETS_IN_SANKEY]

        nodes_dict: dict[str, bool] = {"Market": True}
        links: list[dict[str, Any]] = []

        for idx, w in enumerate(wallets):
            label = (w.get("label") or "Unknown").strip() or "Unknown"
            try:
                flow = float(w.get("net_flow_usd") or 0)
            except (TypeError, ValueError):
                continue
            if flow == 0:
                continue

            # Suffix index when label is non-unique to avoid Sankey node collision.
            addr = (w.get("address") or "")[:8]
            node_id = label if addr == "" else f"{label} ({addr})"
            nodes_dict[node_id] = True

            if flow > 0:
                links.append({"source": "Market", "target": node_id, "value": flow})
            else:
                links.append({"source": node_id, "target": "Market", "value": abs(flow)})

        nodes = [{"id": n} for n in nodes_dict.keys()]

        return {
            "source_domain": "nansen.ai",
            "nodes": nodes,
            "links": links,
            "net_flow_amount": net_flow_usd,
            "currency": "USD",
        }

    return get_smart_money_flow
