"""Smart money flow wrapper tool.

Wraps the raw Nansen smart money data to provide Sankey-ready visualization data.
Fallback to Arkham Intelligence and Dune Analytics if Nansen is unavailable or missing data.
"""

import asyncio
import logging
import math
import os
import re
from typing import Any

from langchain_core.tools import tool

from app.connectors.arkham_connector import ArkhamConnector, ArkhamFatalError
from app.connectors.dexscreener_connector import DexScreenerConnector
from app.connectors.dune_connector import DuneConnector

from ..middleware.circuit_breaker import circuit_breaker
from ._rate_limiter import _ApiRateLimiter
from .nansen_smart_money import create_nansen_smart_money_tool

logger = logging.getLogger(__name__)

_EVM_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
_DEXSCREENER_RESOLVE_TIMEOUT = 10.0
_NANSEN_INVOKE_TIMEOUT = 30.0
_ARKHAM_INVOKE_TIMEOUT = 15.0
_DUNE_INVOKE_TIMEOUT = 60.0
_MAX_WALLETS_IN_SANKEY = 30

# Spec mitigation: prefer fund/whale entities when Arkham labels them.
# Entities without a `type` field are kept (insufficient signal to filter out).
_ARKHAM_PREFERRED_ENTITY_TYPES = frozenset({"fund", "whale"})


def _arkham_usd_gte_default() -> int:
    """Min USD threshold for Arkham `/transfers`.

    Defaults to $1k to avoid noise on majors like ETH/PEPE. Operators can lower
    via `ARKHAM_USD_GTE` for low-cap tokens where whale activity is sub-$1k.
    """
    raw = os.getenv("ARKHAM_USD_GTE")
    try:
        return max(0, int(raw)) if raw else 1000
    except ValueError:
        return 1000


def _disambiguate_label(label: str, addr: str) -> str:
    """Produce a Sankey node id that won't collapse two distinct wallets sharing
    the same entity name (e.g. multiple "Binance" hot wallets).

    Mirrors the Nansen path: `f"{label} ({addr_prefix})"` when addr is available.
    """
    label = (label or "").strip() or "Unknown"
    if addr and addr.startswith("0x"):
        return f"{label} ({addr[:8]})"
    return label


# Story 10.1.4: cohort taxonomy. Categorize wallets so Sankey can color-code +
# analytics can answer "smart money inflow vs CEX outflow".
_VALID_COHORTS: tuple[str, ...] = (
    "smart_money", "cex", "dex", "retail", "insider", "unknown",
)

# Arkham `arkhamEntity.type` → cohort mapping (AC6).
_ARKHAM_TYPE_TO_COHORT: dict[str, str] = {
    "fund": "smart_money",
    "whale": "smart_money",
    "cex": "cex",
    "exchange": "cex",
    "dex": "dex",
}


def _arkham_entity_to_cohort(entity: dict[str, Any]) -> str:
    """Map Arkham entity to cohort taxonomy. Falls back to 'unknown'."""
    etype = (entity.get("type") or "").strip().lower()
    return _ARKHAM_TYPE_TO_COHORT.get(etype, "unknown")


