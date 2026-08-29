"""Config domain: urls."""

from __future__ import annotations

import os

from app.config.memory import NOWING_PUBLIC_URL

# Backend URL to override the http to https in the OAuth redirect URI
BACKEND_URL = (
    os.getenv("BACKEND_URL") or NOWING_PUBLIC_URL or "http://localhost:8000"
)



__all__ = ['BACKEND_URL']
