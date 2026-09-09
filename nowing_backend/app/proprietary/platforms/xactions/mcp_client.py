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
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.config import config

logger = logging.getLogger(__name__)


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
        self._session: ClientSession | None = None
        self._transport_cm = None
        self._headers: dict[str, str] = {
            "X-Consumer-Id": self.consumer_id,
        }
        if self.api_key:
            self._headers["Authorization"] = f"Bearer {self.api_key}"

    async def __aenter__(self) -> XActionsMcpClient:
        self._transport_cm = streamablehttp_client(
            self.url, headers=self._headers
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

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Call an XActions tool and parse its 3-layer JSON envelope."""
        if not self._session:
            raise RuntimeError("MCP session not initialized. Use `async with client:`.")

        logger.info("Calling XActions MCP tool %s", tool_name)
        response = await self._session.call_tool(tool_name, arguments=arguments)

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

        artifact_path = envelope.get("meta", {}).get("datasetArtifactPath")
        artifact_data: list[Any] = []
        if artifact_path:
            logger.info("XActions returned artifact for %s: %s", tool_name, artifact_path)
            artifact_data = await self._fetch_artifact(artifact_path)

        if response.isError:
            error = envelope.get("error", {})
            raise XActionsMcpError(
                message=error.get("message", f"XActions tool {tool_name} failed"),
                code=error.get("code"),
                retry_after=error.get("retryAfter") or error.get("retryAfterMs"),
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
            async with httpx.AsyncClient() as http_client:
                resp = await http_client.get(artifact_path, headers=self._headers)
                resp.raise_for_status()
                try:
                    return resp.json()
                except Exception:
                    logger.warning("Artifact %s is not valid JSON", artifact_path)
                    return []
        # Local shared volume path
        try:
            with open(artifact_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Failed to read artifact %s: %s", artifact_path, exc)
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
