"""Zalo OpenAPI client, token refresher, rate limiter, and message sender (Story 21.6 / AD-41)."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import litellm
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import ZaloConnection
from app.gateway.ratelimit import acquire_token
from app.services.llm_router_service import LLMRouterService
from app.services.token_tracking_service import UsageType, record_token_usage
from app.utils.oauth_security import TokenEncryption

logger = logging.getLogger(__name__)

# Constants
ZALO_OPENAPI_BASE = "https://openapi.zalo.me"
ZALO_OAUTH_BASE = "https://oauth.zalo.me"
ZALO_RATE_LIMIT_PER_MINUTE = 20


_VIETNAM_MOBILE_RE = re.compile(
    r"^(?:0|84)(3[2-9]|5[6-9]|7[0-9]|8[1-9]|9[0-9])\d{7}$"
)


def format_vietnam_phone(phone: str | None) -> dict[str, str]:
    """Format and normalize a Vietnamese mobile phone number.

    Rejects landlines, VoIP, and malformed numbers. ZNS/Zalo deep links require
    a valid Vietnamese mobile number.

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

    if not _VIETNAM_MOBILE_RE.match(digits):
        return {"clean_phone": "", "international_phone": "", "zalo_url": ""}

    if digits.startswith("84"):
        clean_phone = "0" + digits[2:]
        international_phone = digits
    else:
        clean_phone = digits
        international_phone = "84" + digits[1:]

    return {
        "clean_phone": clean_phone,
        "international_phone": international_phone,
        "zalo_url": f"https://zalo.me/{clean_phone}",
    }


