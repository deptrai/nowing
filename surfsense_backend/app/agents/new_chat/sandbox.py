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

from daytona import CreateSandboxFromSnapshotParams, Daytona, DaytonaConfig, SandboxState
from deepagents.backends.protocol import ExecuteResponse
from langchain_daytona import DaytonaSandbox

logger = logging.getLogger(__name__)


class _TimeoutAwareSandbox(DaytonaSandbox):
    """DaytonaSandbox subclass that accepts the per-command *timeout*
    kwarg required by the deepagents middleware.

    The upstream ``langchain-daytona`` ``execute()`` ignores timeout,
    so deepagents raises *"This sandbox backend does not support
    per-command timeout overrides"* on every first call.  This thin
    wrapper forwards the parameter to the Daytona SDK.
    """

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        t = timeout if timeout is not None else self._timeout
        result = self._sandbox.process.exec(command, timeout=t)
        return ExecuteResponse(
            output=result.result,
            exit_code=result.exit_code,
            truncated=False,
        )

    async def aexecute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:  # type: ignore[override]
        return await asyncio.to_thread(self.execute, command, timeout=timeout)

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


def _find_or_create(thread_id: str) -> _TimeoutAwareSandbox:
    """Find an existing sandbox for *thread_id*, or create a new one.

    If an existing sandbox is found but is stopped/archived, it will be
    restarted automatically before returning.
    """
    client = _get_client()
    labels = {THREAD_LABEL_KEY: thread_id}

    try:
        sandbox = client.find_one(labels=labels)
        logger.info(
            "Found existing sandbox %s (state=%s)", sandbox.id, sandbox.state
        )

        if sandbox.state in (
            SandboxState.STOPPED,
            SandboxState.STOPPING,
            SandboxState.ARCHIVED,
        ):
            logger.info("Starting stopped sandbox %s …", sandbox.id)
            sandbox.start(timeout=60)
            logger.info("Sandbox %s is now started", sandbox.id)
        elif sandbox.state in (SandboxState.ERROR, SandboxState.BUILD_FAILED, SandboxState.DESTROYED):
            logger.warning(
                "Sandbox %s in unrecoverable state %s — creating a new one",
                sandbox.id,
                sandbox.state,
            )
            sandbox = client.create(
                CreateSandboxFromSnapshotParams(language="python", labels=labels)
            )
            logger.info("Created replacement sandbox: %s", sandbox.id)
        elif sandbox.state != SandboxState.STARTED:
            sandbox.wait_for_sandbox_start(timeout=60)

    except Exception:
        logger.info("No existing sandbox for thread %s — creating one", thread_id)
        sandbox = client.create(
            CreateSandboxFromSnapshotParams(language="python", labels=labels)
        )
        logger.info("Created new sandbox: %s", sandbox.id)

    return _TimeoutAwareSandbox(sandbox=sandbox)


async def get_or_create_sandbox(thread_id: int | str) -> _TimeoutAwareSandbox:
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
