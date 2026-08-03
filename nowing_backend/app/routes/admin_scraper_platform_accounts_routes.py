"""Admin routes for managing scraper platform accounts and credentials."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import ScraperPlatformAccount, get_async_session
from app.schemas.scraper_platform_account import (
    ScraperPlatformAccountCreate,
    ScraperPlatformAccountRead,
    ScraperPlatformAccountUpdate,
)
from app.services.scraper_platform_account_service import (
    ScraperPlatformAccountService,
    decrypt_credentials,
)
from app.users import require_superuser

router = APIRouter(prefix="/admin/scraper-platform-accounts")
logger = logging.getLogger(__name__)



def _to_read(
    account: ScraperPlatformAccount, include_credentials: bool = False
) -> ScraperPlatformAccountRead:
    credentials = None
    if include_credentials:
        try:
            credentials = decrypt_credentials(account.encrypted_credentials)
        except Exception:
            logger.exception("Failed to decrypt credentials for account %s", account.id)
    return ScraperPlatformAccountRead(
        id=account.id,
        platform=account.platform,
        label=account.label,
        is_enabled=account.is_enabled,
        is_default=account.is_default,
        credentials=credentials,
        created_at=account.created_at,
        updated_at=getattr(account, "updated_at", None) or account.created_at,
    )


@router.get("", response_model=list[ScraperPlatformAccountRead])
async def list_scraper_platform_accounts(
    platform: str | None = None,
    session: AsyncSession = Depends(get_async_session),
    _auth: AuthContext = Depends(require_superuser),
) -> list[ScraperPlatformAccount]:
    svc = ScraperPlatformAccountService(session)
    accounts = await svc.list(platform=platform)
    return [_to_read(a) for a in accounts]


@router.post("", response_model=ScraperPlatformAccountRead, status_code=status.HTTP_201_CREATED)
async def create_scraper_platform_account(
    data: ScraperPlatformAccountCreate,
    session: AsyncSession = Depends(get_async_session),
    _auth: AuthContext = Depends(require_superuser),
) -> ScraperPlatformAccount:
    svc = ScraperPlatformAccountService(session)
    account = await svc.create(
        platform=data.platform,
        label=data.label,
        is_enabled=data.is_enabled,
        is_default=data.is_default,
        credentials=data.credentials.model_dump(exclude_unset=True) if data.credentials else None,
    )
    return _to_read(account, include_credentials=True)


@router.get("/{account_id}", response_model=ScraperPlatformAccountRead)
async def get_scraper_platform_account(
    account_id: int,
    session: AsyncSession = Depends(get_async_session),
    _auth: AuthContext = Depends(require_superuser),
) -> ScraperPlatformAccount:
    svc = ScraperPlatformAccountService(session)
    account = await svc.get(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return _to_read(account, include_credentials=True)


@router.patch("/{account_id}", response_model=ScraperPlatformAccountRead)
async def update_scraper_platform_account(
    account_id: int,
    data: ScraperPlatformAccountUpdate,
    session: AsyncSession = Depends(get_async_session),
    _auth: AuthContext = Depends(require_superuser),
) -> ScraperPlatformAccount:
    svc = ScraperPlatformAccountService(session)
    account = await svc.get(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    updates = data.model_dump(exclude_unset=True)
    if data.credentials is not None:
        updates["credentials"] = data.credentials.model_dump(exclude_unset=True)
    updated = await svc.update(account, updates)
    return _to_read(updated, include_credentials=True)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scraper_platform_account(
    account_id: int,
    session: AsyncSession = Depends(get_async_session),
    _auth: AuthContext = Depends(require_superuser),
) -> None:
    svc = ScraperPlatformAccountService(session)
    account = await svc.get(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    await svc.delete(account)


class CaptureSessionResponse(BaseModel):
    message: str
    platform: str
    capture_id: str


def _capture_script_path(platform: str) -> Path:
    """Locate the platform-specific capture script next to the backend package."""
    # app/routes/admin_scraper_platform_accounts_routes.py -> nowing_backend
    root = Path(__file__).resolve().parents[2]
    if platform == "batdongsan":
        return root / "scripts" / "capture_batdongsan_session.py"
    return root / "scripts" / f"capture_{platform}_session.py"


@router.post("/{platform}/capture-session", status_code=status.HTTP_202_ACCEPTED)
async def capture_scraper_platform_session(
    platform: str,
    _auth: AuthContext = Depends(require_superuser),
) -> CaptureSessionResponse:
    """Open a headed browser so an admin can log in and refresh auth cookies.

    The capture runs in a background process so the HTTP request returns
    immediately. Once the admin completes login, the process writes the
    captured cookies to the default `ScraperPlatformAccount` for the
    platform.  Only supported for platforms that ship a capture script.
    """
    script = _capture_script_path(platform)
    if not script.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session capture is not supported for platform '{platform}'",
        )

    # Ensure the backend package is importable by the script.
    root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{root}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(root)
    )

    capture_id = str(uuid.uuid4())[:8]
    cdp_url = os.getenv("BATDONGSAN_CAPTURE_CDP_URL")
    try:
        # Start Playwright capture in the background; it may run for several
        # minutes while the admin completes OAuth. If BATDONGSAN_CAPTURE_CDP_URL
        # is set, the script will attach to the admin's existing Chrome instead
        # of launching its own automated browser (which many OAuth providers block).
        cmd = [
            sys.executable,
            str(script),
            "--auto",
            "--timeout",
            "300",
            "--platform",
            platform,
        ]
        if cdp_url:
            cmd.extend(["--cdp", cdp_url])
        subprocess.Popen(
            cmd,
            cwd=str(root),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not start capture process: {exc}",
        ) from exc

    return CaptureSessionResponse(
        message="A browser window has opened. Please log in; cookies will be saved automatically.",
        platform=platform,
        capture_id=capture_id,
    )
