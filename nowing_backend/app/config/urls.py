"""Config domain: urls."""

from __future__ import annotations

import os

from app.config.memory import NOWING_PUBLIC_URL

# Backend URL to override the http to https in the OAuth redirect URI
BACKEND_URL = (
    os.getenv("BACKEND_URL") or NOWING_PUBLIC_URL or "http://localhost:8000"
)

# Base URL for the public self-serve meeting booking page (Story 37.3 / AC-5).
# Falls back to the web frontend origin when unset.
MEETING_BOOKING_BASE_URL = os.getenv("MEETING_BOOKING_BASE_URL")

# Base URL for the multi-tenant mini-pitch portal host (Story 37.5 / AD-119).
# Served by the unified Next.js SSR route /pitch/[workspace_slug]/[lead_id] —
# per-lead Dokploy containers are prohibited, so this is only a URL prefix.
PITCH_PORTAL_BASE_URL = os.getenv("PITCH_PORTAL_BASE_URL")



__all__ = ['BACKEND_URL', 'MEETING_BOOKING_BASE_URL', 'PITCH_PORTAL_BASE_URL']
