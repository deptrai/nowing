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


def _artifact_url(run_artifact_path: str, *, prefix: str = "") -> str:
    """Best-effort public/CI link to the artifact.

    ponytail: expects CI to set ``NOWING_EVALS_ARTIFACT_URL_PREFIX``. Without
    it the notification falls back to a local path.
    """
    if not prefix:
        return run_artifact_path
    prefix = prefix.rstrip("/")
    run_path = run_artifact_path.lstrip("/")
    return f"{prefix}/{run_path}"


def _looks_like_url(url: str) -> bool:
    """Return True when ``url`` is safe to use as a clickable link."""

    return url.startswith(("http://", "https://"))


def _md_code(value: Any) -> str:
    """Telegram/Markdown code span with a minimal backtick guard."""

    text = str(value)
    # Backticks become single quotes so they cannot break the code span.
    text = text.replace("`", "'")
    return f"`{text}`"


def _slack_text(
    suite: str,
    benchmark: str,
    run_timestamp: str,
    failing_thresholds: list[str],
    run_artifact_path: str,
    extra: dict[str, Any] | None = None,
    *,
    prefix: str = "",
) -> str:
    """Slack webhook text in Slack mrkdwn with a clickable artifact link."""

    lines = [
        f"Gate failed for {_md_code(suite)}/{_md_code(benchmark)} at {_md_code(run_timestamp)}.",
        "",
        "Failing thresholds:",
    ]
    for value in failing_thresholds:
        lines.append(f"• {_md_code(value)}")

    url = _artifact_url(
        run_artifact_path,
        prefix=prefix,
    )
    if _looks_like_url(url):
        lines.append(f"\nArtifact: <{url}|View run artifact>")
    else:
        lines.append(f"\nArtifact: {_md_code(url)}")

    if extra:
        env = _md_code(extra.get("environment") or "unknown")
        build = _md_code(extra.get("build_id") or "unknown")
        lines.append(f"Env: {env} | Build: {build}")

    return "\n".join(lines)


def _slack_payload(
    suite: str,
    benchmark: str,
    run_timestamp: str,
    failing_thresholds: list[str],
    run_artifact_path: str,
    extra: dict[str, Any] | None = None,
    *,
    prefix: str = "",
) -> dict[str, Any]:
    return {
        "text": _slack_text(
            suite,
            benchmark,
            run_timestamp,
            failing_thresholds,
            run_artifact_path,
            extra,
            prefix=prefix,
        )
    }


def _telegram_text(
    suite: str,
    benchmark: str,
    run_timestamp: str,
    failing_thresholds: list[str],
    run_artifact_path: str,
    extra: dict[str, Any] | None = None,
    *,
    prefix: str = "",
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

    url = _artifact_url(
        run_artifact_path,
        prefix=prefix,
    )
    if _looks_like_url(url):
        # Telegram Markdown v1 has no inline escape for parentheses, so
        # percent-encode them so a path like ``.../file(1).json`` does not
        # break the link syntax.
        safe_url = url.replace("(", "%28").replace(")", "%29")
        lines.append(f"\n[View run artifact]({safe_url})")
    else:
        lines.append(f"\nArtifact: {_md_code(url)}")

    if extra:
        env = _md_code(extra.get("environment") or "unknown")
        build = _md_code(extra.get("build_id") or "unknown")
        lines.append(f"Env: {env} | Build: {build}")

    return "\n".join(lines)


def _telegram_payload(
    suite: str,
    benchmark: str,
    run_timestamp: str,
    failing_thresholds: list[str],
    run_artifact_path: str,
    extra: dict[str, Any] | None = None,
    *,
    prefix: str = "",
) -> dict[str, Any]:
    return {
        "text": _telegram_text(
            suite,
            benchmark,
            run_timestamp,
            failing_thresholds,
            run_artifact_path,
            extra,
            prefix=prefix,
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
    *,
    prefix: str = "",
) -> bool:
    """Post a benchmark gate failure to a Slack webhook."""
    if not slack_webhook_url:
        return False
    payload = _slack_payload(
        suite,
        benchmark,
        run_timestamp,
        failing_thresholds,
        run_artifact_path,
        extra,
        prefix=prefix,
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(slack_webhook_url, json=payload)
            response.raise_for_status()
        return True
    except httpx.HTTPStatusError as exc:
        body = exc.response.text if exc.response is not None else ""
        logger.warning("Failed to send Slack notification: %s (body: %s)", exc, body)
        return False
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
    *,
    prefix: str = "",
) -> bool:
    """Post a benchmark gate failure to a Telegram chat."""
    if not bot_token or not chat_id:
        return False
    payload = _telegram_payload(
        suite,
        benchmark,
        run_timestamp,
        failing_thresholds,
        run_artifact_path,
        extra,
        prefix=prefix,
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
    except httpx.HTTPStatusError as exc:
        body = exc.response.text if exc.response is not None else ""
        logger.warning("Failed to send Telegram notification: %s (body: %s)", exc, body)
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to send Telegram notification: %s", exc)
        return False


_UNSET: Any = object()


async def notify_gate_failure(
    suite: str,
    benchmark: str,
    run_timestamp: str,
    failing_thresholds: list[str],
    run_artifact_path: str,
    extra: dict[str, Any] | None = None,
    *,
    slack_url: str | None | Any = _UNSET,
    telegram_bot_token: str | None | Any = _UNSET,
    telegram_chat_id: str | None | Any = _UNSET,
    prefix: str | Any = _UNSET,
) -> bool:
    """Send a gate-failure notification to any configured channel.

    When credential arguments are omitted (not passed at all), the function
    falls back to the matching ``SLACK_WEBHOOK_URL``, ``TELEGRAM_BOT_TOKEN``,
    ``TELEGRAM_CHAT_ID`` and ``NOWING_EVALS_ARTIFACT_URL_PREFIX`` environment
    variables for backwards compatibility with the CI workflow. Passing
    ``None`` explicitly disables the corresponding channel / prefix.
    """
    if slack_url is _UNSET:
        slack_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if telegram_bot_token is _UNSET:
        telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if telegram_chat_id is _UNSET:
        telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if prefix is _UNSET:
        prefix = os.environ.get("NOWING_EVALS_ARTIFACT_URL_PREFIX", "")

    slack_url = slack_url or ""
    bot_token = telegram_bot_token or ""
    chat_id = telegram_chat_id or ""
    prefix = prefix or ""

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
                prefix=prefix,
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
                prefix=prefix,
            )
            or ok
        )
    return ok
