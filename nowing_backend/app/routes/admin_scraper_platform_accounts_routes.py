"""Admin routes for managing scraper platform accounts and credentials."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import ScraperPlatformAccount, get_async_session
from app.schemas.scraper_platform_account import (
    ScraperPlatformAccountCreate,
    ScraperPlatformAccountRead,
    ScraperPlatformAccountUpdate,
    TelegramAuthResponse,
    TelegramRequestOtpRequest,
    TelegramVerify2FaRequest,
    TelegramVerifyOtpRequest,
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


@router.post(
    "", response_model=ScraperPlatformAccountRead, status_code=status.HTTP_201_CREATED
)
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
        credentials=data.credentials.model_dump(exclude_unset=True)
        if data.credentials
        else None,
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


# ---------------------------------------------------------------------------
# Telegram MTProto Userbot Onboarding Flow (Story 22.2 / AC-1)
# ---------------------------------------------------------------------------


async def telethon_request_login_code(
    phone: str,
    api_id: int,
    api_hash: str,
    proxy_url: str | None = None,
    label: str | None = None,
    redis_client: Any = None,
) -> dict[str, Any]:
    """Send Telegram login OTP code and cache session string in Redis (TTL=300s)."""
    import json

    from telethon import TelegramClient
    from telethon.sessions import StringSession

    from app.proprietary.platforms.telegram.client import parse_proxy_url
    from app.redis_client import get_redis_client

    proxy_config = parse_proxy_url(proxy_url) if proxy_url else None
    client = TelegramClient(
        StringSession(),
        int(api_id),
        str(api_hash),
        proxy=proxy_config,
    )
    await client.connect()
    try:
        sent_code = await client.send_code_request(phone)
        phone_code_hash = getattr(sent_code, "phone_code_hash", "")
        temp_session_string = client.session.save()
    finally:
        await client.disconnect()

    redis = redis_client or await get_redis_client()
    redis_key = f"telegram:auth_flow:{phone}"
    flow_data = {
        "phone": phone,
        "phone_code_hash": phone_code_hash,
        "session_string": temp_session_string,
        "api_id": int(api_id),
        "api_hash": str(api_hash),
        "proxy_url": proxy_url,
        "label": label,
    }
    await redis.set(redis_key, json.dumps(flow_data), ex=300)

    return {
        "status": "otp_sent",
        "phone": phone,
        "phone_code_hash": phone_code_hash,
    }


async def telethon_verify_login_code(
    phone: str,
    code: str,
    session: AsyncSession | None = None,
    redis_client: Any = None,
) -> dict[str, Any]:
    """Verify Telegram OTP code and export encrypted StringSession or request 2FA."""
    import json

    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
    from telethon.sessions import StringSession

    from app.proprietary.platforms.telegram.client import parse_proxy_url
    from app.redis_client import get_redis_client

    redis = redis_client or await get_redis_client()
    redis_key = f"telegram:auth_flow:{phone}"
    raw_data = await redis.get(redis_key)
    if not raw_data:
        raise ValueError("Auth flow expired or not found in Redis cache")

    data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
    proxy_config = (
        parse_proxy_url(data.get("proxy_url")) if data.get("proxy_url") else None
    )
    client = TelegramClient(
        StringSession(data.get("session_string", "")),
        int(data["api_id"]),
        str(data["api_hash"]),
        proxy=proxy_config,
    )
    await client.connect()
    try:
        try:
            user = await client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=data.get("phone_code_hash"),
            )
            final_session_string = client.session.save()
        except SessionPasswordNeededError as exc:
            updated_session_string = client.session.save()
            data["session_string"] = updated_session_string
            await redis.set(redis_key, json.dumps(data), ex=300)
            hint = getattr(exc, "hint", None) or "2FA Password Required"
            return {
                "status": "2fa_required",
                "phone": phone,
                "hint": hint,
            }
    finally:
        await client.disconnect()

    account_id = None
    if session is not None:
        svc = ScraperPlatformAccountService(session)
        credentials = {
            "api_id": data["api_id"],
            "api_hash": data["api_hash"],
            "session_string": final_session_string,
            "phone": phone,
        }
        if data.get("proxy_url"):
            credentials["proxy_url"] = data["proxy_url"]

        account = await svc.create(
            platform="telegram",
            label=data.get("label") or f"Telegram ({phone})",
            is_enabled=True,
            is_default=False,
            credentials=credentials,
        )
        account_id = account.id

    await redis.delete(redis_key)

    return {
        "status": "authenticated",
        "phone": phone,
        "account_id": account_id,
        "session_string": final_session_string,
        "username": getattr(user, "username", None) if user else None,
        "user_id": getattr(user, "id", None) if user else None,
    }


async def telethon_verify_2fa_password(
    phone: str,
    password: str,
    session: AsyncSession | None = None,
    redis_client: Any = None,
) -> dict[str, Any]:
    """Verify Telegram 2FA Cloud Password, export StringSession, and persist in DB."""
    import json

    from telethon import TelegramClient
    from telethon.sessions import StringSession

    from app.proprietary.platforms.telegram.client import parse_proxy_url
    from app.redis_client import get_redis_client

    redis = redis_client or await get_redis_client()
    redis_key = f"telegram:auth_flow:{phone}"
    raw_data = await redis.get(redis_key)
    if not raw_data:
        raise ValueError("Auth flow expired or not found in Redis cache")

    data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
    proxy_config = (
        parse_proxy_url(data.get("proxy_url")) if data.get("proxy_url") else None
    )
    client = TelegramClient(
        StringSession(data.get("session_string", "")),
        int(data["api_id"]),
        str(data["api_hash"]),
        proxy=proxy_config,
    )
    await client.connect()
    try:
        user = await client.sign_in(password=password)
        final_session_string = client.session.save()
    finally:
        await client.disconnect()

    account_id = None
    if session is not None:
        svc = ScraperPlatformAccountService(session)
        credentials = {
            "api_id": data["api_id"],
            "api_hash": data["api_hash"],
            "session_string": final_session_string,
            "phone": phone,
        }
        if data.get("proxy_url"):
            credentials["proxy_url"] = data["proxy_url"]

        account = await svc.create(
            platform="telegram",
            label=data.get("label") or f"Telegram ({phone})",
            is_enabled=True,
            is_default=False,
            credentials=credentials,
        )
        account_id = account.id

    await redis.delete(redis_key)

    return {
        "status": "authenticated",
        "phone": phone,
        "account_id": account_id,
        "session_string": final_session_string,
        "username": getattr(user, "username", None) if user else None,
        "user_id": getattr(user, "id", None) if user else None,
    }


@router.post("/telegram/request-otp", response_model=TelegramAuthResponse)
async def request_telegram_otp(
    data: TelegramRequestOtpRequest,
    _auth: AuthContext = Depends(require_superuser),
) -> TelegramAuthResponse:
    """Request a login code for Telegram userbot account."""
    try:
        await telethon_request_login_code(
            phone=data.phone,
            api_id=data.api_id,
            api_hash=data.api_hash,
            proxy_url=data.proxy_url,
            label=data.label,
        )
        return TelegramAuthResponse(
            status="otp_sent",
            phone=data.phone,
            message="OTP code sent via Telegram/SMS",
        )
    except Exception as exc:
        logger.exception("Failed to request Telegram OTP for %s: %s", data.phone, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to request Telegram OTP: {exc}",
        ) from exc


@router.post("/telegram/verify-otp", response_model=TelegramAuthResponse)
async def verify_telegram_otp(
    data: TelegramVerifyOtpRequest,
    session: AsyncSession = Depends(get_async_session),
    _auth: AuthContext = Depends(require_superuser),
) -> TelegramAuthResponse:
    """Verify Telegram OTP code and complete onboarding or signal 2FA required."""
    try:
        result = await telethon_verify_login_code(
            phone=data.phone,
            code=data.code,
            session=session,
        )
        return TelegramAuthResponse(
            status=result["status"],
            phone=data.phone,
            account_id=result.get("account_id"),
            hint=result.get("hint"),
            session_string=result.get("session_string"),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Failed to verify Telegram OTP for %s: %s", data.phone, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to verify Telegram OTP: {exc}",
        ) from exc


@router.post("/telegram/verify-2fa", response_model=TelegramAuthResponse)
async def verify_telegram_2fa(
    data: TelegramVerify2FaRequest,
    session: AsyncSession = Depends(get_async_session),
    _auth: AuthContext = Depends(require_superuser),
) -> TelegramAuthResponse:
    """Verify Telegram 2FA Cloud Password and complete onboarding."""
    try:
        result = await telethon_verify_2fa_password(
            phone=data.phone,
            password=data.password,
            session=session,
        )
        return TelegramAuthResponse(
            status=result["status"],
            phone=data.phone,
            account_id=result.get("account_id"),
            session_string=result.get("session_string"),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Failed to verify Telegram 2FA for %s: %s", data.phone, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to verify Telegram 2FA: {exc}",
        ) from exc


scraper_accounts_alias_router = APIRouter(prefix="/admin/scraper-accounts")


@scraper_accounts_alias_router.post(
    "/telegram/request-otp", response_model=TelegramAuthResponse
)
async def request_telegram_otp_alias(
    data: TelegramRequestOtpRequest,
    _auth: AuthContext = Depends(require_superuser),
) -> TelegramAuthResponse:
    return await request_telegram_otp(data, _auth)


@scraper_accounts_alias_router.post(
    "/telegram/verify-otp", response_model=TelegramAuthResponse
)
async def verify_telegram_otp_alias(
    data: TelegramVerifyOtpRequest,
    session: AsyncSession = Depends(get_async_session),
    _auth: AuthContext = Depends(require_superuser),
) -> TelegramAuthResponse:
    return await verify_telegram_otp(data, session, _auth)


@scraper_accounts_alias_router.post(
    "/telegram/verify-2fa", response_model=TelegramAuthResponse
)
async def verify_telegram_2fa_alias(
    data: TelegramVerify2FaRequest,
    session: AsyncSession = Depends(get_async_session),
    _auth: AuthContext = Depends(require_superuser),
) -> TelegramAuthResponse:
    return await verify_telegram_2fa(data, session, _auth)
