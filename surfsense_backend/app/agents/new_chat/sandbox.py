"""
Microsandbox provider for SurfSense deep agent.

Manages the lifecycle of sandboxed code execution environments.
Each conversation thread gets its own isolated sandbox instance.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compatibility shim
# ---------------------------------------------------------------------------
# deepagents-microsandbox imports SandboxInfo, SandboxListResponse, and
# SandboxProvider from deepagents.backends.sandbox.  These types were added
# in a fork and have not yet landed in the official deepagents package.
# We inject minimal stubs so the import succeeds without patching the venv.
# ---------------------------------------------------------------------------

def _ensure_sandbox_provider_types() -> None:
    """Inject missing SandboxProvider / SandboxInfo types if absent."""
    import importlib
    sandbox_mod = importlib.import_module("deepagents.backends.sandbox")

    if hasattr(sandbox_mod, "SandboxProvider"):
        return  # Already present – nothing to do.

    from abc import ABC, abstractmethod
    from dataclasses import dataclass, field
    from typing import Any, Generic, TypeVar

    _M = TypeVar("_M")

    @dataclass
    class SandboxInfo(Generic[_M]):
        sandbox_id: str
        metadata: _M = field(default_factory=dict)  # type: ignore[assignment]

    @dataclass
    class SandboxListResponse(Generic[_M]):
        items: list[SandboxInfo[_M]] = field(default_factory=list)
        cursor: str | None = None

    class SandboxProvider(ABC, Generic[_M]):
        @abstractmethod
        def list(self, *, cursor: str | None = None, **kwargs: Any) -> SandboxListResponse[_M]: ...

        @abstractmethod
        async def alist(self, *, cursor: str | None = None, **kwargs: Any) -> SandboxListResponse[_M]: ...

        @abstractmethod
        def get_or_create(self, *, sandbox_id: str | None = None, **kwargs: Any) -> Any: ...

        @abstractmethod
        async def aget_or_create(self, *, sandbox_id: str | None = None, **kwargs: Any) -> Any: ...

        @abstractmethod
        def delete(self, *, sandbox_id: str, **kwargs: Any) -> None: ...

        @abstractmethod
        async def adelete(self, *, sandbox_id: str, **kwargs: Any) -> None: ...

    sandbox_mod.SandboxInfo = SandboxInfo  # type: ignore[attr-defined]
    sandbox_mod.SandboxListResponse = SandboxListResponse  # type: ignore[attr-defined]
    sandbox_mod.SandboxProvider = SandboxProvider  # type: ignore[attr-defined]


_ensure_sandbox_provider_types()

from deepagents_microsandbox import MicrosandboxBackend, MicrosandboxProvider  # noqa: E402

_provider: MicrosandboxProvider | None = None


def is_sandbox_enabled() -> bool:
    return os.environ.get("MICROSANDBOX_ENABLED", "FALSE").upper() == "TRUE"


def _get_provider() -> MicrosandboxProvider:
    global _provider
    if _provider is None:
        server_url = os.environ.get(
            "MICROSANDBOX_SERVER_URL", "http://127.0.0.1:5555"
        )
        api_key = os.environ.get("MICROSANDBOX_API_KEY")
        _provider = MicrosandboxProvider(
            server_url=server_url,
            api_key=api_key,
            namespace="surfsense",
        )
    return _provider


async def get_or_create_sandbox(thread_id: int | str) -> MicrosandboxBackend:
    """Get or create a sandbox for a conversation thread.

    Uses the thread_id as the sandbox name so the same sandbox persists
    across multiple messages within the same conversation.

    Args:
        thread_id: The conversation thread identifier.

    Returns:
        MicrosandboxBackend connected to the sandbox.
    """
    provider = _get_provider()
    sandbox_name = f"thread-{thread_id}"
    sandbox = await provider.aget_or_create(
        sandbox_id=sandbox_name,
        timeout=120,
        memory=512,
        cpus=1.0,
    )
    logger.info("Sandbox ready: %s", sandbox.id)
    return sandbox


async def delete_sandbox(thread_id: int | str) -> None:
    """Delete the sandbox for a conversation thread."""
    provider = _get_provider()
    sandbox_name = f"thread-{thread_id}"
    try:
        await provider.adelete(sandbox_id=sandbox_name)
        logger.info("Sandbox deleted: surfsense/%s", sandbox_name)
    except Exception:
        logger.warning("Failed to delete sandbox surfsense/%s", sandbox_name, exc_info=True)
