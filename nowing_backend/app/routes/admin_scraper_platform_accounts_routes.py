"""Admin routes for managing scraper platform accounts and credentials."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
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
        updated_at=account.updated_at,
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
