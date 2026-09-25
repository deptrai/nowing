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
    PreparedPitchAlert,
    _dispatch_telegram_alert,
    _format_alert_message,
    _resolve_alert_recipient_id,
    _resolve_zalo_deep_link,
    build_zalo_deep_link,
    classify_device_type,
    dispatch_prepared_pitch_alert,
    is_crawler_user_agent,
    mark_pitch_beacon_alerted,
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
    redis.delete = AsyncMock()
    return redis


def _session(execute_scalar=None):
    """AsyncSession stand-in; ``add`` stays sync like the real session.

    ``execute()`` returns a result whose ``scalar_one_or_none`` yields
    ``execute_scalar`` (default None = "no existing timeline row").
    """
    session = AsyncMock()
    session.add = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = execute_scalar
    session.execute = AsyncMock(return_value=result)
    return session


def _prepared_alert() -> PreparedPitchAlert:
    return PreparedPitchAlert(
        token="tok", external_peer_id="peer-1", text="alert text"
    )


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
            "WhatsApp/2.23.20.0",  # bare product token = link-preview fetcher
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
            # Zalo/WhatsApp in-app browsers keep the product token inside a
            # full Mozilla UA — real prospects, not preview pings.
            "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Zalo/24.0 Mobile",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) AppleWebKit/605.1.15 WhatsApp/2.24",
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
        result = await record_pitch_beacon(
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
        assert result.outcome == "filtered_crawler"
        session.add.assert_not_called()
        redis.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_short_dwell_filtered(self):
        session = _session()
        redis = _redis()
        result = await record_pitch_beacon(
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
        assert result.outcome == "filtered_short_dwell"
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_first_view_prepares_alert_and_logs(self):
        session = _session()
        redis = _redis(set_result=True)
        lead = _lead()
        with patch(
            "app.services.pitch_engagement._prepare_telegram_alert",
            new=AsyncMock(return_value=_prepared_alert()),
        ) as prepare:
            result = await record_pitch_beacon(
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
        # The send is deferred to post-commit dispatch — the service only
        # prepares it and the flag flips via mark_pitch_beacon_alerted.
        assert result.outcome == "recorded_pending_alert"
        assert result.alert is not None
        redis.set.assert_awaited_once_with(
            pitch_beacon_lock_key(lead.id),
            "1",
            nx=True,
            ex=PITCH_BEACON_LOCK_TTL_SECONDS,
        )
        prepare.assert_awaited_once()
        session.add.assert_called_once()
        log = session.add.call_args.args[0]
        assert result.activity_log is log
        assert log.activity_type == "pitch_portal_view"
        assert log.details["dwell_seconds"] == 12.0
        assert log.details["telegram_alerted"] is False
        assert log.details["device_type"] == "desktop"  # UA fallback

    @pytest.mark.asyncio
    async def test_cooldown_records_silently(self):
        session = _session()
        redis = _redis(set_result=None)  # lock already held
        with patch(
            "app.services.pitch_engagement._prepare_telegram_alert",
            new=AsyncMock(),
        ) as prepare:
            result = await record_pitch_beacon(
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
        assert result.outcome == "recorded_silent"
        assert result.alert is None
        prepare.assert_not_called()
        session.add.assert_called_once()
        assert session.add.call_args.args[0].details["telegram_alerted"] is False

    @pytest.mark.asyncio
    async def test_redis_failure_fails_closed(self):
        session = _session()
        redis = _redis()
        redis.set = AsyncMock(side_effect=ConnectionError("redis down"))
        with patch(
            "app.services.pitch_engagement._prepare_telegram_alert",
            new=AsyncMock(),
        ) as prepare:
            result = await record_pitch_beacon(
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
        assert result.outcome == "recorded_silent"
        prepare.assert_not_called()
        session.add.assert_called_once()


@pytest.mark.unit
class TestWorkspaceRefResolution:
    @pytest.mark.asyncio
    async def test_numeric_ref_maps_to_workspace_id(self):
        session = _session()
        assert await resolve_pitch_workspace_id(session, "42") == 42
        session.execute.assert_not_called()

    def _slug_session(self, rows):
        session = _session()
        result = MagicMock()
        result.all.return_value = rows
        session.execute = AsyncMock(return_value=result)
        return session

    def _row(self, workspace_id, status):
        return SimpleNamespace(workspace_id=workspace_id, status=status)

    @pytest.mark.asyncio
    async def test_slug_resolves_via_published_app(self):
        session = self._slug_session([self._row(9, "published")])
        assert await resolve_pitch_workspace_id(session, "acme-sales") == 9

    @pytest.mark.asyncio
    async def test_unknown_slug_returns_none(self):
        session = self._slug_session([])
        assert await resolve_pitch_workspace_id(session, "nope") is None

    @pytest.mark.asyncio
    async def test_unpublished_slug_still_resolves_when_unambiguous(self):
        # Link permanence: unpublishing the app must not 404 already-sent
        # pitch links when the slug maps to exactly one workspace.
        session = self._slug_session([self._row(9, "archived")])
        assert await resolve_pitch_workspace_id(session, "acme-sales") == 9

    @pytest.mark.asyncio
    async def test_published_row_wins_over_ambiguous_duplicates(self):
        session = self._slug_session(
            [self._row(9, "archived"), self._row(11, "published")]
        )
        assert await resolve_pitch_workspace_id(session, "acme-sales") == 11

    @pytest.mark.asyncio
    async def test_ambiguous_unpublished_slug_returns_none(self):
        session = self._slug_session(
            [self._row(9, "draft"), self._row(11, "archived")]
        )
        assert await resolve_pitch_workspace_id(session, "acme-sales") is None


@pytest.mark.unit
class TestDispatchGuardAndLockRelease:
    """record_pitch_beacon: unsendable alerts stay silent + release the lock."""

    @pytest.mark.asyncio
    async def test_prepare_exception_still_logs_and_releases_lock(self):
        session = _session()
        redis = _redis(set_result=True)
        lead = _lead()
        with patch(
            "app.services.pitch_engagement._prepare_telegram_alert",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            result = await record_pitch_beacon(
                session,
                redis,
                lead=lead,
                dwell_seconds=10.0,
                sections_viewed=[],
                device_type=None,
                session_id=None,
                event="open",
                user_agent=CHROME_UA,
            )
        assert result.outcome == "recorded_silent"
        assert result.alert is None
        redis.delete.assert_awaited_once_with(pitch_beacon_lock_key(lead.id))
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_unsendable_alert_releases_lock(self):
        session = _session()
        redis = _redis(set_result=True)
        lead = _lead()
        with patch(
            "app.services.pitch_engagement._prepare_telegram_alert",
            new=AsyncMock(return_value=None),  # e.g. no Telegram binding
        ):
            result = await record_pitch_beacon(
                session,
                redis,
                lead=lead,
                dwell_seconds=10.0,
                sections_viewed=[],
                device_type=None,
                session_id=None,
                event="open",
                user_agent=CHROME_UA,
            )
        assert result.outcome == "recorded_silent"
        redis.delete.assert_awaited_once_with(pitch_beacon_lock_key(lead.id))

    @pytest.mark.asyncio
    async def test_prepared_alert_keeps_lock(self):
        session = _session()
        redis = _redis(set_result=True)
        lead = _lead()
        with patch(
            "app.services.pitch_engagement._prepare_telegram_alert",
            new=AsyncMock(return_value=_prepared_alert()),
        ):
            result = await record_pitch_beacon(
                session,
                redis,
                lead=lead,
                dwell_seconds=10.0,
                sections_viewed=[],
                device_type=None,
                session_id=None,
                event="open",
                user_agent=CHROME_UA,
            )
        assert result.outcome == "recorded_pending_alert"
        redis.delete.assert_not_called()


@pytest.mark.unit
class TestSessionDedupe:
    """Repeat beacons in one session update the same timeline row."""

    @pytest.mark.asyncio
    async def test_heartbeat_updates_existing_row(self):
        existing = SimpleNamespace(
            details={
                "dwell_seconds": 4.0,
                "sections_viewed": ["hero"],
                "telegram_alerted": True,
            },
            title="Xem mini-pitch portal (4s)",
        )
        session = _session(execute_scalar=existing)
        redis = _redis(set_result=None)  # inside cooldown
        with patch(
            "app.services.pitch_engagement._prepare_telegram_alert",
            new=AsyncMock(),
        ):
            result = await record_pitch_beacon(
                session,
                redis,
                lead=_lead(),
                dwell_seconds=34.0,
                sections_viewed=["hero", "roi"],
                device_type="mobile",
                session_id="sess-1",
                event="heartbeat",
                user_agent=CHROME_UA,
            )
        assert result.outcome == "recorded_silent"
        session.add.assert_not_called()
        assert existing.details["dwell_seconds"] == 34.0
        assert existing.details["sections_viewed"] == ["hero", "roi"]
        assert existing.details["event"] == "heartbeat"
        assert existing.details["telegram_alerted"] is True  # preserved
        assert existing.title == "Xem mini-pitch portal (34s)"

    @pytest.mark.asyncio
    async def test_first_event_of_session_inserts(self):
        session = _session(execute_scalar=None)  # no prior row for session
        redis = _redis(set_result=None)
        result = await record_pitch_beacon(
            session,
            redis,
            lead=_lead(),
            dwell_seconds=5.0,
            sections_viewed=["hero"],
            device_type="desktop",
            session_id="sess-new",
            event="open",
            user_agent=CHROME_UA,
        )
        assert result.outcome == "recorded_silent"
        session.add.assert_called_once()


@pytest.mark.unit
class TestPostCommitDispatch:
    """The send runs post-commit via dispatch_prepared_pitch_alert (review
    37.6: the network call must not sit inside the open DB transaction)."""

    @pytest.mark.asyncio
    async def test_dispatch_sends_prepared_payload(self):
        adapter_cls = MagicMock()
        adapter_cls.return_value.send_message = AsyncMock()
        alert = _prepared_alert()
        with patch(
            "app.gateway.telegram.adapter.TelegramAdapter", adapter_cls
        ):
            sent = await dispatch_prepared_pitch_alert(alert)
        assert sent is True
        adapter_cls.assert_called_once_with("tok")
        kwargs = adapter_cls.return_value.send_message.await_args.kwargs
        assert kwargs["external_peer_id"] == "peer-1"
        assert kwargs["parse_mode"] == "MarkdownV2"

    @pytest.mark.asyncio
    async def test_dispatch_failure_returns_false(self):
        adapter_cls = MagicMock()
        adapter_cls.return_value.send_message = AsyncMock(
            side_effect=RuntimeError("telegram down")
        )
        with patch(
            "app.gateway.telegram.adapter.TelegramAdapter", adapter_cls
        ):
            sent = await dispatch_prepared_pitch_alert(_prepared_alert())
        assert sent is False

    @pytest.mark.asyncio
    async def test_mark_alerted_flips_flag_on_row(self):
        log = SimpleNamespace(details={"telegram_alerted": False, "x": 1})
        await mark_pitch_beacon_alerted(AsyncMock(), log)
        assert log.details["telegram_alerted"] is True
        assert log.details["x"] == 1


@pytest.mark.unit
class TestDispatchTelegramAlert:
    """AC-4: real dispatch chain (Telegram adapter mocked at boundary)."""

    def _binding(self):
        return SimpleNamespace(
            external_peer_id="peer-123",
            account_id=5,
            account=SimpleNamespace(),
        )

    @pytest.mark.asyncio
    async def test_sends_markdown_v2_to_resolved_peer(self):
        session = _session(execute_scalar=None)  # no verified phone
        lead = _lead(assigned_to_user_id=uuid4())
        adapter_cls = MagicMock()
        adapter_cls.return_value.send_message = AsyncMock()
        with (
            patch(
                "app.automations.services.telegram_notifications."
                "resolve_telegram_binding_for_run",
                new=AsyncMock(return_value=self._binding()),
            ),
            patch("app.gateway.accounts.account_token", return_value="tok"),
            patch("app.gateway.telegram.adapter.TelegramAdapter", adapter_cls),
        ):
            sent = await _dispatch_telegram_alert(
                session,
                lead,
                dwell_seconds=42.0,
                sections_viewed=["hero"],
                device_type="mobile",
            )
        assert sent is True
        kwargs = adapter_cls.return_value.send_message.await_args.kwargs
        assert kwargs["external_peer_id"] == "peer-123"
        assert kwargs["parse_mode"] == "MarkdownV2"
        assert "42s" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_no_binding_returns_false(self):
        session = _session()
        lead = _lead(assigned_to_user_id=uuid4())
        with patch(
            "app.automations.services.telegram_notifications."
            "resolve_telegram_binding_for_run",
            new=AsyncMock(return_value=None),
        ):
            sent = await _dispatch_telegram_alert(
                session,
                lead,
                dwell_seconds=10.0,
                sections_viewed=[],
                device_type="desktop",
            )
        assert sent is False

    @pytest.mark.asyncio
    async def test_no_recipient_returns_false(self):
        session = _session(execute_scalar=None)
        session.get = AsyncMock(return_value=None)  # no workspace owner either
        lead = _lead(assigned_to_user_id=None)
        with patch(
            "app.automations.services.telegram_notifications."
            "resolve_telegram_binding_for_run",
            new=AsyncMock(),
        ) as resolve:
            sent = await _dispatch_telegram_alert(
                session,
                lead,
                dwell_seconds=10.0,
                sections_viewed=[],
                device_type="desktop",
            )
        assert sent is False
        resolve.assert_not_called()


@pytest.mark.unit
class TestZaloLinkResolution:
    @pytest.mark.asyncio
    async def test_encrypted_phone_is_decrypted(self):
        from app.services.pii.verified_contact_encryption import (
            VerifiedContactEncryption,
        )

        enc = VerifiedContactEncryption(secret_key="unit-test-key")
        ciphertext = enc.encrypt("0901234567")
        assert ciphertext != "0901234567"

        session = _session(execute_scalar=ciphertext)
        with patch(
            "app.services.pii.verified_contact_encryption."
            "VerifiedContactEncryption",
            return_value=enc,
        ):
            link = await _resolve_zalo_deep_link(session, _lead())
        assert link == "https://zalo.me/84901234567"

    @pytest.mark.asyncio
    async def test_plaintext_phone_still_works(self):
        session = _session(execute_scalar="+84 912 345 678")
        with patch(
            "app.services.pii.verified_contact_encryption."
            "VerifiedContactEncryption",
        ) as enc_cls:
            enc_cls.return_value.is_encrypted.return_value = False
            link = await _resolve_zalo_deep_link(session, _lead())
        enc_cls.return_value.is_encrypted.assert_called_once()
        assert link == "https://zalo.me/84912345678"

    @pytest.mark.asyncio
    async def test_no_contact_returns_none(self):
        session = _session(execute_scalar=None)
        assert await _resolve_zalo_deep_link(session, _lead()) is None


@pytest.mark.unit
class TestRecipientFallback:
    """AC-4: assigned rep → latest assignment → workspace owner."""

    @pytest.mark.asyncio
    async def test_assigned_to_user_wins(self):
        owner = uuid4()
        session = _session()
        result = await _resolve_alert_recipient_id(
            session, _lead(assigned_to_user_id=owner)
        )
        assert result == owner
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_latest_assignment(self):
        assignee = uuid4()
        session = _session(execute_scalar=assignee)
        result = await _resolve_alert_recipient_id(session, _lead())
        assert result == assignee

    @pytest.mark.asyncio
    async def test_falls_back_to_workspace_owner(self):
        owner = uuid4()
        session = _session(execute_scalar=None)
        session.get = AsyncMock(
            return_value=SimpleNamespace(user_id=owner)
        )
        result = await _resolve_alert_recipient_id(session, _lead())
        assert result == owner


@pytest.mark.unit
class TestAlertMessageFormat:
    def test_markdown_v2_escapes_dynamic_fields(self):
        lead = _lead(company_name="Công ty *ABC* (VN).")
        with patch(
            "app.services.pitch_engagement.config",
            SimpleNamespace(NEXT_FRONTEND_URL="https://app.test"),
        ):
            text = _format_alert_message(
                lead=lead,
                dwell_seconds=42.0,
                sections_viewed=["hero"],
                device_type="mobile",
                zalo_link="https://zalo.me/84901234567",
            )
        # Reserved MarkdownV2 chars in the company name are escaped…
        assert "\\*ABC\\*" in text
        assert "\\(VN\\)\\." in text
        # …while generated markdown links stay raw.
        assert "[💬 Chat Zalo ngay](https://zalo.me/84901234567)" in text
        assert f"/dashboard/{lead.workspace_id}/leads/pipeline" in text
