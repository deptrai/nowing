"""Arkham Intelligence Connector."""

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ArkhamFatalError(Exception):
    """Arkham auth/rate-limit error that should not be retried as a generic failure.

    Carries the HTTP status so callers can decide whether to record a circuit-breaker
    failure (5xx, 429) vs propagate as a config error (401, 403).
    """

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


# Arkham docs map chain values for the `chains` filter on /transfers.
# The connector accepts the user-friendly names from the wider tool layer and
# normalizes here so the upstream caller doesn't have to know Arkham's vocabulary.
_CHAIN_NORMALIZE = {
    "ethereum": "ethereum",
    "eth": "ethereum",
    "polygon": "polygon",
    "matic": "polygon",
    "arbitrum": "arbitrum",
    "base": "base",
    "optimism": "optimism",
    "avalanche": "avalanche",
    "bsc": "bsc",
    "binance": "bsc",
    "bnb": "bsc",
    "bitcoin": "bitcoin",
    "btc": "bitcoin",
    "solana": "solana",
    "sol": "solana",
    "tron": "tron",
    "ton": "ton",
    "dogecoin": "dogecoin",
    "doge": "dogecoin",
}


class ArkhamConnector:
    """Connector for Arkham Intelligence API."""

    def __init__(self):
        self.api_key = os.getenv("ARKHAM_API_KEY")
        self.base_url = "https://api.arkm.com"

    async def get_transfers(
        self,
        base_address: str,
        flow: str = "all",
        time_last: str = "1d",
        usd_gte: int = 1000,
        chain: str | None = None,
    ) -> dict[str, Any] | None:
        """Get token transfers from Arkham API.

        Args:
            base_address: Token contract or entity address.
            flow: "in", "out", or "all".
            time_last: e.g. "1d", "7d".
            usd_gte: Minimum USD value filter (default 1000 — small-cap tokens may
                need this lowered to surface activity).
            chain: Optional chain filter (forwarded as Arkham `chains` param).

        Raises:
            ArkhamFatalError: On 401/403 (bad/missing key) or 429 (rate limited).
                Caller should propagate config errors and back off on rate limits
                rather than swallowing them as generic failures.
        """
        if not self.api_key:
            return None

        url = f"{self.base_url}/transfers"
        params: dict[str, Any] = {
            "base": base_address,
            "flow": flow,
            "timeLast": time_last,
            "usdGte": usd_gte,
            "limit": 100,
        }
        if chain:
            normalized = _CHAIN_NORMALIZE.get(chain.lower())
            if normalized:
                params["chains"] = normalized
        headers = {"API-Key": self.api_key}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params, headers=headers)
            if response.status_code in (401, 403):
                raise ArkhamFatalError(
                    response.status_code,
                    f"Arkham auth failed ({response.status_code}) — check ARKHAM_API_KEY scope/tier",
                )
            if response.status_code == 429:
                raise ArkhamFatalError(429, "Arkham rate limited (429)")
            response.raise_for_status()
            return response.json()
