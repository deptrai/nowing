# Nowing proprietary crawler engine.
#
# This module is part of the ``app.proprietary`` package and is licensed
# SEPARATELY from the Apache-2.0 project root. See ``app/proprietary/LICENSE``.
# Do not relicense or redistribute this file under Apache-2.0.
"""Browser screenshot helpers for anti-bot/CAPTCHA evidence capture (Story 10.5)."""

from __future__ import annotations

import logging
from typing import Any

from app.utils.crawl import BlockType, classify_block

logger = logging.getLogger(__name__)


def maybe_capture_screenshot(
    page: Any, *, status: int | None, html: str | None
) -> bytes | None:
    """Capture a PNG screenshot of ``page`` if it looks like an anti-bot block.

    The decision uses the same ``classify_block`` logic as the rest of the
    crawler so the screenshot is only taken when there is a CAPTCHA or
    anti-bot interstitial to show an operator. Returns ``None`` for OK pages
    or if capture fails.
    """
    block = classify_block(status, html)
    if block in (BlockType.OK, BlockType.EMPTY):
        return None

    try:
        # Playwright / patchright page.screenshot supports ``type="png"``.
        return page.screenshot(type="png")
    except Exception as exc:
        logger.warning("[webcrawler] screenshot capture failed: %s", exc)
        return None
