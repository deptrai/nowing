"""Config domain: core."""

from __future__ import annotations

import os
from typing import Any

from app.config._helpers import (
    _env_json,
    is_ffmpeg_installed,
)

# Check if ffmpeg is installed
if not is_ffmpeg_installed():
    allow_static_ffmpeg = (
        os.getenv("NOWING_ALLOW_STATIC_FFMPEG_DOWNLOAD", "TRUE").upper() == "TRUE"
    )
    if allow_static_ffmpeg:
        import static_ffmpeg

        # ffmpeg installed on first call to add_paths(), threadsafe.
        static_ffmpeg.add_paths()

    # check if ffmpeg is installed again
    if not is_ffmpeg_installed():
        raise ValueError(
            "FFmpeg is not installed on the system. Please install it to use the Nowing Podcaster."
        )

# Deployment Mode (self-hosted or cloud)
# self-hosted: Full access to local file system connectors (Obsidian, etc.)
# cloud: Only cloud-based connectors available
DEPLOYMENT_MODE = os.getenv("NOWING_DEPLOYMENT_MODE", "self-hosted")
# True only when the operator *explicitly* opted into self-hosted. Used by the
# presentation entitlement gate so a cloud SaaS that forgets to set the env var
# fails closed (applies the paywall) instead of silently bypassing it.
SELF_HOSTED_EXPLICIT = os.getenv("NOWING_DEPLOYMENT_MODE", "").lower() == "self-hosted"
ENABLE_DESKTOP_LOCAL_FILESYSTEM = (
    os.getenv("ENABLE_DESKTOP_LOCAL_FILESYSTEM", "FALSE").upper() == "TRUE"
)

# Optional plan-limit overrides.  Values must be a JSON object mapping
# plan tier -> {max_documents, max_members, max_runs, max_storage_bytes,
# run_period_hours}.  Database seeded defaults remain the source of truth
# unless overridden here.
WORKSPACE_PLAN_LIMITS: dict[str, dict[str, Any]] | None = _env_json(
    "WORKSPACE_PLAN_LIMITS"
)



__all__ = ["DEPLOYMENT_MODE", "ENABLE_DESKTOP_LOCAL_FILESYSTEM", "SELF_HOSTED_EXPLICIT", "WORKSPACE_PLAN_LIMITS"]
