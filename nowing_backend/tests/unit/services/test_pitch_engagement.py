"""Unit tests for Story 37.6: pitch-portal engagement beacon (AD-120).

Covers AC-2 (30-minute Redis cooldown, silent timeline updates),
AC-3 (crawler UA + <3s dwell filtering), and AC-4 (Zalo deep-link).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.pitch_engagement import (
    MIN_DWELL_SECONDS,
    PITCH_BEACON_LOCK_TTL_SECONDS,
    build_zalo_deep_link,
    classify_device_type,
    is_crawler_user_agent,
    pitch_beacon_lock_key,
    record_pitch_beacon,
    resolve_pitch_workspace_id,
    sanitize_sections_viewed,
)

CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)


def _lead(**overrides):
    defaults = {
        "id": uuid4(),
        "workspace_id": 7,
        "company_name": "Công ty ABC",
        "assigned_to_user_id": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _redis(set_result=True):
    redis = MagicMock()
    redis.set = AsyncMock(return_value=set_result)
    return redis


def _session():
    """AsyncSession stand-in; ``add`` stays sync like the real session."""
    session = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.mark.unit
class TestCrawlerFilter:
    """AC-3: crawler user-agents are preview pings, not views."""

    @pytest.mark.parametrize(
        "ua",
        [
            "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
            "ZaloPC-crawler/2.0",
            "Mozilla/5.0 (compatible; Googlebot/2.1)",
            "TelegramBot (like TwitterBot)",
            "Slackbot-LinkExpanding 1.0",
            "WhatsApp/2.23",
            "Mozilla/5.0 HeadlessChrome/120.0",
        ],
    )
    def test_crawlers_detected(self, ua):
        assert is_crawler_user_agent(ua) is True

    @pytest.mark.parametrize(
        "ua",
        [
            CHROME_UA,
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604.1",
            None,
            "",
        ],
    )
    def test_humans_pass(self, ua):
        assert is_crawler_user_agent(ua) is False


@pytest.mark.unit
class TestDeviceClassification:
    def test_mobile(self):
        assert (
            classify_device_type(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
            )
            == "mobile"
        )

    def test_tablet(self):
        assert classify_device_type("Mozilla/5.0 (iPad; CPU OS 17_0)") == "tablet"

    def test_desktop_default(self):
        assert classify_device_type(CHROME_UA) == "desktop"
        assert classify_device_type(None) == "desktop"


@pytest.mark.unit
class TestZaloDeepLink:
    def test_local_vn_number(self):
        assert build_zalo_deep_link("0901 234 567") == "https://zalo.me/84901234567"

    def test_international_format(self):
        assert build_zalo_deep_link("+84 901-234-567") == "https://zalo.me/84901234567"

    def test_empty(self):
        assert build_zalo_deep_link(None) is None
        assert build_zalo_deep_link("abc") is None


@pytest.mark.unit
class TestSectionSanitization:
    def test_keeps_well_formed_ids(self):
        assert sanitize_sections_viewed(["hero", "roi-calc", "booking_cta"]) == [
            "hero",
            "roi-calc",
            "booking_cta",
        ]

    def test_drops_untrusted_values(self):
        assert sanitize_sections_viewed(
            ["hero", "<script>alert(1)</script>", 42, None, "x" * 65]
        ) == ["hero"]

    def test_non_list(self):
        assert sanitize_sections_viewed("hero") == []
        assert sanitize_sections_viewed(None) == []


@pytest.mark.unit
class TestRecordPitchBeacon:
    """AC-2/AC-3/AC-4: filtering, cooldown, timeline writes."""

    @pytest.mark.asyncio
    async def test_crawler_filtered_before_any_writes(self):
        session = _session()
        redis = _redis()
        outcome = await record_pitch_beacon(
            session,
            redis,
            lead=_lead(),
            dwell_seconds=60,
            sections_viewed=["hero"],
            device_type=None,
            session_id=None,
            event="open",
            user_agent="facebookexternalhit/1.1",
        )
        assert outcome == "filtered_crawler"
        session.add.assert_not_called()
        redis.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_short_dwell_filtered(self):
        session = _session()
        redis = _redis()
        outcome = await record_pitch_beacon(
            session,
            redis,
            lead=_lead(),
            dwell_seconds=MIN_DWELL_SECONDS - 0.5,
            sections_viewed=[],
            device_type="mobile",
            session_id=None,
            event="close",
            user_agent=CHROME_UA,
        )
        assert outcome == "filtered_short_dwell"
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_first_view_alerts_and_logs(self):
        session = _session()
        redis = _redis(set_result=True)
        lead = _lead()
        with patch(
            "app.services.pitch_engagement._dispatch_telegram_alert",
            new=AsyncMock(return_value=True),
        ) as dispatch:
            outcome = await record_pitch_beacon(
                session,
                redis,
                lead=lead,
                dwell_seconds=12.0,
                sections_viewed=["hero"],
                device_type=None,
                session_id="s1",
                event="open",
                user_agent=CHROME_UA,
            )
        assert outcome == "recorded_alerted"
        redis.set.assert_awaited_once_with(
            pitch_beacon_lock_key(lead.id),
            "1",
            nx=True,
            ex=PITCH_BEACON_LOCK_TTL_SECONDS,
        )
        dispatch.assert_awaited_once()
        session.add.assert_called_once()
        log = session.add.call_args.args[0]
        assert log.activity_type == "pitch_portal_view"
        assert log.details["dwell_seconds"] == 12.0
        assert log.details["telegram_alerted"] is True
        assert log.details["device_type"] == "desktop"  # UA fallback

    @pytest.mark.asyncio
    async def test_cooldown_records_silently(self):
        session = _session()
        redis = _redis(set_result=None)  # lock already held
        with patch(
            "app.services.pitch_engagement._dispatch_telegram_alert",
            new=AsyncMock(),
        ) as dispatch:
            outcome = await record_pitch_beacon(
                session,
                redis,
                lead=_lead(),
                dwell_seconds=45.0,
                sections_viewed=["roi"],
                device_type="mobile",
                session_id="s1",
                event="heartbeat",
                user_agent=CHROME_UA,
            )
        assert outcome == "recorded_silent"
        dispatch.assert_not_called()
        session.add.assert_called_once()
        assert session.add.call_args.args[0].details["telegram_alerted"] is False

    @pytest.mark.asyncio
    async def test_redis_failure_fails_closed(self):
        session = _session()
        redis = _redis()
        redis.set = AsyncMock(side_effect=ConnectionError("redis down"))
        with patch(
            "app.services.pitch_engagement._dispatch_telegram_alert",
            new=AsyncMock(),
        ) as dispatch:
            outcome = await record_pitch_beacon(
                session,
                redis,
                lead=_lead(),
                dwell_seconds=10.0,
                sections_viewed=[],
                device_type=None,
                session_id=None,
                event="open",
                user_agent=CHROME_UA,
            )
        assert outcome == "recorded_silent"
        dispatch.assert_not_called()
        session.add.assert_called_once()


@pytest.mark.unit
class TestWorkspaceRefResolution:
    @pytest.mark.asyncio
    async def test_numeric_ref_maps_to_workspace_id(self):
        session = _session()
        assert await resolve_pitch_workspace_id(session, "42") == 42
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_slug_resolves_via_published_app(self):
        session = _session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = 9
        session.execute.return_value = result
        assert await resolve_pitch_workspace_id(session, "acme-sales") == 9

    @pytest.mark.asyncio
    async def test_unknown_slug_returns_none(self):
        session = _session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute.return_value = result
        assert await resolve_pitch_workspace_id(session, "nope") is None
