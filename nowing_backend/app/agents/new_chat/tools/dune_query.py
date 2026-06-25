"""Dune Analytics query tool for Nowing deep agent.

Provides 1 tool: run_dune_query

Pre-registered queries are stored as JSON files under
`queries/dune/` in this package. The tool loads the registry at import
time and executes queries via the Dune Analytics API v1.

All queries return {"source_domain": "dune.com", "dune_url": "...", ...}
so SourceAttributionMiddleware emits citation events (AC3, Story 9-UX-1).
`dune_url` deeplinks to the original Dune query so users can remix it.

Environment variables:
    DUNE_API_KEY — Required (Basic plan $99/mo, 40 req/min).

Rate limits (AC14):
    Basic plan: 40 req/min.
    Plus plan: 180 req/min.
    Default budget: 40 req/min (Basic).
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx
from langchain_core.tools import tool

from ._rate_limiter import _ApiRateLimiter

logger = logging.getLogger(__name__)

_TIMEOUT = 60.0  # Dune queries can take longer than 30s on cold cache
_DUNE_BASE = "https://api.dune.com/api/v1"

# AC14: Dune Basic plan = 40 req/min
_dune_rate_limit = int(os.getenv("DUNE_RATE_LIMIT", "40"))
_dune_rl = _ApiRateLimiter(max_calls=_dune_rate_limit, window_seconds=60.0, name="dune")

# --------------------------------------------------------------------------
# Query registry — loaded from JSON files at import time
# --------------------------------------------------------------------------

_QUERIES_DIR = Path(__file__).parent / "queries" / "dune"


def _load_query_registry() -> dict[int, dict[str, Any]]:
    """Load all Dune query metadata from JSON files.

    Returns a mapping of query_id → metadata dict.
    Missing / malformed files are logged and skipped.
    """
    registry: dict[int, dict[str, Any]] = {}
    if not _QUERIES_DIR.is_dir():
        logger.warning("Dune queries directory not found: %s", _QUERIES_DIR)
        return registry
    for path in _QUERIES_DIR.glob("*.json"):
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
            qid = int(meta["query_id"])
            if qid < 100_000:
                logger.warning(
                    "Dune query '%s' has placeholder ID %d — "
                    "replace with a real Dune query ID before use. Skipping.",
                    meta.get("name", path.name),
                    qid,
                )
                continue
            registry[qid] = meta
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load Dune query file %s: %s", path, exc)
    return registry


# Module-level query registry — populated once at import
_QUERY_REGISTRY: dict[int, dict[str, Any]] = _load_query_registry()

# Reverse-lookup: query name (lowercase) → query_id
_QUERY_NAME_INDEX: dict[str, int] = {
    meta["name"].lower(): qid for qid, meta in _QUERY_REGISTRY.items()
}


def _api_key() -> str | None:
    return os.getenv("DUNE_API_KEY", "").strip() or None


def _unavailable_error(status: int) -> dict[str, Any]:
    messages = {
        401: "Dune API key missing or invalid. Add DUNE_API_KEY to .env.",
        403: "Dune API key does not have access. Upgrade to Basic plan ($99/mo).",
        429: "Dune rate limit exceeded (40 req/min on Basic). Retry later.",
    }
    return {
        "error": messages.get(status, f"Dune API returned HTTP {status}"),
        "status": status,
        "source_domain": "dune.com",
    }


def create_run_dune_query_tool():
    """Factory: run_dune_query — execute a pre-registered Dune Analytics query."""

    @tool
    async def run_dune_query(
        query_id: int,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a pre-registered Dune Analytics query and return results.

        Use for on-chain data that is NOT available from DeFiLlama or
        CoinGecko — e.g. DEX volume by pool, staking flows, whale
        concentration, NFT floor prices.

        Pre-registered queries are loaded from queries/dune/*.json at startup.
        Call with a valid query_id from the registry. If no queries are
        registered, ask the user to configure real Dune query IDs.

        The returned `dune_url` deeplinks to the original Dune query so users
        can remix it for their own analysis (AC9).

        Args:
            query_id: Pre-registered Dune query ID.
            params: Optional dict of query parameters (see each query's schema).

        Returns:
            Dict with rows (list of result rows), columns (list of str),
            row_count (int), dune_url (str), query_name (str),
            source_domain "dune.com"; or {"error": ..., "status": ...}.
        """
        if query_id not in _QUERY_REGISTRY:
            available = sorted(_QUERY_REGISTRY.keys())
            return {
                "error": (
                    f"Query ID {query_id} is not in the pre-registered registry. "
                    f"Available IDs: {available}"
                ),
                "source_domain": "dune.com",
            }

        if not _api_key():
            return _unavailable_error(401)

        query_meta = _QUERY_REGISTRY[query_id]
        params = params or {}

        await _dune_rl.acquire()
        # Dune v1 flow: POST /execute → poll /status/<execution_id> → GET /results/<execution_id>
        try:
            async with httpx.AsyncClient(
                timeout=_TIMEOUT,
                headers={"X-Dune-Api-Key": _api_key() or ""},
            ) as client:
                # Step 1: execute
                exec_resp = await client.post(
                    f"{_DUNE_BASE}/query/{query_id}/execute",
                    json={"query_parameters": params},
                )
                if exec_resp.status_code in (401, 403, 429):
                    return _unavailable_error(exec_resp.status_code)
                exec_resp.raise_for_status()
                execution_id = exec_resp.json()["execution_id"]

                # Step 2: poll until terminal state (max 60s, already in timeout)
                import asyncio
                for attempt in range(12):  # 12 × 5s = 60s budget
                    await asyncio.sleep(5)
                    status_resp = await client.get(
                        f"{_DUNE_BASE}/execution/{execution_id}/status"
                    )
                    if status_resp.status_code in (401, 403, 429):
                        return _unavailable_error(status_resp.status_code)
                    status_resp.raise_for_status()
                    state = status_resp.json().get("state", "")
                    if state == "QUERY_STATE_COMPLETED":
                        break
                    if state in ("QUERY_STATE_FAILED", "QUERY_STATE_CANCELLED"):
                        return {
                            "error": f"Dune query {query_id} {state}",
                            "source_domain": "dune.com",
                        }
                else:
                    return {
                        "error": f"Dune query {query_id} timed out after 60s",
                        "source_domain": "dune.com",
                    }

                # Step 3: fetch results
                results_resp = await client.get(
                    f"{_DUNE_BASE}/execution/{execution_id}/results",
                    params={"limit": 100},
                )
                if results_resp.status_code in (401, 403, 429):
                    return _unavailable_error(results_resp.status_code)
                results_resp.raise_for_status()
                result_data = results_resp.json().get("result", {})

            rows = result_data.get("rows", [])
            metadata = result_data.get("metadata", {})
            columns = [c.get("name", "") for c in metadata.get("column_names", [])] if "column_names" in metadata else (list(rows[0].keys()) if rows else [])

            return {
                "source_domain": "dune.com",
                "query_id": query_id,
                "query_name": query_meta["name"],
                "dune_url": query_meta["dune_url"],
                "rows": rows[:100],  # cap at 100 rows for context budget
                "columns": columns,
                "row_count": len(rows),
                "params_used": params,
            }

        except httpx.TimeoutException:
            logger.warning("dune query timeout for query_id=%s", query_id)
            return {"error": "Dune API timeout (query may still be running)", "source_domain": "dune.com"}
        except httpx.HTTPStatusError as exc:
            logger.warning("dune query HTTP error %s for query_id=%s", exc.response.status_code, query_id)
            return {"error": f"Dune API error: {exc.response.status_code}", "source_domain": "dune.com"}
        except Exception as exc:
            logger.exception("dune query unexpected error for query_id=%s", query_id)
            return {"error": f"Unexpected error: {exc}", "source_domain": "dune.com"}

    return run_dune_query


def list_available_dune_queries() -> list[dict[str, Any]]:
    """Return metadata for all pre-registered Dune queries.

    Useful for the LLM to discover available queries before calling
    run_dune_query. Not exposed as a tool — called internally.
    """
    return [
        {
            "query_id": qid,
            "name": meta["name"],
            "description": meta["description"],
            "params_schema": meta.get("params_schema", {}),
            "dune_url": meta["dune_url"],
        }
        for qid, meta in sorted(_QUERY_REGISTRY.items())
    ]
