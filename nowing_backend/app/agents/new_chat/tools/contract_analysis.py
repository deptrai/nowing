"""Contract analysis tools for Nowing deep agent.

Provides 2 tools for smart contract analysis:
- get_contract_info: Contract source + ABI from block explorers (Etherscan/BscScan/etc.)
- check_token_security: Token security audit from GoPlus Labs API

All tools are stateless (NFR-CS4) and use httpx.AsyncClient for non-blocking I/O.
Leverages @crypto_tool_decorator for global resilience (Circuit Breaker, Pacing, Error Handling).

Environment variables (add to .env.example):
    ETHERSCAN_API_KEY  — Required for Ethereum contract inspection
    BSCSCAN_API_KEY    — Optional, for BSC chain
    POLYGONSCAN_API_KEY — Optional, for Polygon
"""

import logging
import os
import re
from typing import Any

import httpx
from langchain_core.tools import tool

from .utils import crypto_tool_decorator

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0
_EVM_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")

# Chain ID → (explorer base URL, env var name for API key)
_CHAIN_EXPLORER_MAP: dict[str, tuple[str, str]] = {
    "ethereum": ("https://api.etherscan.io/api", "ETHERSCAN_API_KEY"),
    "eth": ("https://api.etherscan.io/api", "ETHERSCAN_API_KEY"),
    "1": ("https://api.etherscan.io/api", "ETHERSCAN_API_KEY"),
    "bsc": ("https://api.bscscan.com/api", "BSCSCAN_API_KEY"),
    "bnb": ("https://api.bscscan.com/api", "BSCSCAN_API_KEY"),
    "56": ("https://api.bscscan.com/api", "BSCSCAN_API_KEY"),
    "polygon": ("https://api.polygonscan.com/api", "POLYGONSCAN_API_KEY"),
    "matic": ("https://api.polygonscan.com/api", "POLYGONSCAN_API_KEY"),
    "137": ("https://api.polygonscan.com/api", "POLYGONSCAN_API_KEY"),
}

# GoPlus chain name → numeric chain ID string
_GOPLUS_CHAIN_MAP: dict[str, str] = {
    "ethereum": "1",
    "eth": "1",
    "bsc": "56",
    "bnb": "56",
    "polygon": "137",
    "matic": "137",
    "arbitrum": "42161",
    "optimism": "10",
    "avalanche": "43114",
    "base": "8453",
}


