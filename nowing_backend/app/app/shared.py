"""Shared app helpers that both factory and lifespan need."""

import functools
import logging
import os
from pathlib import Path

from fastapi import HTTPException, status

from app.config import config


def registration_allowed() -> None:
    """Master auth kill switch keyed on the REGISTRATION_ENABLED env var."""
    if not config.REGISTRATION_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Registration is disabled"
        )


@functools.lru_cache(maxsize=1)
def _backend_build_id() -> str:
    """Resolve the running backend's git commit for build-label verification."""
    build_id = os.environ.get("NOWING_GIT_SHA")
    if build_id:
        return build_id.strip()

    repo_root = Path(__file__).resolve().parents[2]
    git_dir = repo_root / ".git"
    head = git_dir / "HEAD"
    try:
        ref = head.read_text().strip()
    except (OSError, UnicodeDecodeError):
        return "unknown"

    if ref.startswith("ref:"):
        ref_path = git_dir / ref[4:].strip()
        try:
            build_id = ref_path.read_text().strip()
        except (OSError, UnicodeDecodeError):
            return "unknown"
        return build_id

    return ref


def _warn_if_build_id_unknown() -> None:
    """Warn at startup if /health would report an unlabeled build."""
    if _backend_build_id() == "unknown":
        logging.getLogger(__name__).warning(
            "[startup] NOWING_GIT_SHA is not set and no .git metadata is "
            "available; /health will report build_id='unknown'. Set "
            "NOWING_GIT_SHA in the container build / deployment environment."
        )
