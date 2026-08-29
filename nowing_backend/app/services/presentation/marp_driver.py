"""Marp Markdown writer and optional HTML renderer (Story 27.2a)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _safe_md_inline(text: Any) -> str:
    """Flatten newlines and neutralize Marp slide separators in inline text."""
    return str(text).replace("\r", " ").replace("\n", " ").replace("---", " - ").strip()


def _safe_html_comment(text: Any) -> str:
    """Prevent notes from terminating an HTML comment early."""
    return str(text).replace("--", "- -").replace(">", "")


def build_marp_markdown(deck_spec: dict[str, Any]) -> str:
    """Build Marp-compatible Markdown from a DeckSpec dict."""
    title = _safe_md_inline(deck_spec.get("title", "Untitled"))
    lines = [
        "---",
        "marp: true",
        "size: 16:9",
        'theme: "default"',
        'class: "invert"',
        "paginate: true",
        "---",
        "",
        f"# {title}",
        "",
    ]
    if description := deck_spec.get("description"):
        lines.append(_safe_md_inline(description))
        lines.append("")

    for slide in deck_spec.get("slides", []):
        lines.append("---")
        lines.append("")
        lines.append(f"## {_safe_md_inline(slide.get('title', ''))}")
        lines.append("")
        for bullet in slide.get("bullets", []):
            lines.append(f"- {_safe_md_inline(bullet)}")
        lines.append("")

        # Optional chart rendered as a simple markdown table (Marp does not render
        # inline charts natively; the table is the lightweight, dependency-free MVP).
        chart = slide.get("chart")
        if chart and chart.get("series"):
            categories = [_safe_md_inline(c) for c in chart.get("categories", [])]
            values: list[str] = []
            for v in chart.get("series", []):
                if v is None:
                    continue
                values.append(_safe_md_inline(v))
            n = min(len(categories), len(values))
            categories, values = categories[:n], values[:n]
            if categories and values:
                lines.append("| " + " | ".join(categories) + " |")
                lines.append("| " + " | ".join(["---"] * len(categories)) + " |")
                lines.append("| " + " | ".join(values) + " |")
                lines.append("")

        if notes := slide.get("notes"):
            lines.append(f"<!-- {_safe_html_comment(notes)} -->")
            lines.append("")

    return "\n".join(lines)


async def render_marp_html(
    md_path: Path,
    output_html_path: Path,
    timeout: float = 30.0,
) -> tuple[bool, str | None]:
    """Render a Marp Markdown file to HTML if the ``marp`` binary is on PATH.

    Returns ``(ok, error_reason)``.
    """
    if not md_path.is_file():
        logger.warning("Marp markdown input does not exist: %s", md_path)
        return False, "input_missing"

    output_dir = output_html_path.parent
    if output_dir and not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    binary = shutil.which("marp")
    if not binary:
        return False, "dependency_missing"

    proc: asyncio.subprocess.Process | None = None
    try:
        proc = await asyncio.create_subprocess_exec(
            binary,
            str(md_path.resolve()),
            "--output",
            str(output_html_path.resolve()),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except TimeoutError:
            proc.kill()
            with contextlib.suppress(Exception):
                await proc.communicate()
            return False, "marp_timeout"

        if proc.returncode != 0:
            logger.warning(
                "marp render failed: %s",
                (stderr or b"").decode("utf-8", errors="replace")[:500],
            )
            return False, "marp_render_failed"

        return True, None
    except Exception as e:
        logger.warning("marp render exception: %s", e)
        if proc is not None and proc.returncode is None:
            proc.kill()
            with contextlib.suppress(Exception):
                await proc.communicate()
        return False, "marp_render_exception"
