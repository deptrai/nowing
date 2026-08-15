"""Unit tests for Zalo Gateway (Story 21.6 / AD-41)."""

from __future__ import annotations

import hashlib
import hmac
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import Response

from app.gateway.zalo.client import (
    ZaloClient,
    format_vietnam_phone,
    generate_assisted_outbound_draft,
)
from app.gateway.zalo.telegram_alerts import build_lead_telegram_alert
from app.gateway.zalo.webhook import (
    detect_buying_intent,
    verify_zalo_signature,
)


@pytest.mark.unit
class TestZaloPhoneFormatting:
    """Test Vietnamese phone formatting for deep links and ZNS."""

    def test_national_10_digits(self):
        res = format_vietnam_phone("0912345678")
        assert res["clean_phone"] == "0912345678"
        assert res["international_phone"] == "84912345678"
        assert res["zalo_url"] == "https://zalo.me/0912345678"

    def test_plus_84_format(self):
        res = format_vietnam_phone("+84912345678")
        assert res["clean_phone"] == "0912345678"
        assert res["international_phone"] == "84912345678"
        assert res["zalo_url"] == "https://zalo.me/0912345678"

    def test_84_without_plus(self):
        res = format_vietnam_phone("84912345678")
        assert res["clean_phone"] == "0912345678"
        assert res["international_phone"] == "84912345678"
        assert res["zalo_url"] == "https://zalo.me/0912345678"

    def test_phone_with_dots_and_spaces(self):
        res = format_vietnam_phone("091.234.5678")
        assert res["clean_phone"] == "0912345678"
        assert res["international_phone"] == "84912345678"
        assert res["zalo_url"] == "https://zalo.me/0912345678"

    def test_empty_or_none(self):
        assert format_vietnam_phone(None) == {
            "clean_phone": "",
            "international_phone": "",
            "zalo_url": "",
        }
        assert format_vietnam_phone("") == {
            "clean_phone": "",
            "international_phone": "",
            "zalo_url": "",
        }


@pytest.mark.unit
class TestZaloDraftGenerator:
    """Test AI Assisted Outbound greeting script generation."""

    def test_real_estate_draft(self):
        lead_data = {
            "company_name": "Nguyễn Văn A",
            "source": "batdongsan",
            "intent": "BÁN",
            "location": "Quận 2, TP.HCM",
            "price_estimate": "5.2 tỷ",
            "content_snippet": "Bán căn hộ 2PN view sông",
        }
        draft = generate_assisted_outbound_draft(lead_data)
        assert "BĐS" in draft
        assert "Quận 2, TP.HCM" in draft
        assert "5.2 tỷ" in draft
        assert "Zalo" in draft

    def test_recruitment_draft(self):
        lead_data = {
            "company_name": "Công ty Công Nghệ ABC",
            "source": "topcv",
            "intent": "TUYỂN DỤNG",
            "industry": "IT Phần mềm",
        }
        draft = generate_assisted_outbound_draft(lead_data)
        assert "Công ty Công Nghệ ABC" in draft
        assert "tuyển dụng" in draft
        assert "IT Phần mềm" in draft

    def test_tender_draft(self):
        lead_data = {
            "company_name": "Ban Quản Lý Dự Án X",
            "source": "muasamcong",
            "intent": "ĐẤU THẦU",
        }
        draft = generate_assisted_outbound_draft(lead_data)
        assert "gói thầu" in draft or "dự án" in draft

    def test_custom_context_included(self):
        lead_data = {"company_name": "Công ty Y", "source": "other"}
        draft = generate_assisted_outbound_draft(
            lead_data, custom_context="Chiết khấu 15% tháng này"
        )
        assert "Chiết khấu 15% tháng này" in draft