def _build_cohort_summary(
    wallets: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Aggregate {cohort: {count, net_flow_usd}} from a list of wallet dicts.

    Each wallet must carry `cohort` and `net_flow_usd`. Empty cohorts (count=0)
    are omitted to keep the payload compact for downstream FE.
    """
    summary: dict[str, dict[str, Any]] = {
        c: {"count": 0, "net_flow_usd": 0.0} for c in _VALID_COHORTS
    }
    for w in wallets:
        cohort = w.get("cohort") or "unknown"
        if cohort not in summary:
            cohort = "unknown"
        try:
            flow = float(w.get("net_flow_usd") or 0)
        except (TypeError, ValueError):
            flow = 0.0
        if not math.isfinite(flow):
            flow = 0.0
        summary[cohort]["count"] += 1
        summary[cohort]["net_flow_usd"] += flow
    return {k: v for k, v in summary.items() if v["count"] > 0}

_arkham_rl = _ApiRateLimiter(max_calls=1, window_seconds=1.0, name="arkham")
_dune_rl = _ApiRateLimiter(max_calls=15, window_seconds=60.0, name="dune")


async def _safe_circuit_is_open(name: str) -> bool:
    try:
        return await circuit_breaker.is_open(name)
    except Exception as exc:
        logger.warning("circuit_breaker.is_open failed for %s: %s", name, exc)
        return False


async def _safe_circuit_record_failure(name: str) -> None:
    try:
        await circuit_breaker.record_failure(name)
    except Exception as exc:
        logger.warning("circuit_breaker.record_failure failed for %s: %s", name, exc)


async def _safe_circuit_record_success(name: str) -> None:
    try:
        await circuit_breaker.record_success(name)
    except Exception as exc:
        logger.warning("circuit_breaker.record_success failed for %s: %s", name, exc)


async def _try_arkham(token_address: str, chain: str) -> dict[str, Any] | None:
    if await _safe_circuit_is_open("arkham"):
        return None
    try:
        await _arkham_rl.acquire()
        connector = ArkhamConnector()
        res = await connector.get_transfers(
            base_address=token_address,
            chain=chain,
            usd_gte=_arkham_usd_gte_default(),
        )
        await _safe_circuit_record_success("arkham")
        return res
    except ArkhamFatalError as exc:
        # 401/403 = bad key/tier; 429 = rate-limited. Both should trip the circuit
        # so we stop hammering the upstream, but log distinctly so operators can
        # tell config errors from runtime degradation.
        if exc.status in (401, 403):
            logger.error("Arkham auth/tier error: %s — fallback disabled until key fixed", exc)
        else:
            logger.warning("Arkham %s — backing off via circuit breaker", exc)
        await _safe_circuit_record_failure("arkham")
        return None
    except Exception as exc:
        logger.warning("Arkham fallback failed: %s", exc, exc_info=True)
        await _safe_circuit_record_failure("arkham")
        return None


def _arkham_entity_passes_filter(entity: dict[str, Any]) -> bool:
    """Spec mitigation: keep transfers whose entity is fund/whale, OR has no `type`
    field at all (insufficient signal). Drop CEX/DEX/exchange flows that pollute
    the smart-money view.
    """
    etype = (entity.get("type") or "").strip().lower()
    if not etype:
        return True
    return etype in _ARKHAM_PREFERRED_ENTITY_TYPES


def _build_sankey_from_arkham(transfers: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(transfers, dict):
        return None

    # Track cohort per node id; Market is the aggregate counterparty (no cohort).
    nodes_with_cohort: dict[str, str | None] = {"Market": None}
    raw_links: list[dict[str, Any]] = []
    rendered_wallets: list[dict[str, Any]] = []
    net_flow_usd = 0.0

    for t in (transfers.get("in") or []):
        if not isinstance(t, dict):
            continue
        entity = (t.get("fromAddress") or {}).get("arkhamEntity") or {}
        if not _arkham_entity_passes_filter(entity):
            continue
        addr = (t.get("fromAddress") or {}).get("address", "")
        label = _disambiguate_label(entity.get("name") or "", addr)
        try:
            usd = float((t.get("token") or {}).get("usdAmount", 0) or 0)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(usd) or usd <= 0:
            continue
        raw_links.append({"source": label, "target": "Market", "value": usd, "_cohort": _arkham_entity_to_cohort(entity)})
        net_flow_usd += usd

    for t in (transfers.get("out") or []):
        if not isinstance(t, dict):
            continue
        entity = (t.get("toAddress") or {}).get("arkhamEntity") or {}
        if not _arkham_entity_passes_filter(entity):
            continue
        addr = (t.get("toAddress") or {}).get("address", "")
        label = _disambiguate_label(entity.get("name") or "", addr)
        try:
            usd = float((t.get("token") or {}).get("usdAmount", 0) or 0)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(usd) or usd <= 0:
            continue
        raw_links.append({"source": "Market", "target": label, "value": usd, "_cohort": _arkham_entity_to_cohort(entity)})
        net_flow_usd -= usd

    if not raw_links:
        return None

    raw_links = sorted(raw_links, key=lambda x: x["value"], reverse=True)[:_MAX_WALLETS_IN_SANKEY]

    # Materialize nodes_with_cohort and rendered_wallets from final link set.
    for link in raw_links:
        cohort = link.pop("_cohort", "unknown")
        wallet_node = link["target"] if link["source"] == "Market" else link["source"]
        nodes_with_cohort[wallet_node] = cohort
        signed_flow = link["value"] if link["source"] == "Market" else -link["value"]
        rendered_wallets.append({"cohort": cohort, "net_flow_usd": signed_flow})

    nodes = [
        ({"id": n} if cohort is None else {"id": n, "cohort": cohort})
        for n, cohort in nodes_with_cohort.items()
    ]

    return {
        "nodes": nodes,
        "links": raw_links,
        "net_flow_amount": net_flow_usd,
        "currency": "USD",
        "source_domain": "arkm.com",
        "cohort_summary": _build_cohort_summary(rendered_wallets),
    }


async def _try_dune(token_address: str) -> list[dict[str, Any]] | None:
    if await _safe_circuit_is_open("dune"):
        return None
    try:
        await _dune_rl.acquire()
        connector = DuneConnector()
        res = await connector.get_smart_money_flow(token_address)
        await _safe_circuit_record_success("dune")
        return res
    except Exception as exc:
        logger.warning("Dune fallback failed: %s", exc, exc_info=True)
        await _safe_circuit_record_failure("dune")
        return None


def _build_sankey_from_dune(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not isinstance(rows, list):
        return None

    # Story 10.1.4: track cohort per node id; Market is aggregate counterparty
    # (no cohort). Dune rows lack entity-type metadata so all wallet nodes
    # default to "unknown" — future enhancement: classify via label heuristics
    # once Dune query starts surfacing entity labels.
    nodes_with_cohort: dict[str, str | None] = {"Market": None}
    raw_links: list[dict[str, Any]] = []
    net_flow_usd = 0.0
    rendered_wallets: list[dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        addr = row.get("address", "") or ""
        label = _disambiguate_label(row.get("label") or "", addr)
        try:
            flow = float(row.get("net_flow_usd") or 0)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(flow) or flow == 0:
            continue

        cohort = "unknown"
        nodes_with_cohort[label] = cohort
        if flow > 0:
            raw_links.append({"source": "Market", "target": label, "value": flow})
        else:
            raw_links.append({"source": label, "target": "Market", "value": abs(flow)})
        net_flow_usd += flow
        rendered_wallets.append({"cohort": cohort, "net_flow_usd": flow})

    if not raw_links:
        return None

    raw_links = sorted(raw_links, key=lambda x: x["value"], reverse=True)[:_MAX_WALLETS_IN_SANKEY]

    nodes = [
        ({"id": n} if cohort is None else {"id": n, "cohort": cohort})
        for n, cohort in nodes_with_cohort.items()
    ]

    return {
        "nodes": nodes,
        "links": raw_links,
        "net_flow_amount": net_flow_usd,
        "currency": "USD",
        "source_domain": "dune.com",
        "cohort_summary": _build_cohort_summary(rendered_wallets),
    }


def create_smart_money_flow_tool():
    """Factory: get_smart_money_flow."""

    nansen_tool = create_nansen_smart_money_tool()

    @tool
    async def get_smart_money_flow(token_address: str, chain: str = "ethereum") -> dict[str, Any]:
        """Show smart money flow for a token as an interactive Sankey chart.

        ALWAYS use this tool when the user asks to "show", "display", "visualize",
        or "get" smart money flow, whale flows, or on-chain capital flows for any token.
        This renders an interactive Sankey diagram in the UI automatically.
        Falls back to Dune Analytics if Nansen has no data.

        Args:
            token_address: EVM token contract address (0x...) OR a token symbol (e.g., 'PEPE').
            chain: Target chain — currently only "ethereum" is supported.

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
        nansen_res = None
        try:
            res = await asyncio.wait_for(
                nansen_tool.ainvoke({"token_address": normalized}),
                timeout=_NANSEN_INVOKE_TIMEOUT,
            )
            nansen_res = res
        except asyncio.TimeoutError:
            nansen_res = {"error": "Nansen smart money fetch timed out", "source_domain": "nansen.ai"}
            logger.warning("Nansen timed out for %s", normalized)
        except Exception as exc:  # noqa: BLE001 — tool must never raise
            nansen_res = {"error": f"Nansen smart money fetch failed: {exc}", "source_domain": "nansen.ai"}
            logger.warning("Nansen fetch failed", exc_info=True)

        if isinstance(nansen_res, dict):
            if "error" in nansen_res:
                logger.warning("Nansen returned error: %s", nansen_res["error"])
            else:
                wallets = nansen_res.get("smart_money_wallets") or []
                if wallets:
                    try:
                        net_flow_usd = float(nansen_res.get("net_flow_24h_usd") or 0)
                    except (TypeError, ValueError):
                        net_flow_usd = 0.0

                    def _abs_flow(w: dict) -> float:
                        try:
                            return abs(float(w.get("net_flow_usd") or 0))
                        except (TypeError, ValueError):
                            return 0.0

                    wallets = sorted(wallets, key=_abs_flow, reverse=True)[:_MAX_WALLETS_IN_SANKEY]

                    # Build nodes with cohort metadata (Story 10.1.4 AC2).
                    # Market node is special — no cohort (it's the aggregate counterparty).
                    nodes_with_cohort: dict[str, str | None] = {"Market": None}
                    links: list[dict[str, Any]] = []
                    rendered_wallets: list[dict[str, Any]] = []

                    for w in wallets:
                        if not isinstance(w, dict):
                            continue
                        label = (w.get("label") or "Unknown").strip() or "Unknown"
                        try:
                            flow = float(w.get("net_flow_usd") or 0)
                        except (TypeError, ValueError):
                            continue
                        if flow == 0:
                            continue

                        addr = w.get("address") or ""
                        node_id = _disambiguate_label(label, addr)
                        cohort = w.get("cohort") or "unknown"
                        nodes_with_cohort[node_id] = cohort

                        if flow > 0:
                            links.append({"source": "Market", "target": node_id, "value": flow})
                        else:
                            links.append({"source": node_id, "target": "Market", "value": abs(flow)})

                        rendered_wallets.append({"cohort": cohort, "net_flow_usd": flow})

                    nodes = [
                        ({"id": n} if cohort is None else {"id": n, "cohort": cohort})
                        for n, cohort in nodes_with_cohort.items()
                    ]

                    return {
                        "source_domain": "nansen.ai",
                        "nodes": nodes,
                        "links": links,
                        "net_flow_amount": net_flow_usd,
                        "currency": "USD",
                        "cohort_summary": _build_cohort_summary(rendered_wallets),
                    }

        # 3. Fallback: Arkham
        if os.getenv("ARKHAM_API_KEY"):
            try:
                arkham_res = await asyncio.wait_for(
                    _try_arkham(normalized, chain),
                    timeout=_ARKHAM_INVOKE_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.warning("Arkham fallback timed out for %s", normalized)
                arkham_res = None
            if arkham_res:
                sankey = _build_sankey_from_arkham(arkham_res)
                if sankey:
                    return sankey

        # 4. Fallback: Dune
        if os.getenv("DUNE_API_KEY"):
            try:
                dune_res = await asyncio.wait_for(
                    _try_dune(normalized),
                    timeout=_DUNE_INVOKE_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.warning("Dune fallback timed out for %s", normalized)
                dune_res = None
            if dune_res:
                sankey = _build_sankey_from_dune(dune_res)
                if sankey:
                    return sankey

        # 5. All failed — empty but valid Sankey.
        # Always attribute to nansen.ai (the primary provider tried). The previous
        # "system" sentinel produced a broken citation badge URL on the FE
        # (icons.duckduckgo.com/ip3/system.ico → 404).
        return {
            "source_domain": "nansen.ai",
            "cohort_summary": {},
            "nodes": [{"id": "Market"}],
            "links": [],
            "net_flow_amount": 0.0,
            "currency": "USD",
        }

    return get_smart_money_flow
