"""ChainLens Webhook Monitors Client (Story 20.8).

Manages recurring web monitors on ChainLens:
- Creation via POST /v1/monitors
- Teardown via DELETE /v1/monitors/{monitor_id}
- Webhook signature verification via HMAC-SHA256
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

import httpx

from app.config import config
from app.services.chainlens.auth import get_chainlens_auth

logger = logging.getLogger(__name__)


class ChainLensMonitorError(Exception):
    """Raised when ChainLens Monitors API fails."""


class ChainLensMonitorClient:
    """Client for managing recurring search monitors on ChainLens."""

    def __init__(self, *, base_url: str | None = None) -> None:
        self.base_url = (
            base_url
            or getattr(config, "CHAINLENS_API_URL", "http://localhost:3001")
        ).rstrip("/")

    def _get_secret(self) -> str:
        return (
            getattr(config, "CHAINLENS_AUTH_CONTEXT_SECRET", "")
            or getattr(config, "SECRET_KEY", "")
            or "chainlens_default_monitor_secret"
        )

    def verify_webhook_signature(
        self,
        raw_body: bytes,
        signature: str | None,
    ) -> bool:
        """Verify HMAC-SHA256 signature from X-ChainLens-Signature header."""
        if not signature or not signature.strip():
            return False

        secret = self._get_secret().encode("utf-8")
        expected = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()

        # ChainLens may send "sha256=<hex>" or plain hex
        sig_to_compare = signature.strip()
        if sig_to_compare.startswith("sha256="):
            sig_to_compare = sig_to_compare[7:]

        return hmac.compare_digest(expected.lower(), sig_to_compare.lower())

    async def create_monitor(
        self,
        *,
        workspace_id: int,
        name: str,
        query: str,
        cron: str,
        webhook_url: str,
        dedup_key_policy: str = "content_hash",
        mode: str = "fast",
        data_sources: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a recurring monitor on ChainLens.

        Returns:
            Dict containing ``monitorId``, ``name``, ``cron``, etc.
        """
        auth = get_chainlens_auth()
        headers = auth.get_outbound_headers(workspace_id=workspace_id)
        headers["Content-Type"] = "application/json"

        payload = {
            "name": name,
            "query": query,
            "cron": cron,
            "webhookUrl": webhook_url,
            "dedupKeyPolicy": dedup_key_policy,
            "mode": mode,
            "dataSources": data_sources or ["web"],
        }

        url = f"{self.base_url}/v1/monitors"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                res = await client.post(url, json=payload, headers=headers)
                if not res.is_success:
                    raise ChainLensMonitorError(
                        f"ChainLens monitor creation failed ({res.status_code}): {res.text}"
                    )
                return res.json()
            except httpx.HTTPError as exc:
                logger.error("[ChainLensMonitor] HTTP error creating monitor: %s", exc)
                raise ChainLensMonitorError(f"HTTP connection error: {exc}") from exc

    async def delete_monitor(
        self,
        monitor_id: str,
        *,
        workspace_id: int = 0,
    ) -> bool:
        """Delete an existing monitor on ChainLens. Returns True on success or 404."""
        auth = get_chainlens_auth()
        headers = auth.get_outbound_headers(workspace_id=workspace_id)

        url = f"{self.base_url}/v1/monitors/{monitor_id}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                res = await client.delete(url, headers=headers)
                if res.status_code == 404:
                    return True
                if not res.is_success:
                    logger.warning(
                        "[ChainLensMonitor] Failed to delete monitor %s: %s %s",
                        monitor_id,
                        res.status_code,
                        res.text,
                    )
                    return False
                return True
            except Exception as exc:
                logger.warning(
                    "[ChainLensMonitor] Error deleting monitor %s: %s", monitor_id, exc
                )
                return False
