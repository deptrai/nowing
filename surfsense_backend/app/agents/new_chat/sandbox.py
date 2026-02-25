"""
Daytona sandbox provider for SurfSense deep agent.

Manages the lifecycle of sandboxed code execution environments.
Each conversation thread gets its own isolated sandbox instance
via the Daytona cloud API, identified by labels.
"""

from __future__ import annotations

import asyncio
import logging
import os

from daytona import CreateSandboxFromSnapshotParams, Daytona, DaytonaConfig
from langchain_daytona import DaytonaSandbox

logger = logging.getLogger(__name__)

_daytona_client: Daytona | None = None
THREAD_LABEL_KEY = "surfsense_thread"


def is_sandbox_enabled() -> bool:
    return os.environ.get("DAYTONA_SANDBOX_ENABLED", "FALSE").upper() == "TRUE"


def _get_client() -> Daytona:
    global _daytona_client
    if _daytona_client is None:
        config = DaytonaConfig(
            api_key=os.environ.get("DAYTONA_API_KEY", ""),
            api_url=os.environ.get("DAYTONA_API_URL", "https://app.daytona.io/api"),
            target=os.environ.get("DAYTONA_TARGET", "us"),
        )
        _daytona_client = Daytona(config)
    return _daytona_client


def _find_or_create(thread_id: str) -> DaytonaSandbox:
    """Find an existing sandbox for *thread_id*, or create a new one."""
    client = _get_client()
    labels = {THREAD_LABEL_KEY: thread_id}

    try:
        sandbox = client.find_one(labels=labels)
        logger.info("Reusing existing sandbox: %s", sandbox.id)
    except Exception:
        sandbox = client.create(
            CreateSandboxFromSnapshotParams(language="python", labels=labels)
        )
        logger.info("Created new sandbox: %s", sandbox.id)

    return DaytonaSandbox(sandbox=sandbox)


async def get_or_create_sandbox(thread_id: int | str) -> DaytonaSandbox:
    """Get or create a sandbox for a conversation thread.

    Uses the thread_id as a label so the same sandbox persists
    across multiple messages within the same conversation.

    Args:
        thread_id: The conversation thread identifier.

    Returns:
        DaytonaSandbox connected to the sandbox.
    """
    return await asyncio.to_thread(_find_or_create, str(thread_id))


async def delete_sandbox(thread_id: int | str) -> None:
    """Delete the sandbox for a conversation thread."""

    def _delete() -> None:
        client = _get_client()
        labels = {THREAD_LABEL_KEY: str(thread_id)}
        try:
            sandbox = client.find_one(labels=labels)
            client.delete(sandbox)
            logger.info("Sandbox deleted: %s", sandbox.id)
        except Exception:
            logger.warning(
                "Failed to delete sandbox for thread %s",
                thread_id,
                exc_info=True,
            )

    await asyncio.to_thread(_delete)