@pytest.mark.unit
class TestZaloSignatureVerifier:
    """Test Zalo webhook HMAC / SHA256 signature verification."""

    def test_valid_mac_signature(self):
        app_id = "123456789"
        raw_body = b'{"event_name":"user_send_text","message":{"text":"hello"}}'
        timestamp = str(int(time.time()))
        secret_key = "my_secret_key"

        data_to_hash = (
            f"{app_id}{raw_body.decode('utf-8')}{timestamp}{secret_key}".encode()
        )
        expected_sig = hashlib.sha256(data_to_hash).hexdigest()

        assert (
            verify_zalo_signature(app_id, raw_body, timestamp, expected_sig, secret_key)
            is True
        )

    def test_valid_hmac_signature(self):
        app_id = "123456789"
        raw_body = b'{"event_name":"user_send_text"}'
        timestamp = str(int(time.time()))
        secret_key = "my_secret_key"

        hmac_sig = hmac.new(
            secret_key.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        assert (
            verify_zalo_signature(app_id, raw_body, timestamp, hmac_sig, secret_key)
            is True
        )

    def test_invalid_signature(self):
        assert (
            verify_zalo_signature("123", b"{}", "12345", "invalid_sig_hex", "secret")
            is False
        )

    def test_missing_secret_fails_closed(self):
        assert (
            verify_zalo_signature("123", b"{}", str(int(time.time())), "sig", "")
            is False
        )

    def test_stale_timestamp_rejected(self):
        assert (
            verify_zalo_signature(
                "123", b"{}", "1700000000", "invalid", "secret"
            )
            is False
        )


@pytest.mark.unit
class TestBuyingIntentDetection:
    """Test Vietnamese buying signal detection."""

    def test_positive_pricing_intent(self):
        has_intent, reason = detect_buying_intent(
            "Chào bạn, sản phẩm này giá bao nhiêu vậy?"
        )
        assert has_intent is True
        assert "giá" in reason.lower()

    def test_positive_consultation_intent(self):
        has_intent, reason = detect_buying_intent(
            "Bên mình cần tư vấn thêm về gói dịch vụ"
        )
        assert has_intent is True
        assert "tư vấn" in reason.lower()

    def test_positive_meeting_intent(self):
        has_intent, reason = detect_buying_intent(
            "Mình muốn hẹn gặp demo vào sáng mai nhé"
        )
        assert has_intent is True
        assert (
            "hẹn" in reason.lower()
            or "gặp" in reason.lower()
            or "demo" in reason.lower()
        )

    def test_negative_neutral_message(self):
        has_intent, reason = detect_buying_intent("Cảm ơn thông tin từ bạn nhé")
        assert has_intent is False
        assert reason == ""


@pytest.mark.unit
class TestTelegramLeadAlertFormatting:
    """Test Telegram rich notification layout and inline keyboard."""

    def test_build_alert_layout(self):
        text, keyboard = build_lead_telegram_alert(
            lead_name="Anh Nam",
            company_name="BĐS Thủ Đức",
            phone="0912345678",
            source="batdongsan",
            intent="Quan tâm mua căn 2PN",
            message_content="Gửi mình bảng giá chi tiết nhé",
            workspace_id=42,
            lead_id="d3b07384-d113-46fb-a0b2-32b0f4d3824f",
            frontend_url="https://nowing.net",
        )

        assert "TÍN HIỆU LEAD MỚI" in text
        assert "BĐS Thủ Đức" in text
        assert "0912345678" in text

        # Check inline keyboard
        buttons = keyboard["inline_keyboard"][0]
        assert len(buttons) == 2
        assert buttons[0]["text"] == "📱 Mở Zalo"
        assert buttons[0]["url"] == "https://zalo.me/0912345678"
        assert buttons[1]["text"] == "📋 Xem Chi Tiết Lead"
        assert "dashboard/42/leads" in buttons[1]["url"]


@pytest.mark.unit
@pytest.mark.asyncio
class TestZaloClient:
    """Test ZaloClient methods."""

    async def test_refresh_token_success(self):
        mock_http = AsyncMock()
        mock_resp = MagicMock(spec=Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "new_access_token_123",
            "refresh_token": "new_refresh_token_456",
            "expires_in": 90000,
        }
        mock_resp.raise_for_status = MagicMock()
        mock_http.post.return_value = mock_resp

        client = ZaloClient(
            app_id="app_123",
            secret_key="sec_456",
            refresh_token="old_refresh_token",
            http_client=mock_http,
        )

        res = await client.refresh_access_token()
        assert res["access_token"] == "new_access_token_123"
        assert client.access_token == "new_access_token_123"
        assert client.refresh_token == "new_refresh_token_456"
        assert client.token_expires_at is not None

    async def test_send_zns_success(self):
        mock_http = AsyncMock()
        mock_resp = MagicMock(spec=Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "error": 0,
            "message": "Success",
            "data": {"msg_id": "zns_msg_999"},
        }
        mock_resp.raise_for_status = MagicMock()
        mock_http.post.return_value = mock_resp

        client = ZaloClient(
            access_token="valid_access_token",
            oa_id="oa_123",
            http_client=mock_http,
        )

        with patch.object(client, "check_rate_limit", return_value=True):
            result = await client.send_zns(
                phone="0912345678",
                template_id="tpl_001",
                template_data={"customer_name": "Nam", "order_id": "1234"},
            )
            assert result["error"] == 0
            assert result["data"]["msg_id"] == "zns_msg_999"

    async def test_send_cs_message_success(self):
        mock_http = AsyncMock()
        mock_resp = MagicMock(spec=Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "error": 0,
            "message": "Success",
            "data": {"message_id": "cs_msg_888"},
        }
        mock_resp.raise_for_status = MagicMock()
        mock_http.post.return_value = mock_resp

        client = ZaloClient(
            access_token="valid_access_token",
            oa_id="oa_123",
            http_client=mock_http,
        )

        with patch.object(client, "check_rate_limit", return_value=True):
            result = await client.send_cs_message(
                user_id="user_zalo_123",
                text="Xin chào quý khách!",
            )
            assert result["error"] == 0
