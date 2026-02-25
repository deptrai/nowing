"""
Microsandbox provider for SurfSense deep agent.

Manages the lifecycle of sandboxed code execution environments.
Each conversation thread gets its own isolated sandbox instance.
"""

import logging
import os

from deepagents_microsandbox import MicrosandboxBackend, MicrosandboxProvider

logger = logging.getLogger(__name__)

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
