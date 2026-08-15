"""Zalo OpenAPI client, token refresher, rate limiter, and message sender (Story 21.6 / AD-41)."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import ZaloConnection
from app.gateway.ratelimit import acquire_token
from app.utils.oauth_security import TokenEncryption

logger = logging.getLogger(__name__)

# Constants
ZALO_OPENAPI_BASE = "https://openapi.zalo.me"
ZALO_OAUTH_BASE = "https://oauth.zalo.me"
ZALO_RATE_LIMIT_PER_MINUTE = 20


def format_vietnam_phone(phone: str | None) -> dict[str, str]:
    """Format and normalize a Vietnamese phone number.

    Returns:
        dict with keys:
            clean_phone: standard 10-digit national format (e.g. '0912345678')
            international_phone: 84-prefixed format without '+' (e.g. '84912345678')
            zalo_url: deep-link URL (e.g. 'https://zalo.me/0912345678')
    """
    if not phone:
        return {"clean_phone": "", "international_phone": "", "zalo_url": ""}

    # Strip whitespace, dots, hyphens, parentheses, and letters
    digits = re.sub(r"\D", "", str(phone))

    if not digits:
        return {"clean_phone": "", "international_phone": "", "zalo_url": ""}

    # Normalize to national 0xxx and international 84xxx
    if digits.startswith("84") and len(digits) in (11, 12):
        clean_phone = "0" + digits[2:]
        international_phone = digits
    elif digits.startswith("0") and len(digits) == 10:
        clean_phone = digits
        international_phone = "84" + digits[1:]
    elif len(digits) == 9:
        clean_phone = "0" + digits
        international_phone = "84" + digits
    else:
        # Fallback to digits as-is
        clean_phone = digits
        international_phone = (
            digits if digits.startswith("84") else f"84{digits.lstrip('0')}"
        )

    return {
        "clean_phone": clean_phone,
        "international_phone": international_phone,
        "zalo_url": f"https://zalo.me/{clean_phone}",
    }


def generate_assisted_outbound_draft(
    lead_data: dict[str, Any], custom_context: str | None = None
) -> str:
    """Generate high-converting, personalized Vietnamese outreach draft for Assisted Zalo Co-pilot.

    Contextually adapts to Real Estate, Recruitment/Jobs, Tenders, or B2B outreach.
    100% ToS compliant (rendered for client review/paste).
    """
    company_name = str(
        lead_data.get("company_name") or lead_data.get("author") or "bạn"
    ).strip()
    source = str(lead_data.get("source") or "").lower()
    intent = str(lead_data.get("intent") or "").upper()
    industry = lead_data.get("industry") or ""
    location = lead_data.get("location") or ""
    price_estimate = lead_data.get("price_estimate") or ""
    snippet = lead_data.get("content_snippet") or ""

    # Real estate focus
    if (
        any(k in source for k in ("batdongsan", "bds", "muaban", "nhatot", "chotot"))
        or "BÁN" in intent
        or "MUA" in intent
    ):
        parts = ["Chào bạn,"]
        loc_str = f" tại {location}" if location else ""
        price_str = f" (mức giá tham khảo: {price_estimate})" if price_estimate else ""
        parts.append(f"Mình thấy tin đăng BĐS của bạn{loc_str}{price_str}.")
        if snippet:
            parts.append(f'Về thông tin: "{snippet[:100]}..."')
        parts.append(
            "Bên mình có khách hàng/đối tác đang rất quan tâm phân khúc này. Mình kết nối qua Zalo trao đổi thêm nhé!"
        )
        if custom_context:
            parts.append(f"\n({custom_context})")
        return " ".join(parts)

    # Job / Recruitment focus
    if (
        any(k in source for k in ("topcv", "itviec", "vietnamworks", "job"))
        or "TUYỂN" in intent
        or "RECRUIT" in intent
    ):
        parts = [f"Chào {company_name},"]
        parts.append(
            f"Mình thấy bên mình đang có nhu cầu tuyển dụng qua {source or 'kênh trực tuyến'}."
        )
        if industry:
            parts.append(
                f"Bên mình có mạng lưới ứng viên và giải pháp hỗ trợ mảng {industry}."
            )
        parts.append(
            "Mình muốn gửi profile và trao đổi nhanh để hỗ trợ bên mình sớm tìm được nhân sự phù hợp ạ."
        )
        if custom_context:
            parts.append(f"\n({custom_context})")
        return " ".join(parts)

    # Tender / Mua sắm công focus
    if "tender" in source or "muasamcong" in source or "THẦU" in intent:
        parts = [f"Chào anh/chị đại diện {company_name},"]
        parts.append(
            "Mình liên hệ liên quan đến thông tin gói thầu/dự án bên mình đang triển khai."
        )
        parts.append(
            "Bên mình có năng lực cung ứng và hồ sơ phù hợp, muốn kết nối để trao đổi chi tiết phương án hợp tác."
        )
        if custom_context:
            parts.append(f"\n({custom_context})")
        return " ".join(parts)

    # General B2B Prospecting
    parts = [f"Chào {company_name},"]
    parts.append(
        f"Mình liên hệ từ Nowing sau khi tìm hiểu về hoạt động của bên mình{f' trong ngành {industry}' if industry else ''}."
    )
    parts.append(
        "Bên mình muốn gửi thông tin giải pháp hỗ trợ tối ưu vận hành và mở rộng thị trường."
    )
    parts.append("Mình xin phép gửi thông tin chi tiết qua Zalo để tiện trao đổi nhé!")
    if custom_context:
        parts.append(f"\n({custom_context})")
    return " ".join(parts)


class ZaloClient:
    """Zalo OpenAPI & ZNS Gateway Client with rate limiting and token management."""

    def __init__(
        self,
        *,
        access_token: str | None = None,
        refresh_token: str | None = None,
        app_id: str | None = None,
        secret_key: str | None = None,
        oa_id: str | None = None,
        token_expires_at: datetime | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.app_id = app_id or getattr(config, "ZALO_APP_ID", "")
        self.secret_key = secret_key or getattr(config, "ZALO_APP_SECRET", "")
        self.oa_id = oa_id or getattr(config, "ZALO_OA_ID", "")
        self.token_expires_at = token_expires_at
        self._client = http_client

    @classmethod
    def from_connection(cls, connection: ZaloConnection) -> ZaloClient:
        """Instantiate a client from a ZaloConnection model with decrypted tokens."""
        secret = config.SECRET_KEY or ""
        enc = TokenEncryption(secret) if secret else None

        access_token = (
            enc.decrypt_token(connection.access_token_encrypted)
            if enc and connection.access_token_encrypted
            else connection.access_token_encrypted
        )
        refresh_token = (
            enc.decrypt_token(connection.refresh_token_encrypted)
            if enc and connection.refresh_token_encrypted
            else connection.refresh_token_encrypted
        )

        return cls(
            access_token=access_token,
            refresh_token=refresh_token,
            app_id=connection.app_id or getattr(config, "ZALO_APP_ID", ""),
            secret_key=connection.webhook_secret
            or getattr(config, "ZALO_APP_SECRET", ""),
            oa_id=connection.oa_id,
            token_expires_at=connection.token_expires_at,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or getattr(self._client, "is_closed", False) is True:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def check_rate_limit(self, oa_id: str | None = None) -> bool:
        """Enforce maximum 20 messages/minute per OA via Redis token bucket."""
        target_oa = oa_id or self.oa_id or "default"
        scope = f"zalo:oa:{target_oa}"
        wait_ms = await acquire_token(
            scope,
            capacity=ZALO_RATE_LIMIT_PER_MINUTE,
            refill_per_sec=ZALO_RATE_LIMIT_PER_MINUTE / 60.0,
            consume=1.0,
        )
        return wait_ms == 0

    async def refresh_access_token(
        self,
        app_id: str | None = None,
        secret_key: str | None = None,
        refresh_token: str | None = None,
    ) -> dict[str, Any]:
        """Refresh Zalo OA Access Token using OAuth v4 endpoint."""
        target_app_id = app_id or self.app_id
        target_secret = secret_key or self.secret_key
        target_refresh = refresh_token or self.refresh_token

        if not target_app_id or not target_secret or not target_refresh:
            raise ValueError(
                "Missing app_id, secret_key, or refresh_token for Zalo token refresh"
            )

        url = f"{ZALO_OAUTH_BASE}/v4/oa/access_token"
        headers = {
            "secret_key": target_secret,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "app_id": target_app_id,
            "grant_type": "refresh_token",
            "refresh_token": target_refresh,
        }

        client = await self._get_client()
        try:
            resp = await client.post(url, headers=headers, data=data)
            resp.raise_for_status()
            res_data = resp.json()
        except Exception as exc:
            logger.error("Failed to refresh Zalo OA token: %s", exc)
            raise RuntimeError(f"Zalo OAuth token refresh failed: {exc}") from exc

        if "access_token" in res_data:
            self.access_token = res_data["access_token"]
            self.refresh_token = res_data.get("refresh_token", target_refresh)
            expires_in = int(res_data.get("expires_in", 90000))
            self.token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
            return res_data
        else:
            error_msg = (
                res_data.get("error_name") or res_data.get("message") or "Unknown error"
            )
            logger.error("Zalo token refresh error response: %s", res_data)
            raise RuntimeError(f"Zalo OAuth error: {error_msg}")

    async def ensure_valid_token(
        self, session: AsyncSession, connection: ZaloConnection
    ) -> str:
        """Ensure token is valid and refreshed in DB if expired or expiring soon."""
        now = datetime.now(UTC)
        is_expired = (
            connection.token_expires_at is not None
            and connection.token_expires_at <= (now + timedelta(minutes=5))
        )

        if is_expired or not self.access_token:
            logger.info(
                "Refreshing expired Zalo OA token for connection %s", connection.id
            )
            await self.refresh_access_token()
            secret = config.SECRET_KEY or ""
            enc = TokenEncryption(secret) if secret else None

            connection.access_token_encrypted = (
                enc.encrypt_token(self.access_token)
                if enc and self.access_token
                else self.access_token
            )
            if self.refresh_token:
                connection.refresh_token_encrypted = (
                    enc.encrypt_token(self.refresh_token) if enc else self.refresh_token
                )
            connection.token_expires_at = self.token_expires_at
            await session.commit()

        return self.access_token or ""

    async def send_zns(
        self,
        phone: str,
        template_id: str,
        template_data: dict[str, Any],
        tracking_id: str | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        """Send a Zalo Notification Service (ZNS) message.

        Requires approved template_id and user consent (Decree 356 compliance).
        Rate limited to 20 msg/min.
        """
        if not await self.check_rate_limit():
            raise RuntimeError("Zalo OA rate limit exceeded (max 20 messages/minute)")

        if not self.access_token:
            raise ValueError("Missing access_token for ZNS message")

        phone_meta = format_vietnam_phone(phone)
        int_phone = phone_meta["international_phone"]
        if not int_phone:
            raise ValueError(f"Invalid recipient phone number: {phone}")

        url = f"{ZALO_OPENAPI_BASE}/v3.0/oa/message/zns"
        headers = {
            "access_token": self.access_token,
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "phone": int_phone,
            "template_id": template_id,
            "template_data": template_data,
            "tracking_id": tracking_id or str(uuid.uuid4()),
        }
        if mode:
            payload["mode"] = mode

        client = await self._get_client()
        try:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            res_json = resp.json()
        except Exception as exc:
            logger.error("Failed to send ZNS message: %s", exc)
            raise RuntimeError(f"ZNS send request failed: {exc}") from exc

        return res_json

    async def send_cs_message(self, user_id: str, text: str) -> dict[str, Any]:
        """Send Customer Support text message to a follower / existing conversation."""
        if not await self.check_rate_limit():
            raise RuntimeError("Zalo OA rate limit exceeded (max 20 messages/minute)")

        if not self.access_token:
            raise ValueError("Missing access_token for Zalo message")

        url = f"{ZALO_OPENAPI_BASE}/v3.0/oa/message/cs"
        headers = {
            "access_token": self.access_token,
            "Content-Type": "application/json",
        }
        payload = {
            "recipient": {"user_id": user_id},
            "message": {"text": text},
        }

        client = await self._get_client()
        try:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("Failed to send Zalo CS message: %s", exc)
            raise RuntimeError(f"Zalo CS message send failed: {exc}") from exc

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
