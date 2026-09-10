"""StreamableHTTP MCP client for XActions (Story 21.8a).

Reuses the existing `mcp` SDK transport and `ClientSession`, but is tailored
for the XActions daemon running at `http://xactions:3001/mcp` with Bearer auth
and the `X-Consumer-Id` header required by AD-20 / Trinity contract.

Usage:
    async with XActionsMcpClient() as client:
        result = await client.call_tool("x_facebook_group_posts", {...})
"""

from __future__ import annotations

import json
import logging
import os
from datetime import timedelta
from pathlib import Path
from typing import Any

import anyio
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.config import config

logger = logging.getLogger(__name__)

XACTIONS_MCP_DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("XACTIONS_MCP_TIMEOUT", "60.0"))


class XActionsMcpError(RuntimeError):
    """Raised when the XActions MCP server returns a structured error."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        retry_after: int | None = None,
        suggested_action: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.retry_after = retry_after
        self.suggested_action = suggested_action


class XActionsMcpClient:
    """Persistent StreamableHTTP MCP client for XActions.

    Usage:
        async with XActionsMcpClient() as client:
            result = await client.call_tool("x_facebook_group_posts", {...})
    """

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        consumer_id: str | None = None,
    ):
        self.url = (
            url or config.XACTIONS_MCP_URL or "http://xactions:3001/mcp"
        ).rstrip("/")
        self.api_key = api_key or getattr(config, "XACTIONS_MCP_API_KEY", "")
        self.consumer_id = consumer_id or getattr(
            config, "XACTIONS_CONSUMER_ID", "nowing"
        )
        self.admin_token = getattr(config, "XACTIONS_ADMIN_TOKEN", "")
        self._session: ClientSession | None = None
        self._transport_cm = None
        self._headers: dict[str, str] = {
            "X-Consumer-Id": self.consumer_id,
        }
        if self.api_key:
            self._headers["Authorization"] = f"Bearer {self.api_key}"

    async def __aenter__(self) -> XActionsMcpClient:
        self._transport_cm = streamablehttp_client(
            self.url,
            headers=self._headers,
            timeout=XACTIONS_MCP_DEFAULT_TIMEOUT_SECONDS,
        )
        read, write, _ = await self._transport_cm.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._session is not None:
            await self._session.__aexit__(exc_type, exc, tb)
            self._session = None
        if self._transport_cm is not None:
            await self._transport_cm.__aexit__(exc_type, exc, tb)
            self._transport_cm = None

    @staticmethod
    def _resolve_artifact_path(artifact_root: str, artifact_path: str) -> str:
        """Resolve a local artifact path under a trusted root.

        Rejects absolute paths and traversal attempts that escape the root.
        """
        root = Path(artifact_root).resolve()
        candidate = Path(artifact_path)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (root / candidate).resolve()
        if not str(resolved).startswith(str(root)):
            raise ValueError(
                f"Artifact path {artifact_path} escapes configured root {artifact_root}"
            )
        return str(resolved)

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return available XActions tools."""
        if not self._session:
            raise RuntimeError("MCP session not initialized. Use `async with client:`.")

        response = await self._session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema if hasattr(tool, "inputSchema") else {},
            }
            for tool in response.tools
        ]

    def _admin_args(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Inject admin token into admin-only tools, preserving caller overrides."""
        if self.admin_token and "token" not in arguments:
            return {**arguments, "token": self.admin_token}
        return arguments

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Call an XActions tool and parse its 3-layer JSON envelope."""
        if not self._session:
            raise RuntimeError("MCP session not initialized. Use `async with client:`.")

        if tool_name.startswith("x_admin_"):
            arguments = self._admin_args(arguments)

        logger.info("Calling XActions MCP tool %s", tool_name)
        response = await self._session.call_tool(
            tool_name,
            arguments=arguments,
            read_timeout_seconds=timedelta(seconds=XACTIONS_MCP_DEFAULT_TIMEOUT_SECONDS),
        )

        texts = []
        for content in response.content:
            if hasattr(content, "text"):
                texts.append(content.text)
            elif hasattr(content, "data"):
                texts.append(str(content.data))
            else:
                texts.append(str(content))

        result_text = "\n".join(texts).strip()
        if not result_text:
            return {"success": True, "data": [], "meta": {}}

        try:
            envelope = json.loads(result_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Non-JSON XActions response for {tool_name}: {exc}") from exc

        artifact_path = (envelope.get("meta") or {}).get("datasetArtifactPath")
        artifact_data: list[Any] = []
        if artifact_path:
            logger.info("XActions returned artifact for %s: %s", tool_name, artifact_path)
            artifact_data = await self._fetch_artifact(artifact_path)

        if response.isError:
            error = envelope.get("error") or {}
            retry_after = error.get("retryAfter")
            retry_after_ms = error.get("retryAfterMs")
            if retry_after is None and retry_after_ms is not None:
                retry_after = retry_after_ms / 1000
            raise XActionsMcpError(
                message=error.get("message", f"XActions tool {tool_name} failed"),
                code=error.get("code"),
                retry_after=retry_after,
                suggested_action=error.get("suggestedAction"),
            )

        data = envelope.get("data", [])
        if artifact_data:
            data = data + artifact_data if isinstance(data, list) else artifact_data

        return {
            "success": envelope.get("success", True),
            "data": data,
            "meta": envelope.get("meta", {}),
            "summary": envelope.get("summary", {}),
            "artifact_path": artifact_path,
        }

    async def _fetch_artifact(self, artifact_path: str) -> list[Any]:
        """Fetch a large dataset artifact exported by XActions."""
        # Artifact path is expected to be a URL or a local path on a shared volume.
        if artifact_path.startswith(("http://", "https://")):
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(XACTIONS_MCP_DEFAULT_TIMEOUT_SECONDS)
            ) as http_client:
                resp = await http_client.get(artifact_path, headers=self._headers)
                resp.raise_for_status()
                try:
                    return resp.json()
                except Exception:
                    logger.warning("Artifact %s is not valid JSON", artifact_path)
                    return []
        # Local shared volume path — require a configured, absolute root and
        # prevent traversal outside that root (Story 21.8a security hardening).
        artifact_root = getattr(config, "XACTIONS_ARTIFACT_ROOT", None)
        if not artifact_root:
            logger.warning(
                "Local artifact %s dropped: XACTIONS_ARTIFACT_ROOT not configured",
                artifact_path,
            )
            return []

        try:
            safe_path = self._resolve_artifact_path(artifact_root, artifact_path)
        except ValueError as exc:
            logger.warning("Rejected unsafe artifact path: %s", exc)
            return []

        try:
            return await anyio.to_thread.run_sync(
                lambda: json.load(open(safe_path, encoding="utf-8"))
            )
        except Exception as exc:
            logger.warning("Failed to read artifact %s: %s", safe_path, exc)
            return []

    async def health_check(self) -> dict[str, Any]:
        """Check XActions daemon health by calling a lightweight tool."""
        try:
            result = await self.call_tool("x_governor_status", {})
            return {
                "status": "healthy" if result.get("success") else "degraded",
                "data": result.get("data", {}),
            }
        except Exception as exc:
            return {"status": "unavailable", "error": str(exc)}