def create_contract_info_tool():
    """Factory: get_contract_info — contract source/ABI from block explorers."""

    @tool
    @crypto_tool_decorator("explorer")
    async def get_contract_info(
        contract_address: str,
        chain: str,
    ) -> dict[str, Any]:
        """Get smart contract source code, ABI, and metadata from a block explorer.

        Use when the user wants to inspect a smart contract, check if it's
        verified, or understand what functions it exposes.

        Requires API key env vars: ETHERSCAN_API_KEY (Ethereum),
        BSCSCAN_API_KEY (BSC), POLYGONSCAN_API_KEY (Polygon).

        Args:
            contract_address: The contract's address (0x...).
            chain: Chain name or ID — "ethereum"/"1", "bsc"/"56", "polygon"/"137".

        Returns:
            Dict with contract_name, is_verified, abi_summary, source_code preview,
            or {"error": ...}.
        """
        chain_key = chain.lower().strip()
        explorer_info = _CHAIN_EXPLORER_MAP.get(chain_key)
        if not explorer_info:
            supported = list({k for k in _CHAIN_EXPLORER_MAP if not k.isdigit()})
            return {"error": f"Unsupported chain '{chain}'. Supported: {supported}"}

        if not _EVM_ADDRESS_RE.match(contract_address or ""):
            return {"error": f"Invalid EVM address: {contract_address!r}"}

        base_url, api_key_env = explorer_info
        api_key = os.getenv(api_key_env, "").strip()

        if not api_key:
            return {
                "error": (
                    f"Missing API key for {chain} explorer. "
                    f"Set {api_key_env} environment variable."
                )
            }

        params = {
            "module": "contract",
            "action": "getsourcecode",
            "address": contract_address,
            "apikey": api_key,
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(base_url, params=params)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "1":
            msg = data.get("message") or data.get("result") or "Unknown error"
            return {"error": f"Explorer API error: {msg}"}

        result_list: list[dict] = data.get("result", [])
        if not result_list:
            return {"error": "No contract data returned"}

        contract = result_list[0]
        source_code = contract.get("SourceCode", "")
        abi_raw = contract.get("ABI", "")
        is_verified = bool(source_code)

        # Build ABI summary (function names only, to keep response compact)
        abi_summary: list[str] = []
        if abi_raw and abi_raw != "Contract source code not verified":
            try:
                import json
                abi_list = json.loads(abi_raw)
                abi_summary = [
                    f"{item.get('type', 'unknown')}: {item.get('name', '(unnamed)')}"
                    for item in abi_list
                    if item.get("type") in ("function", "event")
                ][:30]  # cap at 30 entries
            except Exception:
                abi_summary = ["(ABI parse error)"]

        return {
            "contract_address": contract_address,
            "chain": chain,
            "contract_name": contract.get("ContractName") or "(unverified)",
            "compiler_version": contract.get("CompilerVersion"),
            "is_verified": is_verified,
            "optimization_used": contract.get("OptimizationUsed") == "1",
            "runs": contract.get("Runs"),
            "license_type": contract.get("LicenseType"),
            "abi_summary": abi_summary,
            "source_code_preview": source_code[:500] if source_code else None,
            "proxy_implementation": contract.get("Implementation"),
        }

    return get_contract_info


def create_check_token_security_tool():
    """Factory: check_token_security — GoPlus Labs token security audit."""

    @tool
    @crypto_tool_decorator("goplus")
    async def check_token_security(
        contract_address: str,
        chain_id: str,
    ) -> dict[str, Any]:
        """Run a security audit on a token contract using GoPlus Labs API.

        Use when the user asks if a token is safe, a scam, or has rug-pull risks.
        Also useful for honeypot detection, tax analysis, and holder concentration.

        Args:
            contract_address: The token contract address (0x...).
            chain_id: GoPlus chain ID string — "1" (Ethereum), "56" (BSC),
                      "137" (Polygon), "42161" (Arbitrum), "10" (Optimism),
                      "43114" (Avalanche), "8453" (Base), or chain name like
                      "ethereum", "bsc", "polygon".

        Returns:
            Dict with risk_level, risks_detected list (with emoji), key security
            fields, or {"error": ...}.
        """
        # Validate address before URL construction
        if not _EVM_ADDRESS_RE.match(contract_address or ""):
            return {"error": f"Invalid EVM address: {contract_address!r}"}
        # Normalize chain_id
        resolved_chain = _GOPLUS_CHAIN_MAP.get(chain_id.lower(), chain_id)
        if not str(resolved_chain).isdigit():
            return {"error": f"Unsupported chain_id: {chain_id!r}. Supported: {sorted(_GOPLUS_CHAIN_MAP.values())}"}
        url = f"https://api.gopluslabs.io/api/v1/token_security/{resolved_chain}"
        params = {"contract_addresses": contract_address}

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, params=params)
        if resp.status_code == 429:
            return {"error": "GoPlus rate limit reached (2000 req/day free tier)"}
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 1:
            return {"error": f"GoPlus API error: {data.get('message', 'Unknown')}"}

        result_map: dict = data.get("result") or {}
        token_data: dict = result_map.get(contract_address.lower()) or {}

        if not token_data:
            return {"error": f"No GoPlus data for address {contract_address} on chain {chain_id}"}

        # Normalize helper
        def flag(key: str) -> bool:
            return str(token_data.get(key, "0")) == "1"

        def pct(key: str) -> float | None:
            v = token_data.get(key)
            return float(v) * 100 if v is not None else None

        is_open_source = flag("is_open_source")
        is_honeypot = flag("is_honeypot")
        is_mintable = flag("is_mintable")
        can_blacklist = flag("can_take_back_ownership") or flag("transfer_pausable") or flag("is_blacklisted")
        has_proxy = flag("is_proxy")
        buy_tax = pct("buy_tax")
        sell_tax = pct("sell_tax")
        holder_count = token_data.get("holder_count")
        creator_percent = pct("creator_percent")
        top10_holder_pct = pct("top10_holder_percent") if "top10_holder_percent" in token_data else None

        # Build risk indicators
        risks_detected: list[str] = []
        risk_score = 0

        if is_honeypot:
            risks_detected.append("🔴 HONEYPOT — cannot sell")
            risk_score += 40
        if not is_open_source:
            risks_detected.append("🟡 Not open source — code unverified")
            risk_score += 10
        if is_mintable:
            risks_detected.append("🟡 Mintable — supply can be inflated")
            risk_score += 15
        if buy_tax is not None and buy_tax > 10:
            risks_detected.append(f"🟡 High buy tax: {buy_tax:.1f}%")
            risk_score += 10
        if sell_tax is not None and sell_tax > 10:
            risks_detected.append(f"🔴 High sell tax: {sell_tax:.1f}%")
            risk_score += 20
        if has_proxy:
            risks_detected.append("🟡 Proxy contract — logic can change")
            risk_score += 10
        if can_blacklist:
            risks_detected.append("🔴 Owner can pause transfers / blacklist holders")
            risk_score += 20
        if creator_percent is not None and creator_percent > 30:
            risks_detected.append(f"🔴 Creator holds {creator_percent:.1f}% — concentration risk")
            risk_score += 20
        if not risks_detected:
            risks_detected.append("🟢 No major risks detected")

        if risk_score == 0:
            risk_level = "SAFE"
        elif risk_score <= 15:
            risk_level = "LOW"
        elif risk_score <= 35:
            risk_level = "MEDIUM"
        else:
            risk_level = "HIGH"

        return {
            "contract_address": contract_address,
            "chain_id": chain_id,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "risks_detected": risks_detected,
            # Key security fields
            "is_open_source": is_open_source,
            "is_honeypot": is_honeypot,
            "is_mintable": is_mintable,
            "has_proxy": has_proxy,
            "can_blacklist": can_blacklist,
            "buy_tax_pct": buy_tax,
            "sell_tax_pct": sell_tax,
            "holder_count": int(holder_count) if holder_count else None,
            "creator_percent": creator_percent,
            "top10_holder_pct": top10_holder_pct,
            # Token metadata from GoPlus
            "token_name": token_data.get("token_name"),
            "token_symbol": token_data.get("token_symbol"),
            "total_supply": token_data.get("total_supply"),
            "lp_holder_count": token_data.get("lp_holder_count"),
        }

    return check_token_security
