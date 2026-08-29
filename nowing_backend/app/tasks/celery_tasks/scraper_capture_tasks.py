"""Celery tasks for scraper platform session capture.

These tasks replace the synchronous ``subprocess.Popen`` call in the admin
route so capture runs off the request thread, with timeout and process
cleanup handled by the worker.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sys
import uuid
from pathlib import Path

from app.celery_app import celery_app
from app.tasks.celery_tasks import run_async_celery_task

logger = logging.getLogger(__name__)

# Capture is only supported for a fixed set of platforms. The script name is
# derived deterministically from the platform slug.
_ALLOWED_PLATFORMS = {"batdongsan"}


def _capture_script_path(platform: str) -> Path:
    """Locate the platform-specific capture script next to the backend package."""
    root = Path(__file__).resolve().parents[3]
    return root / "scripts" / f"capture_{platform}_session.py"


@celery_app.task(name="scraper.capture_session", bind=True, max_retries=0)
def capture_scraper_session_task(self, platform: str, cdp_url: str | None = None) -> dict:
    """Launch a headed browser capture for *platform* in a sandboxed subprocess.

    The task runs the platform-specific capture script with a bounded timeout
    and logs the result. It never uses ``shell=True`` and only accepts scripts
    from the pre-defined list.
    """
    return run_async_celery_task(
        lambda: _capture_session_impl(platform, cdp_url)
    )


async def _capture_session_impl(platform: str, cdp_url: str | None = None) -> dict:
    if platform not in _ALLOWED_PLATFORMS:
        raise ValueError(f"Unsupported capture platform: {platform}")

    script = _capture_script_path(platform)
    if not script.exists():
        raise FileNotFoundError(f"Capture script not found: {script}")

    root = script.parents[1]
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{root}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(root)
    )

    capture_id = str(uuid.uuid4())[:8]
    cmd = [
        sys.executable,
        str(script),
        "--auto",
        "--timeout",
        "300",
        "--platform",
        platform,
    ]
    if cdp_url:
        # Validate that the CDP URL looks like a WebSocket URL to prevent
        # command injection through an environment variable.
        if not cdp_url.startswith("ws://") and not cdp_url.startswith("wss://"):
            raise ValueError(f"Invalid CDP URL scheme: {cdp_url[:20]!r}")
        cmd.extend(["--cdp", cdp_url])

    logger.info(
        "[scraper-capture:%s] starting capture for platform=%s script=%s",
        capture_id,
        platform,
        script,
    )

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(root),
            env=env,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            close_fds=True,
        )
    except OSError as exc:
        logger.error(
            "[scraper-capture:%s] failed to start process: %s",
            capture_id,
            exc,
        )
        raise

    try:
        returncode = await asyncio.wait_for(proc.wait(), timeout=360)
    except TimeoutError:
        logger.warning(
            "[scraper-capture:%s] capture timed out, killing process",
            capture_id,
        )
        with contextlib.suppress(Exception):
            proc.kill()
        return {
            "capture_id": capture_id,
            "platform": platform,
            "status": "timeout",
            "returncode": None,
        }

    status = "success" if returncode == 0 else "failed"
    logger.info(
        "[scraper-capture:%s] finished status=%s returncode=%s",
        capture_id,
        status,
        returncode,
    )
    return {
        "capture_id": capture_id,
        "platform": platform,
        "status": status,
        "returncode": returncode,
    }
