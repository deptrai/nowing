"""API-level integration tests for telegram.search capability (Story 22.1 / AC-6 / AD-6).

Verifies the POST /workspaces/{id}/scrapers/telegram/search door returns a
typed TelegramSearchOutput with billable_units equal to the number of messages.
"""

from __future__ import annotations

import httpx
import pytest
import respx

pytestmark = [pytest.mark.integration]

_TELEGRAM_PREVIEW_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Telegram: Contact @batdongsanhanoi</title>
</head>
<body>
  <div class="tgme_page">
    <div class="tgme_channel_info">
      <div class="tgme_channel_info_header">
        <div class="tgme_channel_info_title">
          <span dir="auto">Bất Động Sản Hà Nội 2026</span>
        </div>
      </div>
      <div class="tgme_channel_info_description">
        Kênh chia sẻ nguồn nhà đất Hà Nội.
      </div>
    </div>

    <div class="tgme_channel_history">
      <div class="tgme_widget_message_wrap" data-post="batdongsanhanoi/1001">
        <div class="tgme_widget_message" data-post="batdongsanhanoi/1001">
          <div class="tgme_widget_message_owner_name">
            <span dir="auto">Admin BĐS</span>
          </div>
          <div class="tgme_widget_message_text js-message_text" dir="auto">
            Bán gấp nhà mặt phố Cầu Giấy 50m2 x 5 tầng.<br>
            Giá bán: 12.5 tỷ.<br>
            Liên hệ: 0988.123.456
          </div>
          <div class="tgme_widget_message_footer">
            <div class="tgme_widget_message_info">
              <span class="tgme_widget_message_views">1.5K</span>
              <span class="tgme_widget_message_meta">
                <a class="tgme_widget_message_date" href="https://t.me/batdongsanhanoi/1001">
                  <time datetime="2026-08-15T08:30:00+00:00">08:30</time>
                </a>
              </span>
            </div>
          </div>
        </div>
      </div>

      <div class="tgme_widget_message_wrap" data-post="batdongsanhanoi/1002">
        <div class="tgme_widget_message" data-post="batdongsanhanoi/1002">
          <div class="tgme_widget_message_text js-message_text" dir="auto">
            Cần mua căn hộ 2PN Smart City, tài chính 3.2 tỷ.
            Gửi mail: investor@bds.vn
          </div>
          <div class="tgme_widget_message_footer">
            <div class="tgme_widget_message_info">
              <span class="tgme_widget_message_views">850</span>
              <span class="tgme_widget_message_meta">
                <a class="tgme_widget_message_date" href="https://t.me/batdongsanhanoi/1002">
                  <time datetime="2026-08-15T09:15:00+00:00">09:15</time>
                </a>
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</body>
</html>
"""


@pytest.mark.skip(reason="RED PHASE: activation pending full API acceptance gate")
@respx.mock
async def test_post_telegram_search_returns_output_and_billable_units(
    client_as_regular_user: httpx.AsyncClient,
    db_workspace,
):
    """AC-6: the REST door returns TelegramSearchOutput and billable_units."""
    respx.get("https://t.me/s/batdongsanhanoi").mock(
        return_value=httpx.Response(200, text=_TELEGRAM_PREVIEW_HTML)
    )

    response = await client_as_regular_user.post(
        f"/api/v1/workspaces/{db_workspace.id}/scrapers/telegram/search",
        json={"channel_username": "batdongsanhanoi", "limit": 10},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["channel_info"]["username"] == "batdongsanhanoi"
    assert body["channel_info"]["title"] == "Bất Động Sản Hà Nội 2026"
    assert body["total_found"] >= 0
    assert isinstance(body["messages"], list)
    assert body["billable_units"] == len(body["messages"])
    assert len(body["messages"]) <= 10

    if body["messages"]:
        first = body["messages"][0]
        assert "message_id" in first
        assert "text" in first
        assert "entities" in first
        assert "intent_tag" in first
