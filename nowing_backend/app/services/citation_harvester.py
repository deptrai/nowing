"""Parse [[cite:id]]value[[/cite]] tags from synthesis output and build citation_map."""

from __future__ import annotations

import re
import time
from typing import Any

_CITE_RE = re.compile(r"\[\[cite:([^\]]+)\]\](.*?)\[\[/cite\]\]", re.DOTALL)

# Known providers inferred from citation ID suffix
_PROVIDER_ALIASES: dict[str, str] = {
    "coingecko": "CoinGecko",
    "defillama": "DefiLlama",
    "goplus": "GoPlus",
    "etherscan": "Etherscan",
    "dexscreener": "DexScreener",
    "messari": "Messari",
    "coinmarketcap": "CoinMarketCap",
    "certik": "CertiK",
    "nansen": "Nansen",
    "dune": "Dune",
    "tokeninsight": "TokenInsight",
    # Coordinator-fill: estimates from coordinator's training knowledge when a
    # sub-agent returned no data. Suffix `-coordinator` on cite IDs.
    "coordinator": "Coordinator (estimated)",
}


def _infer_provider(cite_id: str) -> str:
    lower = cite_id.lower()
    for key, name in _PROVIDER_ALIASES.items():
        if lower.endswith(f"-{key}") or lower.startswith(f"{key}-") or f"-{key}-" in lower:
            return name
    return "Unknown"


def harvest_citations(text: str) -> dict[str, Any]:
    """
    Extract [[cite:id]]value[[/cite]] tags from synthesis text.

    Returns a citation_map dict suitable for SSE metadata emission and FE consumption.
    Multiple occurrences of the same ID are de-duped (first value wins).

    Example input:
        Price is [[cite:price-current-coingecko]]$2.34[[/cite]] today.

    Example output:
        {
            "price-current-coingecko": {
                "id": "price-current-coingecko",
                "value": "$2.34",
                "sources": [{"provider": "CoinGecko", "fetchedAt": "2024-..."}],
            }
        }
    """
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    citation_map: dict[str, Any] = {}

    for match in _CITE_RE.finditer(text):
        cite_id = match.group(1).strip()
        value = match.group(2).strip()

        if cite_id in citation_map:
            continue

        provider = _infer_provider(cite_id)
        citation_map[cite_id] = {
            "id": cite_id,
            "value": value,
            "sources": [
                {
                    "provider": provider,
                    "fetchedAt": now_iso,
                    "rawValue": value,
                }
            ],
        }

    return citation_map


def strip_cite_tags(text: str) -> str:
    """Remove [[cite:id]] and [[/cite]] wrapper tags, keeping the inner value."""
    return _CITE_RE.sub(lambda m: m.group(2), text)
