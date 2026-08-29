"""Config domain: agents."""

from __future__ import annotations

import os

from app.config._helpers import (
    _env_int,
)

# Agent chat public API surface (Epic 18)
# Default FALSE until the security review checklist is green.
AGENT_CHAT_PUBLIC_ENABLED = (
    os.getenv("AGENT_CHAT_PUBLIC_ENABLED", "false").strip().upper() == "TRUE"
)
AGENT_CHAT_RATE_LIMIT_RPM = _env_int("AGENT_CHAT_RATE_LIMIT_RPM", 30)
AGENT_CHAT_WORKSPACE_RATE_LIMIT_RPM = _env_int(
    "AGENT_CHAT_WORKSPACE_RATE_LIMIT_RPM", 100
)

# Agent cache (in-process LRU+TTL cache for built agents)
AGENT_CACHE_MAXSIZE = int(os.getenv("NOWING_AGENT_CACHE_MAXSIZE", "256"))
AGENT_CACHE_TTL_SECONDS = float(os.getenv("NOWING_AGENT_CACHE_TTL_SECONDS", "1800"))



__all__ = ['AGENT_CACHE_MAXSIZE', 'AGENT_CACHE_TTL_SECONDS', 'AGENT_CHAT_PUBLIC_ENABLED', 'AGENT_CHAT_RATE_LIMIT_RPM', 'AGENT_CHAT_WORKSPACE_RATE_LIMIT_RPM']
