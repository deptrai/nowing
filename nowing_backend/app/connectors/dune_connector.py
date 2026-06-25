"""Dune Analytics Connector."""

import asyncio
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DUNE_BASE = "https://api.dune.com/api/v1"
_POLL_INTERVAL = 3.0
_MAX_POLLS = 20  # 60s max wait


class DuneConnector:
    """Connector for Dune Analytics API (direct HTTP — avoids blocking SDK)."""

    def __init__(self) -> None:
        self.api_key = os.getenv("DUNE_API_KEY", "").strip() or None

    def _headers(self) -> dict[str, str]:
        return {"X-Dune-API-Key": self.api_key or ""}

    async def get_smart_money_flow(self, token_address: str) -> list[dict[str, Any]] | None:
        """Execute parameterized Dune query and return rows.

        Returns list of dicts with keys: address, label, net_flow_usd, tx_count.
        Returns None when API key is missing or query fails.
        """
        if not self.api_key:
            return None

        query_id_str = os.getenv("DUNE_SMART_MONEY_QUERY_ID", "7431659")
        try:
            query_id = int(query_id_str)
        except ValueError:
            query_id = 7431659

        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Execute query with token_address parameter
            exec_resp = await client.post(
                f"{_DUNE_BASE}/query/{query_id}/execute",
                json={"query_parameters": {"token_address": token_address}},
                headers=self._headers(),
            )
            if exec_resp.status_code != 200:
                logger.warning(
                    "Dune execute failed: %s %s", exec_resp.status_code, exec_resp.text[:200]
                )
                return None
            execution_id = exec_resp.json().get("execution_id")
            if not execution_id:
                return None

        # 2. Poll status (separate client to allow longer total timeout)
        async with httpx.AsyncClient(timeout=10.0) as client:
            for _ in range(_MAX_POLLS):
                await asyncio.sleep(_POLL_INTERVAL)
                status_resp = await client.get(
                    f"{_DUNE_BASE}/execution/{execution_id}/status",
                    headers=self._headers(),
                )
                state = status_resp.json().get("state", "")
                if state == "QUERY_STATE_COMPLETED":
                    break
                if state in ("QUERY_STATE_FAILED", "QUERY_STATE_CANCELLED"):
                    logger.warning("Dune execution %s ended with state: %s", execution_id, state)
                    return None
            else:
                logger.warning("Dune execution %s timed out after %ss", execution_id, _MAX_POLLS * _POLL_INTERVAL)
                return None

            # 3. Fetch results
            result_resp = await client.get(
                f"{_DUNE_BASE}/execution/{execution_id}/results",
                headers=self._headers(),
            )
            if result_resp.status_code != 200:
                return None
            return result_resp.json().get("result", {}).get("rows") or []
