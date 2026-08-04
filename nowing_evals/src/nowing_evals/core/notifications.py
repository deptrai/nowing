"""Lightweight notifications for benchmark gates.

Send a concise run summary to Slack (via webhook) or Telegram (via bot API).
This is intentionally dependency-free beyond ``httpx`` which the eval harness
already requires.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _artifact_url(run_artifact_path: str) -> str:
    """Best-effort public/CI link to the artifact.

    ponytail: expects CI to set ``NOWING_EVALS_ARTIFACT_URL_PREFIX``. Without
    it the notification falls back to a local path.
    """
    prefix = os.environ.get("NOWING_EVALS_ARTIFACT_URL_PREFIX", "")
    return f"{prefix}{run_artifact_path}" if prefix else run_artifact_path


def _payload(
    suite: str,
    benchmark: str,
    run_timestamp: str,
    failing_thresholds: list[str],
    run_artifact_path: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    text = (
        f"Gate failed for *{suite}/{benchmark}* at `{run_timestamp}`.\n"
        f"Failing thresholds:\n" + "\n".join(f"- {v}" for v in failing_thresholds)
        + f"\nArtifact: {_artifact_url(run_artifact_path)}"
    )
    if extra:
        text += f"\nEnv: {extra.get('environment', 'unknown')} | Build: {extra.get('build_id', 'unknown')}"
    return {"text": text}


async def notify_slack(
    slack_webhook_url: str,
    suite: str,
    benchmark: str,
    run_timestamp: str,
    failing_thresholds: list[str],
    run_artifact_path: str,
    extra: dict[str, Any] | None = None,
) -> bool:
    """Post a benchmark gate failure to a Slack webhook."""
    if not slack_webhook_url:
        return False
    payload = _payload(suite, benchmark, run_timestamp, failing_thresholds, run_artifact_path, extra)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(slack_webhook_url, json=payload)
            response.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to send Slack notification: %s", exc)
        return False


async def notify_telegram(
    bot_token: str,
    chat_id: str,
    suite: str,
    benchmark: str,
    run_timestamp: str,
    failing_thresholds: list[str],
    run_artifact_path: str,
    extra: dict[str, Any] | None = None,
) -> bool:
    """Post a benchmark gate failure to a Telegram chat."""
    if not bot_token or not chat_id:
        return False
    payload = _payload(suite, benchmark, run_timestamp, failing_thresholds, run_artifact_path, extra)
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    body = {
        "chat_id": chat_id,
        "text": payload["text"],
        "parse_mode": "Markdown",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=body)
            response.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to send Telegram notification: %s", exc)
        return False


async def notify_gate_failure(
    suite: str,
    benchmark: str,
    run_timestamp: str,
    failing_thresholds: list[str],
    run_artifact_path: str,
    extra: dict[str, Any] | None = None,
) -> bool:
    """Send a gate-failure notification to any configured channel."""
    slack_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    ok = False
    if slack_url:
        ok = await notify_slack(
            slack_url, suite, benchmark, run_timestamp, failing_thresholds, run_artifact_path, extra
        ) or ok
    if bot_token and chat_id:
        ok = await notify_telegram(
            bot_token, chat_id, suite, benchmark, run_timestamp, failing_thresholds, run_artifact_path, extra
        ) or ok
    return ok
