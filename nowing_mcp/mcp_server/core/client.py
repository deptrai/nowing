"""Authenticated transport to a Nowing backend's REST API.

Sends requests to fully-formed paths, returns parsed JSON, and turns any
transport or HTTP failure into a readable ``ToolError``.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from .auth.identity import current_api_key
from .errors import ThreadBusyError, ToolError
from .sse import SseEvent, iter_sse_events

_FAILURE_HINTS: dict[int, str] = {
    401: "Authentication failed — the Nowing API key is invalid or expired.",
    402: "The workspace is out of credits for this operation.",
    403: (
        "Access denied — the token lacks permission, or API access is disabled "
        "for this workspace (enable it in Nowing workspace settings)."
    ),
    404: "The requested resource was not found.",
    429: "Rate limited by the backend — retry after a short pause.",
}


class NowingClient:
    """Issues authenticated requests against ``{base_url}{api_prefix}``."""

    def __init__(
        self, *, api_base: str, timeout: float, fallback_api_key: str | None = None
    ) -> None:
        self._api_base = api_base
        # Resolved per request, so no key is baked into the shared client. The
        # fallback is the env key used under stdio, where there is no header.
        self._fallback_api_key = fallback_api_key
        self._http = httpx.AsyncClient(
            base_url=api_base,
            headers={"Accept": "application/json"},
            timeout=timeout,
        )

    def _auth_headers(self) -> dict[str, str]:
        """Resolve the caller's key: the per-request header, else the env key."""
        api_key = current_api_key() or self._fallback_api_key
        if not api_key:
            raise ToolError(
                "No Nowing API key supplied. Send it as an 'Authorization: "
                "Bearer nw_pat_...' header (remote server), or set the "
                "NOWING_API_KEY environment variable (stdio)."
            )
        return {"Authorization": f"Bearer {api_key}"}

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        data: dict[str, Any] | None = None,
        files: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Send a request and return the parsed body, or raise ``ToolError``.

        ``headers`` are merged with the auth headers for this call.
        """
        # Omit unset query params: sending them empty makes the API parse ""
        # as a value (e.g. int("") on folder_id) and fail.
        if params is not None:
            params = {key: value for key, value in params.items() if value is not None}
        headers = {**self._auth_headers(), **(headers or {})}
        try:
            response = await self._http.request(
                method,
                path,
                params=params,
                json=json,
                data=data,
                files=files,
                headers=headers,
            )
        except httpx.RequestError as exc:
            raise ToolError(
                f"Could not reach Nowing at {self._api_base}: {exc}. "
                "Confirm the backend is running and NOWING_BASE_URL is correct."
            ) from exc

        if response.is_success:
            return self._parse_body(response)
        raise ToolError(self._explain_failure(response))

    async def request_bytes(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> tuple[bytes, str | None]:
        """Send a request and return ``(raw bytes, content-type)``.

        Used for binary responses (report exports) where ``request`` would
        corrupt the payload by decoding it as text. Failure handling matches
        ``request``.
        """
        if params is not None:
            params = {key: value for key, value in params.items() if value is not None}
        headers = self._auth_headers()
        try:
            response = await self._http.request(
                method,
                path,
                params=params,
                headers=headers,
            )
        except httpx.RequestError as exc:
            raise ToolError(
                f"Could not reach Nowing at {self._api_base}: {exc}. "
                "Confirm the backend is running and NOWING_BASE_URL is correct."
            ) from exc

        if response.is_success:
            return response.content, response.headers.get("content-type")
        raise ToolError(self._explain_failure(response))

    async def stream_sse(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        timeout_s: float = 600.0,
    ) -> AsyncIterator[SseEvent]:
        """Open a streaming request and yield parsed SSE events.

        Used by ``nowing_chat`` to consume the ``/new_chat`` stream. Yields
        ``SseEvent`` objects; raises ``ThreadBusyError`` on a 409 busy reply
        (with the backend ``errorCode``) and ``ToolError`` for any other
        failure. Kept as an async generator so the stream stays open across
        yields, mirroring the evals ``_stream_once`` client.
        """
        headers = self._auth_headers()
        headers["Accept"] = "text/event-stream"
        timeout = httpx.Timeout(timeout_s, connect=10.0)
        try:
            async with self._http.stream(
                method,
                path,
                json=json,
                headers=headers,
                timeout=timeout,
            ) as response:
                if response.status_code == 409:
                    detail = await self._extract_busy_detail(response)
                    raise ThreadBusyError(
                        error_code=detail.get("errorCode", "THREAD_BUSY"),
                        message=detail.get("message", "Thread is busy"),
                    )
                if not response.is_success:
                    body = await response.aread()
                    status = response.status_code
                    hint = _FAILURE_HINTS.get(status)
                    detail = self._extract_detail_text(body)
                    if detail and hint:
                        raise ToolError(f"{hint} (server said: {detail})")
                    if detail:
                        raise ToolError(f"Nowing returned {status}: {detail}")
                    raise ToolError(hint or f"Nowing returned HTTP {status}.")
                async for event in iter_sse_events(response.aiter_lines()):
                    yield event
        except httpx.RequestError as exc:
            raise ToolError(
                f"Could not reach Nowing at {self._api_base}: {exc}. "
                "Confirm the backend is running and NOWING_BASE_URL is correct."
            ) from exc

    @staticmethod
    async def _extract_busy_detail(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = json.loads(await response.aread())
        except (json.JSONDecodeError, ValueError):
            return {"errorCode": "THREAD_BUSY", "message": response.text}
        if isinstance(payload, dict) and isinstance(payload.get("detail"), dict):
            return payload["detail"]
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _extract_detail_text(body: bytes) -> str | None:
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return body.decode("utf-8", "replace").strip() or None
        if isinstance(payload, dict):
            detail = payload.get("detail", payload)
            if isinstance(detail, dict):
                return detail.get("message") or str(detail)
            return str(detail)
        return str(payload)

    async def aclose(self) -> None:
        await self._http.aclose()

    @staticmethod
    def _parse_body(response: httpx.Response) -> Any:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    @classmethod
    def _explain_failure(cls, response: httpx.Response) -> str:
        """Turn an error response into one actionable sentence for the model."""
        detail = cls._extract_detail(response)
        hint = _FAILURE_HINTS.get(response.status_code)
        if detail and hint:
            return f"{hint} (server said: {detail})"
        if detail:
            return f"Nowing returned {response.status_code}: {detail}"
        return hint or f"Nowing returned HTTP {response.status_code}."

    @staticmethod
    def _extract_detail(response: httpx.Response) -> str | None:
        try:
            body = response.json()
        except ValueError:
            return response.text.strip() or None
        if isinstance(body, dict):
            detail = body.get("detail", body)
            if isinstance(detail, dict):
                return detail.get("message") or str(detail)
            return str(detail)
        return str(body)
