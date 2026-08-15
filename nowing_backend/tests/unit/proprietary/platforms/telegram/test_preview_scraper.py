"""Unit tests for Telegram Web Preview Scraper (Story 22.1 / AD-1, AD-2, AD-5)."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.proprietary.platforms.telegram.preview_scraper import (
    TelegramWebPreviewScraper,
    parse_channel_info,
    parse_messages,
)

SAMPLE_PREVIEW_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Telegram: Contact @batdongsanhanoi</title>
</head>
<body>
  <div class="tgme_page">
    <div class="tgme_channel_info">
      <div class="tgme_channel_info_header">
        <div class="tgme_page_photo">
          <img src="https://cdn.telegram.org/file/batdongsan.jpg">
        </div>
        <div class="tgme_channel_info_title">
          <span dir="auto">Bất Động Sản Hà Nội 2026</span>
        </div>
        <div class="tgme_channel_info_counter">
          <span class="counter_value">25.4K</span>
          <span class="counter_type">subscribers</span>
        </div>
      </div>
      <div class="tgme_channel_info_description">
        Kênh chia sẻ nguồn nhà đất Hà Nội chính chủ, giá tốt nhất. Liên hệ hotline: 0912345678
      </div>
    </div>

    <div class="tgme_channel_history">
      <!-- Message 1: Sell -->
      <div class="tgme_widget_message_wrap" data-post="batdongsanhanoi/1001">
        <div class="tgme_widget_message" data-post="batdongsanhanoi/1001">
          <div class="tgme_widget_message_owner_name">
            <span dir="auto">Admin BĐS</span>
          </div>
          <div class="tgme_widget_message_photo_wrap" style="background-image:url('https://cdn.telegram.org/photo1001.jpg')"></div>
          <div class="tgme_widget_message_text js-message_text" dir="auto">
            Bán gấp nhà mặt phố Cầu Giấy 50m2 x 5 tầng, vỉa hè rộng, kinh doanh sầm uất.<br>
            Giá bán: 12.5 tỷ có thương lượng.<br>
            Liên hệ chính chủ: 0988.123.456<br>
            #bds #caugiay #nhamatpho
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

      <!-- Message 2: Buy -->
      <div class="tgme_widget_message_wrap" data-post="batdongsanhanoi/1002">
        <div class="tgme_widget_message" data-post="batdongsanhanoi/1002">
          <div class="tgme_widget_message_owner_name">
            <span dir="auto">BĐS Hà Nội</span>
          </div>
          <div class="tgme_widget_message_text js-message_text" dir="auto">
            Cần tìm mua căn hộ 2PN 2WC tại Vinhomes Smart City, tài chính khoảng 3.2 tỷ.<br>
            Yêu cầu tầng trung, view thoáng. Ai có hàng gửi mail: investor@bds.vn hoặc Zalo 0901 234 567.
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

      <!-- Message 3: News with forwarded & media -->
      <div class="tgme_widget_message_wrap" data-post="batdongsanhanoi/1003">
        <div class="tgme_widget_message" data-post="batdongsanhanoi/1003">
          <div class="tgme_widget_message_text js-message_text" dir="auto">
            Tin tức thị trường: Lãi suất cho vay mua nhà tháng 8/2026 giảm thêm 0.5%.
          </div>
          <div class="tgme_widget_message_footer">
            <div class="tgme_widget_message_info">
              <span class="tgme_widget_message_views">2.8K</span>
              <span class="tgme_widget_message_meta">
                <a class="tgme_widget_message_date" href="https://t.me/batdongsanhanoi/1003">
                  <time datetime="2026-08-15T10:00:00+00:00">10:00</time>
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


def test_parse_channel_info() -> None:
    """Test extracting channel header metadata from preview HTML."""
    info = parse_channel_info(SAMPLE_PREVIEW_HTML, username="batdongsanhanoi")
    assert info is not None
    assert info.username == "batdongsanhanoi"
    assert info.title == "Bất Động Sản Hà Nội 2026"
    assert "chính chủ" in info.description
    assert info.subscribers_count == 25400
    assert info.avatar_url == "https://cdn.telegram.org/file/batdongsan.jpg"


def test_parse_messages() -> None:
    """Test parsing messages, views, dates, and media presence."""
    messages = parse_messages(SAMPLE_PREVIEW_HTML, channel_username="batdongsanhanoi")
    assert len(messages) == 3

    # Message 1
    m1 = messages[0]
    assert m1.message_id == 1001
    assert m1.channel_username == "batdongsanhanoi"
    assert "Cầu Giấy" in m1.text
    assert m1.views == 1500
    assert m1.published_at.isoformat().startswith("2026-08-15T08:30:00")
    assert m1.has_media is True
    assert m1.author_name == "Admin BĐS"
    assert len(m1.entities.phone_numbers) >= 1
    assert m1.intent_tag == "sell"

    # Message 2
    m2 = messages[1]
    assert m2.message_id == 1002
    assert "Vinhomes Smart City" in m2.text
    assert m2.views == 850
    assert "investor@bds.vn" in m2.entities.emails
    assert m2.intent_tag == "buy"

    # Message 3
    m3 = messages[2]
    assert m3.message_id == 1003
    assert m3.views == 2800
    assert m3.intent_tag == "news"


@pytest.mark.asyncio
@respx.mock
async def test_telegram_web_preview_scraper_fetch() -> None:
    """Test scraper fetches from t.me/s/{channel} and returns parsed data."""
    respx.get("https://t.me/s/batdongsanhanoi").mock(
        return_value=httpx.Response(200, text=SAMPLE_PREVIEW_HTML)
    )

    scraper = TelegramWebPreviewScraper()
    result = await scraper.scrape_channel("batdongsanhanoi")

    assert result.channel_info.username == "batdongsanhanoi"
    assert result.channel_info.title == "Bất Động Sản Hà Nội 2026"
    assert len(result.messages) == 3


@pytest.mark.asyncio
@respx.mock
async def test_telegram_web_preview_scraper_not_found() -> None:
    """Test scraper handling 404 or empty channel."""
    respx.get("https://t.me/s/nonexistent_chan_12345").mock(
        return_value=httpx.Response(404, text="Channel not found")
    )

    scraper = TelegramWebPreviewScraper()
    result = await scraper.scrape_channel("nonexistent_chan_12345")

    assert result.channel_info.username == "nonexistent_chan_12345"
    assert len(result.messages) == 0


def test_sanitize_username() -> None:
    """Test extracting clean username from full URLs or @ handles."""
    assert TelegramWebPreviewScraper.sanitize_username("@batdongsanhanoi") == "batdongsanhanoi"
    assert TelegramWebPreviewScraper.sanitize_username("https://t.me/batdongsanhanoi") == "batdongsanhanoi"
    assert TelegramWebPreviewScraper.sanitize_username("https://t.me/s/diaocsaigon/") == "diaocsaigon"
    assert TelegramWebPreviewScraper.sanitize_username("t.me/hn_bds_group") == "hn_bds_group"

    with pytest.raises(ValueError, match="Invalid Telegram channel"):
        TelegramWebPreviewScraper.sanitize_username("inv?bad=param")


def test_parse_count_edge_cases() -> None:
    """Test European format decimal commas and space separators."""
    from app.proprietary.platforms.telegram.preview_scraper import parse_count

    assert parse_count("1,5K") == 1500
    assert parse_count("2.5K") == 2500
    assert parse_count("1,2M") == 1200000
    assert parse_count("25 400") == 25400
    assert parse_count("150,000") == 150000
    assert parse_count("0") == 0
    assert parse_count(None) == 0


def test_parse_messages_album_single_query_param() -> None:
    """Test parsing message ID from album post with ?single suffix."""
    html = """
    <div class="tgme_widget_message_wrap" data-post="testchan/9999?single">
      <div class="tgme_widget_message" data-post="testchan/9999?single">
        <div class="tgme_widget_message_text">Album post caption</div>
      </div>
    </div>
    """
    messages = parse_messages(html, channel_username="testchan")
    assert len(messages) == 1
    assert messages[0].message_id == 9999
