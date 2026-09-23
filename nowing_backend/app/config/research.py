"""Config domain: research."""

from __future__ import annotations

import os

from app.config._helpers import (
    logger,
)

# Default research mode. "balanced" is the planned new default (SD6/PRD D3);
# "quality" is the old default and remains an explicit opt-in.
_default_mode = os.getenv("DEFAULT_RESEARCH_MODE", "balanced").strip().lower()
if _default_mode not in {"speed", "balanced", "quality", "auto"}:
    logger.warning(
        "Invalid DEFAULT_RESEARCH_MODE=%r; falling back to 'balanced'",
        _default_mode,
    )
    _default_mode = "balanced"
DEFAULT_RESEARCH_MODE = _default_mode
# NFR-9 State A vs State B for deep research in chat.
#
# State A (default, launch setting): DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED is
# False. Both the REST and agent paths force chainlens.research to async mode
# so the chat turn returns immediately and ChainLens runs in the background.
# This is the launch default because the GTM review shows ChainLens balanced
# p95 at 44.3s, which is above the 30s synchronous target.
#
# State B (opt-in): DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED is True. The REST
# and agent paths may run chainlens.research synchronously, blocking on
# ChainLens. Do not enable until a ratified baseline shows p95 <= 30s.
DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED = (
    os.getenv("DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED", "FALSE").upper() == "TRUE"
)



__all__ = ['DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED', 'DEFAULT_RESEARCH_MODE', '_default_mode']
