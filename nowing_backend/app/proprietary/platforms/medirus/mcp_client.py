"""StreamableHTTP MCP client for Medirus (Story 21.8a, updated for Story 40.1).

Reuses the existing `mcp` SDK transport and `ClientSession`, but is tailored
for the Medirus daemon running at `http://medirus:3001/mcp` with Bearer auth
and the `X-Consumer-Id` header required by AD-20 / Trinity contract.

Usage:
    async with MedirusMcpClient() as client:
        result = await client.call_tool("medirus_facebook_group_posts", {...})

Story 40.1 additions:
    - Circuit breaker integration (3 consecutive failures → OPEN for 60s)
    - Fail-fast with MEDIRUS_4001 code when circuit is open
    - 4.0s connectivity timeout for health probes
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import threading
import weakref
from datetime import timedelta
from pathlib import Path
from typing import Any

import anyio
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.config import config
from app.proprietary.platforms.medirus.circuit_breaker import (
    MEDIRUS_CIRCUIT_BREAKER,
    CircuitBreakerOpenError,
)

logger = logging.getLogger(__name__)

MEDIRUS_MCP_DEFAULT_TIMEOUT_SECONDS = float(
    os.environ.get("MEDIRUS_MCP_TIMEOUT", "60.0")
)
# Story 40.1: Fast timeout for connectivity/health checks (4.0s)
MEDIRUS_CONNECTIVITY_TIMEOUT_SECONDS = float(
    os.environ.get("MEDIRUS_CONNECTIVITY_TIMEOUT", "4.0")
)


class _LoopClientEntry:
    def __init__(self) -> None:
        self.client: MedirusMcpClient | None = None
        self.ready: bool = False
        self.connecting: asyncio.Lock = asyncio.Lock()
        self.init_error: BaseException | None = None


_LOOP_CLIENTS: weakref.WeakKeyDictionary[
    asyncio.AbstractEventLoop, _LoopClientEntry
] = weakref.WeakKeyDictionary()
_CLIENTS_LOCK = threading.Lock()


class MedirusMcpError(RuntimeError):
    """Raised when the Medirus MCP server returns a structured error."""

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


class MedirusMcpClient:
    """Persistent StreamableHTTP MCP client for Medirus.

    Usage:
        async with MedirusMcpClient() as client:
            result = await client.call_tool("medirus_facebook_group_posts", {...})
    """

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        consumer_id: str | None = None,
    ):
        self.url = (
            url or config.MEDIRUS_MCP_URL or "http://medirus:3001/mcp"
        ).rstrip("/")
        self.api_key = api_key or getattr(config, "MEDIRUS_MCP_API_KEY", "")
        self.consumer_id = consumer_id or getattr(
            config, "MEDIRUS_CONSUMER_ID", "nowing"
        )
        self.admin_token = getattr(config, "MEDIRUS_ADMIN_TOKEN", "")
        self._session: ClientSession | None = None
        self._transport_cm = None
        self._serialize_lock: asyncio.Lock | None = None
        self._serialize_lock_loop_ref: (
            weakref.ReferenceType[asyncio.AbstractEventLoop] | None
        ) = None
        self._is_managed: bool = False
        self._tainted: bool = False
        self._headers: dict[str, str] = {
            "X-Consumer-Id": self.consumer_id,
        }
        if self.api_key:
            # pi-lens-ignore: ast-grep:no-secret-in-env-var-name -- runtime credential value, not hardcoded
            self._headers["Authorization"] = f"Bearer {self.api_key}"

    @property
    def serialize_lock(self) -> asyncio.Lock:
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if (
            self._serialize_lock is None
            or self._serialize_lock_loop_ref is None
            or self._serialize_lock_loop_ref() is not current_loop
        ):
            self._serialize_lock = asyncio.Lock()
            self._serialize_lock_loop_ref = (
                weakref.ref(current_loop) if current_loop is not None else None
            )
        return self._serialize_lock

    async def __aenter__(self) -> MedirusMcpClient:
        if self._session is not None:
            return self
        self._tainted = False
        self._transport_cm = streamablehttp_client(
            self.url,
            headers=self._headers,
            timeout=MEDIRUS_MCP_DEFAULT_TIMEOUT_SECONDS,
        )
        try:
            read, write, _ = await self._transport_cm.__aenter__()
            self._session = ClientSession(read, write)
            await self._session.__aenter__()
            await self._session.initialize()
        except BaseException:
            await self._close_session()
            raise
        return self

    async def _close_session(
        self,
        exc_type: type[BaseException] | None = None,
        exc: BaseException | None = None,
        tb: Any = None,
    ) -> None:
        try:
            if self._session is not None:
                await self._session.__aexit__(exc_type, exc, tb)
        finally:
            self._session = None
            try:
                if self._transport_cm is not None:
                    await self._transport_cm.__aexit__(exc_type, exc, tb)
            finally:
                self._transport_cm = None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc: BaseException | None = None,
        tb: Any = None,
    ) -> None:
        if self._is_managed:
            return
        await self._close_session(exc_type, exc, tb)

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

    async def _handle_transport_error(self, exc: BaseException) -> None:
        self._tainted = True
        with contextlib.suppress(RuntimeError):
            current_loop = asyncio.get_running_loop()
            with _CLIENTS_LOCK:
                if (
                    _LOOP_CLIENTS.get(current_loop) is not None
                    and _LOOP_CLIENTS[current_loop].client is self
                ):
                    _LOOP_CLIENTS.pop(current_loop, None)
        with contextlib.suppress(Exception):
            await self._close_session()

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return available Medirus tools."""
        async with self.serialize_lock:
            if not self._session or getattr(self, "_tainted", False):
                raise RuntimeError(
                    "MCP session not initialized: session is closed or tainted"
                )

            try:
                response = await self._session.list_tools()
            except (
                ConnectionError,
                anyio.ClosedResourceError,
                anyio.EndOfStream,
                anyio.BrokenResourceError,
                httpx.TransportError,
                asyncio.CancelledError,
            ) as exc:
                await self._handle_transport_error(exc)
                raise exc
            return [
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema
                    if hasattr(tool, "inputSchema")
                    else {},
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
        """Call an Medirus tool and parse its 3-layer JSON envelope.

        Story 40.1: Wrapped in circuit breaker for fail-fast on Medirus outage.
        """
        # Story 40.1: wrap the actual call through the circuit breaker
        try:
            return await MEDIRUS_CIRCUIT_BREAKER.call(
                self._call_tool_inner, tool_name, arguments
            )
        except CircuitBreakerOpenError as exc:
            # Map circuit-open to MEDIRUS_4001 error envelope for upstream handling
            logger.warning("Medirus circuit breaker OPEN: %s", exc)
            raise MedirusMcpError(
                message="scraper_temporarily_unavailable",
                code="MEDIRUS_4001",
            ) from exc

    async def _call_tool_inner(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Inner implementation of call_tool (pre-Story-40.1 logic)."""
        async with self.serialize_lock:
            if not self._session or getattr(self, "_tainted", False):
                raise RuntimeError(
                    "MCP session not initialized: session is closed or tainted"
                )

            effective_arguments = arguments
            if tool_name.startswith("medirus_admin_"):
                effective_arguments = self._admin_args(arguments)

            logger.info("Calling Medirus MCP tool %s", tool_name)
            try:
                response = await self._session.call_tool(
                    tool_name,
                    arguments=effective_arguments,
                    read_timeout_seconds=timedelta(
                        seconds=MEDIRUS_MCP_DEFAULT_TIMEOUT_SECONDS
                    ),
                )
            except (
                ConnectionError,
                anyio.ClosedResourceError,
                anyio.EndOfStream,
                anyio.BrokenResourceError,
                httpx.TransportError,
                asyncio.CancelledError,
            ) as exc:
                await self._handle_transport_error(exc)
                raise exc

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
                raise RuntimeError(
                    f"Non-JSON Medirus response for {tool_name}: {exc}"
                ) from exc

            artifact_path = (envelope.get("meta") or {}).get("datasetArtifactPath")

            if response.isError:
                error = envelope.get("error") or {}
                retry_after = error.get("retryAfter")
                retry_after_ms = error.get("retryAfterMs")
                if retry_after is None and retry_after_ms is not None:
                    retry_after = retry_after_ms / 1000
                raise MedirusMcpError(
                    message=error.get("message", f"Medirus tool {tool_name} failed"),
                    code=error.get("code"),
                    retry_after=retry_after,
                    suggested_action=error.get("suggestedAction"),
                )

            data = envelope.get("data", [])

        # Fetch artifact outside serialize_lock to prevent blocking I/O and deadlocks
        artifact_data: list[Any] = []
        if artifact_path:
            logger.info(
                "Medirus returned artifact for %s: %s", tool_name, artifact_path
            )
            artifact_data = await self._fetch_artifact(artifact_path)

        if artifact_data:
            items = (
                artifact_data if isinstance(artifact_data, list) else [artifact_data]
            )
            data = (data if isinstance(data, list) else []) + items

        return {
            "success": envelope.get("success", True),
            "data": data,
            "error": envelope.get("error"),
            "meta": envelope.get("meta", {}),
            "summary": envelope.get("summary", {}),
            "artifact_path": artifact_path,
        }

    async def _fetch_artifact(self, artifact_path: str) -> list[Any]:
        """Fetch a large dataset artifact exported by Medirus."""
        # Artifact path is expected to be a URL or a local path on a shared volume.
        if artifact_path.startswith(("http://", "https://")):
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(MEDIRUS_MCP_DEFAULT_TIMEOUT_SECONDS)
            ) as http_client:
                resp = await http_client.get(artifact_path, headers=self._headers)
                resp.raise_for_status()
                try:
                    return resp.json()
                except Exception:  # artifact response not JSON; return empty list
                    logger.warning("Artifact %s is not valid JSON", artifact_path)
                    return []
        # Local shared volume path — require a configured, absolute root and
        # prevent traversal outside that root (Story 21.8a security hardening).
        artifact_root = getattr(config, "MEDIRUS_ARTIFACT_ROOT", None)
        if not artifact_root:
            logger.warning(
                "Local artifact %s dropped: MEDIRUS_ARTIFACT_ROOT not configured",
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
                lambda: json.load(
                    open(safe_path, encoding="utf-8")
                )  # pi-lens-ignore: python-path-traversal -- safe_path validated by _resolve_artifact_path above
            )
        except (
            Exception
        ) as exc:  # local artifact file read/JSON parse failure; return empty list
            logger.warning("Failed to read artifact %s: %s", safe_path, exc)
            return []

    async def health_check(self) -> dict[str, Any]:
        """Check Medirus daemon health by calling a lightweight tool.

        Story 40.1: Uses MEDIRUS_CONNECTIVITY_TIMEOUT_SECONDS (4s) for a fast
        connectivity probe — distinct from the 60s default for real tool calls.
        """
        try:
            async with asyncio.timeout(MEDIRUS_CONNECTIVITY_TIMEOUT_SECONDS):
                result = await self.call_tool("medirus_governor_status", {})
            return {
                "status": "healthy" if result.get("success") else "degraded",
                "data": result.get("data", {}),
            }
        except (
            TimeoutError
        ):  # asyncio.TimeoutError is an alias of the builtin since Python 3.11
            return {
                "status": "unavailable",
                "error": f"connectivity check timed out after {MEDIRUS_CONNECTIVITY_TIMEOUT_SECONDS}s",
            }
        except Exception as exc:  # health check tool failure; mark unavailable
            return {"status": "unavailable", "error": str(exc)}


async def get_shared_client(
    url: str | None = None,
    api_key: str | None = None,
    consumer_id: str | None = None,
) -> MedirusMcpClient:
    """Retrieve or create a loop-scoped shared MedirusMcpClient."""
    default_url = (config.MEDIRUS_MCP_URL or "http://medirus:3001/mcp").rstrip("/")
    default_api_key = getattr(config, "MEDIRUS_MCP_API_KEY", "")
    default_consumer_id = getattr(config, "MEDIRUS_CONSUMER_ID", "nowing")

    if url is not None and url.rstrip("/") != default_url:
        raise ValueError(
            f"Custom url {url!r} is not supported with get_shared_client(). "
            "Use standalone MedirusMcpClient instance instead."
        )
    if api_key is not None and api_key != default_api_key:
        raise ValueError(
            "Custom api_key is not supported with get_shared_client(). "
            "Use standalone MedirusMcpClient instance instead."
        )
    if consumer_id is not None and consumer_id != default_consumer_id:
        raise ValueError(
            f"Custom consumer_id {consumer_id!r} is not supported with get_shared_client(). "
            "Use standalone MedirusMcpClient instance instead."
        )

    loop = asyncio.get_running_loop()

    while True:
        with _CLIENTS_LOCK:
            entry = _LOOP_CLIENTS.get(loop)
            if (
                entry is not None
                and entry.ready
                and entry.client is not None
                and not getattr(entry.client, "_tainted", False)
            ):
                return entry.client

            if entry is not None and getattr(
                getattr(entry, "client", None), "_tainted", False
            ):
                _LOOP_CLIENTS.pop(loop, None)
                entry = None

            if entry is None:
                entry = _LoopClientEntry()
                _LOOP_CLIENTS[loop] = entry

        async with entry.connecting:
            with _CLIENTS_LOCK:
                current = _LOOP_CLIENTS.get(loop)
            if current is not entry:
                # Prior attempt failed and evicted entry; retry with fresh entry
                continue

            if (
                entry.ready
                and entry.client is not None
                and not getattr(entry.client, "_tainted", False)
            ):
                return entry.client

            client = MedirusMcpClient()
            client._is_managed = True
            try:
                await client.__aenter__()
                entry.client = client
                entry.ready = True
                return client
            except BaseException as exc:
                entry.init_error = exc
                with _CLIENTS_LOCK:
                    if _LOOP_CLIENTS.get(loop) is entry:
                        _LOOP_CLIENTS.pop(loop, None)
                client._is_managed = False
                with contextlib.suppress(Exception):
                    await client._close_session()
                raise


async def release_shared_client_for_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Explicitly release and close the shared MCP client for the specified loop."""
    with _CLIENTS_LOCK:
        entry = _LOOP_CLIENTS.pop(loop, None)

    if entry:
        async with entry.connecting:
            if entry.client:
                client = entry.client
                client._is_managed = False  # Enable teardown on session
                client._tainted = True
                try:
                    async with asyncio.timeout(0.5):
                        async with client.serialize_lock:
                            await client._close_session()
                except Exception:
                    await client._close_session()


__all__ = [
    "MedirusMcpClient",
    "MedirusMcpError",
    "get_shared_client",
    "release_shared_client_for_loop",
]