_PII_KEY_RE = re.compile(
    r"(phone|mobile|email|name|address|cccd|cmnd|passport|identity|dob|birth|bank|card|salary)",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_PHONE_RE = re.compile(
    r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b"
)
_ID_RE = re.compile(r"\b\d{9,12}\b")


def redact_template_data(template_data: dict[str, Any]) -> dict[str, Any]:
    """Redact likely PII values from ZNS template_data before logging."""
    redacted: dict[str, Any] = {}
    for key, value in template_data.items():
        if isinstance(value, dict):
            redacted[key] = redact_template_data(value)
        elif isinstance(value, list):
            redacted[key] = [
                redact_template_data({"_": item})["_"] if isinstance(item, dict) else item
                for item in value
            ]
        elif isinstance(value, str):
            if _PII_KEY_RE.search(key) or _EMAIL_RE.search(value) or _PHONE_RE.search(value) or _ID_RE.search(value):
                redacted[key] = "***"
            else:
                redacted[key] = value
        else:
            redacted[key] = value
    return redacted


def _build_draft_prompt(
    lead_data: dict[str, Any], custom_context: str | None = None
) -> str:
    """Build a structured prompt for the LLM to write a Vietnamese Zalo outreach draft."""
    company_name = str(
        lead_data.get("company_name") or lead_data.get("author") or "bạn"
    ).strip()
    source = str(lead_data.get("source") or "").lower()
    intent = str(lead_data.get("intent") or "").upper()
    industry = lead_data.get("industry") or ""
    location = lead_data.get("location") or ""
    price_estimate = lead_data.get("price_estimate") or ""
    snippet = lead_data.get("content_snippet") or ""

    context_lines = [
        f"- Tên liên hệ / công ty: {company_name}",
        f"- Nguồn lead: {source or 'không rõ'}",
        f"- Intent: {intent or 'tiếp cận bán hàng'}",
    ]
    if industry:
        context_lines.append(f"- Ngành: {industry}")
    if location:
        context_lines.append(f"- Địa điểm: {location}")
    if price_estimate:
        context_lines.append(f"- Mức giá / ngân sách: {price_estimate}")
    if snippet:
        context_lines.append(f"- Nội dung gốc: {snippet[:200]}")
    if custom_context:
        context_lines.append(f"- Bối cảnh bổ sung: {custom_context}")

    return (
        "Bạn là trợ lý bán hàng B2B của Nowing. Hãy viết một tin nhắn tiếp cận ngắn gọn, "
        "thân thiện, ToS-compliant qua Zalo cho lead sau:\n\n"
        "\n".join(context_lines)
        + "\n\nYêu cầu:\n"
        "- Tiếng Việt, lịch sự, tự nhiên.\n"
        "- 2-3 câu, tối đa 250 ký tự.\n"
        "- Không spam, không hứa hẹn quá mức, không yêu cầu thông tin nhạy cảm.\n"
        "- Tập trung vào giá trị đối tác/mua bán có thể mang lại.\n"
        "- Kết thúc bằng lời mời trao đổi qua Zalo.\n"
        "Chỉ trả về nội dung tin nhắn, không giải thích."
    )


def _fallback_template(
    lead_data: dict[str, Any], custom_context: str | None = None
) -> str:
    """Fallback template when LLM is unavailable or fails."""
    company_name = str(
        lead_data.get("company_name") or lead_data.get("author") or "bạn"
    ).strip()
    source = str(lead_data.get("source") or "").lower()
    intent = str(lead_data.get("intent") or "").upper()
    industry = lead_data.get("industry") or ""
    location = lead_data.get("location") or ""
    price_estimate = lead_data.get("price_estimate") or ""
    snippet = lead_data.get("content_snippet") or ""

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


async def generate_assisted_outbound_draft(
    session: AsyncSession,
    lead_data: dict[str, Any],
    workspace_id: int,
    user_id: UUID,
    custom_context: str | None = None,
) -> str:
    """Generate high-converting, personalized Vietnamese outreach draft using an LLM.

    Falls back to a deterministic template if the LLM router is unavailable or the
    call fails. Token usage is recorded in the workspace's TokenUsage table.
    """
    router = LLMRouterService.get_router()
    if not router:
        logger.warning("LLM router unavailable; using fallback Zalo draft template")
        return _fallback_template(lead_data, custom_context=custom_context)

    try:
        response = await router.acompletion(
            model="auto",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Bạn là trợ lý bán hàng B2B tại Việt Nam. "
                        "Viết tin nhắn tiếp cận khách hàng ngắn gọn, lịch sự, tuân thủ ToS."
                    ),
                },
                {
                    "role": "user",
                    "content": _build_draft_prompt(lead_data, custom_context=custom_context),
                },
            ],
            temperature=0.6,
            max_tokens=300,
        )
    except Exception as exc:
        logger.warning("LLM draft generation failed: %s; using fallback template", exc)
        return _fallback_template(lead_data, custom_context=custom_context)

    content = ""
    try:
        content = response.choices[0].message.content.strip()
    except (AttributeError, IndexError, TypeError) as exc:
        logger.warning("LLM draft response malformed: %s", exc)
        return _fallback_template(lead_data, custom_context=custom_context)

    if not content:
        return _fallback_template(lead_data, custom_context=custom_context)

    # Record token usage for cost visibility
    usage = getattr(response, "usage", None) or {}
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    total_tokens = getattr(usage, "total_tokens", 0) or 0

    cost_usd = 0.0
    try:
        cost_usd = float(litellm.completion_cost(completion_response=response) or 0.0)
    except Exception:
        logger.debug("Could not compute draft cost via litellm")
    cost_micros = round(cost_usd * 1_000_000)

    if total_tokens > 0:
        model_name = getattr(response, "model", None) or "unknown"
        await record_token_usage(
            session,
            usage_type=UsageType.ASSISTED_DRAFT,
            workspace_id=workspace_id,
            user_id=user_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_micros=cost_micros,
            model_breakdown={
                model_name: {
                    "provider": "llm_router",
                    "cost_micros": cost_micros,
                    "total_tokens": total_tokens,
                }
            },
            call_details={"lead_source": str(lead_data.get("source") or "")},
        )

    return content


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

        def _decrypt_if_needed(value: str | None) -> str | None:
            if not value:
                return value
            if enc and enc.is_encrypted(value):
                return enc.decrypt_token(value)
            return value

        access_token = _decrypt_if_needed(connection.access_token_encrypted)
        refresh_token = _decrypt_if_needed(connection.refresh_token_encrypted)
        app_secret = _decrypt_if_needed(connection.app_secret_encrypted) or ""

        return cls(
            access_token=access_token,
            refresh_token=refresh_token,
            app_id=connection.app_id or getattr(config, "ZALO_APP_ID", ""),
            secret_key=app_secret or getattr(config, "ZALO_APP_SECRET", ""),
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

        if not isinstance(res_data, dict):
            logger.error("Unexpected Zalo token refresh response: %s", res_data)
            raise RuntimeError(
                f"Unexpected Zalo token refresh response: {type(res_data).__name__}"
            )

        if res_data.get("access_token"):
            self.access_token = res_data["access_token"]
            self.refresh_token = res_data.get("refresh_token", target_refresh)
            expires_in = int(res_data.get("expires_in", 90000))
            self.token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
            return res_data

        error_msg = res_data.get("error_name") or res_data.get("message") or str(res_data)
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
            "tracking_id": tracking_id or str(uuid4()),
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

    async def send_cs_message(
        self,
        user_id: str,
        text: str,
        session: AsyncSession | None = None,
        connection: ZaloConnection | None = None,
    ) -> dict[str, Any]:
        """Send Customer Support text message to a follower / existing conversation."""
        if not await self.check_rate_limit():
            raise RuntimeError("Zalo OA rate limit exceeded (max 20 messages/minute)")

        if session is not None and connection is not None:
            await self.ensure_valid_token(session, connection)

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
