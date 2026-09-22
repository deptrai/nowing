"""Unit tests for Story 37.3: Smart Meeting Booking Engine for Auto-Reply.

Covers AD-117 (Redis soft-lock + strict UTC storage / ICT rendering),
AC-1 (working-hour free/busy), AC-3 (2-3 ICT-formatted proposals),
AC-4 (booking + CRM sync), AC-5 (2-turn negotiation fallback).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, time, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

from app.services.meeting_booking import (
    MAX_NEGOTIATION_TURNS,
    SLOT_LOCK_TTL_SECONDS,
    CalendarCredentials,
    CalendarSlot,
    MeetingBookingService,
    _BookingState,
    compute_free_slots,
    detect_generic_confirmation,
    detect_meeting_intent,
    detect_slot_rejection,
    parse_slot_choice,
    select_proposals,
)

ICT = ZoneInfo("Asia/Ho_Chi_Minh")

# 2026-09-21 is a Monday.
MONDAY_8AM_ICT = datetime(2026, 9, 21, 8, 0, tzinfo=ICT)


def _credentials(provider: str = "google_native") -> list[CalendarCredentials]:
    return [
        CalendarCredentials(
            provider=provider,
            connector_id=7,
            user_id="user-abc",
            config={},
        )
    ]


def _future_slot_ict(hour: int = 14, minute: int = 0) -> CalendarSlot:
    """A 30-min slot at ``hour:minute`` ICT on the next business day."""
    day = (datetime.now(ICT) + timedelta(days=1)).date()
    while day.weekday() >= 5:
        day += timedelta(days=1)
    start = datetime.combine(day, time(hour, minute), tzinfo=ICT)
    return CalendarSlot(start=start, end=start + timedelta(minutes=30))


@pytest.mark.unit
class TestSlotComputation:
    """AC-1: working hours / business days / 15-min buffer."""

    def test_slots_only_inside_working_windows(self):
        slots = compute_free_slots([], now=MONDAY_8AM_ICT, days=5)
        assert slots
        for slot in slots:
            local = slot.start_ict()
            assert local.weekday() < 5  # Mon-Fri only
            minute = local.hour * 60 + local.minute
            end_minute = minute + (slot.end - slot.start).seconds // 60
            in_morning = minute >= 9 * 60 and end_minute <= 12 * 60
            in_afternoon = minute >= 13 * 60 + 30 and end_minute <= 17 * 60 + 30
            assert in_morning or in_afternoon

    def test_weekends_skipped_and_five_business_days(self):
        # Friday 08:00 ICT → weekend must be skipped; days = Fri + next Mon-Thu.
        friday = datetime(2026, 9, 25, 8, 0, tzinfo=ICT)
        slots = compute_free_slots([], now=friday, days=5)
        days = {s.start_ict().date() for s in slots}
        assert len(days) == 5
        assert all(d.weekday() < 5 for d in days)

    def test_buffer_blocks_adjacent_slots(self):
        # Existing event 10:00-11:00 ICT Monday → 09:45-11:15 is buffered out.
        busy = [
            (
                datetime(2026, 9, 21, 10, 0, tzinfo=ICT),
                datetime(2026, 9, 21, 11, 0, tzinfo=ICT),
            )
        ]
        slots = compute_free_slots(
            busy, now=MONDAY_8AM_ICT, days=1, slot_minutes=30
        )
        starts = {s.start_ict().strftime("%H:%M") for s in slots}
        # 09:30 slot ends 10:00 - overlaps the 09:45 buffer start → excluded.
        assert "09:30" not in starts
        # 11:00 slot starts inside 11:15 buffer → excluded.
        assert "11:00" not in starts
        # 09:00 ends 09:30 < 09:45 buffer → allowed; 11:30 > 11:15 → allowed.
        assert "09:00" in starts
        assert "11:30" in starts

    def test_past_slots_excluded(self):
        now = datetime(2026, 9, 21, 10, 30, tzinfo=ICT)
        slots = compute_free_slots([], now=now, days=1)
        assert all(
            s.start_ict() >= now + timedelta(minutes=30) for s in slots
        )

    def test_utc_storage_ict_rendering(self):
        slot = CalendarSlot(
            start=datetime(2026, 9, 22, 7, 0, tzinfo=UTC),  # 14:00 ICT Tuesday
            end=datetime(2026, 9, 22, 7, 30, tzinfo=UTC),
        )
        assert slot.label_ict() == "14:00 Thứ Ba"
        assert "T" in slot.to_dict()["start"]  # ISO-8601 stored


@pytest.mark.unit
class TestIntentParsing:
    """AC-3/AC-5 message parsing helpers."""

    def test_meeting_intent_phrases(self):
        assert detect_meeting_intent("Em muốn đặt lịch hẹn gặp tư vấn")
        assert detect_meeting_intent("Cho mình xin lịch hẹn xem nhà")
        assert detect_meeting_intent("Can we schedule a meeting?")
        assert not detect_meeting_intent("Giá bao nhiêu vậy?")
        assert not detect_meeting_intent(None)

    def test_rejection_phrases(self):
        assert detect_slot_rejection("Hôm đó mình bận rồi")
        assert detect_slot_rejection("Không được, đổi lịch khác đi")
        assert not detect_slot_rejection("Được đấy, chốt luôn")
        assert not detect_slot_rejection(None)

    def test_generic_confirmation(self):
        for phrase in ("ok", "Ok", "được ạ", "chốt", "đồng ý", "xác nhận"):
            assert detect_generic_confirmation(phrase), phrase
        assert not detect_generic_confirmation("không được")
        assert not detect_generic_confirmation("Cho mình hỏi thêm")

    def test_parse_slot_choice_by_time(self):
        slots = [
            CalendarSlot(
                start=datetime(2026, 9, 22, 7, 0, tzinfo=UTC),
                end=datetime(2026, 9, 22, 7, 30, tzinfo=UTC),
            ),
            CalendarSlot(
                start=datetime(2026, 9, 23, 3, 0, tzinfo=UTC),
                end=datetime(2026, 9, 23, 3, 30, tzinfo=UTC),
            ),
        ]
        assert parse_slot_choice("Chốt 14:00 nhé", slots) == 0
        assert parse_slot_choice("Mình chọn 10h thứ năm", slots) == 1
        assert parse_slot_choice("option 2 đi", slots) == 1
        assert parse_slot_choice("cái đầu tiên", slots) == 0
        assert parse_slot_choice("không liên quan", slots) is None

    def test_parse_slot_choice_vietnamese_edge_cases(self):
        # Slot 0: 14:00 ICT Mon 2026-09-21; slot 1: 10:00 ICT Tue 2026-09-22.
        slots = [
            CalendarSlot(
                start=datetime(2026, 9, 21, 7, 0, tzinfo=UTC),
                end=datetime(2026, 9, 21, 7, 30, tzinfo=UTC),
            ),
            CalendarSlot(
                start=datetime(2026, 9, 22, 3, 0, tzinfo=UTC),
                end=datetime(2026, 9, 22, 3, 30, tzinfo=UTC),
            ),
        ]
        # "chiều" shifts a bare hour into PM.
        assert parse_slot_choice("2 giờ chiều", slots) == 0
        # "thứ hai" is Monday (weekday wins over the ordinal sense).
        assert parse_slot_choice("thứ hai", slots) == 0
        assert parse_slot_choice("thứ ba đi", slots) == 1
        # Bare digit picks the ordinal slot.
        assert parse_slot_choice("2", slots) == 1
        # An explicit time inside a re-schedule phrase still resolves.
        assert parse_slot_choice("đổi sang 14:00", slots) == 0

    def test_negated_phrases_are_not_intent_or_rejection(self):
        assert not detect_slot_rejection("không bận đâu")
        assert not detect_meeting_intent("không cần hẹn")
        assert not detect_meeting_intent("chưa cần đặt lịch")
        # ...but the non-negated forms still trigger.
        assert detect_slot_rejection("Hôm đó mình bận")
        assert detect_meeting_intent("anh hẹn em xem nhà")


@pytest.mark.unit
class TestSoftLock:
    """AC-2 / AD-117: Redis soft-lock key shape and TTL."""

    @pytest.mark.asyncio
    async def test_lock_key_and_ttl(self):
        redis = AsyncMock()
        redis.set.return_value = True
        service = MeetingBookingService(session=AsyncMock(), redis_client=redis)

        slot = CalendarSlot(
            start=datetime(2026, 9, 22, 7, 0, tzinfo=UTC),
            end=datetime(2026, 9, 22, 7, 30, tzinfo=UTC),
        )
        locked, token = await service.soft_lock_slots("user-1", [slot])

        assert locked == [slot]
        assert token  # unique ownership token generated
        key = f"lock:calendar_slot:user-1:{slot.lock_timestamp()}"
        redis.set.assert_awaited_once_with(
            key, token, ex=SLOT_LOCK_TTL_SECONDS, nx=True
        )
        assert SLOT_LOCK_TTL_SECONDS == 900

    @pytest.mark.asyncio
    async def test_release_only_deletes_owned_locks(self):
        redis = AsyncMock()
        service = MeetingBookingService(session=AsyncMock(), redis_client=redis)
        slot = CalendarSlot(
            start=datetime(2026, 9, 22, 7, 0, tzinfo=UTC),
            end=datetime(2026, 9, 22, 7, 30, tzinfo=UTC),
        )
        key = f"lock:calendar_slot:user-1:{slot.lock_timestamp()}"

        await service.release_slot_locks("user-1", [slot], "tok-abc")
        redis.eval.assert_awaited_once_with(
            service._RELEASE_LOCK_LUA, 1, key, "tok-abc"
        )
        redis.delete.assert_not_awaited()

        # No token → never delete (the lock may belong to someone else).
        redis.reset_mock()
        await service.release_slot_locks("user-1", [slot])
        redis.eval.assert_not_awaited()
        redis.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_contended_slots_are_skipped(self):
        redis = AsyncMock()
        redis.set.side_effect = [None, True]  # first slot already locked
        service = MeetingBookingService(session=AsyncMock(), redis_client=redis)
        slots = [
            CalendarSlot(
                start=datetime(2026, 9, 22, 7, 0, tzinfo=UTC),
                end=datetime(2026, 9, 22, 7, 30, tzinfo=UTC),
            ),
            CalendarSlot(
                start=datetime(2026, 9, 22, 8, 0, tzinfo=UTC),
                end=datetime(2026, 9, 22, 8, 30, tzinfo=UTC),
            ),
        ]
        locked, _token = await service.soft_lock_slots("user-1", slots)
        assert locked == [slots[1]]


@pytest.mark.unit
class TestBookingFlow:
    """AC-3/4/5: propose → confirm → book → escalate."""

    def _service(self, redis: AsyncMock) -> MeetingBookingService:
        session = AsyncMock()
        session.add = MagicMock()  # Session.add is sync; keep it non-async
        empty_result = MagicMock()
        empty_result.scalars.return_value.first.return_value = None
        session.execute.return_value = empty_result
        service = MeetingBookingService(session=session, redis_client=redis)
        service.availability.resolve_credentials = AsyncMock(
            return_value=_credentials()
        )
        return service

    @pytest.mark.asyncio
    async def test_propose_returns_2_to_3_ict_options(self):
        redis = AsyncMock()
        redis.get.return_value = None
        redis.set.return_value = True
        service = self._service(redis)

        with patch.object(
            service.availability,
            "get_busy_intervals",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await service.handle_turn(
                15, "th_1", "Mình muốn đặt lịch hẹn tư vấn"
            )

        assert result is not None
        assert result.reason == "slots_proposed"
        # 2-3 options rendered with ICT weekday names.
        assert "Thứ" in result.reply_text
        assert result.reply_text.count("\n") >= 2
        # State persisted with the proposed slots.
        state_writes = [
            c for c in redis.set.await_args_list
            if str(c.args[0]).startswith("meeting_booking:state:")
        ]
        assert state_writes, "booking state must be saved"

    @pytest.mark.asyncio
    async def test_confirmation_books_and_syncs_crm(self):
        slot = _future_slot_ict(14, 0)
        state = _BookingState(
            user_id="user-abc", slots=[slot], rejections=0, lock_token="tok1"
        )

        redis = AsyncMock()
        redis.get.return_value = json.dumps(state.to_dict())
        redis.set.return_value = True
        service = self._service(redis)
        service.availability.create_event = AsyncMock(
            return_value=("evt-1", "https://meet.google.com/xyz")
        )

        lead = SimpleNamespace(
            id="lead-1", workspace_id=15, status="new", version=1, stage_id=None
        )

        result = await service.handle_turn(
            15, "th_1", "Chốt 14:00 nhé", lead=lead
        )

        assert result is not None and result.booked is True
        assert result.meeting_link == "https://meet.google.com/xyz"
        assert lead.status == "meeting_scheduled"
        assert lead.version == 2
        service.availability.create_event.assert_awaited_once()
        # Owned soft-locks released via compare-and-delete, state cleared.
        assert redis.eval.await_count == 1
        redis.delete.assert_awaited_once()  # booking state key

    @pytest.mark.asyncio
    async def test_stale_confirm_fails_when_lock_lost(self):
        """State outlives the 15-min lock: re-validation must fail closed."""
        slot = _future_slot_ict(14, 0)
        state = _BookingState(
            user_id="user-abc", slots=[slot], rejections=0, lock_token="tok1"
        )
        state_json = json.dumps(state.to_dict())

        redis = AsyncMock()

        async def _get(key):
            # State key returns the saved conversation; the lock key is now
            # held by another conversation's token.
            if str(key).startswith("meeting_booking:state:"):
                return state_json
            return "someone-elses-token"

        redis.get.side_effect = _get
        redis.set.return_value = None  # NX acquire fails - key exists
        service = self._service(redis)
        service.availability.create_event = AsyncMock()

        result = await service.handle_turn(
            15, "th_1", "Chốt 14:00 nhé", lead=None
        )

        assert result is not None and result.booked is False
        assert result.reason == "booking_failed"
        service.availability.create_event.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_past_slot_never_books(self):
        slot = CalendarSlot(
            start=datetime.now(UTC) - timedelta(hours=2),
            end=datetime.now(UTC) - timedelta(hours=1, minutes=30),
        )
        service = self._service(AsyncMock())
        result = await service.book_slot(15, "user-abc", slot)
        assert result.reason == "slot_past"
        assert result.booked is False

    @pytest.mark.asyncio
    async def test_two_rejections_escalate_with_booking_link(self):
        slot = CalendarSlot(
            start=datetime(2026, 9, 22, 7, 0, tzinfo=UTC),
            end=datetime(2026, 9, 22, 7, 30, tzinfo=UTC),
        )
        state = _BookingState(
            user_id="user-abc",
            slots=[slot],
            rejections=MAX_NEGOTIATION_TURNS - 1,
            lock_token="tok1",
        )
        redis = AsyncMock()
        redis.get.return_value = json.dumps(state.to_dict())
        redis.set.return_value = True
        service = self._service(redis)

        lead = SimpleNamespace(id="lead-9", workspace_id=15)
        result = await service.handle_turn(
            15, "th_1", "Hôm đó mình bận, lịch khác đi", lead=lead
        )

        assert result is not None and result.escalated is True
        assert "/book/15/lead-9" in result.reply_text
        # Lead timeline gets the human_takeover_needed tag.
        service.session.add.assert_called()

    @pytest.mark.asyncio
    async def test_non_meeting_text_falls_through(self):
        redis = AsyncMock()
        redis.get.return_value = None
        service = self._service(redis)
        result = await service.handle_turn(15, "th_1", "Giá bao nhiêu?")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_credentials_falls_through(self):
        redis = AsyncMock()
        redis.get.return_value = None
        service = MeetingBookingService(
            session=AsyncMock(), redis_client=redis
        )
        service.availability.resolve_credentials = AsyncMock(return_value=[])
        result = await service.handle_turn(15, "th_1", "đặt lịch hẹn giúp mình")
        assert result is None


@pytest.mark.unit
class TestSelectProposals:
    def test_spreads_across_days(self):
        free = compute_free_slots([], now=MONDAY_8AM_ICT, days=5)
        picked = select_proposals(free, count=3)
        assert 2 <= len(picked) <= 3
        days = {s.start_ict().date() for s in picked}
        assert len(days) == len(picked)  # one proposal per day first


@pytest.mark.unit
class TestCredentialResolution:
    """Each connector type maps to the expected provider."""

    @pytest.mark.asyncio
    async def test_connector_type_to_provider_mapping(self):
        from app.db import SearchSourceConnectorType
        from app.services.meeting_booking import CalendarAvailabilityService

        connectors = [
            SimpleNamespace(
                connector_type=SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR,
                id=1, user_id="u1", config={},
            ),
            SimpleNamespace(
                connector_type=SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
                id=2, user_id="u2", config={},
            ),
            SimpleNamespace(
                connector_type=SearchSourceConnectorType.LARK_CALENDAR_CONNECTOR,
                id=3, user_id="u3", config={"calendar_id": "cal-1"},
            ),
        ]
        session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = connectors
        session.execute.return_value = result

        creds = await CalendarAvailabilityService(session).resolve_credentials(15)

        assert [c.provider for c in creds] == [
            "google_native", "google_composio", "lark",
        ]


@pytest.mark.unit
class TestLockNamespaceConsistency:
    """_propose and the route must lock under the same owner namespace."""

    @pytest.mark.asyncio
    async def test_propose_uses_caller_matching_credential(self):
        creds = [
            CalendarCredentials(
                provider="lark", connector_id=1, user_id="u-other",
                config={"calendar_id": "c1"},
            ),
            CalendarCredentials(
                provider="google_native", connector_id=2, user_id="u-me",
                config={},
            ),
        ]
        redis = AsyncMock()
        redis.set.return_value = True
        service = MeetingBookingService(session=AsyncMock(), redis_client=redis)
        with patch.object(
            service.availability,
            "get_busy_intervals",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await service._propose(
                15, "th_1", user_id="u-me", lead=None, credentials=creds
            )
        assert result is not None and result.reason == "slots_proposed"
        # Every lock key is namespaced under the caller's credential.
        for call in redis.set.await_args_list:
            key = str(call.args[0])
            if key.startswith("lock:calendar_slot:"):
                assert key.startswith("lock:calendar_slot:u-me:"), key

    @pytest.mark.asyncio
    async def test_route_resolves_same_owner(self):
        creds = [
            CalendarCredentials(
                provider="lark", connector_id=1, user_id="u-other",
                config={"calendar_id": "c1"},
            ),
            CalendarCredentials(
                provider="google_native", connector_id=2, user_id="u-me",
                config={},
            ),
        ]
        from app.routes import lead_pipeline_routes as routes
        from app.schemas.lead_pipeline import MeetingBookRequest
        from app.services.meeting_booking import CalendarAvailabilityService

        lead = SimpleNamespace(id="lead-1", workspace_id=15)
        slot = _future_slot_ict(10, 0)
        payload = MeetingBookRequest(
            start=slot.start, duration_minutes=30, attendee_email="a@b.co"
        )

        with (
            patch.object(
                routes, "_set_lead_tenant_context", new_callable=AsyncMock
            ),
            patch.object(
                routes, "_require_lead_visible",
                new_callable=AsyncMock, return_value=lead,
            ),
            patch.object(
                CalendarAvailabilityService, "resolve_credentials",
                new_callable=AsyncMock, return_value=creds,
            ),
            patch.object(
                MeetingBookingService, "soft_lock_slots",
                new_callable=AsyncMock, return_value=([slot], "tok9"),
            ) as mock_lock,
            patch.object(
                MeetingBookingService, "book_slot",
                new_callable=AsyncMock,
                return_value=MagicMock(
                    booked=True, event_id="e1", meeting_link="m",
                ),
            ),
            patch.object(
                MeetingBookingService, "release_slot_locks",
                new_callable=AsyncMock,
            ),
        ):
            session = AsyncMock()
            await routes.book_meeting_for_lead(
                workspace_id=15,
                lead_id=uuid4(),
                payload=payload,
                auth=SimpleNamespace(user=SimpleNamespace(id="u-me")),
                session=session,
                membership=SimpleNamespace(),
            )

        # Route locks under the same owner namespace _propose would use.
        assert mock_lock.await_args.args[0] == "u-me"


@pytest.mark.unit
class TestMeetingRoutes:
    """CRM route layer: empty slots, 400/409/502/200 book paths."""

    def _ctx(self):
        from app.routes import lead_pipeline_routes as routes

        lead = SimpleNamespace(
            id="lead-1", workspace_id=15, status="new", version=1
        )
        return routes, lead

    @pytest.mark.asyncio
    async def test_slots_empty_without_connector(self):
        routes, lead = self._ctx()
        from app.services.meeting_booking import CalendarAvailabilityService

        with (
            patch.object(
                routes, "_set_lead_tenant_context", new_callable=AsyncMock
            ),
            patch.object(
                routes, "_require_lead_visible",
                new_callable=AsyncMock, return_value=lead,
            ),
            patch.object(
                CalendarAvailabilityService, "compute_availability",
                new_callable=AsyncMock, return_value=([], []),
            ),
        ):
            resp = await routes.list_meeting_slots(
                workspace_id=15,
                lead_id=uuid4(),
                auth=SimpleNamespace(user=SimpleNamespace(id="u1")),
                session=AsyncMock(),
                membership=SimpleNamespace(),
                redis_client=AsyncMock(),
            )
        assert resp.slots == []
        assert resp.provider is None

    @pytest.mark.asyncio
    async def test_book_400_without_connector(self):
        routes, lead = self._ctx()
        from app.schemas.lead_pipeline import MeetingBookRequest
        from app.services.meeting_booking import CalendarAvailabilityService

        payload = MeetingBookRequest(start=_future_slot_ict(10).start)
        with (
            patch.object(
                routes, "_set_lead_tenant_context", new_callable=AsyncMock
            ),
            patch.object(
                routes, "_require_lead_visible",
                new_callable=AsyncMock, return_value=lead,
            ),
            patch.object(
                CalendarAvailabilityService, "resolve_credentials",
                new_callable=AsyncMock, return_value=[],
            ),
            pytest.raises(HTTPException) as exc,
        ):
            await routes.book_meeting_for_lead(
                workspace_id=15, lead_id=uuid4(), payload=payload,
                auth=SimpleNamespace(user=SimpleNamespace(id="u1")),
                session=AsyncMock(), membership=SimpleNamespace(),
            )
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_book_409_on_lock_contention(self):
        routes, lead = self._ctx()
        from app.schemas.lead_pipeline import MeetingBookRequest
        from app.services.meeting_booking import CalendarAvailabilityService

        payload = MeetingBookRequest(start=_future_slot_ict(10).start)
        with (
            patch.object(
                routes, "_set_lead_tenant_context", new_callable=AsyncMock
            ),
            patch.object(
                routes, "_require_lead_visible",
                new_callable=AsyncMock, return_value=lead,
            ),
            patch.object(
                CalendarAvailabilityService, "resolve_credentials",
                new_callable=AsyncMock, return_value=_credentials(),
            ),
            patch.object(
                MeetingBookingService, "soft_lock_slots",
                new_callable=AsyncMock, return_value=([], "tok"),
            ),
            pytest.raises(HTTPException) as exc,
        ):
            await routes.book_meeting_for_lead(
                workspace_id=15, lead_id=uuid4(), payload=payload,
                auth=SimpleNamespace(user=SimpleNamespace(id="u1")),
                session=AsyncMock(), membership=SimpleNamespace(),
            )
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_book_502_releases_lock(self):
        routes, lead = self._ctx()
        from app.schemas.lead_pipeline import MeetingBookRequest
        from app.services.meeting_booking import (
            CalendarAvailabilityService,
            MeetingTurnResult,
        )

        slot = _future_slot_ict(10)
        payload = MeetingBookRequest(
            start=slot.start, attendee_email="a@b.co"
        )
        with (
            patch.object(
                routes, "_set_lead_tenant_context", new_callable=AsyncMock
            ),
            patch.object(
                routes, "_require_lead_visible",
                new_callable=AsyncMock, return_value=lead,
            ),
            patch.object(
                CalendarAvailabilityService, "resolve_credentials",
                new_callable=AsyncMock, return_value=_credentials(),
            ),
            patch.object(
                MeetingBookingService, "soft_lock_slots",
                new_callable=AsyncMock, return_value=([slot], "tok5"),
            ),
            patch.object(
                MeetingBookingService, "book_slot",
                new_callable=AsyncMock,
                return_value=MeetingTurnResult(
                    reply_text="", reason="create_failed"
                ),
            ),
            patch.object(
                MeetingBookingService, "release_slot_locks",
                new_callable=AsyncMock,
            ) as mock_release,
            pytest.raises(HTTPException) as exc,
        ):
            await routes.book_meeting_for_lead(
                workspace_id=15, lead_id=uuid4(), payload=payload,
                auth=SimpleNamespace(user=SimpleNamespace(id="u1")),
                session=AsyncMock(), membership=SimpleNamespace(),
            )
        assert exc.value.status_code == 502
        mock_release.assert_awaited_once()
        assert mock_release.await_args.args[2] == "tok5"

    @pytest.mark.asyncio
    async def test_book_200_commits_and_updates_status(self):
        routes, lead = self._ctx()
        from app.schemas.lead_pipeline import MeetingBookRequest
        from app.services.meeting_booking import (
            CalendarAvailabilityService,
            MeetingTurnResult,
        )

        slot = _future_slot_ict(10)
        payload = MeetingBookRequest(
            start=slot.start, attendee_email="a@b.co"
        )
        booked = MeetingTurnResult(
            reply_text="ok", booked=True, slot=slot,
            event_id="e1", meeting_link="https://meet.google.com/x",
        )
        with (
            patch.object(
                routes, "_set_lead_tenant_context", new_callable=AsyncMock
            ),
            patch.object(
                routes, "_require_lead_visible",
                new_callable=AsyncMock, return_value=lead,
            ),
            patch.object(
                CalendarAvailabilityService, "resolve_credentials",
                new_callable=AsyncMock, return_value=_credentials(),
            ),
            patch.object(
                MeetingBookingService, "soft_lock_slots",
                new_callable=AsyncMock, return_value=([slot], "tok5"),
            ),
            patch.object(
                MeetingBookingService, "book_slot",
                new_callable=AsyncMock, return_value=booked,
            ),
            patch.object(
                MeetingBookingService, "release_slot_locks",
                new_callable=AsyncMock,
            ) as mock_release,
        ):
            session = AsyncMock()
            resp = await routes.book_meeting_for_lead(
                workspace_id=15, lead_id=uuid4(), payload=payload,
                auth=SimpleNamespace(user=SimpleNamespace(id="u1")),
                session=session, membership=SimpleNamespace(),
            )
        assert resp.booked is True
        assert resp.event_id == "e1"
        assert resp.lead_status == "meeting_scheduled"
        session.commit.assert_awaited_once()
        # The lock is released on success too - the event guards the slot.
        mock_release.assert_awaited_once()


@pytest.mark.unit
class TestComposioForwarding:
    @pytest.mark.asyncio
    async def test_create_event_requests_meeting_room(self):
        from app.services.composio_service import ComposioService

        service = ComposioService.__new__(ComposioService)
        service.execute_tool = AsyncMock(
            return_value={"success": True, "data": {"id": "evt-9"}}
        )
        await service.create_calendar_event(
            connected_account_id="ca-1",
            entity_id="nowing_u1",
            summary="Call",
            start_datetime="2026-09-24T14:00:00+07:00",
            end_datetime="2026-09-24T14:30:00+07:00",
            create_meeting_room=True,
        )
        params = service.execute_tool.await_args.kwargs["params"]
        assert params["create_meeting_room"] is True


@pytest.mark.unit
class TestAutoReplyIntegration:
    @pytest.mark.asyncio
    async def test_meeting_turn_short_circuits_rag(self):
        """A handled meeting turn returns its reply without RAG retrieval."""
        from app.services.auto_reply_agent import AutoReplyAgent
        from app.services.meeting_booking import MeetingTurnResult

        agent = AutoReplyAgent()
        turn = MeetingTurnResult(
            reply_text="Dạ em đề xuất 14:00 Thứ Năm ạ.",
            reason="slots_proposed",
        )
        with (
            patch(
                "app.services.auto_reply_agent.is_auto_reply_paused",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.object(
                agent, "_handle_meeting_turn",
                new_callable=AsyncMock, return_value=turn,
            ) as mock_turn,
            patch.object(
                agent, "_retrieve_knowledge_chunks",
                new_callable=AsyncMock,
            ) as mock_rag,
        ):
            result = await agent.generate_reply(
                workspace_id=15,
                channel="zalo_oa",
                sender_id="user_1",
                text="Cho mình đặt lịch hẹn",
                thread_id="th_1",
                session=AsyncMock(),
            )
        assert result.reply_text == "Dạ em đề xuất 14:00 Thứ Năm ạ."
        assert result.is_fallback is False
        mock_turn.assert_awaited_once()
        mock_rag.assert_not_awaited()
