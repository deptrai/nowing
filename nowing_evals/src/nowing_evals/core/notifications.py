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


def _looks_like_url(url: str) -> bool:
    """Return True when ``url`` is safe to use as a clickable link."""

    return url.startswith(("http://", "https://")) and not any(c in url for c in " ()[]<>|")


def _md_code(value: Any) -> str:
    """Telegram/Markdown code span with a minimal backtick guard."""

    text = str(value).replace("`", "'")
    return f"`{text}`"


def _slack_text(
    suite: str,
    benchmark: str,
    run_timestamp: str,
    failing_thresholds: list[str],
    run_artifact_path: str,
    extra: dict[str, Any] | None = None,
) -> str:
    """Slack webhook text in Slack mrkdwn with a clickable artifact link."""

    lines = [
        f"Gate failed for {_md_code(suite)}/{_md_code(benchmark)} at {_md_code(run_timestamp)}.",
        "",
        "Failing thresholds:",
    ]
    for value in failing_thresholds:
        lines.append(f"• {_md_code(value)}")

    url = _artifact_url(run_artifact_path)
    if _looks_like_url(url):
        lines.append(f"\nArtifact: <{url}|View run artifact>")
    else:
        lines.append(f"\nArtifact: {_md_code(url)}")

    if extra:
        env = _md_code(extra.get("environment", "unknown"))
        build = _md_code(extra.get("build_id", "unknown"))
        lines.append(f"Env: {env} | Build: {build}")

    return "\n".join(lines)


def _slack_payload(
    suite: str,
    benchmark: str,
    run_timestamp: str,
    failing_thresholds: list[str],
    run_artifact_path: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "text": _slack_text(
            suite, benchmark, run_timestamp, failing_thresholds, run_artifact_path, extra
        )
    }


def _telegram_text(
    suite: str,
    benchmark: str,
    run_timestamp: str,
    failing_thresholds: list[str],
    run_artifact_path: str,
    extra: dict[str, Any] | None = None,
) -> str:
    """Telegram Markdown text with dynamic values protected in code spans.

    Wrapping threshold names and the artifact path in backticks prevents
    ``_ * [ ] ` `` characters from being interpreted as formatting, which
    causes Telegram's ``parse_mode="Markdown"`` to 400.
    """

    lines = [
        f"Gate failed for {_md_code(suite)}/{_md_code(benchmark)} at {_md_code(run_timestamp)}.",
        "",
        "Failing thresholds:",
    ]
    for value in failing_thresholds:
        lines.append(f"• {_md_code(value)}")

    url = _artifact_url(run_artifact_path)
    if _looks_like_url(url):
        lines.append(f"\n[View run artifact]({url})")
    else:
        lines.append(f"\nArtifact: {_md_code(url)}")

    if extra:
        env = _md_code(extra.get("environment", "unknown"))
        build = _md_code(extra.get("build_id", "unknown"))
        lines.append(f"Env: {env} | Build: {build}")

    return "\n".join(lines)


def _telegram_payload(
    suite: str,
    benchmark: str,
    run_timestamp: str,
    failing_thresholds: list[str],
    run_artifact_path: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "text": _telegram_text(
            suite, benchmark, run_timestamp, failing_thresholds, run_artifact_path, extra
        ),
        "parse_mode": "Markdown",
    }


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
    payload = _slack_payload(
        suite, benchmark, run_timestamp, failing_thresholds, run_artifact_path, extra
    )
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
    payload = _telegram_payload(
        suite, benchmark, run_timestamp, failing_thresholds, run_artifact_path, extra
    )
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    body = {
        "chat_id": chat_id,
        **payload,
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
        ok = (
            await notify_slack(
                slack_url,
                suite,
                benchmark,
                run_timestamp,
                failing_thresholds,
                run_artifact_path,
                extra,
            )
            or ok
        )
    if bot_token and chat_id:
        ok = (
            await notify_telegram(
                bot_token,
                chat_id,
                suite,
                benchmark,
                run_timestamp,
                failing_thresholds,
                run_artifact_path,
                extra,
            )
            or ok
        )
    return ok
